---
title: Vectorized blue-noise dither
description: Reduce integer video bit depth with a reproducible blue-noise tile, exact scalar and SIMD kernels, and explicit video code scaling.
---

# Vectorized blue-noise dither

`odin_dither.Dither` reduces integer video bit depth while distributing rounding
decisions through a reproducible blue-noise pattern. It extends the
[invert filter](invert-plugin.md) with output-format negotiation, immutable
precomputed thresholds, compile-time kernel specialization, and sixteen-lane SIMD
processing with exact scalar parity. On x64, the plugin selects AVX2 at runtime
when the CPU and operating system support it, retaining a portable fallback.

The example accepts constant-format, constant-dimension Gray, RGB, and YUV video
with 8–16 bit integer samples. It preserves dimensions, subsampling, timing, and
frame properties. Every plane is processed using its actual dimensions and its
own source and destination strides. The requested effective depth can be as low
as **one bit per sample**. Depths below eight use an ordinary eight-bit output
format, with the quantized levels expanded across `0..255` for viewing.

## See the quantization pattern

These 768 × 192 comparisons start from the same RGB16 grayscale ramp, spanning
codes `100 × 256` through `112 × 256 - 1`. One view uses nearest rounding; the
other is the native filter's eight-bit output with `scale=0` and `seed=0`.
The displayed grayscale channel receives **the same 20× contrast gain in both
images**, using `display = clamp((sample - 100) × 20 + 8, 0, 255)`.
This amplified display makes quantization steps and the spatial rounding
pattern visible; it does not show the ramp at its natural contrast.

=== "Nearest rounding"

    ![Nearest rounding of a shallow grayscale ramp, with 20 times display contrast exposing vertical quantization bands](../assets/generated/dither-rounding.png){ width="768" height="192" }

=== "Blue-noise dither"

    ![Native blue-noise dither of the same ramp, with the identical 20 times display contrast exposing distributed rounding decisions](../assets/generated/dither-blue-noise.png){ width="768" height="192" }

Reproduce these actual filter-output images with:

```console
uv run tools/render_showcase.py
```

The renderer builds the plugins, runs their checked-in `.vpy` scripts, and writes
the comparisons and a record of the run under `.build/showcase`. These images
are regenerated from those same output nodes during each documentation build.

To inspect them interactively:

```console
uv run --group preview tools/examples.py preview dither
```

VSView presents the comparison at output `0`, amplified nearest rounding at `1`,
and amplified dither at `2`. Outputs `3` and `4` provide the original RGB16 ramp
and native RGB8 dither without display gain. The
[preview guide](../guides/previewing-examples.md) covers the optional viewer
dependency and headless checks.

## See what one, two, and four bits look like

The same demonstration also processes the RGB16 color scene used by the other
examples. These images have **no display contrast gain**. Both sides quantize to
the selected number of levels per channel and store the result in RGB8; the
dithered side calls the native plugin with `scale=1`, `seed=0`, and `simd=1`.
The neutral ramp along the bottom shows the difference particularly clearly.

=== "1 bit: nearest rounding"

    ![One-bit nearest rounding of three colored spheres and a gray ramp, with two levels per RGB channel](../assets/generated/dither-1bit-rounding.png){ width="768" height="320" }

=== "1 bit: blue noise"

    ![One-bit native blue-noise dither of the same scene, with spatial mixtures of two levels per RGB channel](../assets/generated/dither-1bit-blue-noise.png){ width="768" height="320" }

=== "2 bits: nearest rounding"

    ![Two-bit nearest rounding of three colored spheres and a gray ramp, with four levels per RGB channel](../assets/generated/dither-2bit-rounding.png){ width="768" height="320" }

=== "2 bits: blue noise"

    ![Two-bit native blue-noise dither of the same scene, with spatial mixtures of four levels per RGB channel](../assets/generated/dither-2bit-blue-noise.png){ width="768" height="320" }

=== "4 bits: nearest rounding"

    ![Four-bit nearest rounding of three colored spheres and a gray ramp, with sixteen levels per RGB channel](../assets/generated/dither-4bit-rounding.png){ width="768" height="320" }

=== "4 bits: blue noise"

    ![Four-bit native blue-noise dither of the same scene, with spatial mixtures of sixteen levels per RGB channel](../assets/generated/dither-4bit-blue-noise.png){ width="768" height="320" }

One-bit RGB has two choices **per channel**, so it can represent eight RGB color
combinations. It is not a two-color palette. The planes use different spatial
phases, making color noise visible even along the neutral ramp. Inspect the
images at their original size: browser or viewer resizing adds an interpolation
step that can obscure individual quantized samples.

Output `5` is the original RGB16 scene. Outputs `6`/`7`/`8` are its one-bit
rounding, dither, and side-by-side comparison; `9`/`10`/`11` repeat that order for
two bits, and `12`/`13`/`14` for four bits. These nodes also generate the six
illustrations above during the documentation build.

