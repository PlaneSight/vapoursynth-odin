#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Generate reproducible identity and cinematic Hald PNGs using only Python's stdlib."""

import argparse
from pathlib import Path
import struct
import zlib


ROOT = Path(__file__).resolve().parent


def identity(red: float, green: float, blue: float) -> tuple[float, float, float]:
    return red, green, blue


def cinematic(red: float, green: float, blue: float) -> tuple[float, float, float]:
    """A modest S-curve, lower saturation, cool shadows, and warm highlights."""
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    color = [luminance + 0.88 * (channel - luminance) for channel in (red, green, blue)]
    color = [0.7 * channel + 0.3 * channel * channel * (3 - 2 * channel) for channel in color]
    shadows = (1 - luminance) ** 2
    highlights = luminance**2
    color[0] += 0.045 * highlights - 0.012 * shadows
    color[1] += 0.008 * highlights + 0.006 * shadows
    color[2] += 0.035 * shadows - 0.025 * highlights
    return tuple(max(0.0, min(1.0, channel)) for channel in color)


LOOKS = {"identity": identity, "cinematic": cinematic}


def png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def write_hald(path: Path, *, level: int = 4, bits: int = 16, look: str = "identity") -> None:
    """Write RGB PNG with red varying fastest, then green, then blue."""
    if not 2 <= level <= 8:
        raise ValueError("level must be between 2 and 8")
    if bits not in (8, 16):
        raise ValueError("bits must be 8 or 16")
    transform = LOOKS[look]
    edge = level * level
    side = level**3
    maximum = (1 << bits) - 1
    rows = bytearray()
    for y in range(side):
        rows.append(0)  # PNG filter type: None.
        for x in range(side):
            index = y * side + x
            red = (index % edge) / (edge - 1)
            green = ((index // edge) % edge) / (edge - 1)
            blue = (index // (edge * edge)) / (edge - 1)
            samples = [int(channel * maximum + 0.5) for channel in transform(red, green, blue)]
            rows.extend(struct.pack(">HHH", *samples) if bits == 16 else bytes(samples))
    header = struct.pack(">IIBBBBB", side, side, bits, 2, 0, 0, 0)
    encoded = b"\x89PNG\r\n\x1a\n"
    encoded += png_chunk(b"IHDR", header)
    encoded += png_chunk(b"IDAT", zlib.compress(rows, level=9))
    encoded += png_chunk(b"IEND", b"")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".build" / "haldlut-luts")
    parser.add_argument("--level", type=int, choices=range(2, 9), default=4)
    parser.add_argument("--bits", type=int, choices=(8, 16), default=16)
    parser.add_argument("--look", choices=(*LOOKS, "all"), default="all")
    args = parser.parse_args()
    for look in LOOKS if args.look == "all" else (args.look,):
        path = args.output / f"{look}.png"
        write_hald(path, level=args.level, bits=args.bits, look=look)
        print(f"{path}: level {args.level}, {args.level ** 3} x {args.level ** 3}, RGB{args.bits}")


if __name__ == "__main__":
    main()
