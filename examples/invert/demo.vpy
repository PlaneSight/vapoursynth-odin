# SPDX-License-Identifier: LGPL-2.1-or-later
from pathlib import Path

import vapoursynth as vs

plugin = Path(__file__).resolve().parents[2] / ".build" / "odin_invert.dll"
vs.core.std.LoadPlugin(path=str(plugin))

source = vs.core.std.BlankClip(
    width=640, height=360, format=vs.RGB24, color=[32, 96, 160], length=24
)
vs.core.odin_invert.Invert(source).set_output()
