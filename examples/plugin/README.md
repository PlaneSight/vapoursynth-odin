# Identity plugin

This is the smallest plugin example. `VapourSynthPluginInit2` registers
`odin_example.Identity`, which gets an input node reference and transfers it into
the output map. It demonstrates plugin registration and reference ownership
before introducing a frame-processing callback.

```console
odin build examples/plugin -build-mode:dll -out:odin_identity.dll
```

```python
import vapoursynth as vs

vs.core.std.LoadPlugin(path="/absolute/path/to/odin_identity.dll")
source = vs.core.std.BlankClip(width=64, height=48, length=1)
vs.core.odin_example.Identity(source).set_output()
```

The callback uses `proc "system"` and calls only the raw API, so it needs no
Odin context. `mapConsumeNode` consumes the reference even if setting the output
fails; there is no second `freeNode` after that call.

Continue with [invert](../invert) for actual pixel processing. See the
[example guide](../README.md) for platforms and prerequisites.
