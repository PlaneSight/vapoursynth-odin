# VapourSynth for Odin

Complete **VapourSynth API 4.2 bindings** for Odin, an optional idiomatic host
interface, eight progressive examples, and the standalone **Dither Plus** plugin.
The declarations follow the pinned [VapourSynth R76 headers](tests/headers/README.md).

- **Raw API:** all 117 stable `VSAPI` entries, plugin callbacks, types, constants,
  and frame properties. Importing the package does not load a library.
- **Idiomatic interface:** typed maps, explicit ownership, durable errors,
  synchronous frame requests, and stride-aware pixel access.
- **Examples:** core information, properties, hosting, identity, invert,
  SIMD blue-noise dither, and Hald CLUT color grading with Odin's bundled stb.
- **Dither Plus:** blue noise, Bayer, nearest rounding, Floyd–Steinberg, and
  Sierra Lite, including effective one-bit output in an eight-bit container.
- **VSScript:** a separate raw API 4.2 package and optional linked entry point.
  Experimental graph inspection is exposed separately from the stable core API.

## Build and preview

Install [Odin](https://odin-lang.org/docs/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then run from this
repository:

```console
uv run tools/examples.py build
uv run tools/examples.py check --no-build
uv run --group preview tools/examples.py preview --no-build
```

UV provisions the Python environment and VapourSynth. The repository pins
Python 3.14.7 in `.python-version` and dependencies in `uv.lock`. The optional
`preview` group supplies **VSView**; ordinary builds do not install Qt.
All demonstration input is generated locally, so no video downloads are needed.

The build command selects the native target on Windows x64, Linux x64/ARM64,
and macOS x64/ARM64. Binaries go into `.build/examples`. For Hald CLUT, missing
Unix stb archives are built privately using a native C compiler and archiver;
macOS requires Xcode command line tools and macOS 13 or newer. See the
[build and preview guide](docs/guides/previewing-examples.md) for prerequisites
and output selection. Native runtime verification currently covers Windows x64.

Select a single plugin or run a host:

```console
uv run tools/examples.py build dither_plus
uv run --group preview tools/examples.py preview --no-build dither_plus
uv run tools/run_host.py easy_host
```

## Use the bindings

Place this repository at `vendor/vapoursynth-odin` and add `vendor` as an Odin
collection:

```odin
import vs "deps:vapoursynth-odin"
import easy "deps:vapoursynth-odin/easy"
```

```console
odin build . -collection:deps=vendor
```

A plugin receives its API table from VapourSynth. A host obtains one through
`getVapourSynthAPI`, requesting `vs.VAPOURSYNTH_API_VERSION` and checking for
`nil`. The table is borrowed; do not copy, modify, or free it. The
[first-program guide](docs/getting-started/quickstart.md) demonstrates a complete
host with explicit cleanup.

| Source | Purpose |
| --- | --- |
| Root Odin package | Raw core API 4.2 declarations |
| [`easy/`](easy/README.md) | Typed hosting interface and resource ownership |
| `link/` | Optional linked core entry point |
| `vsscript/`, `vsscript/link/` | Raw VSScript API 4.2 and linked entry point |
| [`examples/`](examples/README.md) | Eight teaching examples and their preview scripts |
| [`plugins/dither/`](plugins/dither/README.md) | Standalone Dither Plus plugin |
| `tests/` | Maintained ABI, ownership, pixel, and tooling regression checks |
| `tools/` | Native builds, previews, documentation, and package checks |
| `docs/` | Zensical documentation source |

The bindings remain API 4.2 while the development environment uses VapourSynth
R79. R76 and R79 have both been exercised. Consult the
[compatibility record](docs/maintenance/compatibility.md) for the tested platforms
and the distinction between stable and experimental tables.

## Documentation

Start with [installation](docs/getting-started/installation.md),
[choosing an interface](docs/getting-started/choosing-an-interface.md), or the
[example progression](docs/examples/index.md). The [documentation](docs/index.md)
also covers ownership, errors, maps, frames, loading, public API contracts, and
plugin parameters.

```console
uv run --locked --group docs tools/docs.py serve
uv run --locked --group docs tools/docs.py build
```

Both commands compile the actual examples and generate their illustrations from
the same scripts used in VSView. The build runs Zensical strictly and checks
local links. Generated HTML lives in **`.venv/site`** and is ignored by Git.
Restart the preview command after changing native code or image scripts.

The [publishing guide](docs/maintenance/documentation.md) describes the included
GitHub Pages workflow. It validates pull requests and deploys the default branch
once **Settings → Pages → GitHub Actions** is enabled. Repository and site URLs
come from GitHub metadata.

## Tests and distributions

```console
uv run --locked python -m unittest discover -s tests -p 'test_*.py'
uv run --locked tests/abi.py
uv run --locked tests/examples.py
uv run --locked tests/advanced.py
uv run --locked tests/dither_plus.py
```

ABI verification additionally needs a C compiler. See the
[testing guide](docs/maintenance/testing.md) for toolchain selection, ownership
checks, and which checks apply to a change. Generated fixtures and native probes
stay in `.build`. Historical performance results remain in the documentation;
the development-only collection tools are preserved at revision `f59ecbd`.

```console
uv build
```

An explicit build packages all five native plugins in a platform-specific wheel
using VapourSynth's autoload convention. Ordinary `uv sync` does not compile or
install this repository as an editable plugin package. See the
[packaging guide](docs/guides/python-packaging.md) for source builds, installation,
and verification.

## License

**LGPL-2.1-or-later.** See [LICENSE](LICENSE),
[third-party notices](THIRD_PARTY_LICENSES.md), and the
[pinned header provenance](tests/headers/README.md).
