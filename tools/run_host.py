#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run an Odin host example with the core library in the active Python environment."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.examples import HOST_NAMES, ROOT, build_examples



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=HOST_NAMES)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    args = parser.parse_args()
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
    try:
        artifacts = build_examples([args.example], odin=args.odin)
        command = [str(artifacts[args.example]), str(library)]
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Host example failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
