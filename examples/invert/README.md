# Invert filter plugin

This example implements a complete video filter with the raw API: plugin
registration, argument validation, instance ownership, dependency declarations,
the frame activation protocol, and processing planar pixels with row strides.

Build and preview from the repository root:

```console
uv run --group preview tools/examples.py preview invert
```

The command builds the plugin under `.build/examples` and opens [demo.vpy](demo.vpy)
in VSView. The optional group installs the viewer and Qt and requires Python
3.12–3.14. Output `0` compares the synthetic source and inversion side by side;
outputs `1` and `2` expose them separately. The documentation renders the same
nodes. See the [preview guide](../../docs/guides/previewing-examples.md) for
headless checks, multiple examples, and generated images.

To build without opening a viewer:

```console
uv run tools/examples.py build invert
```

The command selects the native architecture and library extension automatically.
The plugin requires VapourSynth core API 4.2 and links to the platform C runtime
for `malloc`/`free`.

Load the plugin in a VapourSynth Python script:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/examples/invert{suffix}").resolve()))
source = vs.core.std.BlankClip(width=640, height=360, format=vs.RGB24,
                             color=[32, 96, 160], length=24)
vs.core.odin_invert.Invert(source).set_output()
```

The checked-in `demo.vpy` uses `.build/examples/invert` and selects the platform
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
