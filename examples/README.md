# Examples

Each subdirectory is an independently buildable example. Read them in this
order, starting with the optional `easy` interface and then inspecting the raw
API used to implement host and plugin behavior.

| Step | Example | What it teaches |
| --- | --- | --- |
| 1 | [core_info](core_info) | Load the library, request API 4.2, create a core, print its information, and clean up. |
| 2 | [properties](properties) | Typed map values, binary data with embedded zero bytes, borrowed arrays, and empty versus missing properties. |
| 3 | [easy_host](easy_host) | Invoke `std.BlankClip`, retain a node, request a frame, and read padded rows through the idiomatic interface. |
| 4 | [host](host) | Perform hosting operations directly through the raw API table; compare with the previous example. |
| 5 | [plugin](plugin) | Export a plugin entry point, register `Identity`, and transfer a node reference. |
| 6 | [invert](invert) | Implement an actual filter: dependencies, activation reasons, instance lifetime, parallel requests, and sample processing. |
| 7 | [dither](dither) | Reduce bit depth with reproducible blue noise, exact SIMD kernels, scalar tails, range scaling, and measured performance. |
| 8 | [haldlut](haldlut) | Use Odin's bundled stb image decoder, cache a Hald lookup table, and apply tetrahedral color interpolation. |

For a ready-to-run runtime environment, use `uv sync --locked` followed by
`uv run tools/run_host.py core_info`. The helper passes the core library from
the active Python environment to Odin. An explicit `uv build` packages all four
plugins into a native wheel; see the [packaging guide](../docs/guides/python-packaging.md).

The first four are executables. Build or run them from the repository root:

```console
odin run examples/core_info -- /absolute/path/to/libvapoursynth.dll
odin run examples/properties -- /absolute/path/to/libvapoursynth.dll
odin run examples/easy_host -- /absolute/path/to/libvapoursynth.dll
odin run examples/host -- /absolute/path/to/libvapoursynth.dll
```

The path is optional when the core library is available to the platform loader.
Use `libvapoursynth.so` on Linux and `libvapoursynth.dylib` on macOS. API 4.2
requires R74 or newer. All host examples disable plugin autoloading; those that
invoke filters use the core's built-in `std` plugin. They need no third-party
source plugins or video files. Set up library loading before creating the core; release all objects
before destroying the core and unloading the library.

The last four are shared-library plugins. The two introductory plugins build as:

```console
odin build examples/plugin -build-mode:dll -out:odin_identity.dll
odin build examples/invert -build-mode:dll -out:odin_invert.dll
```

Use `.so` or `.dylib` output extensions on the respective platforms. Each plugin
has a distinct identifier and namespace, so both can be loaded together:

```python
import vapoursynth as vs

vs.core.std.LoadPlugin(path="/absolute/path/to/odin_identity.dll")
vs.core.std.LoadPlugin(path="/absolute/path/to/odin_invert.dll")
source = vs.core.std.BlankClip(format=vs.RGB24, color=[32, 96, 160], length=24)
identity = vs.core.odin_example.Identity(source)
vs.core.odin_invert.Invert(identity).set_output()
```

Invert supports planar 8–16 bit integer video, including subsampled YUV. It
subtracts every sample from the format's maximum value, preserving source pixels
and frame properties. Floating-point and variable-format clips produce clear
errors. See its [README](invert/README.md) for the arithmetic and callback contract.

## Run all examples and their checks

The introductory test runner builds its six examples into `.build/examples`, runs the hosts,
and loads both plugins into VapourSynth. It verifies pixel values across several
formats, frame properties, source immutability, concurrent requests, invalid input,
and missing-library diagnostics.

With VapourSynth installed in the current Python environment:

```console
python tests/examples.py
```

To use a local directory that contains the Python module:

```console
python tests/examples.py --runtime .build/runtime
```

Use `--library` to specify a core library path and `--odin` to select the compiler.
The runner does not install or download dependencies.

The advanced suite builds dither and Hald CLUT with optimization and tests them
against independent numerical oracles. The dither benchmark measures scalar and
SIMD throughput after checking output parity:

```console
uv run tests/advanced.py
uv run tests/benchmark_dither.py
```
