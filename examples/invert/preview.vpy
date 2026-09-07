"""Preview an actual frame-processing filter against its RGB8 source."""

from pathlib import Path
import runpy
from types import SimpleNamespace

preview = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name("preview_support.py"))))

import vapoursynth as vs


preview.load_plugin("invert", "odin_invert")
source = preview.rgb16_to_rgb8(preview.clip_from_rgb(preview.color_scene()))
processed = vs.core.odin_invert.Invert(source)

preview.set_output(vs.core.std.StackHorizontal([source, processed]), 0, "Invert: source | output")
preview.set_output(source, 1, "Original synthetic scene")
preview.set_output(processed, 2, "Inverted RGB8 scene")
DOCUMENTATION_OUTPUTS = {1: "invert-source", 2: "invert-output"}
