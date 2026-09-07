#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build and run the examples against an installed VapourSynth API 4.2 runtime.

Requires Python 3.10+, Odin, and the VapourSynth Python module. Use --runtime
to select an existing directory containing that module, and --library to select
the core library for the host examples. Nothing is downloaded or installed;
generated binaries stay in .build/examples.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from ctypes.util import find_library
import importlib
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build" / "examples"
HOSTS = ("core_info", "properties", "easy_host", "host")
PLUGINS = ("plugin", "invert")
EXPECTED_OUTPUT = {
    "core_info": ("Core version:", "API:"),
    "properties": (
        'Frame 42: "example frame"; exposure: 1.25',
        "Binary payload (4 bytes, including the embedded zero): [65, 0, 66, 255]",
        "Durations: [1001, 1001, 1001]; weights: [0.25, 0.5, 0.25]",
        "Existing empty array: 0 elements; absent key: Missing_Key",
    ),
    "easy_host": ("Frame 0: 65 x 48 Gray8", "checksum: 53040"),
    "host": ("Frame 0: 64 x 48 Gray8", "first pixel: 17"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(command: list[str], *, expect_failure: bool = False) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    output = result.stdout + result.stderr
    succeeded = result.returncode == 0
    if succeeded == expect_failure:
        expectation = "a nonzero exit status" if expect_failure else "success"
        raise RuntimeError(
            f"Expected {expectation}, got exit status {result.returncode}:\n"
            f"{subprocess.list2cmdline(command)}\n{output}"
        )
    return output


def runtime_module(directory: Path | None):
    if directory is not None:
        require(directory.is_dir(), f"Runtime directory does not exist: {directory}")
        sys.path.insert(0, str(directory.resolve()))
    try:
        vs = importlib.import_module("vapoursynth")
    except ImportError as error:
        raise RuntimeError(
            "Cannot import VapourSynth. Use a Python environment with VapourSynth "
            "installed, or pass --runtime with the directory containing its module.\n"
            f"{error}"
        ) from error
    if directory is not None:
        require(
            Path(vs.__file__).resolve().is_relative_to(directory.resolve()),
            f"No VapourSynth module found in {directory}; resolved an unrelated module at {vs.__file__}",
        )
    return vs


def core_library(vs, requested: Path | None) -> str:
    if requested is not None:
        require(requested.is_file(), f"Core library does not exist: {requested}")
        return str(requested.resolve())
    package = Path(vs.__file__).resolve().parent
    for name in (
        "libvapoursynth.dll", "libvapoursynth.so.4", "libvapoursynth.4.dylib",
        "libvapoursynth.so", "libvapoursynth.dylib",
    ):
        candidate = package / name
        if candidate.is_file():
            return str(candidate)
    if discovered := find_library("vapoursynth"):
        return discovered
    raise RuntimeError("Cannot locate the core library; pass its path with --library.")


def build_examples(odin: str) -> dict[str, Path]:
    executable = shutil.which(odin)
    require(executable is not None, f"Cannot find Odin compiler: {odin}")
    BUILD.mkdir(parents=True, exist_ok=True)
    executable_suffix = ".exe" if sys.platform == "win32" else ""
    plugin_suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    binaries = {}
    for name in (*HOSTS, *PLUGINS):
        is_plugin = name in PLUGINS
        suffix = plugin_suffix if is_plugin else executable_suffix
        output = BUILD / f"{name}{suffix}"
        command = [executable, "build", str(ROOT / "examples" / name), "-vet", f"-out:{output}"]
        if is_plugin:
            command.append("-build-mode:dll")
        print(f"Building examples/{name}", flush=True)
        run(command)
        binaries[name] = output
    return binaries


def test_hosts(binaries: dict[str, Path], library: str) -> None:
    for name in HOSTS:
        output = run([str(binaries[name]), library])
        for expected in EXPECTED_OUTPUT[name]:
            require(expected in output, f"{name}: expected output {expected!r}, received:\n{output}")
        print(f"PASS {name}\n{output.rstrip()}", flush=True)

    missing = BUILD / "missing-vapoursynth-library"
    require(not missing.exists(), f"Failure-test path unexpectedly exists: {missing}")
    for name in ("core_info", "host"):
        output = run([str(binaries[name]), str(missing)], expect_failure=True)
        require(bool(output.strip()), f"{name}: missing library failed without a diagnostic")
        print(f"PASS {name}: missing-library diagnostic", flush=True)


def snapshot(frame) -> list[list[list[int]]]:
    return [frame[plane].tolist() for plane in range(frame.format.num_planes)]


def patterned_clip(core, format_id: int, width: int, height: int, length: int = 4):
    blank = core.std.BlankClip(format=format_id, width=width, height=height, length=length)

    def fill(n, f):
        output = f.copy()
        maximum = (1 << output.format.bits_per_sample) - 1
        for plane in range(output.format.num_planes):
            pixels = output[plane]
            rows, columns = pixels.shape
            for y in range(rows):
                for x in range(columns):
                    pixels[y, x] = (197 * x + 313 * y + 997 * plane + 101 * n) & maximum
            pixels[rows - 1, columns - 1] = maximum
        output.props["OdinExample"] = 1000 + n
        return output

    return core.std.ModifyFrame(blank, clips=blank, selector=fill)


def check_frame(frame, original: list[list[list[int]]], n: int, *, inverted: bool) -> None:
    maximum = (1 << frame.format.bits_per_sample) - 1
    require(frame.props["OdinExample"] == 1000 + n, f"Frame {n}: custom property was lost")
    actual = snapshot(frame)
    require(len(actual) == len(original), f"Frame {n}: plane count changed")
    for plane, (actual_rows, source_rows) in enumerate(zip(actual, original)):
        expected = [[maximum - value for value in row] for row in source_rows] if inverted else source_rows
        require(actual_rows == expected, f"Frame {n}, plane {plane}: unexpected pixels or dimensions")


def test_identity(core, vs) -> None:
    source = patterned_clip(core, vs.GRAY8, 65, 47, length=1)
    identity = core.odin_example.Identity(source)
    with source.get_frame(0) as original, identity.get_frame(0) as output:
        require(output.format.id == original.format.id, "Identity: format changed")
        check_frame(output, snapshot(original), 0, inverted=False)
    print("PASS identity: pixels and frame properties", flush=True)


def test_invert(core, vs) -> None:
    cases = (
        ("Gray8", vs.GRAY8, 65, 47),
        ("RGB24", vs.RGB24, 65, 47),
        ("YUV420P10", vs.YUV420P10, 66, 48),
        ("Gray16", vs.GRAY16, 65, 47),
    )
    for name, format_id, width, height in cases:
        source = patterned_clip(core, format_id, width, height)
        inverted = core.odin_invert.Invert(source)
        with ExitStack() as frames:
            # Keep the actual source frames alive so recreation cannot hide mutation.
            source_frames = [frames.enter_context(source.get_frame(n)) for n in range(source.num_frames)]
            originals = [snapshot(frame) for frame in source_frames]
            if name == "Gray8":
                require(source_frames[0].get_stride(0) > width, "Gray8 fixture must exercise row padding")

            # Submit every request before waiting, exercising the filter's parallel mode.
            pending = [inverted.get_frame_async(n) for n in range(source.num_frames)]
            for n, future in enumerate(pending):
                with future.result(timeout=30) as frame:
                    require(frame.format.id == format_id, f"{name}: output format changed")
                    check_frame(frame, originals[n], n, inverted=True)
                check_frame(source_frames[n], originals[n], n, inverted=False)

            restored = core.odin_invert.Invert(inverted)
            with restored.get_frame(0) as frame:
                check_frame(frame, originals[0], 0, inverted=False)
        print(f"PASS invert {name}: all pixels, parallel requests, properties, source, double invert", flush=True)


def expect_filter_error(vs, operation, expected_text: str) -> None:
    try:
        operation()
    except vs.Error as error:
        require(expected_text in str(error), f"Unexpected filter diagnostic: {error}")
        return
    raise RuntimeError(f"Invert accepted invalid input; expected an error containing {expected_text!r}")


def test_rejections(core, vs) -> None:
    float_clip = core.std.BlankClip(format=vs.GRAYS, width=64, height=48, length=1)
    expect_filter_error(vs, lambda: core.odin_invert.Invert(float_clip), "8-16 bit integer")
    gray8 = core.std.BlankClip(format=vs.GRAY8, width=64, height=48, length=1)
    gray16 = core.std.BlankClip(format=vs.GRAY16, width=64, height=48, length=1)
    variable = core.std.Splice([gray8, gray16], mismatch=True)
    require(
        variable.format is None or variable.format.id == 0,
        "Variable-format fixture unexpectedly has a constant format",
    )
    expect_filter_error(vs, lambda: core.odin_invert.Invert(variable), "constant format and dimensions")
    print("PASS invert: floating-point and variable-format rejection diagnostics", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--runtime", type=Path, help="Directory containing an existing VapourSynth Python module")
    parser.add_argument("--library", type=Path, help="VapourSynth core library for the host examples")
    args = parser.parse_args()

    vs = runtime_module(args.runtime)
    library = core_library(vs, args.library)
    print(
        f"VapourSynth {vs.__version__}; API {vs.__api_version__}\n"
        f"Python module: {vs.__file__}\nCore library: {library}",
        flush=True,
    )
    binaries = build_examples(args.odin)
    test_hosts(binaries, library)
    core = vs.core
    core.num_threads = 4
    for name in PLUGINS:
        core.std.LoadPlugin(path=str(binaries[name]))
    test_identity(core, vs)
    test_invert(core, vs)
    test_rejections(core, vs)
    print("All example runtime checks passed.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
