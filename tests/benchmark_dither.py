#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compare end-to-end VapourSynth frame throughput for scalar and SIMD dithering.

Requires Python 3.10+, Odin, and an installed VapourSynth Python module. Builds
examples/dither with -o:speed into .build/advanced, verifies exact output parity,
warms both implementations, and reports median throughput. No speedup is assumed.
The source is a reusable in-memory Gray16 frame; each Gray8 output frame is
requested once with output caching disabled. Timings include frame allocation,
scheduling, Python request delivery, and release, rather than only the kernel.
Nothing is downloaded or installed.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import platform
import shutil
from statistics import median
import subprocess
import sys
from time import perf_counter

from examples import ROOT, patterned_clip, require, run, runtime_module


BUILD = ROOT / ".build" / "advanced"


def positive_integer(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def build_plugin(odin: str) -> Path:
    executable = shutil.which(odin)
    require(executable is not None, f"Cannot find Odin compiler: {odin}")
    BUILD.mkdir(parents=True, exist_ok=True)
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    output = BUILD / f"dither_benchmark{suffix}"
    print(run([executable, "version"]).strip(), flush=True)
    command = [
        executable,
        "build",
        str(ROOT / "examples" / "dither"),
        "-build-mode:dll",
        "-vet",
        "-o:speed",
        f"-out:{output}",
    ]
    baseline = "compiler default target"
    if platform.machine().lower() in ("amd64", "x86_64"):
        command.append("-microarch:x86-64")
        baseline = "x86-64 baseline (SSE2)"
    print(f"Building examples/dither with -vet -o:speed; {baseline}", flush=True)
    run(command)
    return output


def dither_pair(core, source):
    outputs = [
        core.odin_dither.Dither(source, bits=8, seed=0, simd=simd, scale=0)
        for simd in (0, 1)
    ]
    for output in outputs:
        core.std.SetVideoCache(output, mode=0)
    return outputs


def verify_parity(outputs, frames: range, deadline: float) -> None:
    scalar, simd = outputs
    for n in frames:
        remaining = deadline - perf_counter()
        require(remaining > 0, "Benchmark runtime limit exceeded during parity verification")
        with scalar.get_frame_async(n).result(timeout=remaining) as expected:
            remaining = deadline - perf_counter()
            require(remaining > 0, "Benchmark runtime limit exceeded during parity verification")
            with simd.get_frame_async(n).result(timeout=remaining) as actual:
                require(
                    (actual.format.id, actual.width, actual.height)
                    == (expected.format.id, expected.width, expected.height),
                    f"Frame {n}: scalar/SIMD output formats or dimensions differ",
                )
                for plane in range(actual.format.num_planes):
                    # memoryview.tobytes copies active samples, omitting row padding.
                    require(
                        actual[plane].tobytes() == expected[plane].tobytes(),
                        f"Frame {n}, plane {plane}: scalar/SIMD pixels differ",
                    )


def request_frames(clip, start: int, count: int, requests: int, deadline: float) -> float:
    started = perf_counter()
    stop = start + count
    next_frame = start + min(requests, count)
    pending = deque(clip.get_frame_async(n) for n in range(start, next_frame))
    while pending:
        remaining = deadline - perf_counter()
        require(remaining > 0, "Benchmark runtime limit exceeded during frame requests")
        with pending.popleft().result(timeout=remaining):
            pass
        if next_frame < stop:
            pending.append(clip.get_frame_async(next_frame))
            next_frame += 1
    return perf_counter() - started


def benchmark(core, vs, args) -> None:
    deadline = perf_counter() + args.timeout
    for format_id, width, height in ((vs.GRAY16, 65, 47), (vs.YUV420P16, 66, 48)):
        patterned = patterned_clip(core, format_id, width, height, length=3)
        verify_parity(dither_pair(core, patterned), range(3), deadline)

    length = 1 + args.warmup_frames + args.runs * args.frames
    source = core.std.BlankClip(
        format=vs.GRAY16,
        width=args.width,
        height=args.height,
        length=length,
        color=[32767],
        keep=True,
    )
    outputs = dither_pair(core, source)
    verify_parity(outputs, range(1), deadline)
    print("PASS exact scalar/SIMD pixel parity: patterned planes and benchmark frame", flush=True)
    print(
        f"{args.width} x {args.height} Gray16 -> Gray8; bits=8, seed=0, scale=0\n"
        f"{args.threads} VapourSynth threads; {args.requests} outstanding requests\n"
        f"{args.warmup_frames} warmup frames, then {args.runs} runs of {args.frames} frames per mode\n"
        "Reusable in-memory source; output caches disabled; unique output frame indices\n"
        "End-to-end VapourSynth frame throughput, including allocation and scheduling",
        flush=True,
    )
    for output in outputs:
        request_frames(output, 1, args.warmup_frames, args.requests, deadline)

    elapsed = [[], []]
    first_frame = 1 + args.warmup_frames
    for iteration in range(args.runs):
        order = (0, 1) if iteration % 2 == 0 else (1, 0)
        for mode in order:
            elapsed[mode].append(
                request_frames(outputs[mode], first_frame, args.frames, args.requests, deadline)
            )
        first_frame += args.frames
        print(
            f"Run {iteration + 1}: scalar {elapsed[0][-1]:.4f} s, SIMD {elapsed[1][-1]:.4f} s",
            flush=True,
        )

    medians = [median(samples) for samples in elapsed]
    print("\nMode     Median seconds   Frames/second   Megapixels/second")
    for name, duration in zip(("Scalar", "SIMD"), medians):
        fps = args.frames / duration
        megapixels = fps * args.width * args.height / 1_000_000
        print(f"{name:<8} {duration:>14.6f} {fps:>15.2f} {megapixels:>19.2f}")
    print(f"Scalar/SIMD median time ratio: {medians[0] / medians[1]:.3f}x")
    print("Results depend on the machine, compiler, source, and request concurrency; no speed threshold is enforced.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--runtime", type=Path, help="Directory containing an existing VapourSynth Python module")
    parser.add_argument("--width", type=positive_integer, default=1920, help="Source width (default: 1920)")
    parser.add_argument("--height", type=positive_integer, default=1080, help="Source height (default: 1080)")
    parser.add_argument("--frames", type=positive_integer, default=256, help="Frames per measured run (default: 256)")
    parser.add_argument("--runs", type=positive_integer, default=5, help="Measured runs per mode (default: 5)")
    parser.add_argument("--warmup-frames", type=positive_integer, default=16, help="Warmup frames per mode (default: 16)")
    parser.add_argument("--threads", type=positive_integer, default=4, help="VapourSynth worker threads (default: 4)")
    parser.add_argument("--requests", type=positive_integer, default=4, help="Outstanding frame requests (default: 4)")
    parser.add_argument("--timeout", type=positive_integer, default=120, help="Parity and timing runtime limit in seconds (default: 120)")
    args = parser.parse_args()

    vs = runtime_module(args.runtime)
    print(
        f"VapourSynth {vs.__version__}; API {vs.__api_version__}\n"
        f"Python module: {vs.__file__}\n"
        f"Python: {platform.python_implementation()} {platform.python_version()}\n"
        f"Machine: {platform.system()} {platform.machine()}; {platform.processor()}",
        flush=True,
    )
    plugin = build_plugin(args.odin)
    core = vs.core
    core.num_threads = args.threads
    core.std.LoadPlugin(path=str(plugin))
    benchmark(core, vs, args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
