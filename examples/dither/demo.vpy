# SPDX-License-Identifier: LGPL-2.1-or-later
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
plugin = Path(__file__).resolve().parents[2] / ".build" / f"odin_dither{suffix}"
vs.core.std.LoadPlugin(path=str(plugin))

blank = vs.core.std.BlankClip(width=512, height=256, format=vs.GRAY16, length=1)


def ramp(n, f):
    output = f.copy()
    pixels = output[0]
    for y in range(output.height):
        for x in range(output.width):
            pixels[y, x] = 65535 * x // (output.width - 1)
    output.props["_Range"] = 1
    return output


source = vs.core.std.ModifyFrame(blank, clips=blank, selector=ramp)
dithered = vs.core.odin_dither.Dither(source, bits=8, scale=1)


def nearest(n, f):
    output = f.copy()
    pixels = output[0]
    for y in range(output.height):
        for x in range(output.width):
            sample = 65535 * x // (output.width - 1)
            pixels[y, x] = (sample * 255 + 32767) // 65535
    output.props["_Range"] = 1
    return output


undithered_blank = vs.core.std.BlankClip(width=512, height=256, format=vs.GRAY8, length=1)
undithered = vs.core.std.ModifyFrame(undithered_blank, clips=undithered_blank, selector=nearest)
vs.core.std.StackHorizontal([undithered, dithered]).set_output()
