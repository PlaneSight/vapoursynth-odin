#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Check the dither and Hald CLUT plugins against independent pixel oracles.

Uses Python's standard library, Odin, and an installed VapourSynth module.
Generated optimized plugins and PNG fixtures stay in .build/advanced. Nothing
is downloaded or installed. --runtime selects an existing Python module parent.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from itertools import permutations
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
import zlib

from examples import ROOT, require, run, runtime_module, snapshot

sys.path.insert(0, str(ROOT))
from tools.native_build import native_target, prepare_stb_image


BUILD = ROOT / ".build" / "advanced"
FIXTURES = BUILD / "fixtures"


def build_plugin(odin: str, name: str) -> Path:
    compiler = shutil.which(odin)
    require(compiler is not None, f"Cannot find Odin compiler: {odin}")
    BUILD.mkdir(parents=True, exist_ok=True)
    target = native_target(sysconfig.get_platform())
    output = BUILD / f"{name}{target.extension}"
    print(f"Building optimized examples/{name}", flush=True)
    with tempfile.TemporaryDirectory(prefix="compile-", dir=BUILD) as directory:
        dependencies = prepare_stb_image(compiler, target, Path(directory)) if name == "haldlut" else ()
        command = [
            compiler, "build", str(ROOT / "examples" / name), "-vet", "-o:speed",
            "-build-mode:dll", *target.flags, *dependencies, f"-out:{output}",
        ]
        run(command)
    return output


def expect_error(vs, operation, label: str, prefix: str | None = None) -> None:
    try:
        operation()
    except (vs.Error, ValueError, IndexError) as error:
        require(bool(str(error)), f"{label}: failed without a diagnostic")
        if prefix is not None:
            require(prefix in str(error), f"{label}: unexpected diagnostic: {error}")
        return
    raise RuntimeError(f"{label}: invalid input was accepted")


def fixture_clip(core, format_id: int, width: int, height: int, sample, length: int = 3):
    blank = core.std.BlankClip(format=format_id, width=width, height=height, length=length)

    def fill(n, f):
        output = f.copy()
        for plane in range(output.format.num_planes):
            view = output[plane]
            rows, columns = view.shape
            for y in range(rows):
                for x in range(columns):
                    view[y, x] = sample(plane, x, y)
        output.props["OdinAdvanced"] = 100 + n
        return output

    return core.std.ModifyFrame(blank, clips=blank, selector=fill)


def equal_pixels(actual, expected, label: str, tolerance: int = 0) -> None:
    require(len(actual) == len(expected), f"{label}: plane count changed")
    for plane, (actual_rows, expected_rows) in enumerate(zip(actual, expected)):
        require(len(actual_rows) == len(expected_rows), f"{label}: plane {plane} height changed")
        for y, (actual_row, expected_row) in enumerate(zip(actual_rows, expected_rows)):
            require(len(actual_row) == len(expected_row), f"{label}: plane {plane} width changed")
            for x, (value, wanted) in enumerate(zip(actual_row, expected_row)):
                require(
                    abs(value - wanted) <= tolerance,
                    f"{label}: plane {plane}, ({x}, {y}): expected {wanted}, got {value}",
                )


def read_noise_tile() -> list[int]:
    text = (ROOT / "examples" / "dither" / "blue_noise.odin").read_text(encoding="utf-8")
    declaration = re.search(r"BLUE_NOISE[^{}]*\{([^}]+)\}", text, re.DOTALL)
    require(declaration is not None, "Cannot locate the BLUE_NOISE rank array")
    body = re.sub(r"//[^\n]*", "", declaration.group(1))
    ranks = [int(value) for value in re.findall(r"\b\d+\b", body)]
    require(sorted(ranks) == list(range(4096)), "Blue-noise tile must contain every rank 0..4095 exactly once")
    return ranks


