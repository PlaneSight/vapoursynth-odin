# SPDX-License-Identifier: LGPL-2.1-or-later
"""Exercise example-command failures, artifact publication, and process isolation."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import examples


class ExampleCommands(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="odin example commands ")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        sources = {name: self.root / "examples" / name for name in ("plugin", "invert")}
        for source in sources.values():
            source.mkdir(parents=True)
            (source / "plugin.odin").write_text("package example\n", encoding="utf-8")
            (source / "demo.vpy").write_text("# preview\n", encoding="utf-8")
        for name, value in (("ROOT", self.root), ("EXAMPLES", sources)):
            patcher = patch.object(examples, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = io.StringIO()
        self.errors = io.StringIO()
        self.enterContext(redirect_stdout(self.output))
        self.enterContext(redirect_stderr(self.errors))

    def test_invalid_selectors_cannot_reach_compilation(self):
        with patch.object(examples.subprocess, "run") as run:
            for name in ("missing", "../outside", "/absolute"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unknown example"):
                    examples.build_examples([name])
            run.assert_not_called()

    def test_missing_compiler_has_no_artifact_side_effects(self):
        with patch.object(examples.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "--odin PATH"):
                examples.build_examples(["plugin"], odin="compiler with spaces")
        self.assertFalse((self.root / ".build").exists())

    def test_build_failure_preserves_every_previous_artifact(self):
        outputs = self.root / ".build" / "examples"
        outputs.mkdir(parents=True)
        for name in ("plugin", "invert"):
            (outputs / f"{name}.dll").write_bytes(b"previous build")
        calls = 0

        def compile_example(command, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise subprocess.CalledProcessError(1, command)
            self.write_artifact(command)

        with self.compiler_environment(), patch.object(examples.subprocess, "run", side_effect=compile_example):
            with self.assertRaises(subprocess.CalledProcessError):
                examples.build_examples(["plugin", "invert"])
        self.assertEqual(calls, 2)
        self.assertEqual(sorted(path.name for path in outputs.iterdir()), ["invert.dll", "plugin.dll"])
        self.assertTrue(all(path.read_bytes() == b"previous build" for path in outputs.iterdir()))

    def test_stale_artifact_cannot_mask_missing_compiler_output(self):
        outputs = self.root / ".build" / "examples"
        outputs.mkdir(parents=True)
        previous = outputs / "plugin.dll"
        previous.write_bytes(b"previous build")
        with self.compiler_environment(), patch.object(examples.subprocess, "run"):
            with self.assertRaisesRegex(RuntimeError, "nonempty artifact"):
                examples.build_examples(["plugin"])
        self.assertEqual(previous.read_bytes(), b"previous build")

    def test_success_publishes_only_expected_native_artifacts(self):
        def compile_example(command, **kwargs):
            self.assertIn("-microarch:x86-64", command)
            self.assertIn("-build-mode:dll", command)
            self.assertTrue(kwargs["check"])
            output = self.write_artifact(command)
            output.with_suffix(".lib").write_bytes(b"linker side product")

        with self.compiler_environment(), patch.object(examples.subprocess, "run", side_effect=compile_example):
            artifacts = examples.build_examples(["plugin", "invert", "plugin"])
        self.assertEqual(tuple(artifacts), ("plugin", "invert"))
        self.assertEqual(set((self.root / ".build" / "examples").iterdir()), set(artifacts.values()))
        self.assertTrue(all(path.read_bytes() == b"new native artifact" for path in artifacts.values()))

    def test_missing_vsview_fails_before_build(self):
        with patch.object(examples.importlib.util, "find_spec", return_value=None):
            with patch.object(examples, "build_examples") as build:
                self.assertEqual(examples.main(["preview", "plugin"]), 1)
                build.assert_not_called()
        self.assertIn("uv run --group preview", self.errors.getvalue())

    def test_host_cannot_be_selected_for_preview(self):
        with patch.object(examples, "build_examples") as build:
            with self.assertRaises(SystemExit) as error:
                examples.main(["preview", "core_info"])
            self.assertEqual(error.exception.code, 2)
            build.assert_not_called()

    def test_preview_preserves_paths_and_forwarded_arguments(self):
        forwarded = ["--no-settings", "--qt-arg", "-platform offscreen"]
        with patch.object(examples, "require_dependency"):
            with patch.object(examples.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                result = examples.main(["preview", "plugin", "--no-build", "--", *forwarded])
        self.assertEqual(result, 0)
        self.assertEqual(run.call_args.args[0], [
            sys.executable, "-m", "vsview", str(self.root / "examples" / "plugin" / "demo.vpy"), *forwarded,
        ])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_checks_use_separate_bounded_processes(self):
        with patch.object(examples.subprocess, "run") as run:
            examples.check_examples(["plugin", "invert"])
        self.assertEqual(run.call_count, 2)
        for name, call in zip(("plugin", "invert"), run.call_args_list, strict=True):
            self.assertEqual(call.args[0][-2:], ["_check-script", str(self.root / "examples" / name / "demo.vpy")])
            self.assertEqual(call.kwargs["timeout"], examples.CHECK_TIMEOUT)
            self.assertTrue(call.kwargs["check"])

    def test_child_failures_and_timeouts_propagate_as_failure(self):
        failures = (
            subprocess.CalledProcessError(5, ["child"]),
            subprocess.TimeoutExpired(["child"], examples.CHECK_TIMEOUT),
        )
        for failure in failures:
            with self.subTest(failure=failure), patch.object(examples, "require_dependency"):
                with patch.object(examples.subprocess, "run", side_effect=failure):
                    self.assertEqual(examples.main(["check", "plugin", "--no-build"]), 1)

    def test_platforms_choose_native_suffixes_and_portable_baselines(self):
        cases = {
            "win-amd64": (".exe", ".dll", "-microarch:x86-64"),
            "linux-x86_64": ("", ".so", "-microarch:x86-64"),
            "linux-aarch64": ("", ".so", "-microarch:generic"),
            "macosx-13.0-x86_64": ("", ".dylib", "-microarch:x86-64"),
            "macosx-13.0-arm64": ("", ".dylib", "-microarch:generic"),
        }
        for platform, (executable, library, microarch) in cases.items():
            with self.subTest(platform=platform):
                result = examples.native_build_options(platform)
                self.assertEqual(result[:2], (executable, library))
                self.assertIn(microarch, result[2])
        for platform in ("win32", "win-arm64", "linux-i686", "macosx-13.0-universal2"):
            with self.subTest(platform=platform), self.assertRaisesRegex(RuntimeError, "Unsupported build platform"):
                examples.native_build_options(platform)

    @unittest.skipUnless(importlib.util.find_spec("vapoursynth"), "VapourSynth is not installed")
    def test_script_without_registered_outputs_is_rejected(self):
        script = self.root / "empty.vpy"
        script.write_text("# No registered output\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "did not register any outputs"):
            examples.check_script(script)

    @unittest.skipUnless(importlib.util.find_spec("vapoursynth"), "VapourSynth is not installed")
    def test_headless_check_requests_real_video_frames(self):
        script = self.root / "video.vpy"
        script.write_text(
            "import vapoursynth as vs\n"
            "vs.core.std.BlankClip(width=8, height=4, format=vs.RGB24, length=3).set_output(2)\n",
            encoding="utf-8",
        )
        examples.check_script(script)
        self.assertIn("output 2: 8 x 4 RGB24, 3 frames; first and last frames passed", self.output.getvalue())

    def compiler_environment(self):
        return patch.multiple(
            examples,
            shutil=unittest.mock.Mock(which=unittest.mock.Mock(return_value="odin compiler.exe")),
            sysconfig=unittest.mock.Mock(get_platform=unittest.mock.Mock(return_value="win-amd64")),
        )

    @staticmethod
    def write_artifact(command):
        output = Path(next(argument[5:] for argument in command if argument.startswith("-out:")))
        output.write_bytes(b"new native artifact")
        return output


if __name__ == "__main__":
    unittest.main()
