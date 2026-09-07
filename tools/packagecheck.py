#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Audit a native wheel, install it in isolation, and exercise plugin autoloading."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from importlib.metadata import version
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from packaging.utils import parse_wheel_filename


ROOT = Path(__file__).resolve().parent.parent
PLUGIN_NAMES = {"odin_example", "odin_invert", "odin_dither", "odin_hald", "odin_dither_plus"}
PLUGIN_DIRECTORY = "vapoursynth/plugins/odin_examples"

SMOKE_TEST = r'''
from pathlib import Path
import runpy
import sys
import vapoursynth as vs

destination = (Path(vs.get_plugin_dir()) / "odin_examples").resolve()
plugins = {plugin.namespace: plugin for plugin in vs.core.plugins()}
expected = {"odin_example", "odin_invert", "odin_dither", "odin_hald", "odin_dither_plus"}
for namespace in sorted(expected):
    if namespace not in plugins:
        raise RuntimeError(f"Plugin did not autoload: {namespace}")
    path = Path(plugins[namespace].plugin_path).resolve()
    if not path.is_relative_to(destination):
        raise RuntimeError(f"Plugin came from an unexpected installation: {path}")

source = vs.core.std.BlankClip(format=vs.GRAY8, width=17, height=8, length=1, color=[17])
identity = vs.core.odin_example.Identity(source)
inverted = vs.core.odin_invert.Invert(source)
for node, expected_value in ((identity, 17), (inverted, 238)):
    with node.get_frame(0) as frame:
        if any(value != expected_value for row in frame[0].tolist() for value in row):
            raise RuntimeError("Unexpected identity/invert pixel in installed wheel")

deep = vs.core.std.BlankClip(format=vs.GRAY16, width=17, height=8, length=1, color=[32768])
dithered = vs.core.odin_dither.Dither(deep, bits=8)
with dithered.get_frame(0) as frame:
    if frame.format.id != vs.GRAY8 or any(value != 128 for row in frame[0].tolist() for value in row):
        raise RuntimeError("Unexpected dither output in installed wheel")

generator = runpy.run_path(sys.argv[1])
lut = Path(sys.argv[2])
generator["write_hald"](lut, level=2, bits=16, look="identity")
rgb = vs.core.std.BlankClip(format=vs.RGB24, width=17, height=8, length=1, color=[32, 96, 192])
graded = vs.core.odin_hald.HaldCLUT(rgb, path=str(lut))
with graded.get_frame(0) as frame:
    for plane, expected_value in enumerate((32, 96, 192)):
        if any(abs(value - expected_value) > 1 for row in frame[plane].tolist() for value in row):
            raise RuntimeError("Unexpected Hald identity output in installed wheel")
for mode in ("blue_noise", "bayer", "none", "floyd_steinberg", "sierra_lite"):
    quantized = vs.core.odin_dither_plus.Dither(deep, bits=2, scale=1, mode=mode)
    with quantized.get_frame(0) as frame:
        if frame.format.id != vs.GRAY8 or any(value not in (85, 170) for row in frame[0].tolist() for value in row):
            raise RuntimeError(f"Unexpected DitherPlus {mode} output in installed wheel")
print(f"PASS installed wheel: all five plugins autoloaded and rendered frames with VapourSynth {vs.__version__}")
print(f"Plugin directory: {destination}")
'''


def check_archive(wheel: Path) -> None:
    distribution, _, _, tags = parse_wheel_filename(wheel.name)
    if distribution != "vapoursynth-odin-examples" or len(tags) != 1:
        raise ValueError("Expected the vapoursynth-odin-examples wheel with one native platform tag")
    tag = next(iter(tags))
    if tag.interpreter != "py3" or tag.abi != "none" or tag.platform == "any":
        raise ValueError(f"Native examples have an incorrect compatibility tag: {tag}")
    extensions = {"win": ".dll", "linux": ".so", "macosx": ".dylib"}
    platform = tag.platform.split("_", 1)[0]
    if platform not in extensions:
        raise ValueError(f"Unsupported local wheel platform: {tag.platform}")
    expected = {f"{PLUGIN_DIRECTORY}/{name}{extensions[platform]}" for name in PLUGIN_NAMES}
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None:
            raise ValueError("Wheel archive contains a corrupt member")
        names = set(archive.namelist())
        metadata_names = {name for name in names if ".dist-info/" in name}
        if names - metadata_names != expected:
            raise ValueError(f"Unexpected native wheel payload: {sorted(names - metadata_names)}")
        for name in expected:
            if archive.getinfo(name).file_size == 0:
                raise ValueError(f"Empty plugin in wheel: {name}")
        wheel_metadata = next(name for name in names if name.endswith(".dist-info/WHEEL"))
        metadata = BytesParser().parsebytes(archive.read(wheel_metadata))
        if metadata["Root-Is-Purelib"] != "false" or metadata.get_all("Tag") != [str(tag)]:
            raise ValueError("Wheel filename and native wheel metadata disagree")
        for license_name in ("LICENSE", "THIRD_PARTY_LICENSES.md"):
            if not any(name.endswith(f".dist-info/licenses/{license_name}") for name in names):
                raise ValueError(f"Required license notice missing from wheel: {license_name}")
    print(f"PASS archive: exactly five native plugins, native metadata, and license notices: {wheel.name}", flush=True)


def check_install(wheel: Path, runtime_version: str) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv must be installed to create the isolated package-check environment")
    build_root = ROOT / ".build" / "packaging"
    build_root.mkdir(parents=True, exist_ok=True)
    child_env = os.environ.copy()
    child_env["UV_CACHE_DIR"] = str(ROOT / ".build" / "uv-cache")
    child_env["UV_PYTHON_INSTALL_DIR"] = str(ROOT / ".build" / "python")
    child_env["PYTHONNOUSERSITE"] = "1"
    child_env.pop("PYTHONPATH", None)
    child_env.pop("VAPOURSYNTH_EXTRA_PLUGIN_PATH", None)
    with tempfile.TemporaryDirectory(prefix="installed-wheel-", dir=build_root) as temporary:
        directory = Path(temporary).resolve()
        if not directory.is_relative_to(build_root.resolve()):
            raise RuntimeError("Package-check environment escaped the build directory")
        environment = directory / "venv"
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([uv, "venv", "--python", sys.executable, str(environment)], env=child_env, check=True)
        subprocess.run(
            [uv, "pip", "install", "--python", str(python), str(wheel), f"vapoursynth=={runtime_version}"],
            env=child_env, check=True,
        )
        subprocess.run(
            [str(python), "-c", SMOKE_TEST, str(ROOT / "examples" / "haldlut" / "generate.py"), str(directory / "identity.png")],
            cwd=directory, env=child_env, check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, help="Built native example wheel")
    parser.add_argument("--runtime", help="Exact VapourSynth version; defaults to the current environment's version")
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    check_archive(wheel)
    check_install(wheel, args.runtime or version("vapoursynth"))


if __name__ == "__main__":
    main()
