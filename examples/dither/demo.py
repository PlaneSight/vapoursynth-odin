#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Create an integer ramp and verify the dither plugin's two implementations."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import vapoursynth as vs


def default_plugin() -> Path:
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    return Path(__file__).resolve().parents[2] / ".build" / "examples" / f"dither{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, default=default_plugin())
    args = parser.parse_args()
    vs.core.std.LoadPlugin(path=str(args.plugin.resolve()))

    blank = vs.core.std.BlankClip(width=1024, height=128, format=vs.GRAY16, length=1)

    def fill(n, f):
        output = f.copy()
        pixels = output[0]
        for y in range(output.height):
            for x in range(output.width):
                pixels[y, x] = 65535 * x // (output.width - 1)
        output.props["_Range"] = 1
        return output

    source = vs.core.std.ModifyFrame(blank, clips=blank, selector=fill)
    scalar = vs.core.odin_dither.Dither(source, bits=8, scale=1, simd=0)
    vector = vs.core.odin_dither.Dither(source, bits=8, scale=1, simd=1)
    with scalar.get_frame(0) as expected, vector.get_frame(0) as actual:
        if expected[0].tobytes() != actual[0].tobytes():
            raise RuntimeError("Scalar and SIMD outputs differ")
        if actual[0][0, 0] != 0 or actual[0][0, actual.width - 1] != 255:
            raise RuntimeError("Full-range endpoints were not preserved")
        if actual.props["_Range"] != 1:
            raise RuntimeError("Frame properties were not preserved")
        print(f"Dither: {actual.width} x {actual.height} Gray16 -> Gray8")
        print("Scalar/SIMD parity, full-range endpoints, and frame properties verified.")


if __name__ == "__main__":
    main()
