# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native target selection and isolated stb dependency preparation boundaries."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.native_build import STB_IMAGE_LIBRARIES, core_library, native_target, prepare_stb_image


class CoreLibrary(unittest.TestCase):
    def test_package_precedes_system_and_missing_library_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            with patch("tools.native_build.sys.platform", "linux"), patch(
                "tools.native_build.find_library", return_value="system-core"
            ) as discover:
                self.assertEqual(core_library(package), "system-core")
                library = package / "libvapoursynth.so.4"
                library.write_bytes(b"core")
                discover.reset_mock()
                self.assertEqual(core_library(package), str(library.resolve()))
                discover.assert_not_called()
                library.unlink()
                discover.return_value = None
                with self.assertRaisesRegex(RuntimeError, "Cannot locate"):
                    core_library(package)


class NativeTargets(unittest.TestCase):
    def test_platforms_keep_portable_baselines_and_honest_tags(self):
        cases = (
            ("win-amd64", "win_amd64", "windows_amd64", ".dll", ".exe", "x86-64"),
            ("linux-x86_64", "linux_x86_64", "linux_amd64", ".so", "", "x86-64"),
            ("linux-aarch64", "linux_aarch64", "linux_arm64", ".so", "", "generic"),
            ("macosx-15.0-arm64", "macosx_13_0_arm64", "darwin_arm64", ".dylib", "", "generic"),
            ("macosx-13.0-x86_64", "macosx_13_0_x86_64", "darwin_amd64", ".dylib", "", "x86-64"),
        )
        for name, wheel, odin, library, executable, microarch in cases:
            with self.subTest(platform=name):
                target = native_target(name)
                self.assertEqual(
                    (target.wheel_platform, target.odin_target, target.extension, target.executable_suffix, target.microarch),
                    (wheel, odin, library, executable, microarch),
                )
                self.assertEqual(target.flags[:2], (f"-target:{odin}", f"-microarch:{microarch}"))
                self.assertEqual(target.flags[2:], ("-minimum-os-version:13.0.0",) if name.startswith("macosx-") else ())

    def test_universal2_uses_active_process_architecture(self):
        for machine in ("x86_64", "arm64"):
            with self.subTest(machine=machine), patch("tools.native_build.platform.machine", return_value=machine):
                target = native_target("macosx-13.0-universal2")
                self.assertEqual(target, native_target(f"macosx-13.0-{machine}"))
                self.assertNotIn("universal", target.wheel_platform)

    def test_explicit_universal2_architecture_does_not_query_the_host(self):
        with patch("tools.native_build.platform.machine") as machine:
            self.assertEqual(native_target("macosx-13.0-universal2", "arm64").odin_target, "darwin_arm64")
        machine.assert_not_called()

    def test_unsupported_platforms_and_unknown_universal2_architecture_fail(self):
        for name in ("win32", "win-arm64", "linux-i686", "freebsd-14-amd64", "macosx-13.0-universal2"):
            with self.subTest(platform=name):
                with self.assertRaisesRegex(RuntimeError, "Unsupported native build platform"):
                    native_target(name, "unexpected")


