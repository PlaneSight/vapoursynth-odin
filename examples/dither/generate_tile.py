#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Reproduce the checked-in 64 x 64 ranked blue-noise tile.

Generator-only requirements: Python 3.14+ and NumPy. The Odin plugin needs
neither Python nor NumPy: it uses the generated constant directly.

This is an original implementation of Robert Ulichney's void-and-cluster
algorithm, "The void-and-cluster method for dither array generation", SPIE
1913, 332-343 (1993), DOI: 10.1117/12.152707.
Original paper: https://cv.ulichney.com/papers/1993-void-cluster.pdf
Filter discussion: https://cv.ulichney.com/papers/1994-filter-design.pdf

Start with 410 randomly distributed occupied pixels (approximately 10%).
Relax the pattern by moving the tightest cluster's pixel to the largest void
until no move reduces the Gaussian interaction energy. Assign descending
ranks by removing clusters from a copy of this seed. Restore the seed and
assign ascending ranks by filling voids to 50% occupancy. Above 50%, regard
the remaining holes as the minority pattern and remove their clusters.

The isotropic Gaussian uses sigma 1.5 pixels and toroidal distances, so its
neighborhood crosses tile boundaries. Its weights are rounded to 40 fractional
bits using Decimal, allowing exact int64 energy updates and repeatable ties.
This quantization discards weights below half a unit, far below the kernel's
peak; no additional spatial cutoff is applied. SHA-256 orders pixels from a
fixed seed, avoiding dependence on a random library's permutation algorithm.
Neither generation nor ranking uses FFT or floating-point accumulation.

Usage from this project directory:
    uv run generate_tile.py
    uv run generate_tile.py --check --metrics

