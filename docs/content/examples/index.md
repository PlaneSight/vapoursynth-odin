# Binding usage examples

The examples demonstrate the bindings through runtime loading, typed properties, ownership, callbacks, and frame allocation. Each directory is an independently buildable Odin package, and every tutorial explains the source that is compiled by the example test runner. You can read the rendered source at the end of each tutorial or edit the corresponding package in your checkout.

The first three examples use the optional `easy` package to make resource ownership and error handling explicit. The fourth exposes the raw API calls behind those operations. The remaining four run inside VapourSynth as shared-library plugins, where the host supplies the API and schedules the work.

## Choose a starting point

| Step | Tutorial | Package | What you will learn |
| --- | --- | --- | --- |
| 1 | [Inspect a core](core-info.md) | `examples/core_info` | Load the runtime, negotiate API 4.2, create a core, inspect its version, and release resources in order. |
| 2 | [Work with properties](properties.md) | `examples/properties` | Write typed map values and distinguish borrowed data, embedded zero bytes, empty arrays, and missing properties. |
| 3 | [Request and read a frame](easy-host.md) | `examples/easy_host` | Invoke a plugin, acquire an independent node reference, request a frame, and compute a checksum without reading padding. |
| 4 | [Host through the raw API](raw-host.md) | `examples/host` | Resolve the entry point, use C return codes, inspect result-map errors, and manage raw references. |
| 5 | [Register an identity plugin](identity-plugin.md) | `examples/plugin` | Export the plugin entry point, declare a function signature, and transfer an owned node reference. |
| 6 | [Implement an invert filter](invert-plugin.md) | `examples/invert` | Declare dependencies, respond to activation reasons, process planar samples, and manage a parallel filter's lifetime. |
| 7 | [Negotiate an output format](dither-plugin.md) | `examples/dither` | Negotiate the output format, allocate new frames, and respect each plane's storage and stride. |
| 8 | [Own native-library resources](haldlut-plugin.md) | `examples/haldlut` | Combine the frame API with a foreign library, validate input, and release persistent resources. |

For a host application, start at step 1 and work through step 4. For a filter plugin, skim the [ownership guide](../guides/ownership.md), then work through steps 5 and 6. The identity function establishes the registration and reference-transfer contract before the invert filter introduces frame scheduling.

## Before you start

Follow [installation](../getting-started/installation.md), then run these commands
from the repository root. Each example can also be copied into its own project;
see [build and preview](../guides/previewing-examples.md).

## Build and inspect the examples

```console
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

The first command compiles all eight binding examples. The second reuses
those binaries and opens all four plugin demonstrations in VSView. Select individual
filters with `preview invert dither`; every script supplies named comparison,
source or baseline, and filtered outputs.

For an optional headless check after compiling, run
`uv run tools/examples.py check --no-build`. It executes the four plugin `.vpy`
scripts and requests their output frames without opening a window.

The [preview guide](../guides/previewing-examples.md) covers selection, output
interpretation, and headless rendering. The screenshots in these tutorials are
generated from the same scripts during each documentation build.

## Run a single host

The core-information example is the shortest environment check:

```console
uv run tools/run_host.py core_info
```

The helper builds the selected executable and supplies the core library from
the active Python environment. Substitute another host name from the table to
run it. To build a host without running it, use
`uv run tools/examples.py build core_info`.

For a separately installed runtime, see
[loading and linking](../guides/loading-and-linking.md). A successful example
exits with status zero; a reported failure exits with status one.

## Run the example suites

```sh
uv run tests/examples.py
uv run tests/advanced.py
```

The introductory runner builds the first six packages into `.build/examples`, runs the host executables, loads identity and invert, and checks their behavior. It exercises every active pixel for Gray8, RGB24, YUV420P10, and Gray16 inversion; concurrent requests; custom frame properties; source preservation; double inversion; unsupported input; and missing-library diagnostics.

The advanced runner builds dither and Hald CLUT into `.build/advanced`. It compares scalar and SIMD quantization against independently calculated pixels, exercises tetrahedral interpolation against a separate numerical reference, and tests malformed inputs and resource lifetimes. Both runners print the selected runtime.

To select an existing runtime directory containing the Python module:

```sh
python tests/examples.py --runtime .build/runtime
```

The `.build/runtime` directory is an example local layout, not a checked-in dependency. The runner does not install or download a runtime. Use `--library` for an explicit core-library path and `--odin` for a compiler executable. The [testing guide](../maintenance/testing.md) explains how these checks fit with the ABI and `easy` suites.

## Read examples as ownership contracts

Watch for the point at which each resource becomes owned, the first deferred release, and any transfer to another owner. A node describes a graph; a requested frame contains evaluated data. A property or plane view borrows memory from another object and needs no separate release, but its owner must remain alive.

The same distinctions recur as the examples grow. The [map guide](../guides/maps.md), [frame guide](../guides/frames.md), and [error guide](../guides/errors.md) collect the rules used throughout the tutorials.
