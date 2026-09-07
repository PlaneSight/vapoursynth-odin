# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unit tests for native wheel selection and compiler failure boundaries."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hatch_build import INSTALL_DIRECTORY, PLUGINS, build_plugins, native_target


class NativePackaging(unittest.TestCase):
    def test_platform_tags_match_compilation_targets(self):
        cases = (
            ("win-amd64", "win_amd64", "windows_amd64", ".dll"),
            ("linux-x86_64", "linux_x86_64", "linux_amd64", ".so"),
            ("linux-aarch64", "linux_aarch64", "linux_arm64", ".so"),
            ("macosx-15.0-arm64", "macosx_13_0_arm64", "darwin_arm64", ".dylib"),
            ("macosx-13.0-x86_64", "macosx_13_0_x86_64", "darwin_amd64", ".dylib"),
        )
        for platform_name, wheel, odin, extension in cases:
            with self.subTest(platform=platform_name):
                target = native_target(platform_name)
                self.assertEqual((target.wheel_platform, target.odin_target, target.extension), (wheel, odin, extension))
                self.assertNotIn("manylinux", target.wheel_platform)
                self.assertNotIn("native", target.microarch)

    def test_unsupported_or_universal_platforms_fail_explicitly(self):
        for platform_name in ("win32", "win-arm64", "linux-i686", "macosx-13.0-universal2", "freebsd-14-amd64"):
            with self.subTest(platform=platform_name):
                with self.assertRaisesRegex(RuntimeError, "Unsupported native wheel platform"):
                    native_target(platform_name)

    def test_missing_sources_fail_before_compilation(self):
        with tempfile.TemporaryDirectory() as directory, patch("hatch_build.subprocess.run") as run:
            with self.assertRaisesRegex(RuntimeError, "Missing Odin plugin sources"):
                root = Path(directory)
                build_plugins(root, native_target("win-amd64"), "odin", root / ".build/packaging/unit")
            run.assert_not_called()

    def test_compiler_failure_cannot_return_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_sources(root)
            failure = subprocess.CalledProcessError(1, ["odin", "build"])
            with patch("hatch_build.subprocess.run", side_effect=failure) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    build_plugins(root, native_target("win-amd64"), "odin", root / ".build/packaging/unit")
            self.assertEqual(run.call_count, 1)

    def test_only_expected_nonempty_libraries_are_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_sources(root)

            def compile_plugin(command, **kwargs):
                output = Path(next(flag[5:] for flag in command if flag.startswith("-out:")))
                output.write_bytes(b"native plugin")
                output.with_suffix(".lib").write_bytes(b"linker artifact")
                self.assertIn("-microarch:x86-64", command)
                self.assertTrue(kwargs["check"])

            with patch("hatch_build.subprocess.run", side_effect=compile_plugin):
                artifacts = build_plugins(root, native_target("win-amd64"), "odin", root / ".build/packaging/unit")
            self.assertEqual(
                set(artifacts.values()),
                {f"{INSTALL_DIRECTORY}/{name}.dll" for _, name in PLUGINS},
            )
            self.assertTrue(all(Path(path).is_relative_to(root / ".build" / "packaging") for path in artifacts))

    def test_successful_process_without_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_sources(root)
            with patch("hatch_build.subprocess.run"):
                with self.assertRaisesRegex(RuntimeError, "nonempty plugin"):
                    build_plugins(root, native_target("win-amd64"), "odin", root / ".build/packaging/unit")

    def test_build_artifacts_cannot_escape_the_build_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_sources(root)
            with patch("hatch_build.subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError, "must remain inside"):
                    build_plugins(root, native_target("win-amd64"), "odin", root / "elsewhere")
            run.assert_not_called()

    @staticmethod
    def create_sources(root):
        for source, _ in PLUGINS:
            package = root / "examples" / source
            package.mkdir(parents=True)
            (package / "plugin.odin").write_text("package example\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
