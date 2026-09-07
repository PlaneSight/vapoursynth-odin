# Invert filter plugin

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

This example implements a complete video filter with the raw API: plugin
registration, argument validation, instance ownership, dependency declarations,
the frame activation protocol, and processing planar pixels with row strides.

Build and preview from this directory:

```console
uv run build.py
uv run --group preview vsview preview.vpy
```

The build command builds the plugin under `.build` and opens [preview.vpy](preview.vpy)
in VSView. The optional group installs the viewer and Qt and requires Python
3.12–3.14. Output `0` compares the synthetic source and inversion side by side;
outputs `1` and `2` expose them separately. The documentation renders the same
nodes. See the [preview guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md) for
headless checks, multiple examples, and generated images.

To build without opening a viewer:

```console
uv run build.py
```

The build command selects the native architecture and library extension automatically.
The plugin requires VapourSynth core API 4.2 and links to the platform C runtime
for `malloc`/`free`.

Load the plugin in a VapourSynth Python script:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/invert{suffix}").resolve()))
source = vs.core.std.BlankClip(width=640, height=360, format=vs.RGB24,
                             color=[32, 96, 160], length=24)
vs.core.odin_invert.Invert(source).set_output()
```

The checked-in `preview.vpy` uses `.build/invert` and selects the platform
extension automatically. Its source is a generated colorful scene rather than
the constant clip above, so no input video file is required.

The filter accepts constant format and dimensions with 8-16 bit integer Gray,
RGB, or YUV samples. It computes `(1 << bitsPerSample) - 1 - sample` for every
plane. Plane dimensions come from the actual frame, so chroma subsampling is
respected; source and destination strides are obtained independently. Padding
bytes are not treated as pixels. Float and variable format/dimension clips
produce an invocation error.

Inversion uses the full integer code range, including for limited-range YUV.
For example, a 10-bit sample of 100 becomes 923. This is an arithmetic
demonstration, not a color-managed photographic negative. `copyFrame` retains
the source properties, and `getWritePtr` makes the output pixels writable
without modifying the input.

The instance retains one source-node reference until `free_invert`. Its data
is immutable during frame processing, permitting `fmParallel`. Each frame
request first declares its upstream dependency with `requestFrameFilter`, then
retrieves it with `getFrameFilter` during `arAllFramesReady`. The callback releases
its acquired source-frame reference and transfers its output-frame reference
to VapourSynth.

All callbacks use `proc "system"` and only context-free operations, so they do
not need Odin's implicit context on VapourSynth's worker threads. Instance
allocation is checked, and the matching `free_invert` releases both the source
node and the C allocation on normal destruction or filter-creation failure.

See the [official filter API documentation](https://www.vapoursynth.com/doc/api/vapoursynth4.h.html)
for the callback and ownership contracts.
