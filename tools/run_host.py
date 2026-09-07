#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run an Odin host example with the core library in the active Python environment."""

import argparse
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.examples import HOST_NAMES, ROOT, build_examples
from tools.native_build import core_library



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=HOST_NAMES)
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    args = parser.parse_args()
    try:
        import vapoursynth
    except ImportError as error:
        parser.error(f"Cannot import VapourSynth; run with 'uv run'. {error}")

    try:
        library = core_library(Path(vapoursynth.__file__).resolve().parent)
    except RuntimeError as error:
        parser.error(str(error))

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
