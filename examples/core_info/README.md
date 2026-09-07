# 1. Inspect a core

Load a VapourSynth library, create a core, and print its version and worker count.
This introduces the optional `easy` package and the acquire/check/`defer` pattern.
Deferred cleanup releases the core before unloading the library.

Run from the repository root:

```console
uv run tools/run_host.py core_info
```

The helper builds the native executable and selects the core library from the
uv environment. The same command works on every supported platform. To compile
without executing it, run `uv run tools/examples.py build core_info`. The example
disables automatic plugin loading, so it does not depend on installed plugins.
See the [build guide](../../docs/guides/previewing-examples.md) for prerequisites.
