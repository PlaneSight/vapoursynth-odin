# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compare native quantizers, RGB correlation, and moving threshold patterns."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "examples"))
from preview_support import clip_from_rgb, color_scene, load_plugin, set_output

import numpy as np
import vapoursynth as vs


load_plugin("dither_plus", "odin_dither_plus")
source = clip_from_rgb(color_scene())
set_output(source, 0, "Original RGB16 color scene")

DOCUMENTATION_OUTPUTS = {}
methods = (
    ("none", "Nearest rounding"),
    ("bayer", "Bayer 8 x 8"),
    ("blue_noise", "Blue noise"),
    ("floyd_steinberg", "Serpentine Floyd-Steinberg"),
    ("sierra_lite", "Serpentine Sierra Lite"),
)
for index, (mode, label) in enumerate(methods, start=1):
    filtered = vs.core.odin_dither_plus.Dither(
        source, bits=2, scale=1, mode=mode, corplane=1,
    )
    set_output(filtered, index, f"2-bit RGB8: {label}")
    DOCUMENTATION_OUTPUTS[index] = f"dither-plus-{mode.replace('_', '-')}"


neutral = np.broadcast_to(
    np.linspace(0, 65535, 768).astype(np.uint16)[None, :, None], (192, 768, 3),
).copy()
neutral[48:144] = 32768
neutral_source = clip_from_rgb(neutral)
for index, correlated in ((6, 0), (7, 1)):
    filtered = vs.core.odin_dither_plus.Dither(
        neutral_source, bits=2, scale=1, mode="blue_noise", corplane=correlated,
    )
    label = "Shared RGB thresholds" if correlated else "Independent RGB thresholds"
    set_output(filtered, index, f"2-bit neutral patch and ramp: {label}")
    suffix = "correlated" if correlated else "independent"
    DOCUMENTATION_OUTPUTS[index] = f"dither-plus-neutral-{suffix}"


def fade_and_pan(n, f):
    output = f.copy()
    gain = 0.9 + 0.1 * np.cos(2 * np.pi * n / source.num_frames)
    for plane in range(3):
        shifted = np.roll(np.asarray(f[plane]), n * 4, axis=1)
        values = np.floor(shifted.astype(np.float64) * gain + 0.5).astype(np.uint16)
        np.copyto(np.asarray(output[plane]), values)
    return output


animated = vs.core.std.ModifyFrame(source, clips=source, selector=fade_and_pan)
static_mask = vs.core.odin_dither_plus.Dither(
    animated, bits=2, scale=1, mode="blue_noise", corplane=1, dyn=0,
)
moving_mask = vs.core.odin_dither_plus.Dither(
    animated, bits=2, scale=1, mode="blue_noise", corplane=1, dyn=1,
)
set_output(animated, 8, "Original RGB16 fade and pan")
set_output(static_mask, 9, "2-bit animation: static blue-noise mask")
set_output(moving_mask, 10, "2-bit animation: moving blue-noise mask")
set_output(
    vs.core.std.StackHorizontal([static_mask, moving_mask]), 11,
    "2-bit animation: static mask | moving mask",
)
