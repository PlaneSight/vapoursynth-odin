---
title: Vectorized blue-noise dither
description: Reduce integer video bit depth with a reproducible blue-noise tile, exact scalar and SIMD kernels, and explicit video code scaling.
---

# Vectorized blue-noise dither

`odin_dither.Dither` reduces integer video bit depth while distributing rounding
decisions through a reproducible blue-noise pattern. It extends the
[invert filter](invert-plugin.md) with output-format negotiation, immutable
precomputed thresholds, compile-time kernel specialization, and eight-lane SIMD
processing with exact scalar parity.

The example accepts constant-format, constant-dimension Gray, RGB, and YUV video
with 8–16 bit integer samples. It preserves dimensions, subsampling, timing, and
frame properties. Every plane is processed using its actual dimensions and its
own source and destination strides.

## See the quantization pattern

These 768 × 192 comparisons start from the same RGB16 grayscale ramp, spanning
codes `100 × 256` through `112 × 256 - 1`. One view uses nearest rounding; the
other is the native filter's eight-bit output with `scale=0` and `seed=0`.
The displayed grayscale channel receives **the same 20× contrast gain in both
images**, using `display = clamp((sample - 100) × 20 + 8, 0, 255)`.
This amplified display makes quantization steps and the spatial rounding
pattern visible; it does not show the ramp at its natural contrast.

=== "Nearest rounding"

    ![Nearest rounding of a shallow grayscale ramp, with 20 times display contrast exposing vertical quantization bands](../assets/examples/dither-rounding.png){ width="768" height="192" }

=== "Blue-noise dither"

    ![Native blue-noise dither of the same ramp, with the identical 20 times display contrast exposing distributed rounding decisions](../assets/examples/dither-blue-noise.png){ width="768" height="192" }

Reproduce these actual filter-output images with:

```console
uv run tests/advanced.py
uv run tools/render_showcase.py
```

