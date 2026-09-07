# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the four native examples for an explicit, non-editable wheel build."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sysconfig
import tempfile

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


PLUGINS = (
    ("plugin", "odin_example"),
    ("invert", "odin_invert"),
    ("dither", "odin_dither"),
    ("haldlut", "odin_hald"),
)
INSTALL_DIRECTORY = "vapoursynth/plugins/odin_examples"


@dataclass(frozen=True)
class NativeTarget:
    wheel_platform: str
    odin_target: str
    extension: str
    microarch: str
    extra_flags: tuple[str, ...] = ()


def native_target(platform_name: str) -> NativeTarget:
    """Map the interpreter's native platform to an honest local wheel target."""
    targets = {
        "win-amd64": NativeTarget("win_amd64", "windows_amd64", ".dll", "x86-64"),
        "linux-x86_64": NativeTarget("linux_x86_64", "linux_amd64", ".so", "x86-64"),
        "linux-aarch64": NativeTarget("linux_aarch64", "linux_arm64", ".so", "generic"),
    }
    if platform_name in targets:
        return targets[platform_name]
    if platform_name.startswith("macosx-"):
        arch = platform_name.rsplit("-", 1)[-1]
        if arch == "x86_64":
            return NativeTarget(
                "macosx_13_0_x86_64", "darwin_amd64", ".dylib", "x86-64",
                ("-minimum-os-version:13.0.0",),
            )
        if arch == "arm64":
            return NativeTarget(
                "macosx_13_0_arm64", "darwin_arm64", ".dylib", "generic",
                ("-minimum-os-version:13.0.0",),
            )
    raise RuntimeError(
        f"Unsupported native wheel platform: {platform_name}. "
        "Use a 64-bit Windows x64, Linux x64/ARM64, or single-architecture macOS x64/ARM64 Python."
    )


def build_plugins(root: Path, target: NativeTarget, odin: str, build_directory: Path) -> dict[str, str]:
    """Return explicit artifact-to-wheel paths after every compiler call succeeds."""
    sources = [(root / "examples" / source, name) for source, name in PLUGINS]
    for source, _ in sources:
        if not source.is_dir() or not any(source.glob("*.odin")):
            raise RuntimeError(f"Missing Odin plugin sources: {source}")

    if not build_directory.resolve().is_relative_to((root / ".build" / "packaging").resolve()):
        raise RuntimeError("Native build directory must remain inside the project's .build/packaging directory")
    build_directory.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    for source, name in sources:
        artifact = build_directory / f"{name}{target.extension}"
        command = [
            odin, "build", str(source), "-build-mode:dll", "-o:speed", "-vet",
            f"-target:{target.odin_target}", f"-microarch:{target.microarch}",
            *target.extra_flags, f"-out:{artifact}",
        ]
        print(f"Building {source.relative_to(root)} for {target.odin_target}", flush=True)
        subprocess.run(command, cwd=root, check=True)
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise RuntimeError(f"Odin did not produce a nonempty plugin: {artifact}")
        artifacts[str(artifact)] = f"{INSTALL_DIRECTORY}/{artifact.name}"
    return artifacts


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        if version != "standard":
            raise RuntimeError(
                "Native plugin wheels require a normal installation. "
                "Use uv build, then install the resulting wheel; uv sync only provisions this project's dependencies."
            )
        target = native_target(sysconfig.get_platform())
        odin = shutil.which("odin")
        if odin is None:
            raise RuntimeError("Odin is required to build native plugins. Install Odin and put it on PATH.")
        root = Path(self.root).resolve()
        build_root = root / ".build" / "packaging"
        build_root.mkdir(parents=True, exist_ok=True)
        self._workspace = tempfile.TemporaryDirectory(prefix=f"{target.wheel_platform}-", dir=build_root)
        try:
            artifacts = build_plugins(root, target, odin, Path(self._workspace.name))
            build_data["pure_python"] = False
            build_data["tag"] = f"py3-none-{target.wheel_platform}"
            build_data["force_include"] = artifacts
        except BaseException:
            self._workspace.cleanup()
            raise

    def finalize(self, version: str, build_data: dict, artifact_path: str) -> None:
        self._workspace.cleanup()
