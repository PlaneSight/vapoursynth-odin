# 1. Inspect a core

This example demonstrates runtime loading, API version negotiation, and core ownership
through the VapourSynth Odin bindings.

## Build this project

Install [Odin](https://odin-lang.org/docs/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then run here:

```console
uv run build.py
uv run build.py --run
```

You can copy this entire directory into a new location and run the same commands.
It has its own Python pin, lockfile, license, sources, and build configuration.
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

Load a VapourSynth library, create a core, and print its version and worker count.
This introduces the optional `easy` package and the acquire/check/`defer` pattern.
Deferred cleanup releases the core before unloading the library.

Run from this directory:

```console
uv run build.py --run
```

The helper builds the native executable and selects the core library from the
uv environment. The same command works on every supported platform. To compile
without executing it, run `uv run build.py`. The example
disables automatic plugin loading, so it does not depend on installed plugins.
See the [build guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md) for prerequisites.
