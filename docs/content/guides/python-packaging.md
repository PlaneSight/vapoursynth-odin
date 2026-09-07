---
title: Python tooling and example packaging
description: Distinguish Odin source bindings from the Python environment used to run examples and demonstrate native plugin packaging.
---

# Python tooling and example packaging

The bindings are distributed as Odin source under `src/vapoursynth`. The root
UV project provisions a runtime for tests, example hosts, previews, and
documentation. It does not build or distribute a filter collection.

For Python, VapourSynth, and optional tool setup, use the
[installation guide](../getting-started/installation.md). This page covers
distributing a compiled example as a Python wheel.

## Package an example plugin

Native wheel packaging is demonstrated within individual plugin examples:

```console
cd examples/invert
uv run build.py --check
uv build
```

The local source distribution includes the example's sources, build files, and
build configuration. Its wheel hook calls the same `build.py` entry point and includes
one native library under `vapoursynth/plugins/<distribution_name>/`, following
[VapourSynth's packaging convention](https://www.vapoursynth.com/doc/packaging.html).
The wheel distributes that compiled example, not the Odin binding packages.

The distribution name comes from `[project].name`; the library filename comes
from `[tool.odin].name`. The hook gives the wheel a native platform tag and
packages only the resulting library. Odin and the platform's native toolchain
remain build prerequisites. Hald additionally uses Odin's bundled stb library.

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
