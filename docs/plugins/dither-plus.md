---
title: Dither Plus
description: Compare five integer dithering methods, control RGB noise correlation, and inspect deterministic moving masks with a standalone Odin plugin.
---

# Dither Plus

`odin_dither_plus.Dither` is a standalone plugin for comparing five quantization
methods under the same bit-depth and scaling rules. It adds ordered dither,
error diffusion, shared RGB thresholds, and moving masks to the numerical
foundation of the [blue-noise tutorial](../examples/dither-plugin.md). The
tutorial remains a focused demonstration of the VapourSynth API and SIMD.

This plugin accepts constant-format, constant-dimension Gray, RGB, and YUV video
with 8–16 bit integer samples. It preserves timing, dimensions, subsampling, and
frame properties. Effective depths below eight are stored in an ordinary
eight-bit output format so existing viewers can display them.

## Build and preview

From the repository root, with Odin and uv installed:

```console
uv run tools/examples.py build dither_plus
uv run tools/examples.py check --no-build dither_plus
uv run --group preview tools/examples.py preview --no-build dither_plus
```

The build command selects the native compiler target and library extension on
Windows x64, Linux x64/ARM64, and macOS x64/ARM64. It writes the plugin under
`.build/examples` as `dither_plus.dll`, `dither_plus.so`, or `dither_plus.dylib`.
VSView is supplied by the optional `preview` dependency group. See the
[build and preview guide](../guides/previewing-examples.md) for setup and platform
requirements. The default build, preview, and native wheel commands include
this plugin alongside the eight teaching examples.

For a script outside the preview, load the local library and use an RGB16 clip:

```python
from pathlib import Path
import sys

import vapoursynth as vs

core = vs.core
suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
core.std.LoadPlugin(path=str(Path(f".build/examples/dither_plus{suffix}").resolve()))
source = core.std.BlankClip(
    width=768, height=320, format=vs.RGB48, color=[32768, 32768, 32768],
).std.SetFrameProps(_Matrix=0, _Range=1)
core.odin_dither_plus.Dither(
    source, bits=2, scale=1, mode="blue_noise", corplane=1,
).set_output()
```

When using an installed plugin wheel, VapourSynth discovers the library
automatically; omit the explicit `LoadPlugin` call. The repository preview
deliberately loads the local build so its output reflects the code being edited.

## Compare the methods

These images are native filter output from the same 768 × 320 RGB16 scene.
Every method uses `bits=2`, `scale=1`, and `corplane=1`. There are four stored
values per channel: `0`, `85`, `170`, and `255`. Two-bit RGB therefore permits
64 RGB combinations; it is not a four-color palette. No display contrast gain
is applied.

=== "Nearest rounding"

    ![Two-bit nearest rounding of a color scene and neutral ramp](../assets/generated/dither-plus-none.png){ width="768" height="320" }

=== "Bayer"

    ![Two-bit Bayer ordered dither with shared RGB thresholds](../assets/generated/dither-plus-bayer.png){ width="768" height="320" }

=== "Blue noise"

    ![Two-bit blue-noise dither with shared RGB thresholds](../assets/generated/dither-plus-blue-noise.png){ width="768" height="320" }

=== "Floyd–Steinberg"

    ![Two-bit serpentine Floyd–Steinberg error diffusion](../assets/generated/dither-plus-floyd-steinberg.png){ width="768" height="320" }

=== "Sierra Lite"

    ![Two-bit serpentine Sierra Lite error diffusion](../assets/generated/dither-plus-sierra-lite.png){ width="768" height="320" }

Inspect the images at their original size. Browser scaling or viewer resizing
interpolates neighboring pixels and changes the apparent quantization pattern.
These deliberately severe two-bit conversions make differences easy to see;
they do not establish a quality ranking for ordinary eight-bit video.

