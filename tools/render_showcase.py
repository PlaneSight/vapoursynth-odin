#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the plugins and export the actual preview scripts' documentation outputs."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
import sys
import tempfile
import zlib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.examples import EXAMPLES, PLUGIN_NAMES, ROOT, build_examples


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload)
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def write_rgb_frame(frame, path: Path) -> None:
    """Write active RGB8 samples; VapourSynth row padding never enters the PNG."""
    import numpy as np
    import vapoursynth as vs

    if frame.format.id != vs.RGB24:
        raise ValueError(f"Documentation output must be RGB24, got {frame.format.name}")
    pixels = np.stack([np.asarray(frame[plane]) for plane in range(3)], axis=2)
    scanlines = b"".join(b"\0" + row.tobytes() for row in pixels)
    header = struct.pack(">IIBBBBB", frame.width, frame.height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + png_chunk(b"IEND", b"")
    )


def render_script(name: str, destination: Path) -> None:
    """Run one script in its own process and read its registered output nodes."""
    import vapoursynth as vs

    script = EXAMPLES[name] / "preview.vpy"
    vs.clear_outputs()
    try:
        variables = runpy.run_path(str(script))
        exports = variables.get("DOCUMENTATION_OUTPUTS")
        if not isinstance(exports, dict) or not exports:
            raise ValueError(f"{script}: DOCUMENTATION_OUTPUTS must be a nonempty index-to-name mapping")
        outputs = vs.get_outputs()
        records = []
        used_names = set()
        for index, basename in exports.items():
            if type(index) is not int or index < 0 or index not in outputs:
                raise ValueError(f"{script}: documentation output index {index!r} is not registered")
            if not isinstance(basename, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", basename):
                raise ValueError(f"{script}: invalid documentation image name {basename!r}")
            if basename in used_names:
                raise ValueError(f"{script}: duplicate image name {basename}")
            used_names.add(basename)
            output = outputs[index]
            if not isinstance(output, vs.VideoOutputTuple):
                raise ValueError(f"{script}: output {index} must be video")
            path = destination / f"{basename}.png"
            with output.clip.get_frame(0) as frame:
                write_rgb_frame(frame, path)
                records.append({
                    "output": index, "image": path.name, "frame": 0,
                    "width": frame.width, "height": frame.height,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
        metadata = {
            "script": script.relative_to(ROOT).as_posix(),
            "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "runtime": str(vs.__version__), "images": records,
        }
        (destination / f"{name}.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(f"Rendered {script.relative_to(ROOT)}: {len(records)} registered outputs", flush=True)
    finally:
        vs.clear_outputs()


def render_all(destination: Path) -> None:
    """Publish a complete set only after all isolated render processes succeed."""
    work = ROOT / ".build"
    work.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="showcase-", dir=work) as temporary:
        staging = Path(temporary)
        records = []
        filenames = set()
        for name in PLUGIN_NAMES:
            subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--script", name, "--output", str(staging)],
                cwd=ROOT, check=True, timeout=120,
            )
            record = json.loads((staging / f"{name}.json").read_text(encoding="utf-8"))
            for entry in record["images"]:
                filename = entry["image"]
                if filename in filenames:
                    raise ValueError(f"Preview scripts export the same image name: {filename}")
                filenames.add(filename)
            records.append(record)
        manifest = staging / "showcase.json"
        manifest.write_text(json.dumps({"examples": records}, indent=2) + "\n", encoding="utf-8")
        for filename in sorted(filenames):
            (staging / filename).replace(destination / filename)
        manifest.replace(destination / manifest.name)
    print(f"Exported {len(filenames)} images from {len(records)} preview scripts to {destination}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".build" / "showcase")
    parser.add_argument("--no-build", action="store_true", help="Use plugins already built by tools/examples.py")
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--script", choices=PLUGIN_NAMES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        destination = args.output.resolve()
        if args.script is not None:
            render_script(args.script, destination)
            return 0
        if not args.no_build:
            build_examples(PLUGIN_NAMES, odin=args.odin)
        render_all(destination)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Image generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
