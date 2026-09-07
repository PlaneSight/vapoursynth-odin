# Identity plugin

This is the smallest plugin example. `VapourSynthPluginInit2` registers
`odin_example.Identity`, which gets an input node reference and transfers it into
the output map. It demonstrates plugin registration and reference ownership
before introducing a frame-processing callback.

Build and preview from the repository root with uv and Odin installed:

```console
uv run --group preview tools/examples.py preview plugin
```

The optional group installs VSView and Qt and requires Python 3.12–3.14.
The command builds `.build/examples/plugin` with the platform's shared-library
extension and opens [demo.vpy](demo.vpy). Named outputs show a side-by-side
comparison (`0`), original synthetic scene (`1`), and identity output (`2`).
Both sides should match exactly. `uv run tools/examples.py check` checks all
four scripts without a GUI; the [preview guide](../../docs/guides/previewing-examples.md)
explains the shared workflow. Documentation images come from these same outputs.

For a minimal manual build and load, create `.build/examples` first, then run:

```console
odin build examples/plugin -build-mode:dll -out:.build/examples/plugin.dll
```

```python
import vapoursynth as vs

vs.core.std.LoadPlugin(path="/absolute/path/to/plugin.dll")
source = vs.core.std.BlankClip(width=64, height=48, length=1)
vs.core.odin_example.Identity(source).set_output()
```

The callback uses `proc "system"` and calls only the raw API, so it needs no
Odin context. `mapConsumeNode` consumes the reference even if setting the output
fails; there is no second `freeNode` after that call.

Continue with [invert](../invert) for actual pixel processing. See the
[example guide](../README.md) for platforms and prerequisites.
