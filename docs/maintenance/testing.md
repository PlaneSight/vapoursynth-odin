---
title: Testing and verification
description: Reproduce ABI and ownership checks, introductory and advanced runtime suites, dither benchmarks, and native wheel verification.
---

# Testing and verification

The repository checks three different boundaries: whether Odin accepts the
declarations, whether those declarations match the pinned C ABI, and whether
the resulting programs behave correctly with a real VapourSynth runtime.
Run the checks that exercise the boundary you changed. A successful compile
alone does not establish ABI compatibility or correct reference ownership.

All commands below run from the repository root. Generated probes, executables,
plugin libraries, and test fixtures belong in the ignored `.build` directory.
Explicit distribution builds write their wheel and source archives to `dist`.

## Requirements by check

| Check | Required tools | VapourSynth installation |
| --- | --- | --- |
| Package and example type checking | Odin; Hald also needs Odin's native stb library | None |
| C/Odin ABI verification | Python 3.10+, Odin, native C compiler | None; headers are checked in |
| `easy` ownership and error suite | Odin, matching core shared library | Core API 4.2 |
| Six introductory examples | Project Python environment, Odin, matching Python module and core | Core API 4.2 |
| Dither and Hald correctness; dither benchmark | Project Python environment, Odin, and the Hald native build prerequisites below | Core API 4.2 |
| Native wheel build and installation check | Project Python environment, uv, Odin, and the Hald native build prerequisites below | Installed-wheel check uses a matching Python runtime |
| Documentation | Project Python environment, Odin, and the `docs` dependency group | Core API 4.2, supplied by the docs group |

See [installation](../getting-started/installation.md) for the compiler and runtime
setup, and [compatibility](compatibility.md) for the exact environment previously
verified. Do not infer runtime support on a target from another target's results.
The Python project requires **Python 3.12 or newer**. Some standalone verification
scripts use Python 3.10-compatible syntax, but that does not lower the project's
requirement or the installed VapourSynth distribution's requirement.

## Select the development environment

```console
uv sync --locked
uv run tools/run_host.py core_info
```

`uv sync --locked` creates the project environment from `uv.lock`. The root
project is not installed as an editable package, so synchronizing dependencies
does not build or autoload this repository's plugins. `run_host.py` passes the
core library from the active VapourSynth Python package to the selected Odin
host. The recorded uv environment used CPython 3.14.6 and VapourSynth R79, which
provides core API 4.2. R76 remains the unchanged header baseline.

Use `uv run` for the Python commands below. An existing environment can also run
the scripts directly with its own `python`. The
[Python environment and wheel guide](../guides/python-packaging.md) explains
dependency selection, plugin discovery, and platform requirements.

## Check the Odin packages

These checks do not load the core library:

```console
odin check . -no-entry-point -vet
odin check easy -no-entry-point -vet
odin check vsscript -no-entry-point -vet
odin check examples/core_info -vet
odin check examples/properties -vet
odin check examples/easy_host -vet
odin check examples/host -vet
odin check examples/plugin -no-entry-point -vet
odin check examples/invert -no-entry-point -vet
odin check examples/dither -no-entry-point -vet
```

The library packages and plugins have no application `main`; this is why those
commands specify `-no-entry-point`. The optional `link` packages are exercised
by a consuming application when the platform's import library or shared library
is available. A dynamic host does not need that link-time dependency.

Build Hald through the common helper so its `stb:image` import receives the
correct collection and any missing Unix image libraries are prepared:

```console
uv run tools/examples.py build haldlut
```

