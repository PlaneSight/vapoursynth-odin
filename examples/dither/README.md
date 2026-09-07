# Blue-noise bit-depth reduction

`odin_dither.Dither` reduces constant-format 8–16-bit integer Gray, RGB, or YUV video to a selected integer bit depth. It uses a reproducible 64 × 64 void-and-cluster blue-noise rank tile, processes independent frames in parallel, and has an explicit eight-lane Odin SIMD implementation with matching scalar code and tails.

This example builds on the [invert filter](../invert). It adds output-format negotiation, immutable per-instance lookup data, a selected row kernel, numerical contracts for quantization, vector memory access, and independent scalar/SIMD verification. It needs no external native library beyond VapourSynth and the platform C runtime.

## Build and load

Run `uv sync --locked` from the repository root to provision the configured Python environment and runtime. Build an optimized Windows x64 plugin for the baseline x86-64 instruction set:

```powershell
New-Item -ItemType Directory -Force .build | Out-Null
odin build examples/dither -build-mode:dll -out:.build/odin_dither.dll -vet -o:speed -microarch:x86-64
```

On Linux x64, use `.so` for the output extension with the same flags. On macOS ARM64, use `.dylib` and omit `-microarch:x86-64`. Odin's shared-library build mode is named `dll` on all these platforms. The explicit x64 baseline avoids inheriting the compiler's newer default microarchitecture; there is no AVX2 requirement and no runtime CPU dispatch to a higher instruction set.

In a Python environment with VapourSynth installed:

```python
from pathlib import Path
import vapoursynth as vs

vs.core.std.LoadPlugin(path=str(Path(".build/odin_dither.dll").resolve()))
source = vs.core.std.BlankClip(
    width=640, height=360, format=vs.YUV420P16,
    color=[4096, 32768, 32768], length=24,
)
output = vs.core.odin_dither.Dither(source, bits=8)
output.set_output()
```

This uses conventional power-of-two scaling: limited-range black 4096 becomes 16, and neutral chroma 32768 becomes 128. The source's subsampling, dimensions, frame rate, frame count, and frame properties are preserved; only the integer sample depth and storage width may change.

`uv run examples/dither/demo.py` creates a ramp and verifies scalar/SIMD parity. The script accepts `--plugin` for a nondefault plugin file. [demo.vpy](demo.vpy) creates an undithered/dithered comparison for a VapourSynth preview application. Both select the platform's shared-library extension automatically. An already configured Python environment can invoke the same scripts with `python` directly.

## Interface

```text
odin_dither.Dither(clip, bits=8, seed=0, simd=1, scale=0) -> video node
```

| Argument | Contract |
| --- | --- |
| `clip` | Constant format and dimensions; integer Gray, RGB, or YUV; 8–16 bits per sample. |
| `bits` | Output depth from 8 through the input depth. Increasing bit depth is rejected. |
| `seed` | Integer 0–4095 selecting the tile's spatial phase. It does not regenerate the tile. |
| `simd` | `1` selects explicit portable SIMD on targets with hardware SIMD; `0` selects the scalar source implementation. Other values are rejected. |
| `scale` | `0` preserves power-of-two code points; `1` normalizes the full input code range to the full output code range. |

If `bits` equals the input depth, the function returns the original node after validating every argument. It does not allocate a new filter or touch the pixels. On a reducing path, malformed integer samples above the input format's maximum are clamped before quantization.

Missing optional arguments use the defaults above. Invalid values, floating-point input, variable format, and variable dimensions produce an invocation error. A failed upstream frame request or output allocation produces a frame-request error. This is a synchronous pixel kernel inside the normal asynchronous VapourSynth filter scheduling contract: the callback requests source frame `n` during `arInitial` and processes it during `arAllFramesReady`.

## Quantization and range semantics

Let `B` be the input bit depth, `b` the output bit depth, `M = 2^B - 1`, `m = 2^b - 1`, `r` the blue-noise rank from 0 through 4095, and `s = min(input, M)`. All arithmetic below is integer arithmetic; `/` rounds down.

For the default `scale=0`:

```text
shift = B - b
step = 2^shift
threshold = ((2*r + 1) * step) / 8192
output = min(m, (s + threshold) >> shift)
```

The tile includes every threshold rank exactly once. Because the supported reduction step is at most 256, each integer threshold from zero through `step-1` occurs equally often over a full tile. A fractional code value is distributed between its two neighboring output values using a spatial blue-noise pattern. Values already on the output grid remain exact. The top endpoint is clamped to the output maximum.

This convention preserves common video code points: for 16-to-8-bit limited-range YUV, black 4096 becomes 16, luma white 60160 becomes 235, and chroma center 32768 becomes 128. Headroom and footroom are retained within the destination's representable code range. The filter does not expand limited-range input to full range or reinterpret `_Range`.

For `scale=1`:

```text
threshold = ((2*r + 1) * M) / 8192
output = (s*m + threshold) / M
```

This maps the full code interval `[0, M]` to `[0, m]`, keeping both endpoints exact. The ranked thresholds approximate uniform ordered rounding; the finite 4096-rank tile limits threshold resolution. This is useful when full-range endpoint normalization is the intended operation.

