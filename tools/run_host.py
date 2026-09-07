#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run an Odin host example with the core library in the active Python environment."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
HOSTS = ("core_info", "properties", "easy_host", "host")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=HOSTS)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    args = parser.parse_args()
    odin = shutil.which(args.odin)
    if odin is None:
        parser.error(f"Cannot find Odin compiler: {args.odin}")
    try:
        import vapoursynth
    except ImportError as error:
        parser.error(f"Cannot import VapourSynth; run with 'uv run'. {error}")

    package = Path(vapoursynth.__file__).resolve().parent
    names = {
        "win32": ("libvapoursynth.dll",),
        "darwin": ("libvapoursynth.4.dylib", "libvapoursynth.dylib"),
    }.get(sys.platform, ("libvapoursynth.so.4", "libvapoursynth.so"))
    library = next((package / name for name in names if (package / name).is_file()), None)
    if library is None:
        parser.error(f"The VapourSynth package at {package} does not contain a core library")

    print(f"Core library: {library}", flush=True)
    command = [odin, "run", str(ROOT / "examples" / args.example), "-vet", "--", str(library)]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