The helper reuses Odin's supplied stb archives or compiles missing Unix archives
privately under `.build` with `cc` and `ar`; see the
[Hald walkthrough](../examples/haldlut-plugin.md#import-an-odin-vendor-library).
The recorded Windows cross-target checks do not establish native Hald execution
on Linux or macOS.

To type-check another target, add Odin's `-target` option. For example:

```console
odin check . -no-entry-point -vet -target:windows_i386
odin check easy -no-entry-point -vet -target:linux_amd64
odin check examples/invert -no-entry-point -vet -target:darwin_arm64
odin check examples/dither -no-entry-point -vet -target:linux_amd64
```

These commands check the selected target's declarations and conditional code.
They do not execute a program on that target, exercise its dynamic loader, or
verify a native C compiler's layout there.

## Compare the C and Odin ABI

```console
uv run tests/abi.py
```

The runner preprocesses the checked-in R76 headers twice: once with
`VS_USE_API_42` and `VSSCRIPT_USE_API_42`, then again with the experimental
`VS_GRAPH_API` extension. It generates independent C and Odin probes and compares:

- Integer constants and packed API versions.
- Struct sizes and alignments.
- Field offsets, including every stable core function slot and the graph suffix.
- Representative calls across C/Odin scalar, pointer, and callback boundaries.

The current reference produces **435 stable measurements** and **439 extended
measurements**. Both modes also run the C/Odin call probes. Successful output
includes lines of this form:

```text
PASS stable: 435 sizes, alignments, field offsets and constants; C/Odin calls passed.
PASS graph: 439 sizes, alignments, field offsets and constants; C/Odin calls passed.
```

The script can also run as `python tests/abi.py` without an installed VapourSynth
library. The C shim supplies representative API implementations, catching
declaration mistakes without depending on a machine's multimedia setup.

### Select the toolchain

```console
uv run tests/abi.py --cc clang --odin odin
```

`--cc` accepts a compiler executable; the `CC` environment variable is also
recognized. Without either, the runner looks for MSVC on Windows, then `cc`,
`clang`, or `gcc`. When it discovers an installed MSVC compiler, it obtains the
Visual Studio developer environment for its child processes. It does not change
the parent shell's environment.

Use a native C compiler and an Odin compiler targeting the same architecture.
The probe executables are run locally. Keep `.build/abi` after a failure: its
generated source makes a mismatched offset or constant straightforward to inspect.

!!! warning "A cast can hide an ABI error"
    Do not fix a layout failure by forcing pointer casts or weakening the check.
    Compare the declaration to the pinned header. Field order, `c.int`, pointer
    indirection, and the `"system"` calling convention are part of the contract.

## Exercise the idiomatic interface

Pass the absolute path to the core library that will be used by the test process:

=== "Windows"

    ```powershell
    odin run tests/easy -- "C:/path/to/libvapoursynth.dll"
    ```

=== "Linux"

    ```sh
    odin run tests/easy -- /absolute/path/to/libvapoursynth.so
    ```

=== "macOS"

    ```sh
    odin run tests/easy -- /absolute/path/to/libvapoursynth.dylib
    ```

The suite combines real runtime calls with injected API behavior. This allows it
to cover allocation failure and ownership transfer precisely, alongside actual
map and frame operations. Coverage includes:

- Reference retention, destruction, and transfer on both success and failure.
- Cross-core rejection before references can be passed into an incompatible core.
- Missing, empty, and wrongly typed map properties; embedded zero bytes and arrays.
- Durable diagnostics, truncation, and cleanup of failed invocation results.
- Frame indices, media types, padded rows, typed sample validation, and alignment.

Keep assertions enabled for this test executable: the assertions express the
test expectations. If an assertion fails, record the compiler, runtime version,
architecture, and the failing procedure before changing the test or implementation.

## Run the six introductory examples

Use the Python environment in which `import vapoursynth` resolves to the runtime
you intend to test:

```console
uv run tests/examples.py
```

If the module lives in an isolated local directory, select that directory
explicitly. This command assumes it already exists:

```console
python tests/examples.py --runtime .build/runtime
```

The runner does not download or install packages. It verifies that an explicitly
selected directory actually supplied the imported module, and prints the module
path, core library, and version. To select a core library separately:

```console
python tests/examples.py --runtime .build/runtime --library /absolute/path/to/core-library
```

The library must match the Python runtime and the process architecture. An
unrelated DLL with the right filename is not a valid substitute.

The runner builds the six introductory examples into `.build/examples`: four
host programs (`core_info`, `properties`, `easy_host`, and `host`) and two plugins
(`plugin` and `invert`). It checks the host programs' output and loads both
plugins through VapourSynth's Python API. It
then verifies the identity plugin and the invert filter against Gray8, RGB24,
YUV420P10, and Gray16 fixtures. The invert checks cover every visible pixel,
subsampled planes, padded layouts, retained frame properties, unchanged source
frames, and restoration after applying invert twice. It submits concurrent frame
requests before waiting for their results, and checks rejection diagnostics for
floating-point and variable-format clips.

This is a correctness suite, not a benchmark. It does not establish throughput,
exhaustively explore scheduler interleavings, or test every installed third-party
plugin.

## Check the advanced filters

```console
uv run tests/advanced.py
```

The advanced runner builds `dither` and `haldlut` with `-vet -o:speed` into
`.build/advanced`. On x64 it explicitly selects `-microarch:x86-64`, matching the
native wheel's baseline. It generates its own PNG fixtures using Python's
standard library and compares every active output pixel with independent
reference calculations.

- **Dither: 410 oracle cases and 28 exact-level checks**, covering scalar/SIMD parity,
  both scaling modes, input depths 8–16, effective output depths from 1 through
  the input depth, vector tails, tile and seed
  boundaries, RGB and subsampled YUV planes. Additional checks cover exact
  nominal code points, endpoints, static temporal behavior, malformed sample
  clamping, passthrough, concurrent requests, properties, retained source-frame
  immutability, and invalid inputs. Low-bit checks verify the eight-bit output
  container and its expanded sample levels, including eight-bit input reduced
  to one through seven effective bits. Zero effective bits is rejected.
- **Hald: 81 oracle cases**, covering RGB/RGBA PNG8/16, all five PNG row filters,
  every tetrahedral ordering, nonlinear lookups across multiple cells, input
  depths 8–16, strengths, identity tables, and levels 2, 3, and 8. Boundary checks
  cover Unicode paths, cached data after file deletion, properties, retained
  source frames, unsupported formats and parameters, truncated files, wrong
  dimensions, level 9, excessive decompressed data, and IHDR/IDAT/IEND CRC errors.

Both complete suites passed with R76 and R79 on Windows x64. Select a single
filter while developing it, or use an already existing isolated runtime:

```console
uv run tests/advanced.py --only dither
uv run tests/advanced.py --only haldlut
python tests/advanced.py --runtime .build/runtime
```

The `--runtime` directory must contain the intended VapourSynth Python module.
The runner verifies its provenance and prints the imported module and version.
It performs no package installation.

## Check the standalone Dither Plus plugin

```console
uv run tests/dither_plus.py
uv run tools/examples.py check --no-build dither_plus
```

The first command compares all five methods with independent integer and
diffusion references. It exercises widths around SIMD and tile boundaries,
low-bit expansion, scaling, per-plane correlation, deterministic frame phases,
and invalid parameters. The second requests the first and last frame of every
preview output, including its animated fade and pan. This plugin has its own
suite so adding algorithms does not turn the focused dither tutorial into a
larger product interface.

For a bounded single-thread comparison against the original example:

```console
uv run tests/benchmark_dither_plus.py --no-build --json
```

The default workload is Gray16 and RGB48 to eight bits at 720p, 1080p, and 4K,
using one VapourSynth worker and four queued requests. It records five runs of
eight measured frames after two warmup frames, with method order rotated between
runs. These short defaults are for a first comparison; increase `--frames` and
`--runs` when assessing small differences. See the
[plugin guide](../plugins/dither-plus.md) for algorithm contracts and the preview
comparisons. Keep its measurements separate from the recorded FMTConv study,
which covers the original blue-noise example.

## Measure dither throughput

The [FMTConv comparison](dither-performance.md) measures Odin's blue-noise filter
against FMTConv's `dmode=8` void-and-cluster mode with `core.num_threads = 1`,
across several integer formats and resolutions through 3840 × 2160. Follow its
setup and reproduction commands to select the exact plugin binaries and matching
code-range semantics. `tests/benchmark_fmtconv.py` records per-run samples and
the environment alongside aggregate timings; a benchmark result should retain
that machine-readable report.

For a focused comparison between this plugin's scalar and SIMD implementations:

```console
uv run tests/benchmark_dither.py
```

The benchmark first requires exact scalar/SIMD pixel parity, then builds its
timing around unique output frame indices with output caching disabled. It uses
a reusable in-memory source, warms both modes, alternates their order between
runs, and reports median elapsed time and throughput. The default workload is
1920 × 1080 Gray16 to Gray8, four worker threads and outstanding requests,
16 warmup frames, and five measured runs of 256 frames per mode.

The optimized x64 build uses the same `x86-64` baseline as the wheel. Results
include frame allocation, scheduling, Python request delivery, and release;
they measure end-to-end frame throughput rather than an isolated arithmetic
kernel. The runner bounds runtime and imposes no speedup threshold. Use
`--help` to adjust the workload and record the compiler, runtime, CPU, and
request concurrency with each result. See the
[performance comparison](dither-performance.md) for the recorded measurements
and their environment.

## Build and check native distributions

```console
uv run python -m unittest discover -s tests -p test_packaging.py
uv build --wheel
uv build --sdist
```

The packaging unit tests cover platform selection, baseline compiler arguments,
missing sources, compiler failures, artifact validation, and output containment.
They complement a real native build and installed-wheel check:

```console
uv run tools/packagecheck.py dist/vapoursynth_odin_examples-0.1.0-py3-none-win_amd64.whl
```

Use the actual filename produced by the native build on your platform. The
checker audits the archive's five plugin binaries, native tags, metadata, and
license notices. It then creates an isolated environment under `.build/packaging`,
installs the wheel and the chosen VapourSynth version, starts a fresh process,
and verifies automatic discovery and frame output from all five plugins. This
step invokes uv to install dependencies; unlike the runtime correctness runners,
it can require package downloads. `--runtime 76` selects R76 explicitly; the
default uses the active environment's VapourSynth version.

Native Windows x64 wheel builds and isolated installation checks passed. A
source distribution was also extracted outside the Git checkout and successfully
rebuilt into a wheel, demonstrating that its included sources are sufficient.
For release validation, repeat that clean source-archive build and audit the
resulting wheel. These results do not establish native Linux or macOS wheel
compatibility; Hald's stb library must be built for each target. See the
[packaging guide](../guides/python-packaging.md) for wheel layout and platform
tag requirements.

## Validate documentation changes

Use the locked documentation dependency group:

```console
uv run --group docs tools/docs.py build
uv run python -m unittest discover -s tests -p test_check_docs.py
```

The build compiles the eight examples and Dither Plus and runs the five visual `.vpy` scripts in
fresh processes. Their designated first frames become the generated images in
the site, so broken native code or script evaluation fails the documentation
build. The `docs` group supplies VapourSynth and NumPy; Odin is required, while
VSView and Qt are optional. The build includes real Odin sources in reference
pages and tutorials and invokes Zensical with clean, strict validation.
The offline checker resolves generated local links, assets, and heading fragments.
Its small test suite covers missing targets, encoded paths, site prefixes, and
directory traversal. It does not check availability of external websites.

Complete standalone programs introduced in documentation should also be compiled
or run with the documented toolchain. A syntax-highlighted code block has not
necessarily been type-checked. The [documentation guide](documentation.md)
describes previewing the rendered result and the GitHub Actions workflow.

## Choose checks for a change

| Change | Verification to perform |
| --- | --- |
| C-facing field, constant, callback, or calling convention | Package checks, native ABI suite, relevant target checks |
| Ownership, errors, maps, or row views in `easy` | Package checks, `tests/easy`, affected example runtime checks |
| Identity/invert callbacks or pixel processing | Plugin check and `tests/examples.py` |
| Dither/Hald callbacks, pixel kernels, or PNG loading | Plugin check and `tests/advanced.py`; measure kernel changes with the dither benchmark when relevant |
| Native build hook, distribution contents, or autoloading | Packaging unit tests, native wheel and source-archive builds, isolated `tools/packagecheck.py` |
| Runtime loading or linked declarations | Relevant host execution on the affected platform; linked consumer build when applicable |
| Preview scripts, shared scene construction, or exported image selections | `tools/examples.py check`, render the outputs, inspect the affected VSView views and generated images |
| Prose, navigation, CSS, or source includes | Strict documentation build, local link checker, visual preview |
| Header baseline or API version | Full ABI and runtime suites, followed by the [upgrade procedure](compatibility.md#updating-the-header-baseline) |

When recording a result, include the actual compiler and runtime versions and
distinguish compile checks from native execution. That makes the compatibility
record useful to the next maintainer.
