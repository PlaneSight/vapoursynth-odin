---
title: Python environments and plugin wheels
description: Use uv to provision VapourSynth, run Odin hosts, and build native plugins that VapourSynth discovers automatically.
---

# Python environments and plugin wheels

The repository's `pyproject.toml` serves two related purposes: it defines a
reproducible Python environment for development, and it describes a native wheel
containing the example plugins. Odin source remains the interface imported by an
Odin application. A wheel distributes the compiled plugins for a Python-hosted
VapourSynth installation.

This follows VapourSynth's [official plugin packaging convention](https://www.vapoursynth.com/doc/packaging.html):
native libraries belong under the installed `vapoursynth/plugins` directory.
The core discovers them there. No Python entry-point registration or wrapper
module is needed merely to load a native filter.

## Provision the development environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and the
[Odin toolchain](../getting-started/installation.md), then run from the repository
root:

```console
uv sync --locked
uv run tools/run_host.py core_info
uv run tools/run_host.py easy_host
```

`uv.lock` records the selected Python dependencies, including the official
VapourSynth wheel. The root project requires CPython 3.12 or newer. `uv sync`
creates a local `.venv`; it does not install a global multimedia runtime.
The Odin compiler remains an external prerequisite.

`tools/run_host.py` builds the selected Odin example through the common build
helper, finds the core library beside the active Python module, and passes its
absolute path to the executable. It checks that Odin is available and prints the
selected library. This avoids depending on whether
a Python environment's package directory is in the platform loader's search path.
Use `core_info`, `properties`, `easy_host`, or `host` as the example argument.

The raw Odin packages still perform no automatic Python discovery. An application
that already has a core library can keep using the explicit paths and entry
points in the [loading guide](loading-and-linking.md).

## Keep runtime and ABI versions distinct

The development lock selects a tested runtime release; the root bindings continue
to describe the pinned R76 **API 4.2** headers. R79 also exposes core API 4.2.
Updating the Python dependency does not silently regenerate declarations or add
new format constants to the Odin package.

The runtime dependency range is declared in `pyproject.toml`, while `uv.lock`
selects the exact development version. A source checkout can therefore be
reproduced without making a platform-independent promise about every compiler
or runtime combination. Read the [compatibility record](../maintenance/compatibility.md)
for actual native and cross-compile evidence.

