# Package reference

The repository exposes two layers over VapourSynth core API 4.2: an exact C ABI translation and an optional synchronous host interface. VSScript has its own package and its own version negotiation. Importing the declarations does not load a library, create a core, initialize Python, or establish a global context.

| Package import suffix | Reference | Purpose |
| --- | --- | --- |
| `vapoursynth` | [Raw API](raw-api.md), [types and constants](types-and-constants.md) | All 117 stable core function-table entries, plugin initialization, callbacks, handles, layouts, and constants. |
| `vapoursynth/easy` | [Idiomatic host interface](easy.md) | Explicit resource owners, typed map access, plugin calls, synchronous frame requests, and borrowed video rows. |
| `vapoursynth/link` | [Loading and linking](../guides/loading-and-linking.md) | Optional linked `getVapourSynthAPI` entry point. |
| `vapoursynth/vsscript` | [VSScript](vsscript.md) | The independent 16-entry VSScript API 4.2 table. |
| `vapoursynth/vsscript/link` | [VSScript loading](vsscript.md#loading-and-version-negotiation) | Optional linked `getVSScriptAPI` entry point. |

Application examples use an Odin collection named `deps` pointing to this repository's `src` directory:

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

Pass `-collection:deps=vendor/vapoursynth-odin/src` when the checkout is `vendor/vapoursynth-odin`. The collection name belongs to your application; it is not a package installation requirement.

## Choosing a starting point

For a host that invokes plugins and reads frames, start with [`easy`](easy.md). It checks common boundary errors and gives each acquired resource an explicit cleanup procedure. For a plugin, audio buffer processing, asynchronous scheduling, writable frames, or graph inspection, use the [raw API](raw-api.md). Raw handles remain available in the `easy` owners for operations the wrapper does not cover.

The reference describes declarations, default arguments, ownership, and failure results. The [guides](../guides/ownership.md) explain how those rules fit into an application, and the [example sequence](../examples/index.md) supplies complete programs.

## Version and provenance

These bindings select core API **4.2** and VSScript API **4.2** from the checked-in VapourSynth R76 headers, pinned to commit `aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7`. The two version numbers must be requested independently. This documentation describes that pinned interface; an upstream documentation page may describe a newer API.

The source listings on these pages are included directly from the Odin files when the documentation is built. Their spelling, field order, and signatures therefore stay tied to the checkout being documented. See [compatibility](../maintenance/compatibility.md) for the supported ABI surface and [testing](../maintenance/testing.md) for how it is verified.
