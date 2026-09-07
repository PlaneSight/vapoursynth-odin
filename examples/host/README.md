# Raw host

This executable loads the core dynamically and performs every operation through
the raw `VSAPI` table. It creates a 64 × 48 Gray8 BlankClip, requests frame zero,
and checks its first pixel. Explicit error checks and `defer` statements show
the C API's reference and object lifetimes.

```console
uv run tools/run_host.py host
```

The helper builds the executable and selects the core library from the uv
environment on every supported platform. Use
`uv run tools/examples.py build host` to compile without executing it.

Compare it with [easy_host](../easy_host) to see the typed wrapper interface.
See the [example guide](../README.md) for platform paths and prerequisites.
