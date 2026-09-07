# Dither Plus

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

A standalone VapourSynth plugin for comparing integer quantizers and dithering
methods. The original [`examples/dither`](https://github.com/PlaneSight/vapoursynth-odin/blob/main/examples/dither/README.md)
remains the focused blue-noise tutorial. This plugin adds Bayer ordered dither,
nearest rounding, serpentine Floyd–Steinberg and Sierra Lite error diffusion,
RGB threshold correlation, and deterministic animated masks.

## Build, inspect, and render

Run from this directory with Odin and uv installed:

```console
uv run build.py
uv run build.py --check
uv run --group preview vsview preview.vpy
```

The same command works on the supported Windows, Linux, and macOS targets. It
writes `.build/dither_plus.dll`, `.so`, or `.dylib` for the running
Python process. The optional preview group supplies VSView. The repository-wide build, preview, documentation, and bundle commands
also include this plugin.

The preview has twelve named outputs: the RGB16 source at `0`, five methods at
`1`–`5`, neutral RGB comparisons at `6`–`7`, and an animated fade/pan comparison
at `8`–`11`. All method comparisons use two effective bits in RGB8, with no
contrast gain. Seven static filter outputs generate the documentation images.
To regenerate the full documentation, run these commands from the original
bindings repository root:

```console
uv run tools/render_showcase.py
uv run --group docs tools/docs.py build
```

## Python interface

After loading the library, call:

```python
result = core.odin_dither_plus.Dither(
    clip,
    bits=2,
    mode="blue_noise",
    seed=0,
    simd=1,
    scale=1,
    corplane=1,
    dyn=0,
)
```

Defaults are `bits=8`, `mode="blue_noise"`, `seed=0`, `simd=1`, `scale=0`,
`corplane=0`, and `dyn=0`. Input must have constant dimensions and format, with
8–16 bit integer Gray, RGB, or YUV samples. The requested depth is `1` through
the input depth. Output depths below eight use an eight-bit container, expanding
the quantized levels to `round(q * 255 / (2**bits - 1))`. Zero is rejected.

| Mode | Behavior |
| --- | --- |
| `none` | Nearest rounding; no spatial threshold pattern. |
| `bayer` | An 8 × 8 ordered threshold matrix. |
| `blue_noise` | The tutorial's 64 × 64 void-and-cluster rank tile. |
| `floyd_steinberg` | Serpentine diffusion with weights 7/16, 3/16, 5/16, 1/16. |
| `sierra_lite` | Serpentine diffusion with weights 1/2, 1/4, 1/4. |

`scale=0` uses power-of-two code scaling. `scale=1` maps the entire input
interval to the effective output interval. Neither performs a full/limited
range conversion or interprets transfer functions. Properties and subsampling
are preserved. Low-bit YUV is useful for inspecting component quantization;
use full-range RGB and `scale=1` for the demonstrated low-bit color scenes.

`corplane=1` shares threshold coordinates between planes. For RGB, equal input
channels then receive equal rounding decisions. `corplane=0` offsets each plane
as in the tutorial. `seed` selects the spatial phase, from 0 through 4095.
These options affect the masked methods; nearest rounding and error diffusion
have no mask. Diffusion processes equal RGB channels identically on its own.

`dyn=1` shifts a blue-noise or Bayer mask by `(13*n, 37*n)` for frame `n`. The
pattern repeats after 64 frames for blue noise and eight for Bayer. It is a
moving spatial mask, not spatiotemporal blue noise. Other methods reject
`dyn=1`. Every flag accepts only `0` or `1`.

The pointwise modes use the scalar or sixteen-lane SIMD quantizers selected by
`simd`. Supported x64 machines select AVX2 at runtime. Error diffusion uses a
separate scalar, serpentine scan with per-frame scratch rows and double-precision
error accumulation; `simd` does not change it. Frames remain independent and
can run in parallel. No method carries error across video frames.

See the [full plugin guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/plugins/dither-plus.md) for the argument
contract, generated comparisons, numerical boundaries, and implementation design.
