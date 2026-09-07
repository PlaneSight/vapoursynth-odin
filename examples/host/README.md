# Raw host

This executable loads the core dynamically and performs every operation through
the raw `VSAPI` table. It creates a 64 × 48 Gray8 BlankClip, requests frame zero,
and checks its first pixel. Explicit error checks and `defer` statements show
the C API's reference and object lifetimes.

```console
odin run examples/host -- /absolute/path/to/libvapoursynth.dll
```

Compare it with [easy_host](../easy_host) to see the typed wrapper interface.
See the [example guide](../README.md) for platform paths and prerequisites.