| Method | Useful comparison | Processing characteristics |
| --- | --- | --- |
| `none` | Exposes the bands and contours introduced by nearest rounding. | Independent pixels; no mask. |
| `bayer` | Produces a regular ordered pattern with an 8 × 8 period. | Independent pixels using a small repeating threshold matrix. |
| `blue_noise` | Distributes rounding decisions using the tutorial's 64 × 64 void-and-cluster tile. | Independent pixels using 4,096 threshold ranks. |
| `floyd_steinberg` | Carries quantization error into neighboring unprocessed pixels. | A causal serpentine scan with two scratch rows. |
| `sierra_lite` | Uses a smaller diffusion stencil for a different distribution of error. | A causal serpentine scan with fewer weighted updates. |

Nearest, Bayer, and blue noise share the pointwise quantization path. Error
diffusion needs its own scan because a pixel depends on error from preceding
pixels. Its smaller stencil does not by itself prove that Sierra Lite is faster
in a complete video pipeline; compare measured frame throughput on the relevant
formats. The [existing performance study](../maintenance/dither-performance.md)
measures the original blue-noise example, not these new methods.

### Measured throughput

The following 3840 × 2160 results were measured on September 7, 2026, on an
AMD Ryzen 9 7950X3D running Windows 11, VapourSynth R79, and CPython 3.14.6.
All methods convert 16-bit input to eight bits with `scale=0`, `simd=1`,
`corplane=0`, and `dyn=0`. The core has **one worker** and four queued frame
requests. Values are median frames per second across seven runs.

| Method | 4K Gray16 → Gray8 | 4K RGB48 → RGB24 |
| --- | ---: | ---: |
| Original blue-noise example | 1,468.8 | 386.7 |
| `none` | 1,568.8 | 384.8 |
| `bayer` | 1,421.1 | 382.2 |
| `blue_noise` | 1,475.4 | 388.2 |
| `floyd_steinberg` | 12.9 | 4.3 |
| `sierra_lite` | 12.9 | 4.3 |

The new blue-noise path is within the observed timing variation of the original
at 4K. These results do not establish a speed difference between them. The
diffusion scans cost much more per frame; their dependence on preceding pixels
prevents using the independent-pixel SIMD path. Allowing multiple VapourSynth
workers can process separate frames concurrently, but this table measures only
one worker.

Each pointwise run renders 1,024 frames; each diffusion run renders eight.
The input is a reusable constant `BlankClip`, and output caching is disabled.
Timings include output allocation, scheduling, request delivery, and frame
release. Source decoding and display are absent. Method order rotates between
runs. Cache state and scheduling affect this workload: the largest median
absolute deviation among the 4K methods is 6.1%, and some 720p measurements
vary substantially more. Small throughput differences should not be ranked
as algorithmic advantages.

The [complete measurement JSON](../assets/benchmarks/dither-plus.json) includes
720p, 1080p, and 4K Gray16/RGB48 cases, every timing sample, dispersion,
configuration, and binary hashes. Reproduce this run with:

```console
uv run tools/examples.py build dither dither_plus
uv run tests/benchmark_dither_plus.py --no-build --frames 1024 --diffusion-frames 8 --runs 7 --timeout 600 --json
```

## Control colored noise in neutral areas

A neutral RGB input has equal red, green, and blue sample values. With different
mask phases per plane, those channels can round in different directions at the
same pixel. Their spatial average may remain neutral while individual pixels
become colored.

`corplane=1` gives each plane the same threshold coordinates. Equal RGB samples
then receive equal rounding decisions. The comparison below contains a neutral
RGB16 ramp and a central patch at code `32768`, reduced to two bits with blue
noise and full-interval scaling.

=== "Independent plane phases"

    ![Neutral two-bit RGB ramp and constant patch with differently phased thresholds producing colored pixels](../assets/generated/dither-plus-neutral-independent.png){ width="768" height="192" }

=== "Shared plane phases"

    ![The same neutral RGB ramp and patch with shared thresholds preserving equal RGB channels](../assets/generated/dither-plus-neutral-correlated.png){ width="768" height="192" }

