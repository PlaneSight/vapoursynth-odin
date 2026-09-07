# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the plugin and run generate.py before loading this script in a host."""

from pathlib import Path
import sys

import vapoursynth as vs

root = Path(__file__).resolve().parents[2]
suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(root / ".build" / f"odin_hald{suffix}"))

blank = vs.core.std.BlankClip(width=640, height=360, format=vs.RGB24, length=48)


def gradient(n, f):
    frame = f.copy()
    for y in range(frame.height):
        for x in range(frame.width):
            frame[0][y, x] = x * 255 // (frame.width - 1)
            frame[1][y, x] = y * 255 // (frame.height - 1)
            frame[2][y, x] = (x + y) * 255 // (frame.width + frame.height - 2)
    return frame


source = vs.core.std.ModifyFrame(blank, clips=blank, selector=gradient)
graded = vs.core.odin_hald.HaldCLUT(
    source, path=str(root / ".build" / "haldlut-luts" / "cinematic.png"), strength=0.8
)
vs.core.std.StackHorizontal([source, graded]).set_output()
