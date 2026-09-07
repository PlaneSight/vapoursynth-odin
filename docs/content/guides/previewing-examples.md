---
title: Build and preview the examples
description: Compile every Odin example, inspect named outputs in VSView, and generate documentation images from the same VapourSynth scripts.
---

# Build and preview the examples

Compile the examples and open their results in VSView with two commands.
The demonstrations generate their own
input scenes and lookup tables, so they need no downloaded video, source plugin,
or separate VapourSynth installation.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Odin](../getting-started/installation.md), then run from the repository root:

```console
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

`uv run` prepares the project environment as needed. The first command compiles
the eight binding examples. The second reuses those
binaries and launches the four plugin scripts in VSView, ready to inspect.
For an optional headless check of
their output frames after the build:

```console
uv run tools/examples.py check --no-build
```

## One build command on every supported platform

Each example is also a standalone project. To build just Invert:

```console
cd examples/invert
uv run build.py
uv run build.py --check
uv run --group preview vsview preview.vpy
uv build
```

These commands compile the plugin, request every preview output's first and last
frames, open the named outputs, and build a source distribution and native wheel.
Hosts use `uv run build.py --run` to execute their program.

### Copy an example into your own project

Copy the entire example directory, including dotfiles. Each project contains:

| File or directory | Responsibility |
| --- | --- |
| `src/` | Editable Odin host or plugin implementation |
| `build.py` | Native build, dependency provisioning, and headless execution |
| `pyproject.toml` | Python dependencies, artifact name, and pinned bindings source |
| `uv.lock`, `.python-version` | Reproducible Python environment |
| `preview.vpy`, `preview_support.py` | Plugin graph, synthetic inputs, and named outputs |
| `hatch_build.py` | Plugin wheel hook using the same native build |
| `LICENSE`, `THIRD_PARTY_LICENSES.md` | Source and native dependency notices |
| `.gitignore` | Excludes environments, dependency caches, binaries, and distributions |

Hosts omit the preview and wheel hook. Dither includes its tile generator; Hald
includes its LUT generator. These are local, editable parts of each project.
There is no nested Git repository or dependency on sibling examples. You can
omit existing `.venv`, `.deps`, `.build`, and `dist` directories when copying.

The first build downloads a full-commit-pinned archive from
[PlaneSight/vapoursynth-odin](https://github.com/PlaneSight/vapoursynth-odin),
checks the manifest's SHA-256 checksum **before executing downloaded build
support**, and extracts only the Odin sources, native helper, and license notices
into `.deps/<commit>/`. Later builds reuse this cache. An incomplete cache
produces an error: remove the indicated directory and retry. Python dependencies
remain managed by uv, following its
[project and lockfile conventions](https://docs.astral.sh/uv/guides/projects/).

The artifact is `.build/<name>` with the native extension; plugin distributions
go in `dist/`. Building a wheel from its source distribution may download the
bindings again into the isolated build directory. The first build needs network
access, and Odin and the platform's native development tools remain prerequisites.

To rename a scaffold, edit `[project]` and `[tool.odin]` in `pyproject.toml`, then
run `uv lock`. For plugins, also change the identifier, namespace, and display
name in `src/plugin.odin` and the corresponding names in `preview.vpy`. Renaming
the Python distribution alone cannot rename the VapourSynth filter API. Retain
the license notices with copies and distributions.

### Develop against the current bindings

Local builds use the pinned dependency even inside this repository. To test
another bindings checkout, explicitly select it:

```console
uv run build.py --bindings /absolute/path/to/vapoursynth-odin
```

The repository command `uv run tools/examples.py build` invokes the same local
build functions with the current checkout supplied explicitly. It publishes
both the `.build/examples/` artifacts used by repository tools and the local
`.build/` artifacts used by previews. Individual plugin projects demonstrate wheel packaging with their own `uv build`;
the root project manages bindings development dependencies.

`uv run tests/standalone.py --all` checks every project after copying it outside
the checkout: dependency downloads, host execution or preview frames, plugin
source distributions, wheels, and isolated wheel autoloading.

### Native toolchain requirements

Use the same `uv run tools/examples.py build` command on Windows x64, Linux
x64 or ARM64, and macOS x64 or ARM64. It creates the output directory, selects
the Odin target and library extension, enables optimized builds, and uses a
baseline CPU instruction set. macOS builds target macOS 13 or newer.

The build follows the architecture of the Python process that will load the
plugins. A universal2 Python installation on macOS produces a single-architecture
plugin for its running process, including x64 when Python runs under Rosetta.
It does not create a universal binary. Odin and the platform's native development
tools must be installed; uv supplies the Python environment and VapourSynth.

Hald CLUT imports Odin's bundled stb image package. The build reuses the image
libraries supplied by your Odin installation. When Unix archives are missing,
it compiles the bundled C sources into a private build directory under `.build`,
using `cc` and `ar`. This requires a native C compiler and archiver on Linux, or
the Xcode command line tools on macOS. The build does not modify your Odin
installation. On Windows, use an Odin distribution that includes its native
vendor libraries.

The helper supplies the plugin's `stb:image` import through a custom collection,
pointing it at Odin's package or the privately prepared copy. See the
[Hald walkthrough](../examples/haldlut-plugin.md#import-an-odin-vendor-library)
for how that native dependency is integrated.

Only builds selecting `haldlut` need these stb libraries. To build a smaller
selection:

```console
uv run tools/examples.py build invert dither
```

The same native build support is used by preview, image generation, documentation,
host execution, and individual examples' wheel builds. Builds compile into temporary directories
before publishing the requested artifacts. If a compiler invocation fails, the
command reports failure and leaves the previous binaries available.

Native execution has been verified on Windows x64. Platform selection and build
commands for the other supported targets are tested separately; see the
[compatibility record](../maintenance/compatibility.md) for the limits of that
evidence.

## Choose what to build or preview

The build command writes host executables and native plugins under
`.build/examples`, using the build selector and the platform's file extension.
Its default selection is the eight binding examples:

| Host executables | Plugin demonstrations |
| --- | --- |
| `core_info` | `plugin` — Identity |
| `properties` | `invert` |
| `easy_host` | `dither` |
| `host` | `haldlut` |

Preview one filter or several by name:

```console
uv run --group preview tools/examples.py preview invert
uv run --group preview tools/examples.py preview dither haldlut
```

The preview command builds its selected plugins before launching their checked-in
`preview.vpy` files under `examples/<name>/`. To reuse binaries from a previous build:

```console
uv run --group preview tools/examples.py preview --no-build dither
```

Close a viewer that has loaded a plugin before rebuilding it. A running core
keeps the loaded machine code; replacing a file cannot update that code in place,
and Windows may keep the library file locked.

Arguments after `--` are passed to VSView. See
[VSView's configuration documentation](https://jaded-encoding-thaumaturgy.github.io/vs-view/usage/configuration/)
for viewer options, and use `uv run tools/examples.py --help` for the repository's
command interface. The example selector `plugin` refers to the identity package;
its VapourSynth namespace remains `odin_example`.

## Read the named outputs

The four teaching demonstrations publish the same first three output nodes. Use VSView's output selector
to switch between the comparison and either side at full size.

| Output | Contents |
| --- | --- |
| `0` | Side-by-side comparison, baseline on the left and filtered result on the right |
| `1` | Source image, or nearest-rounding baseline for dither |
| `2` | Filtered result |

Identity demonstrates exact pass-through: both sides should match. Invert
produces a clearly different image by subtracting each sample from its format's
maximum value. Hald CLUT uses the synthetic RGB scene and a generated cinematic
lookup table, making its tonal and color changes easy to compare.

Dither starts from a shallow sixteen-bit grayscale ramp. Both displayed sides
apply the **same 20× contrast gain** after reducing to eight bits. The gain
exposes nearest-rounding bands and the native filter's distributed rounding
pattern. It is an inspection aid; it does not represent the source's natural
contrast. The [dither walkthrough](../examples/dither-plugin.md#see-the-quantization-pattern)
gives the exact source interval, display formula, and filter parameters.
Dither also publishes output `3` as the original RGB16 ramp and output `4` as
the native RGB8 dither result, both without display gain. These let you inspect
the source and filter samples independently of the amplified comparison.

The remaining dither outputs demonstrate **one-, two-, and four-bit effective
depths in a normal RGB8 container**, using the color scene and no contrast gain:

| Output | Contents |
| ---: | --- |
| `5` | Original RGB16 color scene |
| `6`, `7`, `8` | One-bit nearest rounding, blue-noise dither, and side-by-side comparison |
| `9`, `10`, `11` | Two-bit nearest rounding, blue-noise dither, and side-by-side comparison |
| `12`, `13`, `14` | Four-bit nearest rounding, blue-noise dither, and side-by-side comparison |

Each low-bit view quantizes every channel independently, expands its selected
levels across `0..255`, and returns ordinary eight-bit samples. Two-bit RGB uses
only `0`, `85`, `170`, and `255` in each channel. The
[dither walkthrough](../examples/dither-plugin.md#effective-depth-and-storage-depth)
explains the exact mapping and the distinction between quantization levels and
storage depth.

The scripts name their outputs through VSView's user API when running inside
the previewer. Headless evaluation uses ordinary VapourSynth output nodes and does
not need the GUI package. Source paths are resolved relative to each example project,
including the platform-specific plugin filename.

## Keep the previewer optional

The `preview` dependency group pins **VSView 0.11.0** and supports
**Python 3.12–3.14**. VSView requires Python 3.12 or newer and
**VapourSynth R78 or newer**; the current PySide6 dependency supplies the upper
Python bound. The development lock selects R79. The base project still accepts
Python 3.12 or newer; requesting the preview group adds its narrower interpreter
constraint. See the
[VSView release metadata](https://pypi.org/project/vsview/0.11.0/) for its declared
dependencies.

Ordinary `uv sync` provisions the development environment without VSView or Qt.
Only commands selecting `--group preview` install the viewer. An explicit setup
can use:

```console
uv sync --locked --group preview --python 3.14
uv run --group preview tools/examples.py preview
```

Keep `--group preview` on later uv preview commands: uv synchronizes the selected
groups for each run. The `docs` group supports headless image generation and site
building without a GUI. A desktop session is needed to launch VSView itself.

## Check the scripts without opening a window

```console
uv run tools/examples.py check
```

This exercises the checked-in `.vpy` graphs and requests their published outputs.
By default it builds the selected plugins first, then requests the first and last
frame of every output in a fresh process for each script. Use
`uv run tools/examples.py check --no-build` immediately after a successful build
to reuse its binaries.
It catches missing plugins, script errors, and failed frame evaluation, so a
script that imports successfully but cannot produce pixels does not pass.

The numerical test suites go further: they compare output values against
independent references and exercise format boundaries, malformed inputs,
properties, concurrency, and ownership. Use
`uv run tests/examples.py` and `uv run tests/advanced.py` when changing filter
behavior. Visual inspection and these checks answer different questions; see
the [testing guide](../maintenance/testing.md).

## Render the same outputs for documentation

```console
uv run tools/render_showcase.py
```

The renderer builds the plugins, evaluates each demonstration in a fresh
process, and exports the first frame of the outputs declared in that script's
`DOCUMENTATION_OUTPUTS` mapping. It writes the images and a record of the run
under `.build/showcase`. The scene construction, filter calls, and comparison
display transforms all live in the example scripts and their shared helpers.
Changing those examples changes both the viewer and the generated illustrations.
To regenerate the images in the site and validate the whole documentation:

```console
uv run --group docs tools/docs.py build
```

This builds the eight Odin binding examples, evaluates all four visual demonstrations,
exports their images into the ignored `docs/content/assets/generated` directory, runs a
clean strict Zensical build, and checks local links and assets. Failure to compile,
evaluate, or render stops the build; there is no fallback to checked-in screenshots.
The published pages are static HTML and PNG files. Readers do not need Odin or
VapourSynth to view them.

Use `uv run --group docs tools/docs.py serve` to prepare the same images before
starting the local documentation server. Markdown changes reload while serving.
After editing Odin code or a demonstration script, stop and restart this command
to rebuild the plugins and images. Direct `zensical` commands do not perform
native image generation. The [publishing guide](../maintenance/documentation.md)
explains the same pipeline in GitHub Actions.