## Build and try it

Build from the repository root with the same command on every supported platform:

```console
uv run tools/examples.py build dither
```

This prepares the uv environment and builds the optimized
`.build/examples/dither` library used by the preview script and inline Python
program. The command chooses the native architecture and shared-library
extension. See the [build guide](../guides/previewing-examples.md#one-build-command-on-every-supported-platform)
for supported targets and prerequisites.

On x64, the build keeps the binary's baseline at x86-64. The plugin contains
separate AVX2 functions and calls them only after checking runtime support.
Sixteen logical SIMD lanes can lower into multiple machine vectors: the portable
fallback uses the instructions supported by the compiled target, so AVX2 is
not a minimum requirement for loading the plugin.

Save this as `dither_demo.py` at the repository root and run
`uv run dither_demo.py`:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/examples/dither{suffix}").resolve()))

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
| `bits` | `8` | Effective depth, from 1 through the input depth; depths 1–7 use eight-bit storage |
| `seed` | `0` | Integer 0–4095 selecting a spatial phase |
| `simd` | `1` | `0` selects scalar; `1` selects AVX2 when available on x64, otherwise portable SIMD or scalar according to the target |
| `scale` | `0` | `0` uses power-of-two code scaling; `1` maps the full code range |

All arguments are validated during construction. An unchanged depth returns the
input node reference directly, without allocating filter state or touching
pixels. Consequently, this pass-through path also preserves malformed samples
outside their declared bit depth. A reducing path clamps such samples to the
input maximum before quantization.

### Effective depth and storage depth

`bits` controls the number of quantization levels per sample: `2^bits`.
The registered output format has `max(8, bits)` bits per sample. For depths
below eight, each quantized value `q` is expanded to the nearest eight-bit value:

```text
levels_minus_one = 2^bits - 1
stored = floor((q × 255 + floor(levels_minus_one / 2)) / levels_minus_one)
```

| Requested `bits` | Levels per channel | Output format depth | Stored sample values |
| ---: | ---: | ---: | --- |
| 1 | 2 | 8 | 0, 255 |
| 2 | 4 | 8 | 0, 85, 170, 255 |
| 3 | 8 | 8 | 0, 36, 73, 109, 146, 182, 219, 255 |
| 4 | 16 | 8 | 0, 17, 34, …, 255 |
| 8 | 256 | 8 | 0, 1, 2, …, 255 |

For example, `Dither(rgb8, bits=2, scale=1)` accepts eight-bit input and returns
RGB8 whose channels use only `0`, `85`, `170`, or `255`. This reduces the sample
values used by the image; it does not pack four two-bit samples into one byte.
Ordinary filters and previewers still receive a normal eight-bit clip.

Zero bits would provide only one level and could not preserve both black and
white. `bits=0` is rejected, as are negative depths and depths above the input.

`simd` selects an implementation of the same integer calculation. It does not
select a different noise pattern or a quality level. On x64, `simd=1` checks
AVX2 support once during construction, then stores the selected row function.
Older x64 CPUs and other supported targets use portable SIMD; a target without
hardware SIMD uses scalar processing. The scalar option describes the source
implementation; an optimizing compiler may still auto-vectorize some operations.

## Choose the scale for the signal

Let `a` be the input depth, `b` the requested effective depth, `M = 2^a - 1`, and
`N = 2^b - 1`. A rank `r` lies in `0..4095`.

For the default `scale=0`, set `D = 2^(a-b)`:

```text
threshold = floor((2r + 1) × D / 8192)
q = min(N, floor((min(input, M) + threshold) / D))
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
q = floor((min(input, M) × N + threshold) / M)
```

This maps the full input interval `0..M` onto `0..N`, preserving both endpoints.
Intermediate values follow that ratio rather than a bit shift. Choose it when
that numerical mapping matches the signal you intend to produce. For either
mode, `q` is the stored result at eight bits and above; below eight, the expansion
formula in the preceding section maps `q` into the eight-bit container.

The tile provides 4096 threshold ranks. With `scale=0`, each integer threshold
occurs equally often when `D <= 4096`. Larger reduction steps can reach 32768,
so the tile samples the interval at 4096 midpoint positions instead of visiting
every integer threshold. The rounding probability then has a finite resolution
of one pixel per complete tile. This limitation also applies to full-range
normalization; low-frequency spatial distribution does not remove it.

Neither mode converts limited range to full range, changes transfer functions,
or interprets color metadata. In particular, `scale=1` does not mean “convert
limited-range YUV to full-range YUV.” Frame properties are copied. The caller
must choose a mapping consistent with those properties.

For low-bit RGB demonstrations, `scale=1` gives a clear black-to-white grid at
each depth. Low-bit YUV processing is also supported, but it quantizes stored
luma and chroma codes independently. At very low depths the grid cannot retain
all conventional limited-range endpoints or neutral chroma. This is a code-value
visualization effect, not a color-managed reduction or a range conversion.

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
column 63 can then load sixteen consecutive thresholds across the wrap without
gather instructions or access beyond the allocation.

Each sixteen-sample iteration:

1. Loads sixteen `u8` or `u16` input samples and `u16` thresholds with unaligned loads.
2. Clamps the samples in `u16` lanes and computes the selected integer quantizer.
3. Expands quantized levels into eight-bit values when `bits < 8`, then narrows
   and stores sixteen output samples as `u8` or `u16`.

The guard `x <= width - 16` runs the vector loop only when sixteen active samples
remain, without overflowing an `x + 16` expression. A scalar tail handles the remaining
zero to fifteen samples with the same formula. Input and output padding never
become samples. Eight-bit input uses one-byte loads when reducing to an effective
depth below eight; higher input depths use two-byte loads.

The power-of-two vector path stays in `u16` lanes. It adds thresholds with
unsigned saturation, shifts, and clamps to the effective output maximum. A
16-bit sum can overflow only where the final output would already be clamped,
so saturation preserves the exact scalar result while avoiding wider arithmetic.
Construction bounds the reduction shift to `1..15`; the vector expression also
exposes this bound explicitly to help the compiler lower the shift efficiently.

Full-range processing widens the clamped samples to `u32`. Its multiplication
by `2^b - 1` becomes `(sample << b) - sample`, avoiding a general vector multiply.

The full-range path replaces division by `2^a - 1` with this exact identity for
the numerator bounds of bit-depth reduction:

```text
q = (numerator + 1 + (numerator >> a)) >> a
```

The supported maximum input and strictly smaller output depth keep the
intermediate arithmetic within `u32`. The identity is not a general replacement
for division of arbitrary integers. `tests/advanced.py` deliberately uses
ordinary integer division in its independent reference calculation.

Low-bit expansion also avoids division in the row loop. Construction computes
`R = ceil(2^24 / N)` once; for the supported low-bit levels the exact rounded
expansion is `((q × 255 + floor(N / 2)) × R) >> 24`. The intermediate fits in
`u32`. The independent level checks compare every nominal low-bit level against
ordinary integer division. This expansion step is absent from the kernels for
eight-bit and higher output.

Kernel selection happens once. Input and output storage types, scaling mode, and vector
selection become compile-time parameters of the row implementation; processing
does not branch on those choices for every sample.

### Keep AVX2 optional

`kernels_amd64.odin` is included only on x64. It asks Odin's
`core:sys/info.cpu_features()` for AVX2 support. That check includes CPU features
and operating-system support for saving XMM and YMM register state. Only a
successful check selects an `@(enable_target_feature="avx2")` row function.

The portable and AVX2 entry points share the same forced-inline row implementation,
including scalar tails and low-bit expansion. Inlining places the vector arithmetic
inside the selected function's instruction-set context. There is no CPU-feature
test in the pixel loop, and `simd=0` continues to choose the scalar implementation.

To exercise the portable fallback on an AVX2-capable machine, build a separate
library with `-define:DITHER_ENABLE_AVX2=false`, keeping the normal baseline flag:

```console
odin build examples/dither -build-mode:dll -o:speed -vet -microarch:x86-64 -define:DITHER_ENABLE_AVX2=false -out:.build/dither-portable.dll
```

This Windows command assumes `.build` exists; use `.so` on Linux x64. Load that
file explicitly in a fresh VapourSynth process. The definition disables AVX2
selection without changing the filter's parameters, quantization, or output
format. Keep default and forced-portable binaries distinct when comparing them.

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

The [dither performance comparison](../maintenance/dither-performance.md) measures
this filter against FMTConv's void-and-cluster mode at resolutions through
3840 × 2160 and several integer formats, with `core.num_threads = 1`.
It records the exact build, runtime, input and output formats, range mapping,
dither settings, workload, and measurement procedure alongside the results.

Use the comparison's reproduction commands when changing a hot path. The
scalar/SIMD runner remains useful for focused implementation comparisons:

```console
uv run tests/benchmark_dither.py
```

End-to-end frame timings include allocation, scheduling, Python request delivery,
and release. Their ratios describe the recorded workloads and host; they do not
establish equivalent noise patterns or a performance guarantee for other clips.

??? info "Complete row kernels"

    ```odin title="examples/dither/kernels.odin"
    --8<-- "examples/dither/kernels.odin"
    ```

??? info "Complete plugin lifecycle"

    ```odin title="examples/dither/plugin.odin"
    --8<-- "examples/dither/plugin.odin"
    ```

??? info "Complete x64 AVX2 selection and entry points"

    ```odin title="examples/dither/kernels_amd64.odin"
    --8<-- "examples/dither/kernels_amd64.odin"
    ```
