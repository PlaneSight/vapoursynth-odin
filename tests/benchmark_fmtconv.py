#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Single-worker, end-to-end Odin / FMTConv void-and-cluster benchmark.

Requires existing plugin binaries; nothing is built, downloaded, or installed.
FMTConv uses dmode=8, patsize=64, ampo=1, ampn=0, dyn=0, tpdfo=0, cpuopt=-1.
Limited-to-limited conversion matches Odin scale=0 code-point scaling. Full
Gray/RGB conversion matches scale=1; full YUV chroma has a different offset and
is deliberately excluded. Tiles and threshold rounding differ: this measures
equivalent conversion operations, not pixel-identical implementations.
Use --low-bits for a separate Odin-only matrix: Gray/RGB 8/16-bit input to
1/2/4/7 effective bits in 8-bit containers. FMTConv has no equivalent output.
Untimed tile checks validate quantization neighbours and mean error within
0.01 quantization steps before any timing is accepted.

The source is one reusable BlankClip frame. Output caches are disabled, every
timed output index is unique, and graph construction and warmup are untimed.
Four queued requests keep core.num_threads=1 busy. Timings include allocation,
VapourSynth scheduling, Python request delivery and frame release. Run on an
otherwise idle machine. JSON retains every run, binary hashes and all options.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from math import ceil, floor
import os
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter

from examples import ROOT, require, runtime_module


RESOLUTIONS = {"720p": (1280, 720), "1080p": (1920, 1080),
               "1440p": (2560, 1440), "2160p": (3840, 2160)}


@dataclass(frozen=True)
class Case:
    name: str
    family: str
    input_bits: int
    output_bits: int
    subsampling_w: int = 0
    subsampling_h: int = 0
    scale: int = 0


CASES = (
    Case("gray10_8_shift", "GRAY", 10, 8),
    Case("gray12_8_shift", "GRAY", 12, 8),
    Case("gray16_8_shift", "GRAY", 16, 8),
    Case("rgb16_8_shift", "RGB", 16, 8),
    Case("yuv420p10_8_shift", "YUV", 10, 8, 1, 1),
    Case("yuv420p12_8_shift", "YUV", 12, 8, 1, 1),
    Case("yuv420p16_8_shift", "YUV", 16, 8, 1, 1),
    Case("yuv422p16_8_shift", "YUV", 16, 8, 1, 0),
    Case("yuv444p16_8_shift", "YUV", 16, 8),
    Case("gray16_10_shift", "GRAY", 16, 10),
    Case("yuv420p16_10_shift", "YUV", 16, 10, 1, 1),
    Case("yuv444p16_12_shift", "YUV", 16, 12),
    Case("gray16_8_full", "GRAY", 16, 8, scale=1),
    Case("rgb16_8_full", "RGB", 16, 8, scale=1),
    Case("rgb16_10_full", "RGB", 16, 10, scale=1),
    Case("rgb16_12_full", "RGB", 16, 12, scale=1),
)
LOW_BIT_CASES = tuple(
    Case(f"{family.lower()}{input_bits}_{bits}_full", family, input_bits, bits, scale=1)
    for family in ("GRAY", "RGB") for input_bits in (8, 16) for bits in (1, 2, 4, 7)
)


