# 1. Inspect a core

Load a VapourSynth library, create a core, and print its version and worker count.
This introduces the optional `easy` package and the acquire/check/`defer` pattern.
Deferred cleanup releases the core before unloading the library.

Run from the repository root:

```console
odin run examples/core_info -- /absolute/path/to/libvapoursynth.dll
```

The path is optional; `easy.DEFAULT_LIBRARY` selects the platform's library name.
Use the appropriate `.so` or `.dylib` on Linux or macOS. The loader must also be
able to locate the library's dependencies. The example disables automatic plugin
loading, so it does not depend on plugins installed on the machine.