Full-range normalization differs from preserving YUV code points. For example, 16-bit neutral chroma 32768 becomes a spatial mixture of 127 and 128 at eight bits because `32768*255/65535` is slightly above 127.5. Use the default `scale=0` when retaining conventional chroma center and limited-range code points matters. Both modes preserve metadata rather than changing it to describe an unrequested range conversion.

The filter works in the stored integer code domain. It performs no transfer-function conversion, gamma correction, color conversion, chroma resampling, or error diffusion. A single tile phase remains fixed across frames, so stationary pixels produce stationary dither instead of introducing temporal noise.

## Reproducible blue noise

[generate_tile.py](generate_tile.py) is an original implementation of Robert Ulichney's [void-and-cluster method](https://cv.ulichney.com/papers/1993-void-cluster.pdf). It uses a toroidal Gaussian with sigma 1.5, a fixed seed, 410 initially occupied cells, and the full ranking sequence below and above 50% occupancy. The generator docstring describes the algorithm and numerical choices in detail.

Rank generation uses SHA-256 ordering, a Decimal-generated kernel rounded to 40 fractional bits, and exact `int64` energy updates. It does not depend on a particular NumPy random generator or on floating-point FFT accumulation. NumPy is only needed for regeneration and spectral measurements; plugin builds use the checked-in [blue_noise.odin](blue_noise.odin).

```console
uv run examples/dither/generate_tile.py --check --metrics
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

[kernels.odin](kernels.odin) explicitly loads eight `u16` samples and eight thresholds, widens to `simd.u32x8`, and performs packed integer arithmetic. The output is narrowed to eight `u8` or `u16` samples. Unaligned loads and stores avoid requiring vector alignment at a row or tile phase. A vector block runs only when eight active samples remain; the scalar tail handles every other width.

On a reducing path the input depth is necessarily greater than eight, so reading `u16` storage is valid. Frames at the same depth took the earlier identity path. Each plane uses independent input and output strides; only active samples are read and written. No padding contributes to the result.

The constructor precomputes the thresholds once and duplicates each 64-entry row. A vector load crossing the tile's horizontal seam can then read up to eight consecutive values without a gather or an out-of-bounds access. The per-instance table uses 16 KiB, and all instance state is immutable during processing. There is no RNG, scratch allocation, or mutable shared state in the row loop.

Full-range mode avoids division in the hot loop. For its bounded numerator `n`, division by the Mersenne number `2^B-1` is exactly:

```text
q = (n + 1 + (n >> B)) >> B
```

Reduction guarantees `b < B`; even the 16-to-15-bit case keeps the numerator and corrected numerator below `2^31`. The scalar and SIMD paths use this same identity and produce bit-identical results. The test oracle independently uses ordinary integer division.

The scalar option describes the source implementation; an optimizing compiler may still auto-vectorize parts of it. `simd=1` explicitly expresses vector operations in Odin. Baseline x64 assembly was inspected and contains packed XMM loads, additions, shifts, and multiplication, without AVX or wider-register instructions. Other targets use Odin's portable lowering; a target without hardware SIMD selects the scalar kernel.

## Validation and measured performance

The advanced suite covers both scaling modes, all input depths, multiple output depths, widths around vector and tile boundaries, all 1024 codes of a ten-bit input, malformed high samples, RGB and subsampled YUV, independent plane phases, concurrent requests, unchanged source frames, preserved properties, identity behavior, and invalid inputs. Scalar and SIMD pixels are compared against an independent integer oracle.

```console
uv run tests/advanced.py
uv run tests/benchmark_dither.py
```

Use each runner's `--runtime` option when selecting an existing local Python runtime package directory. See the repository's testing documentation for the configured environment.

One measured Windows AMD64 run used VapourSynth R79 API 4.2, Odin `dev-2026-09-nightly:a2fb372`, and `-vet -o:speed -microarch:x86-64`. On an AMD Family 25 Model 97 Stepping 2 CPU, the 1920 × 1080 Gray16-to-Gray8 benchmark used four worker threads and four outstanding requests, 16 warmup frames, and five measured runs of 256 frames per implementation:

| Implementation | Median elapsed time | Frame throughput |
| --- | ---: | ---: |
| Scalar source | 0.136815 s | 1871.14 frames/s |
| Explicit SIMD | 0.048459 s | 5282.83 frames/s |

The measured median time ratio was **2.823×**. These are end-to-end frame timings, including scheduling, output allocation, Python request delivery, and release. The benchmark uses a reusable in-memory source, requests unique output frames, and disables output caching. It verifies exact scalar/SIMD parity before measuring. Results depend on the machine, runtime, compiler, format, size, and request concurrency; they are not a performance guarantee.

Runtime tests here covered Windows x64 with R76 and R79. Compile checks also covered Windows x86, Linux x64, and macOS ARM64. The algorithm, tile, and integer outputs are designed to remain deterministic across those targets; cross-target compilation alone does not replace runtime testing on them.
