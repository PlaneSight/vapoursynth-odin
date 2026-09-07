# Raw host

This example demonstrates runtime loading and frame requests through the raw API table
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

This executable loads the core dynamically and performs every operation through
the raw `VSAPI` table. It creates a 64 × 48 Gray8 BlankClip, requests frame zero,
and checks its first pixel. Explicit error checks and `defer` statements show
the C API's reference and object lifetimes.

```console
uv run build.py --run
```

The helper builds the executable and selects the core library from the uv
environment on every supported platform. Use
`uv run build.py` to compile without executing it.

Compare it with [easy_host](https://github.com/PlaneSight/vapoursynth-odin/blob/main/examples/easy_host) to see the typed wrapper interface.
See the [example guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/examples/README.md) for platform paths and prerequisites.