The default `corplane=0` preserves the tutorial's per-plane phase behavior.
Correlation changes the appearance of RGB noise; it does not change the set of
available output values. On subsampled YUV, matching plane coordinates do not
represent the same physical pixel grid, so this is not a promise of perceptual
luminance-only noise. Nearest rounding and diffusion have no mask and ignore
`corplane`; diffusion already treats equal RGB planes identically.

## Python argument reference

```python
core.odin_dither_plus.Dither(
    clip,
    bits=8,
    mode="blue_noise",
    seed=0,
    simd=1,
    scale=0,
    corplane=0,
    dyn=0,
)
```

| Argument | Accepted values | Contract |
| --- | --- | --- |
| `clip` | Constant 8–16 bit integer Gray, RGB, or YUV video | Every plane is processed using its own dimensions and strides. |
| `bits` | `1` through the input depth; default `8` | Effective output precision. A request matching the input depth returns the source unchanged after argument validation. |
| `mode` | `"none"`, `"bayer"`, `"blue_noise"`, `"floyd_steinberg"`, `"sierra_lite"` | Exact lowercase method name; default `"blue_noise"`. |
| `seed` | `0`–`4095`; default `0` | Selects the spatial phase for masked methods. Different seed values can be equivalent for the smaller Bayer matrix. |
| `simd` | `0` or `1`; default `1` | Selects scalar or vectorized pointwise processing. It does not change the diffusion scan. |
| `scale` | `0` or `1`; default `0` | Power-of-two code scaling or full-interval scaling, respectively. |
| `corplane` | `0` or `1`; default `0` | Independent or shared mask phase between planes. Ignored by unmasked methods. |
| `dyn` | `0` or `1`; default `0` | Static or frame-dependent mask phase. Only Bayer and blue noise accept `1`. |

Invalid formats, depths, mode names, and flag values fail during filter
creation. Zero bits is rejected: it would provide a single code and make the
low-bit expansion denominator zero. This interface does not implement floating
point input, full/limited range conversion, transfer-function conversion, added
noise amplitude controls, or temporal error diffusion.

## Quantization and low-bit storage

All methods use the same input and effective output intervals. For input depth
`b` and requested depth `k`, write `input_max = 2**b - 1` and
`output_max = 2**k - 1`.

- `scale=0` uses the ideal value `sample / 2**(b-k)`, preserving ordinary
  power-of-two video code scaling. Results at the top of the interval are clipped
  to `output_max`.
- `scale=1` uses `sample * output_max / input_max`, mapping the full input
  interval onto the full effective output interval.

The pointwise dither methods choose the adjacent quantized level using a
precomputed threshold. `none` uses nearest rounding. Error diffusion adds
accumulated error in effective output code units, clamps the corrected value
to `0..output_max`, and rounds with `floor(value + 0.5)`.

For `k < 8`, the quantized integer `q` is stored as
`round(q * 255 / output_max)` in an eight-bit output format. Thus one bit stores
`0` and `255`; two bits stores `0`, `85`, `170`, and `255`; four bits stores
the multiples of `17`. The frame format describes the eight-bit container.

`scale=1` does not convert limited-range YUV to full range. The plugin preserves
frame properties, including range metadata. For the visual color experiments
on this page, use full-range RGB and `scale=1`. Low-bit YUV lets you inspect
component quantization, but a normal YUV-to-RGB viewing transform also applies
its own range and matrix interpretation.

## Moving masks and video behavior

`dyn=1` moves the existing spatial mask by `(13*n, 37*n)` for frame number `n`,
in addition to the seed and plane offsets. Blue noise repeats after 64 frames;
Bayer repeats after eight. Output is determined entirely by the source frame,
frame index, and filter arguments. Seeking or requesting frames out of order
does not change it.

A changed phase does not guarantee changed samples: repeated Bayer thresholds
and particular fractional input levels can produce identical rounding decisions.

