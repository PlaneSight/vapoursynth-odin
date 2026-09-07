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

The separate [Dither Plus plugin](../plugins/dither/README.md) compares additional
dithering methods and RGB noise controls. It lives outside this eight-example
learning sequence, while sharing the repository's build and preview commands.

## Build, check, and see the results

With uv and Odin installed, run from the repository root:

```console
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

The build command compiles these eight packages and Dither Plus into `.build/examples`, choosing
the native target, baseline compiler flags, and executable and shared-library
extensions on Windows x64, Linux x64/ARM64, and macOS x64/ARM64. The preview command
reuses those binaries and launches the five plugin scripts in VSView. Its optional
dependency group supplies VSView and Qt; it requires Python 3.12–3.14 and
VapourSynth R78 or newer. Plain `uv sync` does not install the GUI.

To check the scripts' output frames without a GUI, reuse the same build:

```console
uv run tools/examples.py check --no-build
```

Select filters with `uv run --group preview tools/examples.py preview invert dither`.
Each teaching script exposes output 0 as a side-by-side comparison, output 1 as the
source or rounding baseline, and output 2 as the filtered result. These are named
in VSView. `--no-build` reuses compiled plugins; close a running viewer before
rebuilding its loaded libraries. All source scenes and lookup tables are generated
locally. See the [preview guide](../docs/guides/previewing-examples.md) for details.

`uv run tools/run_host.py core_info` runs an individual host using the core library
from the active Python environment. An explicit `uv build` packages all five
plugins into a native wheel; see the [packaging guide](../docs/guides/python-packaging.md).

## Build or run individual examples

The first four are executables. Build and run them from the repository root:

```console
uv run tools/run_host.py core_info
uv run tools/run_host.py properties
uv run tools/run_host.py easy_host
uv run tools/run_host.py host
```

Each command builds the native executable and supplies the core library from
the active Python environment. To build without executing a host, use
`uv run tools/examples.py build core_info`. All host examples disable plugin
autoloading; those that invoke filters use the core's built-in `std` plugin.
They need no third-party source plugins or video files. For an independently
installed native runtime, see the
[loading guide](../docs/guides/loading-and-linking.md).

The last four are shared-library plugins. Build the two introductory plugins with:

```console
uv run tools/examples.py build plugin invert
```

The build selects the output extensions automatically. Each plugin has a
distinct identifier and namespace, so both can be loaded together:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
for name in ("plugin", "invert"):
    vs.core.std.LoadPlugin(path=str(Path(f".build/examples/{name}{suffix}").resolve()))
source = vs.core.std.BlankClip(format=vs.RGB24, color=[32, 96, 160], length=24)
identity = vs.core.odin_example.Identity(source)
vs.core.odin_invert.Invert(identity).set_output()
```

Invert supports planar 8–16 bit integer video, including subsampled YUV. It
subtracts every sample from the format's maximum value, preserving source pixels
and frame properties. Floating-point and variable-format clips produce clear
errors. See its [README](invert/README.md) for the arithmetic and callback contract.

## Run all examples and their checks

`tools/examples.py check` exercises the visual demonstrations. The following
suites additionally test exact pixel values, ownership, and failure cases.

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

## Generate the documentation images

```console
uv run tools/render_showcase.py
uv run --group docs tools/docs.py build
```

The first command builds the plugins and exports each script's designated
documentation outputs into `.build/showcase`. The second builds the eight
examples and Dither Plus, regenerates the images under `docs/assets/generated`, and validates the
Zensical site. The images come from the same graph and filter calls displayed
in VSView; the renderer does not maintain a second implementation of the scene.
