---
title: VapourSynth bindings for Odin
description: Core API 4.2 and VSScript API 4.2 declarations, ABI compatibility, and explicit resource ownership in Odin.
---

# VapourSynth bindings for Odin

This project provides Odin declarations for **VapourSynth core API 4.2** and
**VSScript API 4.2**, plus an optional idiomatic interface for host applications.
These docs explain how to import the packages, negotiate API versions, manage
references, and use maps, frames, callbacks, and function tables correctly.

The examples are runnable demonstrations of binding usage. Hosts exercise
loading and invocation; plugins exercise callbacks and frame ownership.
Image-processing operations give these API contracts observable results.

**Start with [Installation](getting-started/installation.md)** for the uv setup,
native tool requirements, and first working command.

## Import the packages

Place the repository at `vendor/vapoursynth-odin`:

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

```console
odin build . -collection:deps=vendor/vapoursynth-odin/src
```

The bindings are ordinary Odin source packages. Python and uv support this
repository's development tools and examples; they are not prerequisites for an
Odin application using the core API. VSScript has its own Python runtime needs.
Start with [installation](getting-started/installation.md), then follow the
[first host program](getting-started/quickstart.md).

## Choose an interface

| Package | Use it to |
| --- | --- |
| [`vapoursynth`](reference/raw-api.md) | Call the raw core API or implement callbacks with the C ABI |
| [`vapoursynth/easy`](reference/easy.md) | Load a core, own references, invoke functions, and access checked row views |
| [`vapoursynth/vsscript`](reference/vsscript.md) | Evaluate scripts and obtain output nodes through the separate script API |
| [`vapoursynth/link`](guides/loading-and-linking.md) | Resolve a core entry point through the linker |

The raw declarations preserve the pinned R76 headers' names, integer widths,
calling conventions, and table layout. They include all 117 stable core entries.
The experimental graph extension is separate from the stable table. The `easy`
package wraps selected operations with typed errors and explicit owners while
keeping the raw API accessible. [Compare the interfaces](getting-started/choosing-an-interface.md)
before choosing the layer for your application.

## Understand the contracts

- [Ownership and lifetime](guides/ownership.md): acquire, borrow, retain, transfer, and release references.
- [Maps](guides/maps.md): typed properties, arrays, binary data, and node references.
- [Frames](guides/frames.md): planar samples, strides, subsampling, and writable storage.
- [Errors](guides/errors.md): return codes, map errors, and durable diagnostics.
- [Loading and linking](guides/loading-and-linking.md): entry points and independent core/script version negotiation.

The [reference](reference/index.md) is the canonical description of the binding
packages. The [examples](examples/index.md) connect these contracts to complete
programs, from inspecting a core to producing a frame in a callback.

## Run a binding example

With Odin and uv installed:

```console
uv run tools/run_host.py core_info
uv run tools/examples.py build
uv run tools/examples.py check --no-build
```

The [example build guide](guides/previewing-examples.md) covers copied projects
and optional visual previews. Illustrations are generated from these same
examples during documentation builds.

## Verify the bindings

The repository includes pinned C headers, C/Odin ABI comparisons, ownership and
failure tests for `easy`, and runtime checks of the examples. See
[testing](maintenance/testing.md) for commands and
[compatibility](maintenance/compatibility.md) for recorded environments.
ABI and runtime evidence are reported separately from compile-only checks.