def dither_oracle(planes, ranks: list[int], source_bits: int, bits: int, seed: int, scale: int):
    if bits == source_bits:
        return planes
    source_max, maximum = (1 << source_bits) - 1, (1 << bits) - 1
    shift = source_bits - bits
    result = []
    for plane, rows in enumerate(planes):
        phase_x, phase_y = (seed + 17 * plane) & 63, ((seed >> 6) + 29 * plane) & 63
        output_rows = []
        for y, row in enumerate(rows):
            output_row = []
            for x, raw_sample in enumerate(row):
                sample = min(raw_sample, source_max)
                rank = ranks[((y + phase_y) & 63) * 64 + ((x + phase_x) & 63)]
                if scale == 0:
                    threshold = ((2 * rank + 1) * (1 << shift)) // 8192
                    value = min(maximum, (sample + threshold) >> shift)
                else:
                    threshold = ((2 * rank + 1) * source_max) // 8192
                    value = (sample * maximum + threshold) // source_max
                if bits < 8:
                    value = (value * 255 + maximum // 2) // maximum
                output_row.append(value)
            output_rows.append(output_row)
        result.append(output_rows)
    return result


def check_dither_case(core, vs, ranks, source_bits, bits, width, height, family, subsampling, scale, seed=83):
    format_id = core.query_video_format(family, vs.INTEGER, source_bits, *subsampling).id
    maximum = (1 << source_bits) - 1

    def pattern(plane, x, y):
        if x % 11 == 0:
            return 0
        if x % 11 == 1:
            return maximum
        return (197 * x + 313 * y + 997 * plane) & maximum

    source = fixture_clip(core, format_id, width, height, pattern)
    source = core.std.SetFrameProps(source, _Transfer=13, _Primaries=1, _Range=1)
    scalar = core.odin_dither.Dither(source, bits=bits, seed=seed, simd=0, scale=scale)
    vector = core.odin_dither.Dither(source, bits=bits, seed=seed, simd=1, scale=scale)
    label = f"Dither {source_bits}->{bits}, {width}x{height}, {family}, scale={scale}, seed={seed}"
    for node in (scalar, vector):
        require(node.num_frames == source.num_frames, f"{label}: frame count changed")
        require(node.fps == source.fps, f"{label}: frame rate changed")
    with ExitStack() as frames:
        originals = [frames.enter_context(source.get_frame(n)) for n in range(source.num_frames)]
        before = [snapshot(frame) for frame in originals]
        expected = dither_oracle(before[0], ranks, source_bits, bits, seed, scale)
        requests = [(n, node.get_frame_async(n)) for n in range(source.num_frames) for node in (scalar, vector)]
        for n, future in requests:
            with future.result(timeout=30) as frame:
                require(frame.format.bits_per_sample == max(8, bits), f"{label}: wrong output container depth")
                require(frame.format.bytes_per_sample == (1 if bits <= 8 else 2), f"{label}: wrong sample storage")
                require(frame.format.color_family == family, f"{label}: wrong output family")
                require(
                    (frame.format.subsampling_w, frame.format.subsampling_h) == subsampling,
                    f"{label}: subsampling changed",
                )
                require(frame.props["OdinAdvanced"] == 100 + n, f"{label}: frame properties lost")
                for key in ("_Transfer", "_Primaries", "_Range"):
                    require(frame.props[key] == originals[n].props[key], f"{label}: {key} changed")
                equal_pixels(snapshot(frame), expected, label)
        for n, original in enumerate(originals):
            equal_pixels(snapshot(original), before[n], f"{label}: source mutated")


def test_dither(core, vs) -> None:
    ranks = read_noise_tile()
    tail_widths = (1, 7, 8, 9, 15, 16, 17, 31, 32, 63, 64, 65)
    cases = [(bits, 8, 33, 5, vs.GRAY, (0, 0)) for bits in range(8, 17)]
    cases.extend((16, 8, width, 5, vs.GRAY, (0, 0)) for width in tail_widths)
    cases.extend((16, bits, 33, 5, vs.GRAY, (0, 0)) for bits in (9, 10, 12, 14, 16))
    cases.extend((
        (16, 8, 64, 64, vs.GRAY, (0, 0)),
        (10, 8, 17, 9, vs.RGB, (0, 0)),
        (16, 12, 17, 9, vs.RGB, (0, 0)),
        (12, 8, 66, 18, vs.YUV, (1, 1)),
    ))
    cases.extend(
        (source_bits, bits, 67, 5, vs.GRAY, (0, 0))
        for source_bits in range(8, 17) for bits in range(1, 8)
    )
    cases.extend(
        (source_bits, bits, width, 3, vs.GRAY, (0, 0))
        for source_bits in (8, 16) for bits in (1, 3, 7) for width in tail_widths
    )
    cases.extend(
        (source_bits, bits, width, height, family, subsampling)
        for source_bits in (8, 16) for bits in (1, 4, 7)
        for width, height, family, subsampling in (
            (65, 65, vs.RGB, (0, 0)),
            (66, 66, vs.YUV, (1, 1)),
            (130, 5, vs.YUV, (1, 0)),
            (65, 5, vs.YUV, (0, 0)),
        )
    )
    oracle_cases = 0
    for case in cases:
        for scale in (0, 1):
            check_dither_case(core, vs, ranks, *case, scale)
            oracle_cases += 1
    for seed in (0, 63, 64, 4095):
        for bits in (1, 3, 7, 8):
            for scale in (0, 1):
                check_dither_case(core, vs, ranks, 12, bits, 65, 65, vs.RGB, (0, 0), scale, seed)
                oracle_cases += 1
    print(
        f"PASS dither: {oracle_cases} oracle cases; effective depths 1-16, SIMD tails, subsampling, "
        "parallel requests, temporal stability, properties and retained source frames",
        flush=True,
    )

    check_low_bit_levels(core, vs)

    source = fixture_clip(core, vs.GRAY16, 64, 16, lambda p, x, y: (x + 64 * y) << 6, length=1)
    for seed in (0, 1, 63, 64, 4095):
        output = core.odin_dither.Dither(source, bits=10, seed=seed)
        with output.get_frame(0) as frame:
            equal_pixels(snapshot(frame), [[[x + 64 * y for x in range(64)] for y in range(16)]], "Nominal code points")
    fractional = fixture_clip(core, vs.GRAY16, 64, 64, lambda p, x, y: 128 * 256 + 128, length=1)
    seeded = [core.odin_dither.Dither(fractional, seed=seed) for seed in (0, 1)]
    with seeded[0].get_frame(0) as first, seeded[1].get_frame(0) as second:
        require(snapshot(first) != snapshot(second), "Changing dither seed did not change the spatial pattern")

    malformed = fixture_clip(core, vs.GRAY10, 17, 3, lambda p, x, y: 65535, length=1)
    for scale in (0, 1):
        for simd in (0, 1):
            for bits, wanted in ((1, 255), (3, 255), (7, 255), (8, 255), (10, 65535)):
                output = core.odin_dither.Dither(malformed, bits=bits, scale=scale, simd=simd)
                with output.get_frame(0) as frame:
                    equal_pixels(snapshot(frame), [[[wanted] * 17 for _ in range(3)]], "Malformed source sample policy")

    gray = core.std.BlankClip(format=vs.GRAY10, width=16, height=16, length=1)
    for arguments in (
        {"bits": 0}, {"bits": -1}, {"bits": -(1 << 40)},
        {"bits": 11}, {"bits": 17}, {"bits": 1 << 40}, {"bits": "bad"},
        {"seed": -1}, {"seed": 4096}, {"seed": 1 << 40}, {"seed": "bad"},
        {"simd": -1}, {"simd": 2}, {"scale": -1}, {"scale": 2},
    ):
        expect_error(vs, lambda arguments=arguments: core.odin_dither.Dither(gray, **arguments), f"Dither {arguments}")
    floating = core.std.BlankClip(format=vs.GRAYS, width=16, height=16, length=1)
    variable = core.std.Splice([gray, core.std.BlankClip(format=vs.GRAY8, width=16, height=16, length=1)], mismatch=True)
    variable_size = core.std.Splice([gray, core.std.BlankClip(format=vs.GRAY10, width=17, height=16, length=1)], mismatch=True)
    for invalid in (floating, variable, variable_size):
        expect_error(vs, lambda invalid=invalid: core.odin_dither.Dither(invalid), "Dither source format", "Dither")
    output = core.odin_dither.Dither(gray)
    for n in (-1, output.num_frames):
        expect_error(vs, lambda n=n: output.get_frame(n), f"Dither frame index {n}")
    print("PASS dither: exact nominal codes, seed phase, clamping, pass-through and rejection boundaries", flush=True)


def check_low_bit_levels(core, vs) -> None:
    cases = 0
    for bits in range(1, 8):
        maximum = (1 << bits) - 1
        levels = [(code * 255 + maximum // 2) // maximum for code in range(maximum + 1)]
        require(len(set(levels)) == 1 << bits, "Low-bit reference levels must be distinct")
        source_bits = ((8 + bits - 1) // bits) * bits
        source_max = (1 << source_bits) - 1
        format_id = core.query_video_format(vs.GRAY, vs.INTEGER, source_bits).id
        for scale in (0, 1):
            # A source depth divisible by the effective depth represents every
            # full-range nominal code exactly, regardless of the noise threshold.
            step = (1 << (source_bits - bits)) if scale == 0 else source_max // maximum
            source = fixture_clip(core, format_id, maximum + 1, 65, lambda p, x, y: x * step, length=1)
            expected = [[levels for _ in range(65)]]
            for simd in (0, 1):
                output = core.odin_dither.Dither(source, bits=bits, seed=4095, simd=simd, scale=scale)
                label = f"{bits}-bit nominal levels, scale={scale}, simd={simd}"
                with output.get_frame(0) as frame:
                    actual = snapshot(frame)
                    equal_pixels(actual, expected, label)
                    require(set(actual[0][0]) == set(levels), f"{label}: missing nominal levels")
                    require(actual[0][0][0] == 0 and actual[0][0][-1] == 255, f"{label}: endpoints lost")
                    require(frame.format.id == vs.GRAY8, f"{label}: expected an 8-bit container")
                cases += 1
    print(f"PASS dither: {cases} exact low-bit level checks; all 2^bits levels span 0-255 in an 8-bit container", flush=True)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
    return (left, above, upper_left)[distances.index(min(distances))]


def write_png(path: Path, width: int, height: int, pixels, bits: int = 8, alpha: bool = False) -> None:
    """Write truecolor PNG using all five row filters and big-endian 16-bit samples."""
    channels = 4 if alpha else 3
    pixel_bytes = channels * (bits // 8)
    iterator = iter(pixels)
    filtered = bytearray()
    previous = bytes(width * pixel_bytes)
    for y in range(height):
        row = bytearray()
        for _ in range(width):
            pixel = next(iterator)
            for sample in pixel:
                row.extend(sample.to_bytes(bits // 8, "big"))
        require(len(row) == len(previous), "PNG fixture has the wrong number of channels")
        filter_type = y % 5
        filtered.append(filter_type)
        for index, value in enumerate(row):
            left = row[index - pixel_bytes] if index >= pixel_bytes else 0
            above = previous[index]
            upper_left = previous[index - pixel_bytes] if index >= pixel_bytes else 0
            predictors = (0, left, above, (left + above) // 2, paeth(left, above, upper_left))
            filtered.append((value - predictors[filter_type]) & 255)
        previous = row
    header = struct.pack(">IIBBBBB", width, height, bits, 6 if alpha else 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(filtered)) + png_chunk(b"IEND", b"")
    )


def lut_values(level: int, bits: int, identity: bool):
    edge = level * level
    maximum = (1 << bits) - 1
    values = []
    for b in range(edge):
        for g in range(edge):
            for r in range(edge):
                if identity:
                    color = tuple((component * maximum + (edge - 1) // 2) // (edge - 1) for component in (r, g, b))
                else:
                    color = (
                        (r * r * 1307 + g * b * 1877 + g * 3701 + b * 997) & maximum,
                        (g * g * 1709 + r * b * 2791 + b * 2903 + r * 701) & maximum,
                        (b * b * 2003 + r * g * 3023 + r * 3307 + g * 503) & maximum,
                    )
                values.append(color)
    return values


def make_lut(name: str, level: int, bits: int, identity: bool = False, alpha: bool = False):
    values = lut_values(level, bits, identity)
    path = FIXTURES / f"{name}.png"
    pixels = ((*color, (index * 37) & ((1 << bits) - 1)) for index, color in enumerate(values)) if alpha else values
    write_png(path, level ** 3, level ** 3, pixels, bits, alpha)
    promoted = [tuple(component * (257 if bits == 8 else 1) for component in color) for color in values]
    return path, promoted


def tetrahedral(color, source_max: int, values, edge: int, strength: float):
    coordinates = [sample * (edge - 1) / source_max for sample in color]
    base = [min(math.floor(coordinate), edge - 2) for coordinate in coordinates]
    fraction = [coordinate - origin for coordinate, origin in zip(coordinates, base)]
    order = sorted(range(3), key=lambda axis: -fraction[axis])
    corners = [base.copy()]
    for axis in order:
        corner = corners[-1].copy()
        corner[axis] += 1
        corners.append(corner)
    a, b, c = (fraction[axis] for axis in order)
    weights = (1 - a, a - b, b - c, c)
    result = []
    for channel in range(3):
        lookup = sum(
            weight * values[r + edge * (g + edge * b)][channel]
            for weight, (r, g, b) in zip(weights, corners)
        )
        graded = lookup * source_max / 65535
        blended = color[channel] + strength * (graded - color[channel])
        result.append(math.floor(min(source_max, max(0, blended)) + 0.5))
    return result


def hald_oracle(planes, source_bits: int, values, edge: int, strength: float):
    result = [[[] for _ in plane] for plane in planes]
    for y in range(len(planes[0])):
        for x in range(len(planes[0][y])):
            color = [planes[channel][y][x] for channel in range(3)]
            expected = tetrahedral(color, (1 << source_bits) - 1, values, edge, strength)
            for channel, sample in enumerate(expected):
                result[channel][y].append(sample)
    return result


def check_hald_case(core, vs, path, values, level, source_bits, strength, identity=False):
    maximum = (1 << source_bits) - 1
    edge = level * level
    # These six interior colors visit each strict tetrahedral fraction ordering.
    colors = [tuple(round((1 + fraction) * maximum / (edge - 1)) for fraction in order) for order in permutations((0.2, 0.5, 0.8))]
    for cells in permutations((0, edge // 2, edge - 2)):
        colors.append(tuple(
            round((cell + fraction) * maximum / (edge - 1))
            for cell, fraction in zip(cells, (0.17, 0.49, 0.81))
        ))
    colors.extend(((0, 0, 0), (maximum, maximum, maximum), (0, maximum, 0), (maximum, 0, maximum)))
    format_id = core.query_video_format(vs.RGB, vs.INTEGER, source_bits).id
    source = fixture_clip(core, format_id, 17, 5, lambda p, x, y: colors[(x + 3 * y) % len(colors)][p])
    output = core.odin_hald.HaldCLUT(source, path=str(path), strength=strength)
    label = f"Hald {path.name}, RGB{source_bits}, strength={strength}"
    with ExitStack() as frames:
        originals = [frames.enter_context(source.get_frame(n)) for n in range(source.num_frames)]
        before = [snapshot(frame) for frame in originals]
        expected = hald_oracle(before[0], source_bits, values, edge, strength)
        pending = [output.get_frame_async(n) for n in range(source.num_frames)]
        for n, future in enumerate(pending):
            with future.result(timeout=30) as frame:
                require(frame.format.id == format_id, f"{label}: format changed")
                require(frame.props["OdinAdvanced"] == 100 + n, f"{label}: properties lost")
                equal_pixels(snapshot(frame), expected, label)
                if identity or strength == 0:
                    equal_pixels(snapshot(frame), before[n], f"{label}: identity")
            equal_pixels(snapshot(originals[n]), before[n], f"{label}: source mutated")


def test_hald(core, vs) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    cases = 0
    for png_bits, alpha in ((8, False), (16, False), (8, True), (16, True)):
        path, values = make_lut(f"nonlinear-{png_bits}-{'rgba' if alpha else 'rgb'}", 2, png_bits, alpha=alpha)
        for source_bits in (8, 10, 16):
            for strength in (0.0, 0.375, 1.0):
                check_hald_case(core, vs, path, values, 2, source_bits, strength)
                cases += 1
    for png_bits in (8, 16):
        path, values = make_lut(f"nonlinear-level-three-{png_bits}", 3, png_bits)
        for source_bits in (8, 16):
            for strength in (0.375, 1.0):
                check_hald_case(core, vs, path, values, 3, source_bits, strength)
                cases += 1
    for level in (2, 3):
        for png_bits in (8, 16):
            path, values = make_lut(f"identity-{level}-{png_bits}", level, png_bits, identity=True)
            for source_bits in range(8, 17):
                # Level 2 has exactly representable identity lattice points in both PNG depths.
                check_hald_case(core, vs, path, values, level, source_bits, 1.0, identity=(level == 2))
                cases += 1
    largest_path = FIXTURES / "level-eight.png"
    largest_values = [(10000, 20000, 30000)] * (64 ** 3)
    write_png(largest_path, 512, 512, largest_values, bits=16)
    check_hald_case(core, vs, largest_path, largest_values, 8, 16, 1.0)
    cases += 1
    print(f"PASS Hald: {cases} oracle cases; RGB/RGBA PNG8/16, all PNG filters, all six tetrahedra, strengths and source depths", flush=True)

    cached_path, values = make_lut("cached-café-then-removed", 2, 16, identity=True)
    source = fixture_clip(core, vs.RGB48, 17, 5, lambda p, x, y: (x * 3001 + p * 1709 + y * 997) & 65535)
    cached = core.odin_hald.HaldCLUT(source, path=str(cached_path))
    cached_path.unlink()
    with source.get_frame(0) as original, cached.get_frame(0) as frame:
        equal_pixels(snapshot(frame), snapshot(original), "Hald cached LUT after file removal")

    valid_path, _ = make_lut("rejection-valid", 2, 8, identity=True)
    for kind in (b"IHDR", b"IDAT", b"IEND"):
        corrupted = bytearray(valid_path.read_bytes())
        offset = 8
        while offset < len(corrupted):
            size = struct.unpack_from(">I", corrupted, offset)[0]
            if corrupted[offset + 4:offset + 8] == kind:
                corrupted[offset + 8 + size] ^= 1
                break
            offset += 12 + size
        require(offset < len(corrupted), f"PNG fixture lacks {kind!r}")
        path = FIXTURES / f"bad-crc-{kind.decode('ascii')}.png"
        path.write_bytes(corrupted)
        expect_error(
            vs, lambda path=path: core.odin_hald.HaldCLUT(source, path=str(path)),
            f"Hald {kind!r} checksum", "CRC mismatch",
        )
    bad_paths = []
    oversized_header = struct.pack(">IIBBBBB", 729, 729, 8, 2, 0, 0, 0)
    small_header = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    excess_pixels = (
        b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", small_header)
        + png_chunk(b"IDAT", zlib.compress(bytes(65536))) + png_chunk(b"IEND", b"")
    )
    oversized = (
        b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", oversized_header)
        + png_chunk(b"IDAT", zlib.compress(bytes(729 * (1 + 729 * 3)))) + png_chunk(b"IEND", b"")
    )
    for name, data in (
        ("not-png", b"not a PNG"), ("truncated", valid_path.read_bytes()[:40]),
        ("missing-end", valid_path.read_bytes()[:-12]),
        ("excess-inflated-pixels", excess_pixels), ("level-nine", oversized),
    ):
        path = FIXTURES / f"{name}.png"
        path.write_bytes(data)
        bad_paths.append(path)
    for name, width, height in (("nonsquare", 8, 9), ("not-hald", 9, 9), ("level-one", 1, 1)):
        path = FIXTURES / f"{name}.png"
        write_png(path, width, height, ((0, 0, 0) for _ in range(width * height)))
        bad_paths.append(path)
    bad_paths.append(FIXTURES / "missing.png")
    for path in bad_paths:
        expect_error(vs, lambda path=path: core.odin_hald.HaldCLUT(source, path=str(path)), f"Hald {path.name}", "HaldCLUT")
    for strength in (-0.01, 1.01, float("nan"), float("inf"), -float("inf"), "bad"):
        expect_error(vs, lambda strength=strength: core.odin_hald.HaldCLUT(source, path=str(valid_path), strength=strength), f"Hald strength={strength}")
    gray = core.std.BlankClip(format=vs.GRAY8, width=16, height=16, length=1)
    floating = core.std.BlankClip(format=vs.RGBS, width=16, height=16, length=1)
    variable = core.std.Splice([source, core.std.BlankClip(format=vs.RGB24, width=17, height=5, length=1)], mismatch=True)
    variable_size = core.std.Splice([source, core.std.BlankClip(format=vs.RGB48, width=18, height=5, length=1)], mismatch=True)
    for invalid in (gray, floating, variable, variable_size):
        expect_error(vs, lambda invalid=invalid: core.odin_hald.HaldCLUT(invalid, path=str(valid_path)), "Hald source format", "HaldCLUT")
    print("PASS Hald: cached data, file/format/parameter failures, properties and retained source frames", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--runtime", type=Path, help="Existing VapourSynth Python module parent")
    parser.add_argument("--only", choices=("dither", "haldlut"), help="Build and check only one plugin")
    args = parser.parse_args()
    vs = runtime_module(args.runtime)
    print(f"VapourSynth {vs.__version__}; API {vs.__api_version__}; module {vs.__file__}", flush=True)
    core = vs.core
    core.num_threads = 4
    selected = (args.only,) if args.only else ("dither", "haldlut")
    for name in selected:
        path = build_plugin(args.odin, name)
        core.std.LoadPlugin(path=str(path))
        if name == "dither":
            test_dither(core, vs)
        else:
            test_hald(core, vs)
    print("All advanced example checks passed.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