The renderer writes the comparisons and their configuration record under
`.build/showcase`. It also renders the [Hald CLUT comparison](haldlut-plugin.md#see-the-color-transform).

## Build and try it

Start with the [uv environment](../guides/python-packaging.md):

```console
uv sync --locked
```

Build an optimized baseline binary from the repository root:

=== "Windows x64"

    ```powershell
    New-Item -ItemType Directory -Force .build | Out-Null
    odin build examples/dither -build-mode:dll -o:speed -vet -microarch:x86-64 -out:.build/odin_dither.dll
    ```

=== "Linux x64"

    ```sh
    mkdir -p .build
    odin build examples/dither -build-mode:dll -o:speed -vet -microarch:x86-64 -out:.build/odin_dither.so
    ```

=== "macOS ARM64"

    ```sh
    mkdir -p .build
    odin build examples/dither -build-mode:dll -o:speed -vet -out:.build/odin_dither.dylib
    ```

The x64 commands target the baseline x86-64 instruction set rather than the build
machine's optional extensions. Eight logical SIMD lanes do not require a single
256-bit machine instruction: the compiler can lower them into smaller vectors
supported by the selected target.

Save this as `dither_demo.py` at the repository root and run
`uv run dither_demo.py`:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/odin_dither{suffix}").resolve()))

# 32896 / 256 = 128.5: half of the output tile rounds up.
source = vs.core.std.BlankClip(
    format=vs.GRAY16, width=64, height=64, color=[32896], length=1,
)
output = vs.core.odin_dither.Dither(source, bits=8)

with output.get_frame(0) as frame:
    counts = {128: 0, 129: 0}
    for y in range(frame.height):
        for x in range(frame.width):
            counts[frame[0][y, x]] += 1
    assert counts == {128: 2048, 129: 2048}
    print(counts)
```

For distribution, `uv build --wheel` includes this plugin alongside the other
native examples. An installed wheel exposes the namespace through VapourSynth's
plugin discovery; omit `LoadPlugin` in that case. The
[packaging guide](../guides/python-packaging.md) explains installation and
verification in a fresh process.

## Parameters and unchanged-depth behavior

```python
result = core.odin_dither.Dither(clip, bits=8, seed=0, simd=1, scale=0)
```

| Argument | Default | Contract |
| --- | --- | --- |
| `clip` | Required | Constant integer Gray, RGB, or YUV; 8–16 bits |
| `bits` | `8` | Output depth, from 8 through the input depth |
| `seed` | `0` | Integer 0–4095 selecting a spatial phase |
| `simd` | `1` | `0` selects scalar; `1` enables the portable SIMD path when supported |
| `scale` | `0` | `0` uses power-of-two code scaling; `1` maps the full code range |

All arguments are validated during construction. An unchanged depth returns the
input node reference directly, without allocating filter state or touching
pixels. Consequently, this pass-through path also preserves malformed samples
outside their declared bit depth. A reducing path clamps such samples to the
input maximum before quantization.

`simd` selects an implementation of the same integer calculation. It does not
select a different noise pattern or a quality level. Hardware availability is
determined by the compiled target; there is no runtime dispatch to an optional
CPU instruction set. The scalar option describes the source implementation;
an optimizing compiler may still auto-vectorize some of its operations.

## Choose the scale for the signal

Let `a` be the input depth, `b` the output depth, `M = 2^a - 1`, and
`N = 2^b - 1`. A rank `r` lies in `0..4095`.

For the default `scale=0`, set `D = 2^(a-b)`:

```text
threshold = floor((2r + 1) × D / 8192)
output = min(N, floor((min(input, M) + threshold) / D))
```

This preserves nominal video code points that are exact multiples of `D`.
For ten-bit to eight-bit conversion:

| Ten-bit input | Eight-bit result with `scale=0` |
| ---: | ---: |
| 64 | 16 at every pixel |
| 512 | 128 at every pixel |
| 940 | 235 at every pixel |
| 65 | 16 or 17; one quarter of a complete tile rounds up |

With `scale=1`, the quantizer instead uses:

```text
threshold = floor((2r + 1) × M / 8192)
output = floor((min(input, M) × N + threshold) / M)
```

This maps the full input interval `0..M` onto `0..N`, preserving both endpoints.
Intermediate values follow that ratio rather than a bit shift. Choose it when
that numerical mapping matches the signal you intend to produce.

Neither mode converts limited range to full range, changes transfer functions,
or interprets color metadata. In particular, `scale=1` does not mean “convert
limited-range YUV to full-range YUV.” Frame properties are copied. The caller
must choose a mapping consistent with those properties.

## Generate the pattern once

The checked-in 64 × 64 tile contains every rank from 0 through 4095 exactly once.
It was generated with Robert Ulichney's
[void-and-cluster method](https://cv.ulichney.com/papers/1993-void-cluster.pdf):
relax an initial binary pattern by moving clustered pixels into voids, rank
below that density by removing clusters, fill voids up to half occupancy, then
rank the remaining holes through the complementary pattern.

The generator uses a Gaussian with sigma 1.5 and toroidal distances. A fixed
seed, deterministic pixel ordering, and exact integer energy updates make
regeneration reproducible. The runtime never generates noise or runs an FFT.

```console
uv run examples/dither/generate_tile.py --check --metrics
```

`--check` verifies the generated declaration against the checked-in file.
`--metrics` compares low-frequency spectral power at several binary thresholds
with independent white-noise rank permutations. NumPy belongs to this generator
and measurement workflow; it is not a plugin runtime dependency.

The filter's `seed` argument shifts this existing tile. It does not regenerate
it. For plane `p`, the phases are:

```text
phase_x = (seed + 17p) mod 64
phase_y = (floor(seed / 64) + 29p) mod 64
```

Different planes therefore use offset patterns, including subsampled chroma
planes in their own coordinates. Frame number does not enter the calculation:
unchanged pixels receive unchanged dither across frames and request order.
The tradeoff is a finite 64-pixel spatial repeat. Blue-noise distribution reduces
low-frequency structure within that tile; it does not make the pattern aperiodic.

## Vectorize the bounded operation

Filter creation converts ranks into thresholds for the chosen scaling mode and
stores each threshold row twice in a `[64][128]u16` array. A vector beginning near
column 63 can then load eight consecutive thresholds across the wrap without
gather instructions or access beyond the allocation.

Each eight-sample iteration:

1. Loads eight `u16` input samples and thresholds with unaligned loads.
2. Widens to `u32`, clamps the samples, and computes the integer quantizer.
3. Narrows and stores eight output samples as `u8` or `u16`.

The guard `x <= width - 8` runs the vector loop only when eight active samples
remain, without overflowing an `x + 8` expression. A scalar tail handles the remaining
zero to seven samples with the same formula. Input and output padding never
become samples. Creation has already returned early for unchanged depth, so
every reducing input uses two-byte storage.

The full-range path replaces division by `2^a - 1` with this exact identity for
the numerator bounds of bit-depth reduction:

```text
q = (numerator + 1 + (numerator >> a)) >> a
```

The supported maximum input and strictly smaller output depth keep the
intermediate arithmetic within `u32`. The identity is not a general replacement
for division of arbitrary integers. `tests/advanced.py` deliberately uses
ordinary integer division in its independent reference calculation.

Kernel selection happens once. Output storage type, scaling mode, and vector
selection become compile-time parameters of the row implementation; processing
does not branch on those choices for every sample.

## Ownership, scheduling, and verification

The instance owns one source-node reference and its immutable threshold table.
It declares `rpStrictSpatial` and `fmParallel`. Initial activation requests source
frame `n`; ready activation acquires that frame, allocates a frame with the new
format, and copies properties by passing the source as the property source to
`newVideoFrame`. The callback releases the source and transfers the output
reference to VapourSynth. The free callback releases the node and instance.

Run the independent pixel checks and then measure on the intended machine:

```console
uv run tests/advanced.py --only dither
uv run tests/benchmark_dither.py
```

The correctness suite covers scalar/SIMD parity, both scaling modes, bit depths,
widths around vector and tile boundaries, seed extremes, subsampled planes,
concurrent requests, preserved properties, and unchanged retained source frames.
The benchmark measures end-to-end frame throughput with warmups, repeated runs,
and output caching disabled. Its timings include allocation and scheduling;
they are not isolated arithmetic-kernel timings. See
[testing and verification](../maintenance/testing.md) for runtime selection.

## Measured throughput

One measured Windows run compared both source implementations on the same
1920 × 1080 Gray16-to-Gray8 conversion with `scale=0` and `seed=0`:

| Implementation | Median time for 256 frames | Throughput |
| --- | ---: | ---: |
| Scalar source | 0.136815 s | 1,871.14 frames/s |
| Explicit SIMD | 0.048459 s | 5,282.83 frames/s |

The measured median-time ratio was **2.823×**. The environment was Windows AMD64
on an AMD Family 25 Model 97 Stepping 2 processor, VapourSynth R79, CPython
3.14.6, and Odin `dev-2026-09-nightly:a2fb372`. The plugin was built with
`-microarch:x86-64 -o:speed -vet`.

The benchmark used four VapourSynth workers and four outstanding requests,
16 warmup frames per mode, and five measured runs of 256 frames per mode.
It alternated implementation order, requested unique output indices, and
disabled output caching. Exact scalar/SIMD parity was checked before timing.

These are end-to-end frame measurements: allocation, scheduling, Python request
delivery, and release are included. The result is specific to this host,
compiler, runtime, frame size, and concurrency; it is not a performance
guarantee for other systems or clips. Reproduce the procedure with
`uv run tests/benchmark_dither.py`; use its `--help` output to vary the workload
or select a runtime.

??? info "Complete row kernels"

    ```odin title="examples/dither/kernels.odin"
    --8<-- "examples/dither/kernels.odin"
    ```

??? info "Complete plugin lifecycle"

    ```odin title="examples/dither/plugin.odin"
    --8<-- "examples/dither/plugin.odin"
    ```
