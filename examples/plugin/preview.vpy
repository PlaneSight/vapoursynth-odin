# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preview the native identity plugin; source and returned pixels should match."""

from pathlib import Path
import runpy
from types import SimpleNamespace

preview = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name("preview_support.py"))))

import vapoursynth as vs


preview.load_plugin("plugin", "odin_example")
source = preview.rgb16_to_rgb8(preview.clip_from_rgb(preview.color_scene()))
processed = vs.core.odin_example.Identity(source)

preview.set_output(vs.core.std.StackHorizontal([source, processed]), 0, "Identity: source | output")
preview.set_output(source, 1, "Original synthetic scene")
preview.set_output(processed, 2, "Identity output")
DOCUMENTATION_OUTPUTS = {1: "identity-source", 2: "identity-output"}
