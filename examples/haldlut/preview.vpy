"""Generate a cinematic Hald LUT, then preview its native tetrahedral interpolation."""

from pathlib import Path
import runpy
from types import SimpleNamespace

preview = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name("preview_support.py"))))

import vapoursynth as vs


preview.load_plugin("haldlut", "odin_hald")
source = preview.clip_from_rgb(preview.color_scene())
graded = vs.core.odin_hald.HaldCLUT(source, path=str(preview.cinematic_lut()), strength=1.0)

# Both display outputs use the same exact full-range RGB16-to-RGB8 rounding.
original = preview.rgb16_to_rgb8(source)
processed = preview.rgb16_to_rgb8(graded)
preview.set_output(vs.core.std.StackHorizontal([original, processed]), 0, "Hald CLUT: source | cinematic")
preview.set_output(original, 1, "Original synthetic scene")
preview.set_output(processed, 2, "Cinematic LUT (level 4, strength 1)")
DOCUMENTATION_OUTPUTS = {1: "hald-source", 2: "hald-cinematic"}
