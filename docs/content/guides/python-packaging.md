---
title: Python tooling and example packaging
description: Distinguish Odin source bindings from the Python environment used to run examples and demonstrate native plugin packaging.
---

# Python tooling and example packaging

The bindings are distributed as Odin source under `src/vapoursynth`. The root
UV project provisions a runtime for tests, example hosts, previews, and
documentation. It does not build or distribute a filter collection.

## Provision the development environment

Install Odin and uv, then run from the repository root:

```console
uv sync --locked
uv run tools/run_host.py core_info
```

The helper builds the host example and supplies the core library installed beside
the VapourSynth Python module. This is a convenience for exercising the bindings;
an application may instead load its own native runtime explicitly. See
[loading and linking](loading-and-linking.md).

The lockfile selects the tested Python dependencies. The R76 headers still define
the bindings' API 4.2 contract when tests run against R79. See
[compatibility](../maintenance/compatibility.md) for version negotiation and the
limits of the verification record.

## Optional preview and documentation tools

```console
uv run --group preview tools/examples.py preview invert
uv run --group docs tools/docs.py build
```

VSView and Qt are optional preview dependencies. Documentation rendering requests
frames headlessly and does not require the GUI. The
[build guide](previewing-examples.md) explains the supported native toolchains
and how to use a copied example.

## Package an example plugin

Native wheel packaging is demonstrated within individual plugin examples:

```console
cd examples/invert
uv run build.py --check
uv build
```

The local source distribution includes the example's sources, build files, and
license notices. Its wheel hook calls the same `build.py` entry point and includes
one native library under `vapoursynth/plugins/<distribution_name>/`, following
[VapourSynth's packaging convention](https://www.vapoursynth.com/doc/packaging.html).
The wheel distributes that compiled example, not the Odin binding packages.

The distribution name comes from `[project].name`; the library filename comes
from `[tool.odin].name`. The hook gives the wheel a native platform tag and
packages only the resulting library. Odin and the platform's native toolchain
remain build prerequisites. Hald additionally uses Odin's bundled stb library;
retain the corresponding third-party notices when distributing it.

An installed wheel is discovered by a new VapourSynth core with autoloading
enabled. Avoid installing the example wheel into the environment used for its
local preview: the preview deliberately loads the local build and reports a
namespace conflict if an installed copy has already loaded.

## Check the copied-project workflow

From the bindings repository root:

```console
uv run tests/standalone.py
uv run tests/standalone.py --all
```

The default checks Invert; `--all` checks all eight examples. The runner copies
projects outside the checkout, downloads their pinned bindings, executes hosts
or requests preview frames, and builds plugin wheels from their source
distributions. It then checks autoloading in isolated environments. This verifies
the packaging lesson without making packaging part of the bindings themselves.
