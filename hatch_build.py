# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build native plugins for an explicit, non-editable wheel build."""

from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.native_build import NativeTarget, native_target, prepare_stb_image


PLUGINS = (
    ("examples/plugin", "odin_example"),
    ("examples/invert", "odin_invert"),
    ("examples/dither", "odin_dither"),
    ("examples/haldlut", "odin_hald"),
    ("plugins/dither", "odin_dither_plus"),
)
INSTALL_DIRECTORY = "vapoursynth/plugins/odin_examples"


def build_plugins(root: Path, target: NativeTarget, odin: str, build_directory: Path) -> dict[str, str]:
    """Return explicit artifact-to-wheel paths after every compiler call succeeds."""
    sources = [(root / source, name) for source, name in PLUGINS]
    for source, _ in sources:
        if not source.is_dir() or not any(source.glob("*.odin")):
            raise RuntimeError(f"Missing Odin plugin sources: {source}")

    if not build_directory.resolve().is_relative_to((root / ".build" / "packaging").resolve()):
        raise RuntimeError("Native build directory must remain inside the project's .build/packaging directory")
    build_directory.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    for source, name in sources:
        dependencies = prepare_stb_image(odin, target, build_directory) if source.name == "haldlut" else ()
        artifact = build_directory / f"{name}{target.extension}"
        command = [
            odin, "build", str(source), "-build-mode:dll", "-o:speed", "-vet",
            *target.flags, *dependencies, f"-out:{artifact}",
        ]
        print(f"Building {source.relative_to(root)} for {target.odin_target}", flush=True)
        subprocess.run(command, cwd=root, check=True, timeout=300)
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
