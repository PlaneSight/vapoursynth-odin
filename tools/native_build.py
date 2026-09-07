# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared native targets and workspace-local dependencies for Odin builds."""

from ctypes.util import find_library
from dataclasses import dataclass
from pathlib import Path
import platform
import shutil
import subprocess
import sys


BUILD_TIMEOUT = 300
STB_IMAGE_LIBRARIES = ("stb_image", "stb_image_write", "stb_image_resize")


def core_library(package: Path) -> str:
    """Prefer the active Python package's core, then the system loader's library."""
    names = {
        "win32": ("libvapoursynth.dll",),
        "darwin": ("libvapoursynth.4.dylib", "libvapoursynth.dylib"),
        "linux": ("libvapoursynth.so.4", "libvapoursynth.so"),
    }
    for name in names.get(sys.platform, ()):
        candidate = package / name
        if candidate.is_file():
            return str(candidate.resolve())
    if discovered := find_library("vapoursynth"):
        return discovered
    raise RuntimeError(f"Cannot locate the VapourSynth core in {package} or the system library path")


@dataclass(frozen=True)
class NativeTarget:
    wheel_platform: str
    odin_target: str
    extension: str
    microarch: str
    extra_flags: tuple[str, ...] = ()

    @property
    def executable_suffix(self) -> str:
        return ".exe" if self.odin_target.startswith("windows_") else ""

    @property
    def flags(self) -> tuple[str, ...]:
        return (f"-target:{self.odin_target}", f"-microarch:{self.microarch}", *self.extra_flags)


def native_target(platform_name: str, machine: str | None = None) -> NativeTarget:
    """Select the running interpreter's architecture, including universal2 Python."""
    targets = {
        "win-amd64": NativeTarget("win_amd64", "windows_amd64", ".dll", "x86-64"),
        "linux-x86_64": NativeTarget("linux_x86_64", "linux_amd64", ".so", "x86-64"),
        "linux-aarch64": NativeTarget("linux_aarch64", "linux_arm64", ".so", "generic"),
    }
    if platform_name in targets:
        return targets[platform_name]
    if platform_name.startswith("macosx-"):
        architecture = platform_name.rsplit("-", 1)[-1]
        if architecture == "universal2":
            architecture = platform.machine() if machine is None else machine
        mac_targets = {"x86_64": ("darwin_amd64", "x86-64"), "arm64": ("darwin_arm64", "generic")}
        if architecture in mac_targets:
            target, microarch = mac_targets[architecture]
            return NativeTarget(
                f"macosx_13_0_{architecture}", target, ".dylib", microarch,
                ("-minimum-os-version:13.0.0",),
            )
    raise RuntimeError(
        f"Unsupported native build platform: {platform_name}. "
        "Use Windows x64, Linux x64/ARM64, or macOS x64/ARM64 Python."
    )


def prepare_stb_image(compiler: str, target: NativeTarget, build_directory: Path) -> tuple[str, ...]:
    """Map the stb collection to Odin's package or a private copy with Unix libraries."""
    try:
        result = subprocess.run(
            [compiler, "root"], check=True, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Cannot locate Odin's vendor libraries using {compiler} root: {error}") from error
    root_text = result.stdout.strip()
    if not root_text or not Path(root_text).is_dir():
        raise RuntimeError(f"Odin returned an invalid installation directory: {root_text!r}")
    installed = Path(root_text) / "vendor" / "stb"
    windows = target.odin_target.startswith("windows_")
    darwin = target.odin_target.startswith("darwin_")
    library_directory = Path("lib/darwin") if darwin else Path("lib")
    extension = ".lib" if windows else ".a"
    archives = {name: installed / library_directory / f"{name}{extension}" for name in STB_IMAGE_LIBRARIES}
    missing = [name for name, archive in archives.items() if not archive.is_file() or archive.stat().st_size == 0]
    if not missing:
        return (f"-collection:stb={installed}",)
    if windows:
        raise RuntimeError(
            f"Odin is missing the shipped Windows stb image libraries: {', '.join(missing)}. "
            "Install a complete Odin distribution."
        )

    bindings = sorted((installed / "image").glob("*.odin"))
    if not bindings:
        raise RuntimeError(f"Missing Odin stb image bindings: {installed / 'image'}")
    for name in missing:
        for suffix in (".c", ".h"):
            source = installed / "src" / f"{name}{suffix}"
            if not source.is_file():
                raise RuntimeError(f"Missing Odin stb image source: {source}")
    cc = shutil.which("cc")
    ar = shutil.which("ar")
    if cc is None or ar is None:
        tools = ", ".join(name for name, path in (("cc", cc), ("ar", ar)) if path is None)
        raise RuntimeError(
            f"Building Odin's missing stb image libraries requires {tools} on PATH. "
            "Install a C compiler and archiver (Xcode Command Line Tools on macOS)."
        )

    workspace = build_directory.resolve()
    vendor = workspace / "vendor"
    private_stb = vendor / "stb"
    private_bindings = private_stb / "image"
    private_libraries = private_stb / library_directory
    private_bindings.mkdir(parents=True, exist_ok=True)
    private_libraries.mkdir(parents=True, exist_ok=True)
    for binding in bindings:
        shutil.copy2(binding, private_bindings / binding.name)
    for name, archive in archives.items():
        if name not in missing:
            shutil.copy2(archive, private_libraries / archive.name)

    flags = ["-c", "-O2", "-fPIC"]
    if darwin:
        architecture = "arm64" if target.odin_target == "darwin_arm64" else "x86_64"
        flags.extend(("-arch", architecture, "-mmacosx-version-min=13.0"))
    for name in missing:
        source = installed / "src" / f"{name}.c"
        object_path = workspace / f"{name}.o"
        archive = private_libraries / f"{name}.a"
        object_path.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        print(f"Building {name} for {target.odin_target}", flush=True)
        try:
            subprocess.run([cc, *flags, str(source), "-o", str(object_path)], check=True, timeout=BUILD_TIMEOUT)
            if not object_path.is_file() or object_path.stat().st_size == 0:
                raise RuntimeError(f"C compiler did not produce a nonempty object: {object_path}")
            subprocess.run([ar, "rcs", str(archive), str(object_path)], check=True, timeout=BUILD_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(f"Cannot build {name} for {target.odin_target}: {error}") from error
        if not archive.is_file() or archive.stat().st_size == 0:
            raise RuntimeError(f"Archiver did not produce a nonempty library: {archive}")
    return (f"-collection:stb={private_stb}",)
