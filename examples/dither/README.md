# Output-format binding example

This example demonstrates format negotiation, frame allocation, and planar
sample storage through the VapourSynth Odin bindings.

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

## Binding concepts

This example demonstrates output-format negotiation with `queryVideoFormat`,
new frame allocation with `newVideoFrame`, and independent source/destination
sample widths and strides. The dither operation supplies a concrete workload
for those API calls. Start with the Invert example for callback scheduling and
reference ownership.

`src/plugin.odin` contains registration, argument validation, instance ownership,
frame callbacks, and error paths. The row operation is separate, so these binding
calls can be studied independently of the arithmetic.

## Demonstration inputs

The input has a constant integer Gray, RGB, or YUV format with 8–16 bit samples.
The call is `core.odin_dither.Dither(clip, bits=8, seed=0, simd=1, scale=0)`.

| Argument | Demonstration contract |
| --- | --- |
| `bits` | Effective depth from 1 through the input depth; output storage is at least 8 bits |
| `seed` | Tile phase from 0 through 4095 |
| `simd` | Select an equivalent scalar or vector processing path |
| `scale` | 0 uses power-of-two code scaling; 1 maps the full input code range |

For example, two-bit output uses values 0, 85, 170, and 255 in an eight-bit
container. This illustrates the distinction between sample storage and the
values written by an operation. Zero bits is rejected. No mode performs color
management or interprets range metadata.

The preview supplies synthetic inputs and registers outputs for visual inspection.
Its shallow-ramp comparison uses the same 20× display contrast gain on both sides;
the low-bit color views have no display gain.

The tile is checked into `src/blue_noise.odin`. Its generator preserves the
source data's provenance and can verify it with `uv run generate_tile.py --check`.
The bindings repository's `tests/advanced.py` checks output samples, formats,
properties, concurrency, and retained source frames.
