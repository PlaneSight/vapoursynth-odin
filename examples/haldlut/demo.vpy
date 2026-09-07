# SPDX-License-Identifier: LGPL-2.1-or-later
"""Generate a cinematic Hald LUT, then preview its native tetrahedral interpolation."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview_support import (
    cinematic_lut, clip_from_rgb, color_scene, load_plugin, rgb16_to_rgb8, set_output,
)

import vapoursynth as vs


load_plugin("haldlut", "odin_hald")
source = clip_from_rgb(color_scene())
graded = vs.core.odin_hald.HaldCLUT(source, path=str(cinematic_lut()), strength=1.0)

# Both display outputs use the same exact full-range RGB16-to-RGB8 rounding.
original = rgb16_to_rgb8(source)
processed = rgb16_to_rgb8(graded)
set_output(vs.core.std.StackHorizontal([original, processed]), 0, "Hald CLUT: source | cinematic")
set_output(original, 1, "Original synthetic scene")
set_output(processed, 2, "Cinematic LUT (level 4, strength 1)")
DOCUMENTATION_OUTPUTS = {1: "hald-source", 2: "hald-cinematic"}
