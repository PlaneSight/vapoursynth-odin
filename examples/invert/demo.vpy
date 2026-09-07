# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preview an actual frame-processing filter against its RGB8 source."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview_support import clip_from_rgb, color_scene, load_plugin, rgb16_to_rgb8, set_output

import vapoursynth as vs


load_plugin("invert", "odin_invert")
source = rgb16_to_rgb8(clip_from_rgb(color_scene()))
processed = vs.core.odin_invert.Invert(source)

set_output(vs.core.std.StackHorizontal([source, processed]), 0, "Invert: source | output")
set_output(source, 1, "Original synthetic scene")
set_output(processed, 2, "Inverted RGB8 scene")
DOCUMENTATION_OUTPUTS = {1: "invert-source", 2: "invert-output"}
