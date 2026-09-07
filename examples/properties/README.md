# 2. Read and write map properties

This example demonstrates typed map access, borrowed data, and property errors
through the VapourSynth Odin bindings.

## Build this project

Install [Odin](https://odin-lang.org/docs/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then run here:

```console
uv run build.py
uv run build.py --run
```

You can copy this entire directory into a new location and run the same commands.
It has its own Python pin, lockfile, sources, and build configuration.
The first build downloads the exact bindings commit and verifies the archive
checksum declared in `pyproject.toml`; later builds reuse `.deps/`. Odin is an
external prerequisite. Outputs go in `.build/`.
Both generated directories and the dependency cache are ignored by Git.

`src/` contains the Odin implementation. `build.py` maps its `deps:vapoursynth`
imports to the pinned bindings and reuses that dependency's cross-platform
native build support. To test local bindings, pass
`uv run build.py --bindings /absolute/path/to/vapoursynth-odin`.

To turn this example into your own project, edit `[project]` and `[tool.odin]`
in `pyproject.toml`, then run `uv lock`.

## Walkthrough

Create a map and round-trip integers, floating-point values, text, binary data,
and arrays. The binary payload contains a zero byte, demonstrating why map data
uses an explicit length. An existing empty array and an absent key produce
different results.

Run from this directory:

```console
uv run build.py --run
```

The helper builds the executable and selects the core library from the uv
environment on every supported platform. Use
`uv run build.py` to compile without executing it.
See the [build guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md) for prerequisites.

The setters copy their inputs into the map, so the local arrays in
`write_properties` can go out of scope when that procedure returns. The strings
and slices returned by getters borrow the map's storage: treat them as read-only,
and consume or copy them before changing or destroying the map. The example reads
everything while the map is alive and performs no further mutations.
