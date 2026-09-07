#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compare the advanced dithering modes with the original blue-noise example.

Builds both plugins using the repository's native build command, then measures
Gray16/RGB48 to 8-bit conversion at 720p, 1080p, and 4K. One VapourSynth worker
and four outstanding requests are fixed for every method. The input is a
reusable in-memory BlankClip; output caching is disabled and every output frame
index is requested once. Results include allocation, scheduling, Python request
delivery, and frame release. Graph construction and warmup are untimed.

Run on an otherwise idle machine. The defaults are a short comparison, not a
precise throughput claim; increase --frames, --diffusion-frames, and --runs to
assess variability. Diffusion uses fewer frames because its sequential kernels
take substantially longer per frame than the independent-pixel methods.
The global timeout includes building and setup. No speed threshold is enforced.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
import sysconfig
from time import perf_counter

from benchmark_dither import positive_integer, request_frames
from examples import ROOT, require, runtime_module

sys.path.insert(0, str(ROOT))
from tools.examples import build_examples
from tools.native_build import native_target


RESOLUTIONS = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}
FORMATS = {"gray16": ("GRAY16", [32767]), "rgb48": ("RGB48", [11141, 28180, 53083])}
MODES = ("none", "bayer", "blue_noise", "floyd_steinberg", "sierra_lite")
DIFFUSION_MODES = ("floyd_steinberg", "sierra_lite")
BASELINE = "original_blue_noise"
REQUESTS = 4


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--no-build", action="store_true", help="Use existing .build/examples plugin libraries")
    parser.add_argument("--runtime", type=Path, help="Directory containing an existing VapourSynth Python module")
    parser.add_argument("--resolutions", nargs="+", choices=RESOLUTIONS, default=list(RESOLUTIONS))
    parser.add_argument("--formats", nargs="+", choices=FORMATS, default=list(FORMATS))
    parser.add_argument("--frames", type=positive_integer, default=64,
                        help="Frames per measured run for independent-pixel methods (default: 64)")
    parser.add_argument("--diffusion-frames", type=positive_integer, default=8,
                        help="Frames per measured run for Floyd-Steinberg and Sierra Lite (default: 8)")
    parser.add_argument("--runs", type=positive_integer, default=5, help="Measured runs per method (default: 5)")
    parser.add_argument("--warmup-frames", type=positive_integer, default=2, help="Warmup frames per method (default: 2)")
    parser.add_argument("--timeout", type=positive_integer, default=300, help="Global runtime limit in seconds (default: 300)")
    parser.add_argument("--json", nargs="?", type=Path, const=ROOT / ".build" / "benchmarks" / "dither_plus.json",
                        help="Write machine-readable results (default path: .build/benchmarks/dither_plus.json)")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def plugin_paths(args: argparse.Namespace) -> dict[str, Path]:
    if not args.no_build:
        return build_examples(["dither", "dither_plus"], odin=args.odin)
    suffix = native_target(sysconfig.get_platform()).extension
    paths = {name: ROOT / ".build" / "examples" / f"{name}{suffix}"
             for name in ("dither", "dither_plus")}
    for path in paths.values():
        require(path.is_file() and path.stat().st_size > 0,
                f"Missing plugin: {path}. Run without --no-build to compile it.")
    return paths


