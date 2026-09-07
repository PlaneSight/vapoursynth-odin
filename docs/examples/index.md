# Learn by example

The examples form a progression from a small host executable to a complete video filter. Each directory is an independently buildable Odin package, and every tutorial explains the source that is compiled by the example test runner. You can read the rendered source at the end of each tutorial or edit the corresponding package in your checkout.

The first three examples use the optional `easy` package to make resource ownership and error handling explicit. The fourth exposes the raw API calls behind those operations. The last two run inside VapourSynth as shared-library plugins, where the host supplies the API and schedules the work.

## Choose a starting point

| Step | Tutorial | Package | What you will learn |
| --- | --- | --- | --- |
| 1 | [Inspect a core](core-info.md) | `examples/core_info` | Load the runtime, negotiate API 4.2, create a core, inspect its version, and release resources in order. |
| 2 | [Work with properties](properties.md) | `examples/properties` | Write typed map values and distinguish borrowed data, embedded zero bytes, empty arrays, and missing properties. |
| 3 | [Request and read a frame](easy-host.md) | `examples/easy_host` | Invoke a plugin, acquire an independent node reference, request a frame, and compute a checksum without reading padding. |
| 4 | [Host through the raw API](raw-host.md) | `examples/host` | Resolve the entry point, use C return codes, inspect result-map errors, and manage raw references. |
| 5 | [Register an identity plugin](identity-plugin.md) | `examples/plugin` | Export the plugin entry point, declare a function signature, and transfer an owned node reference. |
| 6 | [Implement an invert filter](invert-plugin.md) | `examples/invert` | Declare dependencies, respond to activation reasons, process planar samples, and manage a parallel filter's lifetime. |

For a host application, start at step 1 and work through step 4. For a filter plugin, skim the [ownership guide](../guides/ownership.md), then work through steps 5 and 6. The identity function establishes the registration and reference-transfer contract before the invert filter introduces frame scheduling.

## What you need

Run all commands from the repository root. Follow the [quickstart](../getting-started/quickstart.md) to make the Odin compiler and an API 4.2 runtime available. The examples use relative package imports, so their directories must remain inside the repository when built without modifying those imports.

The four host executables accept an optional path to the VapourSynth **core** library. They use `std.BlankClip` where a clip is needed; no video file, source plugin, or Python interpreter is involved in those hosts. Plugin autoloading is disabled when their cores are created, while the built-in `std` plugin remains available.

The two plugin demonstrations need a VapourSynth host to load them. Their tutorials use Python with the VapourSynth module installed. Match the plugin architecture to that host and its core library. See [loading and linking](../guides/loading-and-linking.md) for library selection and deployment details.

## Run a single host

The core-information example is the shortest environment check:

=== "Windows"

    ```powershell
    odin run examples/core_info -- "C:\path\to\libvapoursynth.dll"
    ```

=== "Linux"

    ```sh
    odin run examples/core_info -- /absolute/path/to/libvapoursynth.so
    ```

=== "macOS"

    ```sh
    odin run examples/core_info -- /absolute/path/to/libvapoursynth.dylib
    ```

Substitute another host package from the table to run it. If the library is already discoverable by your platform's loader, omit the path and the `--`. A successful example exits with status zero; a reported failure exits with status one.

## Run the complete example suite

```sh
python tests/examples.py
```

The runner builds all six packages into `.build/examples`, runs the host executables, loads both plugins, and checks their behavior. It exercises every active pixel for Gray8, RGB24, YUV420P10, and Gray16 inversion; concurrent requests; custom frame properties; source preservation; double inversion; unsupported input; and missing-library diagnostics.

To select an existing runtime directory containing the Python module:

```sh
python tests/examples.py --runtime .build/runtime
```

The `.build/runtime` directory is an example local layout, not a checked-in dependency. The runner does not install or download a runtime. Use `--library` for an explicit core-library path and `--odin` for a compiler executable. The [testing guide](../maintenance/testing.md) explains how these checks fit with the ABI and `easy` suites.

## Read examples as ownership contracts

Watch for the point at which each resource becomes owned, the first deferred release, and any transfer to another owner. A node describes a graph; a requested frame contains evaluated data. A property or plane view borrows memory from another object and needs no separate release, but its owner must remain alive.

The same distinctions recur as the examples grow. The [map guide](../guides/maps.md), [frame guide](../guides/frames.md), and [error guide](../guides/errors.md) collect the rules used throughout the tutorials.