Official R76 and R79 wheels support Windows x64, Linux x64/ARM64, and macOS
x64/ARM64. Python, operating-system, C library, and architecture requirements
still apply. See the [PyPI file listings](https://pypi.org/project/VapourSynth/#files)
before assuming a wheel exists for another target. A missing binary may lead a
package installer to attempt a source build with additional native dependencies.

## Run tests and documentation

To compile the eight examples and Dither Plus and exercise their visual scripts:

```console
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

The preview reuses the compiled binaries. To check their script outputs without
a GUI after building, run `uv run tools/examples.py check --no-build`.

These commands select the native target, CPU baseline, and output extensions
on Windows x64, Linux x64/ARM64, and macOS x64/ARM64. macOS builds target version
13 or newer; universal2 Python installations build for the architecture of the
running process. The [build guide](previewing-examples.md#one-build-command-on-every-supported-platform)
describes native toolchain requirements, including automatic preparation of
missing Unix stb image libraries for Hald CLUT.

The optional `preview` group installs VSView and Qt. It requires Python 3.12–3.14
and VapourSynth R78 or newer; the development lock selects R79. Ordinary sync
does not install this GUI stack. See the
[preview guide](previewing-examples.md) for selecting filters and their named outputs.

The independent numerical suites remain available:

```console
uv run tests/examples.py
uv run tests/advanced.py
uv run tests/dither_plus.py
```

The first runner covers the six introductory examples. The advanced runner
checks dither and Hald CLUT separately, with numerical reference calculations and
failure cases. Dither Plus has its own independent numerical suite.

Documentation dependencies are in a separate group:

```console
uv run --group docs tools/docs.py serve
uv run --group docs tools/docs.py build
```

A docs-only environment can be synchronized with `uv sync --locked --only-group docs`.
The group includes NumPy and VapourSynth so the documentation can render the same
scripts used in VSView. The documentation command compiles the eight examples and Dither Plus,
generates fresh PNGs, then serves or strictly builds the site. Odin is required;
VSView and Qt are not. Restart the server command after changing native code or
demonstration scripts to regenerate the images.
Local and Pages builds use the same `.python-version` and `uv.lock`. Generated
HTML lives in `.venv/site`; documentation source remains in `docs`.

## Build a native wheel explicitly

The root project sets `tool.uv.package = false`. Ordinary development commands
therefore install dependencies without compiling or installing this repository's
plugins as an editable Python package. The configured Hatchling build backend
is used when a wheel or source distribution is requested explicitly:

```console
uv build --wheel
uv build --sdist
```

The custom build hook invokes Odin in optimized shared-library mode, stages the
five plugin binaries, and gives the wheel a native platform tag. The wheel's
layout is conceptually:

```text
vapoursynth/
└── plugins/
    └── odin_examples/
        ├── odin_example.dll
        ├── odin_invert.dll
        ├── odin_dither.dll
        ├── odin_dither_plus.dll
        └── odin_hald.dll
```

Linux and macOS builds use their platform's shared-library extension. This
directory is merged into the installed VapourSynth package; the distribution
does not replace VapourSynth's `__init__.py` or core library.

The source distribution includes the imported Odin declarations and plugin
sources so the wheel can be rebuilt outside the original Git checkout. The
Hald plugin also uses Odin's bundled stb image binding and its native
libraries. The wheel build uses the same dependency preparation as the example
command: missing Unix archives are compiled into its private staging directory
with `cc` and `ar`, leaving the Odin installation intact. See the
[Hald walkthrough](../examples/haldlut-plugin.md) for that dependency and its
licensing notices. The native build and
installed-wheel checks have been executed on Windows x64; other platforms need
their own native validation.

### What the wheel tag promises

The Windows x64 wheel uses `py3-none-win_amd64`. `none` means the plugins do not
link to a particular CPython ABI. It does not mean the machine code is portable
between operating systems or CPU architectures. A native plugin wheel must not
claim `py3-none-any`.

Local Linux builds use a native Linux tag. Producing a broadly distributable
manylinux or musllinux wheel requires building and checking against that
platform's actual ABI baseline. Likewise, a macOS tag must match the deployment
target and architecture used for the native build. Merely renaming a wheel does
not make its binaries compatible.

The build hook selects a baseline CPU target instead of compiling for the build
machine's most advanced instruction set. The dither filter's SIMD implementation
must be valid on that target. Performance measurements should use the same flags
as the artifact they describe.

## Verify installation and discovery

Install the resulting wheel into a fresh Python environment containing a
compatible VapourSynth runtime. Starting a new process matters: plugin discovery
happens when the core is constructed, and an existing core is not a reliable
test of a newly installed package.

The repository includes a repeatable check that creates a temporary environment,
installs the wheel and its runtime dependency, verifies native archive metadata,
and requests a frame from all five autoloaded plugins:

```console
uv run tools/packagecheck.py dist/vapoursynth_odin_examples-0.1.0-py3-none-win_amd64.whl
```

Substitute the actual filename produced by `uv build` on your platform. The
checker removes its temporary environment after the subprocess exits.

In that environment, this program checks native autoloading without calling
`std.LoadPlugin`:

```python
import vapoursynth as vs

source = vs.core.std.BlankClip(format=vs.GRAY16, width=65, height=48, length=1)
output = vs.core.odin_dither.Dither(source, bits=8)
with output.get_frame(0) as frame:
    assert frame.format.bits_per_sample == 8
print("The packaged dither plugin loaded and produced a frame.")
```

`uv sync` maintains the dependencies declared by the project. A wheel manually
installed into its development environment can be removed by a later exact sync
because the root project is intentionally not installed. Use a separate wheel
test environment, or declare the wheel as a dependency of the consuming project.

An editable install's Python import hooks are not sufficient evidence of native
plugin discovery. The core scans physical native files under its plugin
directory. Inspect `vapoursynth.get_plugin_dir()` and check the expected plugin
namespaces if a package appears installed but the filters are unavailable.

Manual loading remains useful for development and diagnostics. Avoid manually
loading a second copy of a plugin that the core already autoloaded: VapourSynth
rejects duplicate plugin identifiers and namespaces. Cores created with
`ccfDisableAutoLoading` intentionally skip package discovery.

## Use the model in another plugin project

The essential pieces are a PEP 517 build backend, a hook that compiles the native
Odin code, a truthful platform tag, a VapourSynth dependency, and native artifacts
installed below `vapoursynth/plugins`. The build backend does not need to be the
same tool used to compile the plugin; here Hatchling packages what Odin builds.

Give a separate distribution its own project name, plugin identifier, namespace,
and plugin subdirectory. Include every source needed for a source build and the
licenses of native code linked into the result. Test the installed wheel's actual
autoloading and at least one output frame before publishing it.
