# Installation

The bindings are ordinary Odin packages. Add the repository to your project, choose how your application obtains a VapourSynth API table, and compile with Odin. Importing the raw bindings or `easy` does not load a library or create a core.

You can compile the dynamically loaded host examples and the plugin examples before installing a VapourSynth runtime. You need the runtime when you execute a host, or when VapourSynth loads your compiled plugin.

## What you need

| Task | Requirements |
| --- | --- |
| Check the bindings and examples | Odin and its platform toolchain. |
| Run a native host example | Odin and a compatible VapourSynth core library with its dependencies. |
| Build and run a plugin example | Odin, VapourSynth, and a host that can load the plugin. The documented demonstrations use Python. |
| Preview the plugin examples in VSView | Odin, uv, a desktop session, and the optional `preview` group with Python 3.12–3.14. |
| Build the documentation and its filter images | Odin and the `docs` dependency group, including VapourSynth and NumPy. No GUI is needed. |
| Use normal linker resolution | The above runtime, plus an import library on Windows or the appropriate linker library on other platforms. |
| Run the ABI suite | Odin, Python 3.10 or newer, and a C compiler. No VapourSynth installation is required. |

Install Odin using its [official installation instructions](https://odin-lang.org/docs/install/), including the platform requirements listed there. Verify that the command is available:

```console
odin version
```

This repository was verified with Odin `dev-2026-09-nightly:a2fb372`. That identifies the compiler used for validation; it is not a claim that every earlier or later compiler is compatible. Consult [compatibility and verification](../maintenance/compatibility.md) for the tested targets and API baseline.

## Add the packages to your application

Place a checkout or copy of this repository under your application's dependency directory. For example:

```text
my-application/
├── main.odin
└── vendor/
    └── vapoursynth-odin/
        └── src/
            └── vapoursynth/
                ├── api.odin
                ├── constants.odin
                ├── frame_properties.odin
                ├── types.odin
                ├── easy/
                ├── link/
                └── vsscript/
```

Define a library collection that points to the repository's `src` directory:

```console
odin build . -collection:deps=vendor/vapoursynth-odin/src
```

Your application can then import the raw bindings and the optional host interface:

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

`deps` is the collection name chosen by your build command. It does not have to be `deps`, but the import prefix and command must agree. Odin resolves an import without a collection prefix relative to the importing file; the examples in this repository use that approach so they build directly from the checkout. See the [Odin package overview](https://odin-lang.org/docs/overview/#packages) for the language's import rules.

You do not need to copy these packages into Odin's own `core` or `vendor` installation. Keeping dependencies within your application makes the selected binding revision explicit.

## Install a compatible runtime

The host interface requests **core API 4.2**. That core API is available from R74;
runtime verification covers R76 and R79 on Windows x64. An incompatible core
returns `nil` when API 4.2 is requested; `easy.load_library` reports this as
`.Unsupported_API`.

### Use the locked Python environment

The quickest path through this repository's examples is the uv project. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/), keep Odin on your
executable search path, and run:

```console
uv sync --locked
uv run tools/run_host.py core_info
```

This installs the official VapourSynth runtime in `.venv` and passes its core
library to the example explicitly. The project requires CPython 3.12 or newer.
The lockfile selects R79; it does not alter the pinned R76 API 4.2 declarations.
See [Python environments and wheels](../guides/python-packaging.md) for platform
availability, documentation dependency groups, and native plugin distribution.

To compile the eight examples and Dither Plus and inspect the five plugin demonstrations:

```console
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

The second command reuses the first command's binaries. An optional headless
check is `uv run tools/examples.py check --no-build`.

The build command selects the target, CPU baseline, and output filenames on
Windows x64, Linux x64/ARM64, and macOS x64/ARM64. macOS builds target version
13 or newer, including when Python comes from a universal2 installation. Hald
CLUT reuses Odin's supplied stb image libraries or builds missing Unix archives
privately with a native C compiler and archiver. See the
[build requirements](../guides/previewing-examples.md#one-build-command-on-every-supported-platform)
for the platform tools needed by that fallback.

The optional `preview` group adds VSView and Qt when selected; plain `uv sync`
does not install them. See [Build and preview the examples](../guides/previewing-examples.md)
for its interpreter requirements, named outputs, and generated documentation
images. All preview input scenes are generated locally.

### Use an existing native installation

Follow the [official VapourSynth installation instructions](https://www.vapoursynth.com/doc/installation.html) for your platform. Native host applications need the core library and its dependencies. The Python module is additionally needed for the Python demonstrations and the complete example test runner.

For a first run, pass the actual core library path explicitly:

=== "Windows"

    ```powershell
    odin run examples/core_info -- "C:/path/to/libvapoursynth.dll"
    ```

=== "Linux"

    ```console
    odin run examples/core_info -- /absolute/path/to/libvapoursynth.so
    ```

=== "macOS"

    ```console
    odin run examples/core_info -- /absolute/path/to/libvapoursynth.dylib
    ```

These commands run from this repository's root. Replace the example path with an existing library for your machine. Passing the full path removes ambiguity about which core you selected, but its dependent libraries must still be available to the operating system loader.

!!! note "Native libraries must match the executable"

    A Windows x64 executable needs a Windows x64 core and compatible dependencies. The same architecture requirement applies to plugins and to the host that loads them. A filename alone does not establish architecture or API compatibility.

With the loader configured correctly, the path can be omitted. The defaults are `libvapoursynth.dll`, `libvapoursynth.so`, and `libvapoursynth.dylib` on Windows, Linux, and macOS respectively. See [loading and linking](../guides/loading-and-linking.md) for the distinction between runtime loading, link-time resolution, and plugin entry points.

## Check the checkout

From the repository root, these checks require no VapourSynth runtime:

```console
odin check src/vapoursynth -no-entry-point -vet
odin check src/vapoursynth/easy -no-entry-point -vet
odin check src/vapoursynth/vsscript -no-entry-point -vet
odin check examples/core_info -vet
```

Use `-no-entry-point` for library packages because they do not define `main`. The example is an executable package, so it has an entry point.

Once `core_info` prints the runtime's version and thread information, continue to the [quickstart](quickstart.md). If it fails, preserve both the error enum and the diagnostic printed by the example; together they distinguish loader failure, a missing export, and unsupported API negotiation.
