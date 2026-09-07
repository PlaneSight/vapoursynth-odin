#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Check the extended dither plugin against independent integer and diffusion oracles.

Requires Odin and an installed VapourSynth Python module. All generated binaries
stay in .build/examples. --runtime selects an existing module directory; --no-build
checks already compiled plugins. Nothing is downloaded or installed.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import math
from pathlib import Path
import sys
import sysconfig

from examples import ROOT, require, runtime_module, snapshot
from advanced import equal_pixels, expect_error, fixture_clip, read_noise_tile

sys.path.insert(0, str(ROOT))
from tools.examples import build_examples
from tools.native_build import native_target


MODES = ("none", "bayer", "blue_noise", "floyd_steinberg", "sierra_lite")
MASK_MODES = ("bayer", "blue_noise")
DIFFUSION_MODES = ("floyd_steinberg", "sierra_lite")
WIDTHS = (1, 15, 16, 17, 63, 64, 65)


def bayer_matrix() -> list[list[int]]:
    matrix = [[0]]
    quadrants = ((0, 2), (3, 1))
    for _ in range(3):
        size = len(matrix)
        matrix = [
            [4 * matrix[y % size][x % size] + quadrants[y // size][x // size]
             for x in range(2 * size)]
            for y in range(2 * size)
        ]
    require(sorted(value for row in matrix for value in row) == list(range(64)), "Invalid Bayer oracle")
    return matrix


BAYER = bayer_matrix()


def expand(code: int, bits: int) -> int:
    maximum = (1 << bits) - 1
    return (code * 255 + maximum // 2) // maximum if bits < 8 else code


def independent_oracle(planes, ranks, source_bits, bits, mode, seed=0, scale=0, corplane=0, dyn=0, n=0):
    if bits == source_bits:
        return planes
    if mode in DIFFUSION_MODES:
        return diffusion_oracle(planes, source_bits, bits, mode, scale)
    source_max, maximum = (1 << source_bits) - 1, (1 << bits) - 1
    step = 1 << (source_bits - bits)
    threshold_range = step if scale == 0 else source_max
    output = []
    for plane, rows in enumerate(planes):
        channel = 0 if corplane else plane
        phase_x = (seed + 17 * channel + (13 * n if dyn else 0)) & 63
        phase_y = ((seed >> 6) + 29 * channel + (37 * n if dyn else 0)) & 63
        converted = []
        for y, row in enumerate(rows):
            destination = []
            for x, raw_sample in enumerate(row):
                sample = min(raw_sample, source_max)
                if mode == "none":
                    threshold = threshold_range // 2
                elif mode == "bayer":
                    rank = BAYER[(y + phase_y) % 8][(x + phase_x) % 8]
                    threshold = (2 * rank + 1) * threshold_range // 128
                else:
                    rank = ranks[((y + phase_y) & 63) * 64 + ((x + phase_x) & 63)]
                    threshold = (2 * rank + 1) * threshold_range // 8192
                code = ((sample + threshold) // step if scale == 0
                        else (sample * maximum + threshold) // source_max)
                destination.append(expand(min(maximum, code), bits))
            converted.append(destination)
        output.append(converted)
    return output


def diffusion_oracle(planes, source_bits, bits, mode, scale):
    source_max, maximum = (1 << source_bits) - 1, (1 << bits) - 1
    step = 1 << (source_bits - bits)
    output = []
    for rows in planes:
        height, width = len(rows), len(rows[0])
        errors = [[0.0] * width for _ in range(height)]
        converted = [[0] * width for _ in range(height)]
        for y in range(height):
            direction = 1 if y % 2 == 0 else -1
            columns = range(width) if direction == 1 else range(width - 1, -1, -1)
            for x in columns:
                sample = float(min(rows[y][x], source_max))
                scaled = sample / float(step) if scale == 0 else (sample * float(maximum)) / float(source_max)
                value = min(float(maximum), max(0.0, scaled + errors[y][x]))
                code = math.floor(value + 0.5)
                converted[y][x] = expand(code, bits)
                residual = value - float(code)
                neighbors = (
                    ((x + direction, y, 7 / 16), (x - direction, y + 1, 3 / 16),
                     (x, y + 1, 5 / 16), (x + direction, y + 1, 1 / 16))
                    if mode == "floyd_steinberg" else
                    ((x + direction, y, 1 / 2), (x - direction, y + 1, 1 / 4), (x, y + 1, 1 / 4))
                )
                for next_x, next_y, weight in neighbors:
                    if 0 <= next_x < width and next_y < height:
                        errors[next_y][next_x] += residual * weight
        output.append(converted)
    return output


def check_case(core, vs, ranks, source_bits, bits, width, height, family, subsampling, mode, scale, seed=83,
               corplane=0, dyn=0):
    format_id = core.query_video_format(family, vs.INTEGER, source_bits, *subsampling).id
    maximum = (1 << source_bits) - 1

    def pattern(plane, x, y):
        if x % 11 == 0:
            return 0
        if x % 11 == 1:
            return maximum
        return (197 * x + 313 * y + 997 * plane) & maximum

    source = fixture_clip(core, format_id, width, height, pattern, length=3)
    source = core.std.SetFrameProps(source, _Transfer=13, _Primaries=1, _Range=1)
    arguments = dict(bits=bits, mode=mode, seed=seed, scale=scale, corplane=corplane, dyn=dyn)
    outputs = [core.odin_dither_plus.Dither(source, simd=simd, **arguments) for simd in (0, 1)]
    label = f"{mode}: {source_bits}->{bits}, {width}x{height}, {family}, scale={scale}, seed={seed}, corplane={corplane}, dyn={dyn}"
    with ExitStack() as stack:
        originals = [stack.enter_context(source.get_frame(n)) for n in range(source.num_frames)]
        before = [snapshot(frame) for frame in originals]
        expected = [independent_oracle(before[n], ranks, source_bits, bits, mode, seed, scale, corplane, dyn, n)
                    for n in range(source.num_frames)]
        # Out-of-order parallel requests also check that diffusion scratch is local to a frame.
        requests = [(n, output.get_frame_async(n)) for n in (2, 0, 1) for output in outputs]
        for n, future in requests:
            with future.result(timeout=30) as frame:
                require(frame.format.bits_per_sample == max(8, bits), f"{label}: incorrect output depth")
                require(frame.format.color_family == family, f"{label}: incorrect color family")
                require((frame.format.subsampling_w, frame.format.subsampling_h) == subsampling,
                        f"{label}: subsampling changed")
                for key in ("OdinAdvanced", "_Transfer", "_Primaries", "_Range"):
                    require(frame.props[key] == originals[n].props[key], f"{label}: {key} changed")
                equal_pixels(snapshot(frame), expected[n], label)
        for output in outputs:
            require(output.fps == source.fps and output.num_frames == source.num_frames,
                    f"{label}: timing changed")
        for n, original in enumerate(originals):
            equal_pixels(snapshot(original), before[n], f"{label}: source mutated")


def test_oracles(core, vs, ranks):
    cases = [(16, bits, width, 5, vs.GRAY, (0, 0))
             for bits in (1, 4, 7, 8, 10, 16) for width in WIDTHS]
    cases.extend((16, bits, 17, 3, vs.GRAY, (0, 0)) for bits in range(1, 17))
    cases.extend((source_bits, 1, 17, 5, vs.GRAY, (0, 0)) for source_bits in range(8, 17))
    cases.extend((source_bits, bits, width, height, family, subsampling)
                 for source_bits in (8, 12, 16) for bits in (2, 7, 8)
                 for width, height, family, subsampling in (
                     (17, 7, vs.RGB, (0, 0)), (66, 8, vs.YUV, (1, 1)),
                     (130, 5, vs.YUV, (1, 0)), (65, 5, vs.YUV, (0, 0))))
    count = 0
    for mode in MODES:
        for case in cases:
            for scale in (0, 1):
                check_case(core, vs, ranks, *case, mode, scale)
                count += 1
    for mode in MASK_MODES:
        for seed in (0, 63, 64, 4095):
            for corplane in (0, 1):
                for dyn in (0, 1):
                    for scale in (0, 1):
                        check_case(core, vs, ranks, 12, 3, 65, 65, vs.RGB, (0, 0), mode, scale,
                                   seed=seed, corplane=corplane, dyn=dyn)
                        count += 1
    print(f"PASS {count} independent oracle cases: five modes, scalar/SIMD, tails, formats, scales, "
          "phases, asynchronous frame order, source immutability and properties", flush=True)


def test_original_parity(core, vs):
    count = 0
    for format_id, width, height in ((vs.GRAY16, 65, 9), (vs.RGB48, 65, 9), (vs.YUV420P16, 66, 10)):
        source = fixture_clip(core, format_id, width, height,
                              lambda p, x, y: (x * 977 + y * 517 + p * 1031) & 65535, length=1)
        for bits in (1, 2, 7, 8, 10, 16):
            for scale in (0, 1):
                for seed in (0, 4095):
                    arguments = dict(bits=bits, scale=scale, seed=seed)
                    old = core.odin_dither.Dither(source, **arguments)
                    new = core.odin_dither_plus.Dither(source, **arguments)
                    with old.get_frame(0) as expected, new.get_frame(0) as actual:
                        equal_pixels(snapshot(actual), snapshot(expected), "Original blue-noise compatibility")
                    count += 1
    print(f"PASS {count} original blue-noise parity cases", flush=True)


def test_levels_and_correlation(core, vs):
    count = 0
    for bits in range(1, 8):
        maximum = (1 << bits) - 1
        source_bits = ((8 + bits - 1) // bits) * bits
        source_max = (1 << source_bits) - 1
        format_id = core.query_video_format(vs.GRAY, vs.INTEGER, source_bits).id
        wanted = [expand(code, bits) for code in range(maximum + 1)]
        for scale in (0, 1):
            step = (1 << (source_bits - bits)) if scale == 0 else source_max // maximum
            source = fixture_clip(core, format_id, maximum + 1, 3, lambda p, x, y: x * step, length=1)
            for mode in MODES:
                output = core.odin_dither_plus.Dither(source, bits=bits, scale=scale, mode=mode)
                with output.get_frame(0) as frame:
                    equal_pixels(snapshot(frame), [[wanted] * 3], f"{mode}: exact {bits}-bit levels")
                count += 1
    neutral = fixture_clip(core, vs.RGB48, 64, 64, lambda p, x, y: 29000, length=4)
    for mode in MASK_MODES:
        for dyn in (0, 1):
            outputs = [core.odin_dither_plus.Dither(neutral, bits=2, scale=1, mode=mode, corplane=value, dyn=dyn)
                       for value in (0, 1)]
            for n in (3, 0, 2, 1):
                with outputs[1].get_frame(n) as frame:
                    planes = snapshot(frame)
                    require(planes[0] == planes[1] == planes[2], f"{mode}: correlated neutral gained color")
                with outputs[0].get_frame(n) as frame:
                    planes = snapshot(frame)
                    require(planes[0] != planes[1] or planes[1] != planes[2],
                            f"{mode}: uncorrelated fixture did not exercise channel differences")
    print(f"PASS {count} exact low-bit level cases and correlated RGB neutrals", flush=True)


def test_temporal_and_ignored_options(core, vs):
    source = fixture_clip(core, vs.GRAY16, 65, 65, lambda p, x, y: 29000, length=130)
    for mode in MASK_MODES:
        static = core.odin_dither_plus.Dither(source, bits=2, scale=1, mode=mode)
        dynamic = core.odin_dither_plus.Dither(source, bits=2, scale=1, mode=mode, dyn=1)
        core.std.SetVideoCache(dynamic, mode=0)
        with static.get_frame(0) as first, static.get_frame(4) as last:
            equal_pixels(snapshot(first), snapshot(last), f"{mode}: static mask changed")
        pending = [(n, dynamic.get_frame_async(n)) for n in (4, 0, 2, 1, 3)]
        rendered = {}
        for n, future in pending:
            with future.result(timeout=30) as frame:
                rendered[n] = snapshot(frame)
        require(rendered[0] != rendered[1], f"{mode}: dyn=1 did not change the mask")
        for n in (3, 1, 4, 0, 2):
            with dynamic.get_frame(n) as frame:
                equal_pixels(snapshot(frame), rendered[n], f"{mode}: result depends on request history")
        for n in (64, 65, 128, 129):
            with dynamic.get_frame(n) as frame:
                equal_pixels(snapshot(frame), rendered[n % 64], f"{mode}: 64-frame phase period changed")
        changed_seed = core.odin_dither_plus.Dither(source, bits=2, scale=1, mode=mode, seed=1)
        with static.get_frame(0) as first, changed_seed.get_frame(0) as second:
            require(snapshot(first) != snapshot(second), f"{mode}: seed did not change the mask")
    for mode in ("none", *DIFFUSION_MODES):
        first = core.odin_dither_plus.Dither(source, bits=2, mode=mode, seed=0, corplane=0, simd=0)
        second = core.odin_dither_plus.Dither(source, bits=2, mode=mode, seed=4095, corplane=1, simd=1)
        with first.get_frame(0) as expected, second.get_frame(0) as actual:
            equal_pixels(snapshot(actual), snapshot(expected), f"{mode}: inactive options changed pixels")
    print("PASS static/dynamic masks, seed phases, cache-free seeking and inactive options", flush=True)


def test_boundaries(core, vs, ranks):
    gray = core.std.BlankClip(format=vs.GRAY10, width=16, height=16, length=1)
    invalid_arguments = [
        {"bits": 0}, {"bits": -1}, {"bits": 11}, {"bits": 1 << 40}, {"bits": "bad"},
        {"seed": -1}, {"seed": 4096}, {"seed": 1 << 40}, {"seed": "bad"},
        {"mode": ""}, {"mode": "Blue_noise"}, {"mode": "unknown"}, {"mode": 1},
        {"mode": b"blue_noise\0bayer"}, {"mode": b"none\0"}, {"mode": b"\xff"},
    ]
    for key in ("simd", "scale", "corplane", "dyn"):
        invalid_arguments.extend({key: value} for value in (-1, 2, 1 << 40, "bad"))
    invalid_arguments.extend({"mode": mode, "dyn": 1} for mode in ("none", *DIFFUSION_MODES))
    for arguments in invalid_arguments:
        for bits in (8, 10):
            supplied = {"bits": bits, **arguments}
            expect_error(vs, lambda supplied=supplied: core.odin_dither_plus.Dither(gray, **supplied),
                         f"Invalid options before {'passthrough' if bits == 10 else 'conversion'}: {supplied}")
    floating = core.std.BlankClip(format=vs.GRAYS, width=16, height=16, length=1)
    variable_format = core.std.Splice([gray, core.std.BlankClip(format=vs.GRAY8, width=16, height=16, length=1)],
                                     mismatch=True)
    variable_size = core.std.Splice([gray, core.std.BlankClip(format=vs.GRAY10, width=17, height=16, length=1)],
                                   mismatch=True)
    for source in (floating, variable_format, variable_size):
        expect_error(vs, lambda source=source: core.odin_dither_plus.Dither(source), "Invalid source")
    malformed = fixture_clip(core, vs.GRAY10, 17, 3, lambda p, x, y: 65535, length=1)
    for mode in MODES:
        for bits in (1, 7, 8, 10):
            for scale in (0, 1):
                for simd in (0, 1):
                    output = core.odin_dither_plus.Dither(malformed, bits=bits, mode=mode, scale=scale, simd=simd)
                    with output.get_frame(0) as frame:
                        wanted = 65535 if bits == 10 else 255
                        equal_pixels(snapshot(frame), [[[wanted] * 17 for _ in range(3)]],
                                     f"{mode}: malformed sample clamping/passthrough")
    output = core.odin_dither_plus.Dither(gray)
    for n in (-1, output.num_frames):
        expect_error(vs, lambda n=n: output.get_frame(n), f"Invalid frame index {n}")
    # A one-row, one-column source has no diffusion neighbors to receive residuals.
    for mode in DIFFUSION_MODES:
        for width, height in ((1, 1), (1, 7), (7, 1)):
            check_case(core, vs, ranks, 16, 2, width, height, vs.GRAY, (0, 0), mode, 1)
    print("PASS argument/type/mode validation before passthrough, malformed samples, variable clips and image edges",
          flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--runtime", type=Path, help="Existing VapourSynth Python module directory")
    parser.add_argument("--no-build", action="store_true", help="Use existing .build/examples plugins")
    args = parser.parse_args()
    if args.no_build:
        suffix = native_target(sysconfig.get_platform()).extension
        artifacts = {name: ROOT / ".build" / "examples" / f"{name}{suffix}" for name in ("dither", "dither_plus")}
        for artifact in artifacts.values():
            require(artifact.is_file(), f"Missing compiled plugin: {artifact}")
    else:
        artifacts = build_examples(("dither", "dither_plus"), args.odin)
    vs = runtime_module(args.runtime)
    core = vs.core
    core.num_threads = 4
    for artifact in artifacts.values():
        core.std.LoadPlugin(path=str(artifact))
    print(f"VapourSynth {vs.__version__}, API {vs.__api_version__}; {vs.__file__}", flush=True)
    ranks = read_noise_tile()
    test_oracles(core, vs, ranks)
    test_original_parity(core, vs)
    test_levels_and_correlation(core, vs)
    test_temporal_and_ignored_options(core, vs)
    test_boundaries(core, vs, ranks)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
