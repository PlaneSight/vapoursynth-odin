#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Render reproducible synthetic comparisons using the actual advanced plugins.

Run `uv run tests/advanced.py` first to build the native plugins, then:
    uv run tools/render_showcase.py
Generated images belong in .build/showcase unless --output selects another directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import struct
import sys
import zlib

import numpy as np
import vapoursynth as vs


ROOT = Path(__file__).resolve().parent.parent


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def save_rgb(path: Path, pixels: np.ndarray) -> None:
    height, width, channels = pixels.shape
    if channels != 3 or pixels.dtype != np.uint8:
        raise ValueError("PNG output must be an RGB8 array")
    scanlines = b"".join(b"\0" + row.tobytes() for row in pixels)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(scanlines, level=9)) + chunk(b"IEND", b"")
    )


def clip_from_rgb16(pixels: np.ndarray):
    height, width, _ = pixels.shape
    blank = vs.core.std.BlankClip(format=vs.RGB48, width=width, height=height, length=1)

    def fill(n, f):
        output = f.copy()
        for plane in range(3):
            np.copyto(np.asarray(output[plane]), pixels[:, :, plane])
        return output

    return vs.core.std.ModifyFrame(blank, clips=blank, selector=fill)


def rgb16_snapshot(clip) -> np.ndarray:
    with clip.get_frame(0) as frame:
        return np.stack([np.asarray(frame[p]) for p in range(3)], axis=2)


def color_scene() -> np.ndarray:
    width, height = 768, 320
    y, x = np.mgrid[0:height, 0:width].astype(np.float64)
    x /= width - 1
    y /= height - 1
    scene = np.empty((height, width, 3), dtype=np.float64)
    for channel, base in enumerate((0.15, 0.19, 0.25)):
        scene[:, :, channel] = base + 0.12 * x + 0.04 * y
    light = np.array([-0.4, -0.5, 0.7681145748])
    for center, color in ((0.18, (0.85, 0.26, 0.11)), (0.5, (0.17, 0.72, 0.33)), (0.82, (0.19, 0.38, 0.9))):
        nx = (x - center) * width / 96
        ny = (y - 0.40) * height / 96
        radius = nx * nx + ny * ny
        mask = radius <= 1
        nz = np.sqrt(np.maximum(0, 1 - radius))
        diffuse = np.maximum(0, nx * light[0] + ny * light[1] + nz * light[2])
        reflected = np.maximum(0, 2 * nz * diffuse - light[2])
        for channel in range(3):
            shaded = color[channel] * (0.16 + 0.75 * diffuse) + 0.30 * reflected**18
            scene[:, :, channel][mask] = shaded[mask]
    ramp = y >= 0.82
    for channel in range(3):
        scene[:, :, channel][ramp] = x[ramp]
    return np.floor(np.clip(scene, 0, 1) * 65535 + 0.5).astype(np.uint16)


def render_dither(destination: Path) -> None:
    width, height = 768, 192
    row = np.linspace(100 * 256, 112 * 256 - 1, width).astype(np.uint16)
    ramp = np.broadcast_to(row, (height, width)).copy()
    source = clip_from_rgb16(np.repeat(ramp[:, :, None], 3, axis=2))
    result = vs.core.odin_dither.Dither(source, bits=8, scale=0, seed=0)
    rounded = ((ramp.astype(np.uint32) + 128) >> 8).astype(np.uint8)
    with result.get_frame(0) as frame:
        dithered = np.asarray(frame[0]).copy()
    # Display gain makes quantization steps visible; both outputs receive the same transform.
    for name, pixels in (("rounding", rounded), ("blue-noise", dithered)):
        display = np.clip((pixels.astype(np.int32) - 100) * 20 + 8, 0, 255).astype(np.uint8)
        save_rgb(destination / f"dither-{name}.png", np.repeat(display[:, :, None], 3, axis=2))


def render_hald(destination: Path, work: Path) -> None:
    generator = runpy.run_path(str(ROOT / "examples" / "haldlut" / "generate.py"))
    lut = work / "cinematic.png"
    generator["write_hald"](lut, level=4, bits=16, look="cinematic")
    source_pixels = color_scene()
    source = clip_from_rgb16(source_pixels)
    graded = vs.core.odin_hald.HaldCLUT(source, path=str(lut), strength=1.0)
    for name, pixels in (("source", source_pixels), ("cinematic", rgb16_snapshot(graded))):
        display = ((pixels.astype(np.uint32) + 128) // 257).astype(np.uint8)
        save_rgb(destination / f"hald-{name}.png", display)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".build" / "showcase")
    parser.add_argument("--plugins", type=Path, default=ROOT / ".build" / "advanced")
    args = parser.parse_args()
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    for name in ("dither", "haldlut"):
        path = args.plugins / f"{name}{suffix}"
        if not path.is_file():
            parser.error(f"Missing plugin {path}; run 'uv run tests/advanced.py' first")
        vs.core.std.LoadPlugin(path=str(path.resolve()))
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    work = ROOT / ".build" / "showcase"
    work.mkdir(parents=True, exist_ok=True)
    render_dither(destination)
    render_hald(destination, work)
    metadata = {
        "runtime": str(vs.__version__),
        "dither": "16-to-8-bit, scale=0, seed=0; shared display transform (sample-100)*20+8",
        "hald": "Synthetic RGB16 scene, level-4 RGB16 cinematic LUT, strength=1",
        "images": sorted(path.name for path in destination.glob("*.png")),
    }
    (work / "showcase.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered four comparisons to {destination} using VapourSynth {vs.__version__}")


if __name__ == "__main__":
    main()
