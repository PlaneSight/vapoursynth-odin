# VapourSynth bindings for Odin

Odin bindings for **VapourSynth core API 4.2** and **VSScript API 4.2**,
with an optional idiomatic host interface for ownership, maps, and frame access.
The raw declarations follow the pinned VapourSynth R76 headers.

**[Documentation →](https://planesight.github.io/vapoursynth-odin/)**
Installation, API reference, ownership contracts, examples, and testing instructions.

## Use

Place this repository at `vendor/vapoursynth-odin`:

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

```console
odin build . -collection:deps=vendor/vapoursynth-odin/src
```

The bindings are ordinary Odin source packages. Python is needed for this
repository's development tools and VSScript's runtime, not core API imports.

## Develop

Install Odin and uv. The root project and each copyable example select Python
3.14.7 automatically.

```console
uv run tools/examples.py build
uv run tests/abi.py
uv run --group docs tools/docs.py serve
```

The [examples](examples/README.md) demonstrate binding usage through small hosts
and plugins. Their image-processing operations are exercises for API contracts.
