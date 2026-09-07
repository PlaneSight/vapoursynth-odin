# Identity plugin

This example demonstrates plugin registration and node-reference transfer
through the VapourSynth Odin bindings.

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

This is the smallest plugin example. `VapourSynthPluginInit2` registers
`odin_example.Identity`, which gets an input node reference and transfers it into
the output map. It demonstrates plugin registration and reference ownership
before introducing a frame-processing callback.

Build and preview from this directory with uv and Odin installed:

```console
uv run build.py
uv run --group preview vsview preview.vpy
```

The optional group installs VSView and Qt and requires Python 3.12–3.14.
The build command builds `.build/plugin` with the platform's shared-library
extension and opens [preview.vpy](preview.vpy). Named outputs show a side-by-side
comparison (`0`), original synthetic scene (`1`), and identity output (`2`).
Both sides should match exactly. `uv run build.py --check` checks this script's outputs without a GUI; the [preview guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/docs/content/guides/previewing-examples.md)
explains the shared workflow. Documentation images come from these same outputs.

To build without opening a viewer:

```console
uv run build.py
```

Load the resulting native library from a script run in this directory:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/plugin{suffix}").resolve()))
source = vs.core.std.BlankClip(width=64, height=48, length=1)
vs.core.odin_example.Identity(source).set_output()
```

The callback uses `proc "system"` and calls only the raw API, so it needs no
Odin context. `mapConsumeNode` consumes the reference even if setting the output
fails; there is no second `freeNode` after that call.

Continue with [invert](https://github.com/PlaneSight/vapoursynth-odin/blob/main/examples/invert) for actual pixel processing. See the
[example guide](https://github.com/PlaneSight/vapoursynth-odin/blob/main/examples/README.md) for platforms and prerequisites.