def positive_integer(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def binary_metadata(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def cpu_name() -> str:
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor() or platform.machine()


def set_cpu_affinity(cpus: list[int] | None) -> None:
    if cpus is None:
        return
    require(len(cpus) == len(set(cpus)) and all(cpu >= 0 for cpu in cpus),
            "--cpu-affinity requires unique nonnegative logical CPU indices")
    if sys.platform == "win32":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.argtypes = []
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.GetProcessAffinityMask.restype = ctypes.c_int
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        kernel.SetProcessAffinityMask.restype = ctypes.c_int
        process = kernel.GetCurrentProcess()
        current, available = ctypes.c_size_t(), ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(process, ctypes.byref(current), ctypes.byref(available)):
            raise ctypes.WinError(ctypes.get_last_error())
        require(max(cpus) < ctypes.sizeof(ctypes.c_size_t) * 8,
                "CPU index exceeds the Windows primary processor group mask")
        requested = sum(1 << cpu for cpu in cpus)
        require(requested & available.value == requested,
                "Requested logical CPUs are unavailable in the primary processor group")
        if not kernel.SetProcessAffinityMask(process, requested):
            raise ctypes.WinError(ctypes.get_last_error())
        return
    if hasattr(os, "sched_setaffinity"):
        require(set(cpus) <= os.sched_getaffinity(0), "Requested logical CPUs are unavailable")
        os.sched_setaffinity(0, cpus)
        return
    raise RuntimeError("--cpu-affinity is supported only on Windows and sched_setaffinity platforms")


def request_frames(clip, start: int, count: int, requests: int, deadline: float) -> float:
    started = perf_counter()
    stop = start + count
    next_frame = min(start + requests, stop)
    pending = deque(clip.get_frame_async(n) for n in range(start, next_frame))
    while pending:
        remaining = deadline - perf_counter()
        require(remaining > 0, "Benchmark exceeded --timeout")
        with pending.popleft().result(timeout=remaining):
            pass
        if next_frame < stop:
            pending.append(clip.get_frame_async(next_frame))
            next_frame += 1
    return perf_counter() - started


def source_values(case: Case) -> list[int]:
    peak = (1 << case.input_bits) - 1
    return [peak // 2] if case.family == "GRAY" else [peak * k // 100 for k in (17, 43, 81)]


def make_source(core, vs, case: Case, width: int, height: int, length: int):
    fmt = core.query_video_format(getattr(vs, case.family), vs.INTEGER, case.input_bits,
                                  case.subsampling_w, case.subsampling_h)
    return core.std.BlankClip(format=fmt.id, width=width, height=height,
                              length=length, color=source_values(case), keep=True)


def make_outputs(core, source, case: Case, odin_names: list[str], cpuopt: int) -> dict:
    outputs = {name: getattr(core, name).Dither(source, bits=case.output_bits,
                                              simd=1, seed=0, scale=case.scale)
               for name in odin_names}
    if case.output_bits >= 8:
        outputs["fmtconv"] = core.fmtconv_reference.bitdepth(
            source, bits=case.output_bits, dmode=8, fulls=case.scale, fulld=case.scale,
            patsize=64, ampo=1.0, ampn=0.0, dyn=0, staticnoise=1,
            tpdfo=0, tpdfn=0, corplane=0, cpuopt=cpuopt,
        )
    for output in outputs.values():
        core.std.SetVideoCache(output, mode=0)
    return outputs


def verify_outputs(outputs: dict, case: Case, width: int, height: int) -> tuple[int, dict]:
    samples = 0
    validation = {}
    output_max = (1 << case.output_bits) - 1
    scale = output_max / ((1 << case.input_bits) - 1) if case.scale else 2 ** (case.output_bits - case.input_bits)
    expected_values = [min(value * scale, output_max) for value in source_values(case)]
    def container_code(index: int) -> int:
        return (index * 255 + output_max // 2) // output_max if case.output_bits < 8 else index

    for name, output in outputs.items():
        with output.get_frame(0) as frame:
            require((frame.width, frame.height, frame.format.bits_per_sample)
                    == (width, height, max(8, case.output_bits)), f"Wrong output shape/format: {name}")
            plane_samples = 0
            tiles = []
            for plane in range(frame.format.num_planes):
                data = frame[plane]
                plane_samples += data.shape[0] * data.shape[1]
                values = [data[y, x] for y in range(64) for x in range(64)]
                index = expected_values[plane]
                low, high = container_code(floor(index)), container_code(ceil(index))
                expected = low + (high - low) * (index - floor(index))
                require(set(values) <= {low, high},
                        f"{name} plane {plane}: output is outside the expected quantization neighbours")
                mean = sum(values) / len(values)
                step = max(1, high - low)
                require(abs(mean - expected) / step <= 0.01,
                        f"{name} plane {plane}: tile mean {mean} does not match conversion target {expected}")
                tiles.append({"expected": expected, "mean": mean, "mean_error": mean - expected,
                              "mean_error_in_quantization_steps": (mean - expected) / step,
                              "minimum": min(values), "maximum": max(values)})
            if samples:
                require(samples == plane_samples, "Output plane sample counts differ")
            samples = plane_samples
            validation[name] = tiles
    return samples, validation


def summarize(durations: list[float], frames: int, samples_per_frame: int) -> dict:
    center = median(durations)
    mad = median(abs(value - center) for value in durations)
    return {"seconds": durations, "median_ms_per_frame": 1000 * center / frames,
            "mad_percent": 100 * mad / center, "min_ms_per_frame": 1000 * min(durations) / frames,
            "max_ms_per_frame": 1000 * max(durations) / frames,
            "frames_per_second": frames / center,
            "ns_per_sample": center * 1e9 / (frames * samples_per_frame)}


def measure(core, vs, case: Case, resolution: str, args, odin_names: list[str], deadline: float) -> dict:
    width, height = RESOLUTIONS[resolution]
    length = 1 + args.warmup_frames + args.frames * args.runs
    source = make_source(core, vs, case, width, height, length)
    outputs = make_outputs(core, source, case, odin_names, args.fmtconv_cpuopt)
    samples, validation = verify_outputs(outputs, case, width, height)
    for clip in outputs.values():
        request_frames(clip, 1, args.warmup_frames, args.requests, deadline)
    elapsed = {name: [] for name in outputs}
    names = list(outputs)
    first = 1 + args.warmup_frames
    for iteration in range(args.runs):
        offset = iteration % len(names)
        order = names[offset:] + names[:offset]
        if (iteration // len(names)) % 2:
            order.reverse()
        for name in order:
            elapsed[name].append(request_frames(outputs[name], first, args.frames,
                                                 args.requests, deadline))
        first += args.frames
    metrics = {name: summarize(values, args.frames, samples) for name, values in elapsed.items()}
    ratios = {}
    if "fmtconv" in metrics:
        reference = metrics["fmtconv"]["median_ms_per_frame"]
        ratios = {name: reference / metrics[name]["median_ms_per_frame"] for name in odin_names}
    print(f"{resolution:>5} {case.name:<23} " + " | ".join(
        f"{name}: {value['median_ms_per_frame']:.3f} ms, {value['ns_per_sample']:.3f} ns/sample, "
        f"MAD {value['mad_percent']:.1f}%" for name, value in metrics.items()
    ) + (" | " + ", ".join(f"{name}/FMT {ratio:.3f}x" for name, ratio in ratios.items()) if ratios else ""), flush=True)
    return {"case": asdict(case), "resolution": resolution, "width": width, "height": height,
            "samples_per_frame": samples, "tile_validation": validation,
            "metrics": metrics, "odin_speedup_over_fmtconv": ratios}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin-plugin", required=True, type=Path)
    parser.add_argument("--baseline-plugin", type=Path, help="Optional previous Odin DLL for an interleaved comparison")
    parser.add_argument("--fmtconv-plugin", type=Path, help="Required for the FMTConv comparison matrix")
    parser.add_argument("--low-bits", action="store_true",
                        help="Measure Odin 1/2/4/7-bit output in 8-bit containers; FMTConv has no equivalent")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--resolutions", nargs="+", choices=RESOLUTIONS, default=list(RESOLUTIONS))
    parser.add_argument("--cases", nargs="+", choices=[case.name for case in (*CASES, *LOW_BIT_CASES)])
    parser.add_argument("--frames", type=positive_integer, default=64)
    parser.add_argument("--runs", type=positive_integer, default=7)
    parser.add_argument("--warmup-frames", type=positive_integer, default=8)
    parser.add_argument("--requests", type=positive_integer, default=4)
    parser.add_argument("--cpu-affinity", nargs="+", type=int,
                        help="Restrict this benchmark process to these logical CPUs; does not change VS worker count")
    parser.add_argument("--timeout", type=positive_integer, default=1200)
    parser.add_argument("--fmtconv-cpuopt", type=int, choices=(-1, 0, 1, 10), default=-1)
    parser.add_argument("--output", type=Path, default=ROOT / ".build" / "fmtconv" / "benchmark.json")
    parser.add_argument("--build-description", default="Existing binary; consult its build command",
                        help="Exact Odin compiler/target flags recorded alongside the binary hash")
    parser.add_argument("--baseline-build-description", default="Existing binary; consult its build command",
                        help="Compiler/target flags for the optional previous Odin binary")
    args = parser.parse_args()
    require(args.low_bits or args.fmtconv_plugin is not None,
            "--fmtconv-plugin is required unless --low-bits is selected")
    available_cases = LOW_BIT_CASES if args.low_bits else CASES
    cases = [case for case in available_cases if not args.cases or case.name in args.cases]
    require(not args.cases or {case.name for case in cases} == set(args.cases),
            "Selected cases do not belong to the --low-bits/comparison matrix")
    binaries = {"odin": args.odin_plugin}
    if args.fmtconv_plugin:
        binaries["fmtconv"] = args.fmtconv_plugin
    if args.baseline_plugin:
        binaries["odin_baseline"] = args.baseline_plugin
    for path in binaries.values():
        require(path.is_file(), f"Plugin does not exist: {path}")
    set_cpu_affinity(args.cpu_affinity)
    vs = runtime_module(args.runtime)
    core = vs.core
    core.num_threads = 1
    core.max_cache_size = 512
    odin_names = [name for name in binaries if name != "fmtconv"]
    for name in odin_names:
        core.std.LoadPlugin(path=str(binaries[name].resolve()), forcens=name,
                            forceid=f"org.vapoursynth.odin.benchmark.{name}")
    if args.fmtconv_plugin:
        core.std.LoadPlugin(path=str(args.fmtconv_plugin.resolve()), forcens="fmtconv_reference",
                            forceid="org.vapoursynth.odin.benchmark.fmtconv")
    options = vars(args).copy()
    options = {key: str(value) if isinstance(value, Path) else value for key, value in options.items()}
    report = {"schema": 1, "complete": False, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "machine": {"os": platform.platform(), "cpu": cpu_name(), "logical_cpus": os.cpu_count()},
              "runtime": {"vapoursynth": str(vs.__version__), "api": str(vs.__api_version__),
                          "python": platform.python_version(), "num_threads": core.num_threads,
                          "fmtconv": str(core.fmtconv_reference.version) if args.fmtconv_plugin else None,
                          "module": str(vs.__file__)},
              "binaries": {name: binary_metadata(path) for name, path in binaries.items()},
              "options": options, "results": []}
    report["binaries"]["odin"]["build_description"] = args.build_description
    if args.baseline_plugin:
        report["binaries"]["odin_baseline"]["build_description"] = args.baseline_build_description
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2), flush=True)
    deadline = perf_counter() + args.timeout
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for resolution in args.resolutions:
        for case in cases:
            report["results"].append(measure(core, vs, case, resolution, args, odin_names, deadline))
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["complete"] = True
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(report['results'])} cases to {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, TimeoutError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