This mode is a moving spatial mask. It is **not a spatiotemporal blue-noise
sequence**, and its temporal spectrum has not been optimized. The movement can
make a fixed pattern less attached to the screen while introducing visible
flicker. Playback and compression may change the result further.

The preview's final outputs use a two-second, 24 fps source with a horizontal
pan and a gentle brightness cycle. Select output `11` to compare the static
mask on the left with the moving mask on the right. Outputs `9` and `10`
provide each result separately; output `8` is the RGB16 source. At frame zero
the two masks have the same phase, so a single exported image would not explain
this temporal difference. These animated outputs are intended for playback.

No method accumulates error across video frames. The diffusion algorithms can
still change their spatial error paths as an image moves or fades; they do not
provide a separate guarantee of temporal stability.

## Implementation and resource lifetime

The plugin chooses its pointwise or diffusion processing path during filter
creation. Masked methods prepare an immutable 64 × 64 threshold tile with each
row duplicated for contiguous SIMD reads across wrapping boundaries. Bayer's
8 × 8 matrix repeats within that storage. The blue-noise ranks match the
focused tutorial exactly.

Pointwise processing uses sixteen-lane SIMD when `simd=1`. On supported x64
machines, runtime CPU and operating-system checks select AVX2; other machines
use the portable path. `simd=0` provides the scalar comparison. Changing a
method does not add an algorithm-selection branch for every pixel.

Diffusion processes even rows left to right and odd rows right to left. Each
plane starts with zero error. Floyd–Steinberg distributes error to the next
pixel and three positions on the following row with weights `7/16`, `3/16`,
`5/16`, and `1/16`. Sierra Lite uses `1/2` for the next pixel and `1/4` each
for the backward-diagonal and directly-below pixels. The stencil is mirrored
on right-to-left rows. Error outside the active image is discarded.

Scratch rows hold double-precision error in effective output code units and
belong to the current frame request. Their allocation is checked, and they are
released before that request returns. Filter state contains no shared mutable
diffusion history, so VapourSynth can process separate frames in parallel.

## Reproduce the illustrations

The independent numerical suite and single-thread performance runner are:

```console
uv run tests/dither_plus.py
uv run tests/benchmark_dither_plus.py --no-build --json
```

The benchmark uses `core.num_threads = 1` and four queued requests. Its default
matrix covers 720p, 1080p, and 4K Gray16 and RGB48 input, with all five methods
and the original blue-noise plugin as a reference. Results describe the machine
and workload recorded with them; they do not establish a universal speed order.
The numerical suite checks independent quantization and diffusion references,
format boundaries, and invalid arguments. Visual comparisons complement those
checks by making spatial and temporal artifacts visible.

```console
uv run tools/render_showcase.py
uv run --group docs tools/docs.py build
```

Both routes compile the actual plugin and execute `plugins/dither/demo.vpy`.
Its `DOCUMENTATION_OUTPUTS` mapping exports seven RGB8 outputs. They contain
the five two-bit method comparisons and the two neutral RGB comparisons above.
Generated PNGs are ignored by Git and recreated for each documentation build.
The [documentation pipeline](../maintenance/documentation.md) records the
source script and output hashes; it fails if a graph cannot produce its frames.

| Output | Content |
| --- | --- |
| `0` | Original RGB16 color scene |
| `1`–`5` | Two-bit nearest, Bayer, blue noise, Floyd–Steinberg, and Sierra Lite |
| `6`–`7` | Independent and shared thresholds on the neutral patch and ramp |
| `8` | Original RGB16 animated fade and pan |
| `9`–`10` | Static and moving blue-noise masks on the animation |
| `11` | Side-by-side static and moving mask comparison |

??? example "Preview script used for these comparisons"

    ```python title="plugins/dither/demo.vpy" linenums="1"
    --8<-- "plugins/dither/demo.vpy"
    ```