The spectral metric is the mean non-DC power below 1/8 cycle per pixel divided
by mean power over all non-DC bins. A white permutation has expected value 1;
lower values indicate suppressed low spatial frequencies. The report compares
each binary threshold to 16 independent, deterministic white permutations.
This metric checks low-frequency suppression, not every aspect of isotropy or
the absence of a visible 64-pixel repeat in every image.
"""

import argparse
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
from pathlib import Path

import numpy as np


TILE_SIZE = 64
TILE_AREA = TILE_SIZE * TILE_SIZE
INITIAL_PIXELS = 410
SEED = 20260907
KERNEL_SCALE = 1 << 40
WHITE_TRIALS = 16
THRESHOLDS = (256, 512, 1024, 2048, 3072, 3584, 3840)


def pixel_order(seed: int) -> np.ndarray:
    """Return a reproducible pseudorandom ordering without an external PRNG."""
    indices = sorted(
        range(TILE_AREA),
        key=lambda index: hashlib.sha256(f"{seed}:{index}".encode("ascii")).digest(),
    )
    return np.asarray(indices, dtype=np.intp)


def gaussian_kernel() -> np.ndarray:
    """Quantize exp(-distance_squared / (2 * 1.5**2)) on the torus."""
    kernel = np.empty((TILE_SIZE, TILE_SIZE), dtype=np.int64)
    weights: dict[int, int] = {}
    with localcontext() as context:
        context.prec = 60
        for y in range(TILE_SIZE):
            dy = min(y, TILE_SIZE - y)
            for x in range(TILE_SIZE):
                dx = min(x, TILE_SIZE - x)
                distance_squared = dx * dx + dy * dy
                if distance_squared not in weights:
                    exponent = -Decimal(2 * distance_squared) / Decimal(9)
                    weight = exponent.exp() * KERNEL_SCALE
                    weights[distance_squared] = int(
                        weight.to_integral_value(rounding=ROUND_HALF_EVEN)
                    )
                kernel[y, x] = weights[distance_squared]
    if sum(int(weight) for weight in kernel.flat) > np.iinfo(np.int64).max:
        raise ValueError("The Gaussian energy does not fit in int64.")
    return kernel


def contribution(kernel: np.ndarray, index: int) -> np.ndarray:
    y, x = divmod(index, TILE_SIZE)
    return np.roll(kernel, (y, x), axis=(0, 1))


def cluster_pixel(pattern: np.ndarray, energy: np.ndarray, order: np.ndarray) -> int:
    occupied = pattern.ravel()[order]
    if not np.any(occupied):
        raise ValueError("Cannot select a cluster from an empty pattern.")
    candidates = np.where(occupied, energy.ravel()[order], -1)
    return int(order[np.argmax(candidates)])


def void_pixel(pattern: np.ndarray, energy: np.ndarray, order: np.ndarray) -> int:
    empty = ~pattern.ravel()[order]
    if not np.any(empty):
        raise ValueError("Cannot select a void from a full pattern.")
    candidates = np.where(empty, energy.ravel()[order], np.iinfo(np.int64).max)
    return int(order[np.argmin(candidates)])


def remove_pixel(pattern: np.ndarray, energy: np.ndarray, kernel: np.ndarray, index: int) -> None:
    if not pattern.flat[index]:
        raise ValueError("Cannot remove an unoccupied pixel.")
    pattern.flat[index] = False
    energy -= contribution(kernel, index)


def add_pixel(pattern: np.ndarray, energy: np.ndarray, kernel: np.ndarray, index: int) -> None:
    if pattern.flat[index]:
        raise ValueError("Cannot add an occupied pixel.")
    pattern.flat[index] = True
    energy += contribution(kernel, index)


def relaxed_seed(kernel: np.ndarray, order: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    pattern = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.bool_)
    energy = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.int64)
    for index in pixel_order(SEED)[:INITIAL_PIXELS]:
        add_pixel(pattern, energy, kernel, int(index))

    for swaps in range(TILE_AREA * 16):
        cluster = cluster_pixel(pattern, energy, order)
        remove_pixel(pattern, energy, kernel, cluster)
        void = void_pixel(pattern, energy, order)
        if energy.flat[void] >= energy.flat[cluster]:
            # Restore the removed pixel when no strictly improving move exists.
            add_pixel(pattern, energy, kernel, cluster)
            return pattern, energy, swaps
        add_pixel(pattern, energy, kernel, void)
    raise RuntimeError("Seed relaxation did not converge within the swap limit.")


def validate_ranks(ranks: np.ndarray) -> None:
    if ranks.shape != (TILE_SIZE, TILE_SIZE):
        raise ValueError("The rank array has the wrong dimensions.")
    if not np.array_equal(np.sort(ranks, axis=None), np.arange(TILE_AREA)):
        raise ValueError("The tile must contain each rank from 0 through 4095 once.")


def generate_tile() -> tuple[np.ndarray, int]:
    kernel = gaussian_kernel()
    order = pixel_order(SEED + 1)
    seed, seed_energy, swaps = relaxed_seed(kernel, order)
    ranks = np.full((TILE_SIZE, TILE_SIZE), -1, dtype=np.int64)

    pattern, energy = seed.copy(), seed_energy.copy()
    for rank in range(INITIAL_PIXELS - 1, -1, -1):
        index = cluster_pixel(pattern, energy, order)
        remove_pixel(pattern, energy, kernel, index)
        ranks.flat[index] = rank

    pattern, energy = seed.copy(), seed_energy.copy()
    for rank in range(INITIAL_PIXELS, TILE_AREA // 2):
        index = void_pixel(pattern, energy, order)
        add_pixel(pattern, energy, kernel, index)
        ranks.flat[index] = rank

    # Track holes explicitly above 50%, with their own exact Gaussian energy.
    pattern = ~pattern
    energy = int(kernel.sum()) - energy
    for rank in range(TILE_AREA // 2, TILE_AREA):
        index = cluster_pixel(pattern, energy, order)
        remove_pixel(pattern, energy, kernel, index)
        ranks.flat[index] = rank

    validate_ranks(ranks)
    return ranks.astype(np.uint16), swaps


def rank_digest(ranks: np.ndarray) -> str:
    return hashlib.sha256(ranks.astype("<u2").tobytes(order="C")).hexdigest()


def odin_source(ranks: np.ndarray) -> str:
    lines = [
        "// SPDX-License-Identifier: LGPL-2.1-or-later",
        "// Generated by generate_tile.py; regenerate instead of editing ranks.",
        "// Void-and-cluster: sigma 1.5, seed 20260907, initial occupancy 410/4096.",
        "// Rank SHA-256 (row-major, little-endian u16): " + rank_digest(ranks),
        "package dither",
        "",
        "TILE_SIZE :: 64",
        "TILE_AREA :: 4096",
        "",
        "BLUE_NOISE :: [4096]u16{",
    ]
    flat = ranks.ravel()
    for offset in range(0, TILE_AREA, 16):
        lines.append("\t" + ", ".join(f"{int(rank):4d}" for rank in flat[offset:offset + 16]) + ",")
    lines.append("}")
    return "\n".join(lines) + "\n"


def low_frequency_energy(pattern: np.ndarray) -> float:
    centered = pattern.astype(np.float64) - float(np.mean(pattern))
    power = np.abs(np.fft.fft2(centered)) ** 2
    frequency = np.fft.fftfreq(TILE_SIZE)
    radius_squared = frequency[:, None] ** 2 + frequency[None, :] ** 2
    non_dc = radius_squared > 0
    low = non_dc & (radius_squared < (1 / 8) ** 2)
    return float(np.mean(power[low]) / np.mean(power[non_dc]))


def print_metrics(ranks: np.ndarray) -> None:
    white_tiles = []
    for trial in range(WHITE_TRIALS):
        white = np.empty(TILE_AREA, dtype=np.uint16)
        white[pixel_order(SEED + 100 + trial)] = np.arange(TILE_AREA, dtype=np.uint16)
        white_tiles.append(white.reshape(TILE_SIZE, TILE_SIZE))

    print("Low-frequency normalized power: 0 < radius < 1/8 cycle/pixel")
    print(f"White baseline: mean of {WHITE_TRIALS} independent rank permutations")
    print("occupancy  blue-noise  white-mean  blue/white")
    for threshold in THRESHOLDS:
        blue = low_frequency_energy(ranks < threshold)
        white = float(np.mean([low_frequency_energy(tile < threshold) for tile in white_tiles]))
        print(f"{threshold / TILE_AREA:8.2%}  {blue:10.6f}  {white:10.6f}  {blue / white:10.6f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "src" / "blue_noise.odin")
    parser.add_argument("--check", action="store_true", help="Regenerate and verify the existing file without writing.")
    parser.add_argument("--metrics", action="store_true", help="Report spectral measurements against white noise.")
    args = parser.parse_args()

    ranks, swaps = generate_tile()
    source = odin_source(ranks)
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != source:
            parser.exit(1, f"Generated tile differs from {args.output}. Regenerate it without --check.\n")
        print(f"Verified {args.output}")
    else:
        args.output.write_bytes(source.encode("utf-8"))
        print(f"Wrote {args.output}")
    print(f"Ranks: permutation of 0..4095; seed relaxation: {swaps} improving swaps")
    print(f"Rank SHA-256 (little-endian u16): {rank_digest(ranks)}")
    if args.metrics:
        print_metrics(ranks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
