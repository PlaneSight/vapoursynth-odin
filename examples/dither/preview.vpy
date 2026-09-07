"""Inspect eight-bit rounding noise and one-, two-, and four-bit color quantization."""

from pathlib import Path
import runpy
from types import SimpleNamespace

preview = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name("preview_support.py"))))

import numpy as np
import vapoursynth as vs


preview.load_plugin("dither", "odin_dither")
pixels = preview.dither_ramp()
source = preview.clip_from_rgb(pixels)
dithered = vs.core.odin_dither.Dither(source, bits=8, scale=0, seed=0, simd=1)
rounded = preview.clip_from_rgb(((pixels.astype(np.uint32) + 128) >> 8).astype(np.uint8))

# Identical 20x display gain exposes banding. Raw, unamplified clips remain available.
baseline = preview.quantization_display(rounded)
processed = preview.quantization_display(dithered)
preview.set_output(vs.core.std.StackHorizontal([baseline, processed]), 0, "20x gain: rounding | dither")
preview.set_output(baseline, 1, "Nearest rounding (20x display gain)")
preview.set_output(processed, 2, "Blue-noise dither (20x display gain)")
preview.set_output(source, 3, "Original RGB16 ramp (no display gain)")
preview.set_output(dithered, 4, "Dithered RGB8 ramp (no display gain)")
DOCUMENTATION_OUTPUTS = {1: "dither-rounding", 2: "dither-blue-noise"}


scene = preview.color_scene()
scene_source = preview.clip_from_rgb(scene)
preview.set_output(scene_source, 5, "Original RGB16 color scene")
for index, bits in enumerate((1, 2, 4)):
    maximum = (1 << bits) - 1
    quantized = (scene.astype(np.uint32) * maximum + 32767) // 65535
    expanded = ((quantized * 255 + maximum // 2) // maximum).astype(np.uint8)
    nearest = preview.clip_from_rgb(expanded)
    blue_noise = vs.core.odin_dither.Dither(
        scene_source, bits=bits, scale=1, seed=0, simd=1,
    )
    first = 6 + 3 * index
    preview.set_output(nearest, first, f"{bits}-bit nearest rounding in RGB8")
    preview.set_output(blue_noise, first + 1, f"{bits}-bit blue-noise dither in RGB8")
    preview.set_output(
        vs.core.std.StackHorizontal([nearest, blue_noise]), first + 2,
        f"{bits}-bit RGB8: rounding | dither",
    )
    DOCUMENTATION_OUTPUTS[first] = f"dither-{bits}bit-rounding"
    DOCUMENTATION_OUTPUTS[first + 1] = f"dither-{bits}bit-blue-noise"