class StbImagePreparation(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix="odin native build "))
        self.root = Path(directory).resolve()
        self.installed = self.root / "Odin installation"
        self.stb = self.installed / "vendor" / "stb"
        self.workspace = self.root / "private build"
        self.compiler = str(self.root / "Odin compiler" / "odin")
        self.cc = str(self.root / "C tools" / "cc")
        self.ar = str(self.root / "C tools" / "ar")
        (self.stb / "image").mkdir(parents=True)
        (self.stb / "src").mkdir()
        for name in STB_IMAGE_LIBRARIES:
            (self.stb / "image" / f"{name}.odin").write_text("package stb_image\n", encoding="utf-8")
            (self.stb / "src" / f"{name}.c").write_text(f'#include "{name}.h"\n', encoding="utf-8")
            (self.stb / "src" / f"{name}.h").write_text("/* test source */\n", encoding="utf-8")
        self.run = self.enterContext(patch("tools.native_build.subprocess.run", side_effect=self.run_tool))
        self.which = self.enterContext(patch("tools.native_build.shutil.which", side_effect={"cc": self.cc, "ar": self.ar}.get))

    def run_tool(self, command, **kwargs):
        self.assertTrue(kwargs["check"])
        self.assertGreater(kwargs["timeout"], 0)
        if command == [self.compiler, "root"]:
            self.assertTrue(kwargs["capture_output"])
            self.assertTrue(kwargs["text"])
            return subprocess.CompletedProcess(command, 0, stdout=f"{self.installed}\n")
        if command[0] == self.cc:
            self.assertEqual(command[-2], "-o")
            Path(command[-1]).write_bytes(b"compiled object")
            return subprocess.CompletedProcess(command, 0)
        self.assertEqual(command[:2], [self.ar, "rcs"])
        Path(command[2]).write_bytes(b"compiled archive")
        return subprocess.CompletedProcess(command, 0)

    def install_archives(self, platform_name, names=STB_IMAGE_LIBRARIES):
        target = native_target(platform_name)
        directory = self.stb / ("lib/darwin" if target.odin_target.startswith("darwin_") else "lib")
        directory.mkdir(parents=True, exist_ok=True)
        suffix = ".lib" if target.executable_suffix else ".a"
        for name in names:
            (directory / f"{name}{suffix}").write_bytes(f"shipped {name}".encode())
        return directory

    def test_complete_installed_archives_need_no_tools_or_workspace(self):
        for name in ("win-amd64", "linux-x86_64", "macosx-13.0-arm64"):
            with self.subTest(platform=name):
                self.install_archives(name)
                self.assertEqual(
                    prepare_stb_image(self.compiler, native_target(name), self.workspace),
                    (f"-collection:stb={self.stb}",),
                )
        self.assertFalse(self.workspace.exists())
        self.which.assert_not_called()
        self.assertTrue(all(call.args[0] == [self.compiler, "root"] for call in self.run.call_args_list))

    def test_missing_or_empty_windows_archives_report_actual_names(self):
        directory = self.install_archives("win-amd64", ("stb_image", "stb_image_write"))
        (directory / "stb_image_write.lib").write_bytes(b"")
        with self.assertRaisesRegex(RuntimeError, "stb_image_write, stb_image_resize.*complete Odin"):
            prepare_stb_image(self.compiler, native_target("win-amd64"), self.workspace)
        self.which.assert_not_called()
        self.assertFalse(self.workspace.exists())

    def test_linux_builds_only_missing_archives_and_copies_whole_package(self):
        installed = self.install_archives("linux-x86_64", ("stb_image_write", "stb_image_resize"))
        original_files = {path.relative_to(self.installed): path.read_bytes() for path in self.installed.rglob("*") if path.is_file()}
        flags = prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
        self.assertEqual(flags, (f"-collection:stb={self.workspace / 'vendor/stb'}",))
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertEqual(
            commands[1],
            [self.cc, "-c", "-O2", "-fPIC", str(self.stb / "src/stb_image.c"), "-o", str(self.workspace / "stb_image.o")],
        )
        self.assertEqual(
            commands[2],
            [self.ar, "rcs", str(self.workspace / "vendor/stb/lib/stb_image.a"), str(self.workspace / "stb_image.o")],
        )
        for name in STB_IMAGE_LIBRARIES:
            self.assertEqual(
                (self.workspace / "vendor/stb/image" / f"{name}.odin").read_bytes(),
                (self.stb / "image" / f"{name}.odin").read_bytes(),
            )
        for name in ("stb_image_write", "stb_image_resize"):
            self.assertEqual((self.workspace / "vendor/stb/lib" / f"{name}.a").read_bytes(), (installed / f"{name}.a").read_bytes())
        self.assertEqual(
            {path.relative_to(self.installed): path.read_bytes() for path in self.installed.rglob("*") if path.is_file()},
            original_files,
        )

    def test_macos_objects_match_selected_architecture_and_deployment_target(self):
        for architecture in ("x86_64", "arm64"):
            with self.subTest(architecture=architecture):
                self.run.reset_mock()
                workspace = self.workspace / architecture
                prepare_stb_image(self.compiler, native_target("macosx-13.0-universal2", architecture), workspace)
                commands = [call.args[0] for call in self.run.call_args_list]
                self.assertEqual(len(commands), 7)
                for command in commands[1::2]:
                    self.assertIn("-fPIC", command)
                    self.assertIn("-mmacosx-version-min=13.0", command)
                    self.assertEqual(command[command.index("-arch") + 1], architecture)
                for name in STB_IMAGE_LIBRARIES:
                    self.assertTrue((workspace / "vendor/stb/lib/darwin" / f"{name}.a").is_file())

    def test_missing_source_or_header_fails_before_writes(self):
        for suffix in (".c", ".h"):
            with self.subTest(suffix=suffix):
                path = self.stb / "src" / f"stb_image{suffix}"
                content = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(RuntimeError, "Missing Odin stb image source"):
                    prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
                path.write_bytes(content)
                self.assertFalse(self.workspace.exists())

    def test_missing_bindings_fail_before_writes(self):
        for path in (self.stb / "image").glob("*.odin"):
            path.unlink()
        with self.assertRaisesRegex(RuntimeError, "Missing Odin stb image bindings"):
            prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
        self.assertFalse(self.workspace.exists())

    def test_missing_native_tools_fail_before_writes(self):
        for missing in ("cc", "ar"):
            with self.subTest(tool=missing):
                self.which.side_effect = {name: path for name, path in (("cc", self.cc), ("ar", self.ar)) if name != missing}.get
                with self.assertRaisesRegex(RuntimeError, f"requires {missing} on PATH"):
                    prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
                self.assertFalse(self.workspace.exists())

    def test_failed_or_timed_out_root_query_has_context(self):
        for failure in (FileNotFoundError("no compiler"), subprocess.CalledProcessError(1, [self.compiler, "root"]), subprocess.TimeoutExpired([self.compiler, "root"], 30)):
            with self.subTest(failure=type(failure).__name__):
                self.run.side_effect = failure
                with self.assertRaisesRegex(RuntimeError, "Cannot locate Odin's vendor libraries"):
                    prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
                self.assertFalse(self.workspace.exists())

    def test_invalid_root_output_is_rejected(self):
        for output in ("", str(self.root / "missing installation")):
            with self.subTest(output=output):
                self.run.side_effect = None
                self.run.return_value = subprocess.CompletedProcess([self.compiler, "root"], 0, stdout=output)
                with self.assertRaisesRegex(RuntimeError, "invalid installation directory"):
                    prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)

    def test_failed_or_timed_out_dependency_compilation_has_library_context(self):
        for failure in (subprocess.CalledProcessError(1, [self.cc]), subprocess.TimeoutExpired([self.cc], 300)):
            with self.subTest(failure=type(failure).__name__):
                self.run.side_effect = [subprocess.CompletedProcess([self.compiler, "root"], 0, stdout=str(self.installed)), failure]
                with self.assertRaisesRegex(RuntimeError, "Cannot build stb_image for linux_amd64"):
                    prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
                self.assertFalse((self.stb / "lib").exists())

    def test_success_without_nonempty_object_is_rejected_even_with_a_stale_object(self):
        self.workspace.mkdir()
        (self.workspace / "stb_image.o").write_bytes(b"stale object")
        self.run.side_effect = [
            subprocess.CompletedProcess([self.compiler, "root"], 0, stdout=str(self.installed)),
            subprocess.CompletedProcess([self.cc], 0),
        ]
        with self.assertRaisesRegex(RuntimeError, "nonempty object"):
            prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)
        self.assertEqual(self.run.call_count, 2)

    def test_success_without_nonempty_archive_is_rejected(self):
        def skip_archive(command, **kwargs):
            if command[0] == self.ar:
                Path(command[2]).write_bytes(b"")
                return subprocess.CompletedProcess(command, 0)
            return self.run_tool(command, **kwargs)

        self.run.side_effect = skip_archive
        with self.assertRaisesRegex(RuntimeError, "nonempty library"):
            prepare_stb_image(self.compiler, native_target("linux-x86_64"), self.workspace)


if __name__ == "__main__":
    unittest.main()
