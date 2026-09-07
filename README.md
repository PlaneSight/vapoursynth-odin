# VapourSynth bindings for Odin

Odin bindings for **VapourSynth core API 4.2** and **VSScript API 4.2**, with
an optional idiomatic interface for host applications. The declarations follow
the pinned [VapourSynth R76 headers](tests/headers/README.md).

This repository maintains API declarations, ABI compatibility, and ownership
helpers for using VapourSynth from Odin. The examples demonstrate these bindings
through small hosts and plugins; their image-processing operations provide
concrete exercises for the API.

## Use the bindings

Place this repository at `vendor/vapoursynth-odin` and import the packages through
an Odin collection:

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

```console
odin build . -collection:deps=vendor/vapoursynth-odin/src
```

The raw package preserves C names, field order, integer widths, and calling
conventions. Importing it performs no initialization. A plugin receives the API
table from its host; an application loads a runtime and requests the version it
needs. The optional `easy` package provides typed maps, explicit resource
ownership, errors, and borrowed frame-row views.

| Package | Purpose |
| --- | --- |
| `src/vapoursynth/` | All 117 stable core API entries, callbacks, types, constants, and frame properties |
| [`src/vapoursynth/easy/`](src/vapoursynth/easy/README.md) | Idiomatic host interface and resource ownership |
| `src/vapoursynth/link/` | Optional linked core entry point |
| `src/vapoursynth/vsscript/` | VSScript declarations and optional `link/` package |

The stable core API and experimental graph extension are separate types. See the
[API reference](docs/content/reference/raw-api.md) for their contracts and the
[compatibility record](docs/content/maintenance/compatibility.md) for tested targets.

## Learn the API

The [documentation](https://planesight.github.io/vapoursynth-odin/) covers
[installation](docs/content/getting-started/installation.md),
[your first host program](docs/content/getting-started/quickstart.md),
[choosing an interface](docs/content/getting-started/choosing-an-interface.md),
and the [API references](docs/content/reference/index.md). The guides explain
[ownership](docs/content/guides/ownership.md), [maps](docs/content/guides/maps.md),
[errors](docs/content/guides/errors.md), and [frame layout](docs/content/guides/frames.md).

The [eight examples](examples/README.md) progress from loading a core to handling
callbacks, allocating output frames, and combining the bindings with another
native library. Their directories can be copied as starting points for your own
code. Invert demonstrates the frame lifecycle; dither demonstrates changing a
frame's format; Hald demonstrates foreign-library resources and ownership.

With [Odin](https://odin-lang.org/docs/install/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```console
uv run tools/run_host.py core_info
uv run tools/examples.py build
uv run tools/examples.py check --no-build
```

UV supplies the test runtime and Python tooling. Consuming the core Odin bindings
does not require UV or Python. VSScript has its own Python runtime requirements.
Optional visual previews use `uv run --group preview tools/examples.py preview`.
See the [example build guide](docs/content/guides/previewing-examples.md) for
local builds, copied projects, and platform prerequisites.

## Verify changes

```console
uv run --locked tests/abi.py
uv run --locked python -m unittest discover -s tests -p 'test_*.py'
uv run --locked tests/examples.py
uv run --locked tests/advanced.py
```

The ABI suite compares Odin declarations with the pinned C headers and requires
a C compiler. Runtime checks exercise ownership, callbacks, formats, and error
handling through the examples. The [testing guide](docs/content/maintenance/testing.md)
covers the `easy` runtime suite and checks appropriate to each change.

The root UV project manages development and documentation dependencies. The
bindings are distributed as Odin source. Packaging a native plugin is an
optional lesson within individual example projects; see the
[packaging guide](docs/content/guides/python-packaging.md).

## Repository layout and documentation

`src/` contains the bindings; `examples/` demonstrates their use; `tests/` verifies
them; and `tools/` supports builds and documentation. Authored pages live in
`docs/content/`, with theme templates in `docs/overrides/`.

```console
uv run --locked --group docs tools/docs.py serve
uv run --locked --group docs tools/docs.py build
```

The documentation build executes the examples used for illustrations, runs
Zensical strictly, and checks local links. Generated HTML stays in `.venv/site`;
binaries, fixtures, and caches are ignored. The
[publishing guide](docs/content/maintenance/documentation.md) describes GitHub Pages.

## License

**LGPL-2.1-or-later.** See [LICENSE](LICENSE),
[third-party notices](THIRD_PARTY_LICENSES.md), and the
[header provenance](tests/headers/README.md).
