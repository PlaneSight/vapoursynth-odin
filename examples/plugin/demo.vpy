# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preview the native identity plugin; source and returned pixels should match."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview_support import clip_from_rgb, color_scene, load_plugin, rgb16_to_rgb8, set_output

import vapoursynth as vs


load_plugin("plugin", "odin_example")
source = rgb16_to_rgb8(clip_from_rgb(color_scene()))
processed = vs.core.odin_example.Identity(source)

set_output(vs.core.std.StackHorizontal([source, processed]), 0, "Identity: source | output")
set_output(source, 1, "Original synthetic scene")
set_output(processed, 2, "Identity output")
DOCUMENTATION_OUTPUTS = {1: "identity-source", 2: "identity-output"}
