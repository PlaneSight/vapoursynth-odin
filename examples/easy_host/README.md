# 3. Invoke a plugin and read a frame

This example demonstrates invocation, node and frame ownership, and checked row views
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

Build a `std.BlankClip` argument map, invoke the built-in plugin, obtain a node,
request a frame synchronously, and compute a checksum over its visible samples.
The clip is 65 x 48 Gray8 with every sample set to 17, giving a checksum of 53040.

Run from this directory:

```console
uv run build.py --run
```

The helper builds the executable and selects the core library from the uv
environment on every supported platform. Use
`uv run build.py` to compile without executing it.
No external plugins or source media are required. See the
[build guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md) for prerequisites.

`make_blank_clip` destroys its temporary maps before returning. `map_get_node`
acquires an independent reference, so the returned node remains valid. The host
also demonstrates `retain_node` and then releases the original reference. Copying
an owned wrapper value with assignment does not acquire a reference.

`read_plane` returns a borrowed view of the frame. `plane_row` exposes only the
visible bytes of a row, using the reported stride to find each row. The odd width
makes padding likely, and the checksum excludes any padding. Treat row slices as
read-only and keep the frame alive until all rows have been consumed.

Cleanup runs in reverse acquisition order: frame, node, core, library. Releasing
an already cleared wrapper is harmless, so the early explicit node release also
works with its deferred cleanup.
