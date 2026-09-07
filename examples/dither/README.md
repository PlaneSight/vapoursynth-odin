# Blue-noise bit-depth reduction

## Build this project

Install [Odin](https://odin-lang.org/docs/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then run here:

```console
uv run build.py
uv run build.py --check
uv run --group preview vsview preview.vpy
uv build
```

You can copy this entire directory into a new location and run the same commands.
It has its own Python pin, lockfile, license, sources, and build configuration.
The first build downloads the exact bindings commit and verifies the archive
checksum declared in `pyproject.toml`; later builds reuse `.deps/`. Odin is an
external prerequisite. Outputs go in `.build/`; distributions go in `dist/`.
Both generated directories and the dependency cache are ignored by Git.

`src/` contains the Odin implementation. `build.py` maps its `deps:vapoursynth`
imports to the pinned bindings and reuses that dependency's cross-platform
native build support. To test local bindings, pass
`uv run build.py --bindings /absolute/path/to/vapoursynth-odin`.

To turn this example into your own project, edit `[project]` and `[tool.odin]`
in `pyproject.toml`, then run `uv lock`.
Also change the plugin identifier, namespace, and display name in
`src/plugin.odin`, and update the matching names in `preview.vpy`.
The wheel hook reads the distribution name and native filename from the manifest.
`preview_support.py` and any generators are local, editable parts of this example.
Close the viewer before rebuilding a loaded library.

## Walkthrough

`odin_dither.Dither` reduces constant-format 8–16-bit integer Gray, RGB, or YUV video to a selected effective depth from one bit through the input depth. Effective depths below eight use a normal eight-bit output format, with the quantized levels expanded across `0..255` for viewing. It uses a reproducible 64 × 64 void-and-cluster blue-noise rank tile, processes independent frames in parallel, and has an explicit sixteen-lane Odin SIMD implementation with matching scalar code and tails. An x64 binary automatically selects AVX2 when the CPU and operating system support it, with a portable fallback for other machines.

This example builds on the [invert filter](https://github.com/PlaneSight/vapoursynth-odin/blob/main/examples/invert). It adds output-format negotiation, immutable per-instance lookup data, a selected row kernel, numerical contracts for quantization, vector memory access, and independent scalar/SIMD verification. It needs no external native library beyond VapourSynth and the platform C runtime.

## Build and load

For the interactive demonstration, run from this directory:

```console
uv run build.py
uv run --group preview vsview preview.vpy
```

The build command builds `.build/dither` with the platform's shared-library
extension and launches [preview.vpy](preview.vpy) in VSView. The optional group requires
Python 3.12–3.14 and adds VSView and Qt only when selected. The script compares
nearest rounding with native dither using the same **20× display contrast gain**
on both sides: output `0` is the comparison, `1` rounding, and `2` dither.
Outputs `3` and `4` expose the unamplified RGB16 source and RGB8 result.
Output `5` is the original RGB16 color scene. The remaining outputs show the
scene quantized to low effective depths in RGB8, without display gain:

| Effective depth | Nearest rounding | Blue-noise dither | Side by side |
| ---: | ---: | ---: | ---: |
| 1 bit | 6 | 7 | 8 |
| 2 bits | 9 | 10 | 11 |
| 4 bits | 12 | 13 | 14 |

These views use `scale=1` to preserve black and white. One-bit RGB has two levels
per channel and therefore eight possible RGB combinations; it is not a
two-color palette. Each plane uses a different phase of the dither tile.
Documentation images are exported from these same nodes during each site build.
See the [preview guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md) for headless checks
and image generation.

To build the same optimized library without opening a viewer:

```console
uv run build.py
```

This command selects the native target, output extension, and CPU baseline on
every supported platform. On x64, the baseline is x86-64. Separate AVX2 row
functions are selected only after checking runtime support, so loading the
plugin does not require an AVX2-capable CPU. See the
[build guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md#one-build-command-on-every-supported-platform)
for prerequisites.

In a Python environment with VapourSynth installed:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/dither{suffix}").resolve()))
source = vs.core.std.BlankClip(
    width=640, height=360, format=vs.YUV420P16,
    color=[4096, 32768, 32768], length=24,
)
output = vs.core.odin_dither.Dither(source, bits=8)
output.set_output()
```

This uses conventional power-of-two scaling: limited-range black 4096 becomes 16, and neutral chroma 32768 becomes 128. The source's subsampling, dimensions, frame rate, frame count, and frame properties are preserved; only the integer sample depth and storage width may change.

`uv run demo.py` creates a ramp and verifies scalar/SIMD parity.
The script accepts `--plugin` for a nondefault plugin file. The checked-in
`preview.vpy` uses the canonical `.build` path through the preview command
above. Both select the platform's shared-library extension automatically.

## Interface

```text
odin_dither.Dither(clip, bits=8, seed=0, simd=1, scale=0) -> video node
```

| Argument | Contract |
| --- | --- |
| `clip` | Constant format and dimensions; integer Gray, RGB, or YUV; 8–16 bits per sample. |
| `bits` | Effective depth from 1 through the input depth. Depths 1–7 use eight-bit output storage. Zero, negative values, and increasing depth are rejected. |
| `seed` | Integer 0–4095 selecting the tile's spatial phase. It does not regenerate the tile. |
| `simd` | `1` selects AVX2 on supported x64 systems, otherwise portable SIMD or scalar according to the target; `0` selects the scalar source implementation. Other values are rejected. |
| `scale` | `0` preserves power-of-two code points; `1` normalizes the full input code range to the full output code range. |

If `bits` equals the input depth, the function returns the original node after validating every argument. It does not allocate a new filter or touch the pixels. On a reducing path, malformed integer samples above the input format's maximum are clamped before quantization.

Missing optional arguments use the defaults above. Invalid values, floating-point input, variable format, and variable dimensions produce an invocation error. A failed upstream frame request or output allocation produces a frame-request error. This is a synchronous pixel kernel inside the normal asynchronous VapourSynth filter scheduling contract: the callback requests source frame `n` during `arInitial` and processes it during `arAllFramesReady`.

## Low effective depths in an eight-bit container

```python
source = vs.core.std.BlankClip(format=vs.RGB24, color=[75, 125, 175])
two_bit = vs.core.odin_dither.Dither(source, bits=2, scale=1)
assert two_bit.format.bits_per_sample == 8
```

This clip uses only four values in each channel: `0`, `85`, `170`, and `255`.
The requested depth determines `2^bits` quantization levels. The registered
output format uses `max(8, bits)` bits per sample, so existing filters and
previewers can read the output normally. Pixels are not packed into sub-byte
storage.

After quantization, an effective depth below eight expands each level `q` to
the nearest representable eight-bit value:

```text
m = 2^bits - 1
stored = (q*255 + floor(m/2)) / m
```

Integer division rounds down. One bit gives `0, 255`; two bits gives
`0, 85, 170, 255`; four bits gives multiples of 17. Depths whose intervals do not
divide 255 evenly use rounded spacing: three bits gives
`0, 36, 73, 109, 146, 182, 219, 255`.

Zero bits would give one level and could not preserve both black and white.
It is deliberately rejected. Eight-bit sources can reduce to any of the
supported effective depths below eight, using one-byte input and output storage.

## Quantization and range semantics

Let `B` be the input bit depth, `b` the requested effective bit depth, `M = 2^B - 1`, `m = 2^b - 1`, `r` the blue-noise rank from 0 through 4095, and `s = min(input, M)`. All arithmetic below is integer arithmetic; `/` rounds down.

For the default `scale=0`:

```text
shift = B - b
step = 2^shift
threshold = ((2*r + 1) * step) / 8192
q = min(m, (s + threshold) >> shift)
```

The tile includes every threshold rank exactly once. For reduction steps up to 4096, each integer threshold from zero through `step-1` occurs equally often over a full tile. Larger steps can reach 32768, so the tile samples 4096 midpoint positions rather than every integer threshold. Its rounding probability has a resolution of one sample per tile. A fractional code value is distributed between its two neighboring output values using a spatial blue-noise pattern. Values already on the output grid remain exact. The top endpoint is clamped to the output maximum.

This convention preserves common video code points: for 16-to-8-bit limited-range YUV, black 4096 becomes 16, luma white 60160 becomes 235, and chroma center 32768 becomes 128. Headroom and footroom are retained within the destination's representable code range. The filter does not expand limited-range input to full range or reinterpret `_Range`.

For `scale=1`:

```text
threshold = ((2*r + 1) * M) / 8192
q = (s*m + threshold) / M
```

This maps the full code interval `[0, M]` to `[0, m]`, keeping both endpoints exact. The ranked thresholds approximate uniform ordered rounding; the finite 4096-rank tile limits threshold resolution. This is useful when full-range endpoint normalization is the intended operation.

For either mode, `q` is stored directly at eight bits and above. Below eight,
the expansion formula in the preceding section maps `q` into the eight-bit
container. The low-bit RGB preview uses `scale=1`, keeping its black-to-white
interval consistent across the different effective depths.

Full-range normalization differs from preserving YUV code points. For example, 16-bit neutral chroma 32768 becomes a spatial mixture of 127 and 128 at eight bits because `32768*255/65535` is slightly above 127.5. Use the default `scale=0` when retaining conventional chroma center and limited-range code points matters. Both modes preserve metadata rather than changing it to describe an unrequested range conversion.

Low-bit YUV is supported as code-value quantization. Its sparse grid cannot
retain all nominal limited-range endpoints and neutral chroma at very low
depths, so color casts can be expected. The plugin does not reinterpret those
codes or rewrite their range metadata to compensate.

The filter works in the stored integer code domain. It performs no transfer-function conversion, gamma correction, color conversion, chroma resampling, or error diffusion. A single tile phase remains fixed across frames, so stationary pixels produce stationary dither instead of introducing temporal noise.

## Reproducible blue noise

[generate_tile.py](generate_tile.py) is an original implementation of Robert Ulichney's [void-and-cluster method](https://cv.ulichney.com/papers/1993-void-cluster.pdf). It uses a toroidal Gaussian with sigma 1.5, a fixed seed, 410 initially occupied cells, and the full ranking sequence below and above 50% occupancy. The generator docstring describes the algorithm and numerical choices in detail.

Rank generation uses SHA-256 ordering, a Decimal-generated kernel rounded to 40 fractional bits, and exact `int64` energy updates. It does not depend on a particular NumPy random generator or on floating-point FFT accumulation. NumPy is used by the preview, regeneration, and spectral measurements; plugin builds use the checked-in [blue_noise.odin](src/blue_noise.odin).

```console
uv run generate_tile.py --check --metrics
```

The rank SHA-256 over row-major little-endian `u16` values is:

```text
38c0b7c479e4a80d1a582d3513eccdf882de13871c9a1cac5053e1a72956eb6e
```

At binary occupancies from 6.25% through 93.75%, the measured mean non-DC power below 1/8 cycle per pixel was **91.2–98.4% lower** than the average of 16 independent white-rank permutations. At 50% occupancy the blue/white ratio was 0.016292. The generator reproduces the measurements. This establishes low-frequency suppression for those thresholds; it does not guarantee perfect isotropy or that a 64-pixel repeating tile is invisible in every image.

For plane `p`, the phase is:

```text
phase_x = (seed + 17*p) & 63
phase_y = ((seed >> 6) + 29*p) & 63
rank = BLUE_NOISE[((y + phase_y) & 63)*64 + ((x + phase_x) & 63)]
```

Coordinates are local to each plane. Chroma planes use their actual subsampled dimensions. Different planes receive different phases, and frame number has no effect. The seed selects one of the tile's 4096 spatial origins.

## SIMD and memory layout

[kernels.odin](src/kernels.odin) explicitly loads sixteen `u8` or `u16` samples and sixteen thresholds, clamps in `simd.u16x16`, and performs packed integer arithmetic. Effective depths below eight expand their quantized levels before the output is narrowed to sixteen `u8` or `u16` samples. Unaligned loads and stores avoid requiring vector alignment at a row or tile phase. A vector block runs only when sixteen active samples remain; the scalar tail handles the remaining zero to fifteen samples.

Eight-bit input uses `u8` loads when reduced to a lower effective depth; higher input depths use `u16` loads. Frames at the same depth took the earlier identity path. Each plane uses independent input and output strides; only active samples are read and written. No padding contributes to the result.

The constructor precomputes the thresholds once and duplicates each 64-entry row. A vector load crossing the tile's horizontal seam can then read up to sixteen consecutive values without a gather or an out-of-bounds access. The per-instance table uses 16 KiB, and all instance state is immutable during processing. There is no RNG, scratch allocation, or mutable shared state in the row loop.

The power-of-two vector path uses unsigned saturating `u16` addition, a shift,
and an output clamp. Saturation changes only sums whose output would be clamped
anyway, so it preserves scalar parity while avoiding `u32` arithmetic. The
full-range path widens clamped samples to `u32` and replaces multiplication by
`2^b-1` with `(sample << b) - sample`. Construction bounds the reduction shift to
`1..15`; the vector expression exposes that bound explicitly for code generation.

Full-range mode avoids division in the hot loop. For its bounded numerator `n`, division by the Mersenne number `2^B-1` is exactly:

```text
q = (n + 1 + (n >> B)) >> B
```

Reduction guarantees `b < B`; even the 16-to-15-bit case keeps the numerator and corrected numerator below `2^31`. The scalar and SIMD paths use this same identity and produce bit-identical results. The test oracle independently uses ordinary integer division.

The scalar option describes the source implementation; an optimizing compiler
may still auto-vectorize parts of it. With `simd=1`, x64 builds ask Odin's
`core:sys/info.cpu_features()` whether AVX2 is available. Odin checks CPU support
and operating-system support for saving XMM and YMM state before reporting that
feature. The constructor then selects one row function for the instance. Older
x64 CPUs and other targets use the sixteen-lane portable implementation; a
target without hardware SIMD selects scalar processing.

[kernels_amd64.odin](src/kernels_amd64.odin) contains the x64-only selection code and
`@(enable_target_feature="avx2")` entry points. The portable and AVX2 functions
share one forced-inline row implementation, including tails and low-bit
expansion. The default build remains `-microarch:x86-64`, and CPU detection does
not run in the pixel loop.

Add `-define:DITHER_ENABLE_AVX2=false` to a baseline x64 build to exercise the
portable fallback even on a newer CPU. Write that build to a separate output
filename and load it in a fresh process when comparing paths. This definition
changes implementation selection, not numerical semantics. `simd=0` always
selects the scalar source implementation.

Low-bit expansion uses a precomputed reciprocal `R = ceil(2^24 / m)`:

```text
stored = ((q*255 + floor(m/2)) * R) >> 24
```

For the supported depths and quantized levels this equals the ordinary integer
division formula exactly, with bounded `u32` intermediates. The level tests
check all 254 nominal values across depths 1–7. No per-pixel division or extra
frame allocation is needed, and output depths eight and above skip expansion.

## Validation and measured performance

The advanced suite covers both scaling modes, all input depths, multiple output depths, widths around vector and tile boundaries, all 1024 codes of a ten-bit input, malformed high samples, RGB and subsampled YUV, independent plane phases, concurrent requests, unchanged source frames, preserved properties, identity behavior, and invalid inputs. Scalar and SIMD pixels are compared against an independent integer oracle.

```console
uv run tests/advanced.py
```

Use the runner's `--runtime` option when selecting an existing local Python runtime package directory. See the repository's testing documentation for the configured environment.

The [performance comparison](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/maintenance/dither-performance.md) records
single-thread measurements against FMTConv's void-and-cluster mode across
resolutions through 3840 × 2160 and several integer formats. Both filters use
`core.num_threads = 1`. The report gives the exact parameters, build, runtime,
input preparation, warmups, timing method, and archived runner provenance.

These are end-to-end frame timings, including scheduling, output allocation,
Python request delivery, and release. The benchmarks use reusable in-memory
sources, request unique output frames, and disable output caching. Results depend
on the machine, runtime, compiler, format, size, and request concurrency; they
are not a performance guarantee or evidence that different dither patterns are
pixel-identical.

Runtime tests here covered Windows x64 with R76 and R79. Compile checks also covered Windows x86, Linux x64, and macOS ARM64. The algorithm, tile, and integer outputs are designed to remain deterministic across those targets; cross-target compilation alone does not replace runtime testing on them.