def binary_metadata(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def make_outputs(core, source) -> dict:
    options = {"bits": 8, "seed": 0, "simd": 1, "scale": 0}
    outputs = {BASELINE: core.odin_dither.Dither(source, **options)}
    outputs.update({mode: core.odin_dither_plus.Dither(
        source, mode=mode, corplane=0, dyn=0, **options) for mode in MODES})
    for output in outputs.values():
        core.std.SetVideoCache(output, mode=0)
    return outputs


def frames_per_method(args: argparse.Namespace) -> dict[str, int]:
    return {name: args.diffusion_frames if name in DIFFUSION_MODES else args.frames
            for name in (BASELINE, *MODES)}


def run_case(core, vs, args: argparse.Namespace, resolution: str, format_name: str,
             deadline: float) -> dict:
    width, height = RESOLUTIONS[resolution]
    format_constant, color = FORMATS[format_name]
    frame_counts = frames_per_method(args)
    length = args.warmup_frames + args.runs * max(frame_counts.values())
    source = core.std.BlankClip(format=getattr(vs, format_constant), width=width,
                               height=height, length=length, color=color, keep=True)
    outputs = make_outputs(core, source)
    names = tuple(outputs)
    samples = {name: [] for name in names}
    print(f"\n{resolution}: {width} x {height}, {format_constant} -> 8-bit", flush=True)
    for output in outputs.values():
        request_frames(output, 0, args.warmup_frames, REQUESTS, deadline)

    orders = []
    for iteration in range(args.runs):
        offset = iteration % len(names)
        order = names[offset:] + names[:offset]
        orders.append(list(order))
        for name in order:
            count = frame_counts[name]
            start = args.warmup_frames + iteration * count
            elapsed = request_frames(outputs[name], start, count, REQUESTS, deadline)
            samples[name].append(elapsed * 1000 / count)
        print(f"  Completed run {iteration + 1}/{args.runs}", flush=True)

    baseline_ms = median(samples[BASELINE])
    results = {}
    print(f"{'Method':<22} {'Frames/run':>10} {'ms/frame':>10} {'FPS':>10} {'MAD ms':>10} {'MAD %':>8} {'vs original':>12}")
    for name in names:
        center = median(samples[name])
        mad = median(abs(sample - center) for sample in samples[name])
        results[name] = {"frames_per_run": frame_counts[name],
                         "samples_ms_per_frame": samples[name], "median_ms_per_frame": center,
                         "median_fps": 1000 / center, "mad_ms_per_frame": mad,
                         "mad_percent": mad / center * 100, "speed_ratio_to_original": baseline_ms / center}
        print(f"{name:<22} {frame_counts[name]:>10} {center:>10.4f} {1000 / center:>10.2f} {mad:>10.4f} "
              f"{mad / center * 100:>8.2f} {baseline_ms / center:>11.3f}x", flush=True)
    return {"resolution": resolution, "width": width, "height": height,
            "input_format": format_constant, "source_color": color,
            "method_order_by_run": orders, "methods": results}


def benchmark(args: argparse.Namespace) -> None:
    deadline = perf_counter() + args.timeout
    plugins = plugin_paths(args)
    vs = runtime_module(args.runtime)
    core = vs.core
    core.num_threads = 1
    core.std.LoadPlugin(path=str(plugins["dither"]))
    core.std.LoadPlugin(path=str(plugins["dither_plus"]))
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"platform": platform.platform(), "machine": platform.machine(),
                        "processor": platform.processor(), "python": platform.python_version(),
                        "python_implementation": platform.python_implementation(),
                        "vapoursynth": str(vs.__version__), "vapoursynth_api": str(vs.__api_version__),
                        "vapoursynth_module": str(vs.__file__)},
        "plugins": {name: binary_metadata(path) for name, path in plugins.items()},
        "configuration": {"num_threads": 1, "requests": REQUESTS,
                          "frames_per_method": frames_per_method(args),
                          "runs": args.runs, "warmup_frames": args.warmup_frames, "bits": 8,
                          "seed": 0, "simd": 1, "scale": 0, "corplane": 0, "dyn": 0,
                          "source": "reusable BlankClip", "output_cache": False,
                          "timeout_seconds": args.timeout},
        "cases": [],
    }
    print(f"VapourSynth {vs.__version__}; Python {platform.python_version()}; "
          f"{platform.system()} {platform.machine()} / {platform.processor()}\n"
          f"core.num_threads = 1; {REQUESTS} outstanding requests; "
          f"{args.runs} runs; {args.warmup_frames} warmup frames per method\n"
          f"Frames per run: {args.frames} for original blue noise, nearest, Bayer, and advanced blue noise; "
          f"{args.diffusion_frames} for Floyd-Steinberg and Sierra Lite\n"
          "Median absolute deviation (MAD) describes run variability, not a confidence interval.\n"
          "Ratios above 1x mean faster than the original blue-noise example.", flush=True)
    for resolution in dict.fromkeys(args.resolutions):
        for format_name in dict.fromkeys(args.formats):
            report["cases"].append(run_case(core, vs, args, resolution, format_name, deadline))
    if args.json is not None:
        destination = args.json.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {destination}", flush=True)
    print("\nThese timings measure end-to-end frame throughput on a reusable constant source. "
          "Repeat longer runs on an idle machine before drawing performance conclusions.", flush=True)


def main() -> int:
    args = arguments()
    if args.worker:
        benchmark(args)
        return 0
    # A separate process lets the deadline bound native initialization and builds,
    # as well as frame requests whose native callbacks might otherwise block exit.
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"]
    return subprocess.run(command, cwd=ROOT, timeout=args.timeout, check=False).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        print("ERROR: Benchmark exceeded its global --timeout; no complete result was produced.", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
