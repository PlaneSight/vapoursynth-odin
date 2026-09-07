# Loading, linking, and API negotiation

Every core API operation is called through a `^vs.VSAPI` table. A native host obtains that table from the exported `getVapourSynthAPI` entry point. A plugin receives the table from VapourSynth. The raw root package declares the ABI but does not choose either loading strategy for you.

The host interface accepts an API pointer obtained by dynamic loading, a linked entry point, or your application's own loader. Its `load_library` helper provides one explicit implementation of runtime loading; the rest of `easy` does not depend on how you acquired that pointer.

## Choose the integration boundary

| Application shape | How to obtain the API | Relevant package |
| --- | --- | --- |
| Host selects a library path at runtime | Load the library and resolve `getVapourSynthAPI`. | `easy`, or root plus `core:dynlib`. |
| Host uses the platform's normal linker resolution | Call the linked `getVapourSynthAPI` declaration. | `link`. |
| Plugin loaded into VapourSynth | Use the API supplied to registration and processing callbacks. | Root. |
| Host evaluates Python scripts | Obtain `VSSCRIPTAPI`, then negotiate a core API through it. | `vsscript`, optionally `vsscript/link`. |

Dynamic loading is useful for a host that accepts an explicit core path or wants to report load failure as an application error. Linking is useful when packaging determines the library up front. A plugin should normally work with the core and API passed by its host rather than creating a second runtime relationship.

## Dynamic loading with `easy`

`load_library` performs three checks in order:

1. Ask the platform loader to open the selected path.
2. Resolve the exported symbol named `getVapourSynthAPI`.
3. Call that entry point with `vs.VAPOURSYNTH_API_VERSION`, requesting API 4.2.

This excerpt assumes imports of `easy` and `core:fmt` and a surrounding procedure returning `bool`:

```odin
diagnostic: easy.Diagnostic
library, err := easy.load_library(easy.DEFAULT_LIBRARY, &diagnostic)
if err != .None {
    fmt.eprintln("Load VapourSynth:", err, easy.diagnostic_text(&diagnostic))
    return false
}
defer {
    unload_error := easy.unload_library(&library)
    ensure(unload_error == .None)
}

core, core_error := easy.create_core(library.api)
if core_error != .None {
    fmt.eprintln("Create core:", core_error)
    return false
}
defer easy.destroy_core(&core)
```

The default path is a platform-specific filename:

| Platform | `easy.DEFAULT_LIBRARY` |
| --- | --- |
| Windows | `libvapoursynth.dll` |
| Linux | `libvapoursynth.so` |
| macOS | `libvapoursynth.dylib` |

An explicit absolute path selects a particular core library. A bare filename delegates discovery to the operating system loader and its configured search paths. The bindings do not search Python installations, inspect a registry, download a runtime, or adjust environment variables.

The repository's optional development helper does perform Python-package discovery:

```console
uv run tools/run_host.py core_info
```

It selects the library beside the installed VapourSynth module and passes its absolute path to the Odin host. Official Unix wheels use versioned names, `libvapoursynth.so.4` on Linux and `libvapoursynth.4.dylib` on macOS; those differ from the bare defaults above. See [Python environments and plugin wheels](python-packaging.md) for uv setup and native plugin discovery.

Loading the main file can still fail because one of its dependencies is missing or has the wrong architecture. Preserve the loader diagnostic and verify the selected library's dependencies when the file visibly exists but cannot be loaded. Consult the [official VapourSynth installation guide](https://www.vapoursynth.com/doc/installation.html) for current platform installation and configuration procedures.

The [core information example](../examples/core-info.md) accepts the path as its sole optional argument. The [raw host](../examples/raw-host.md) shows the equivalent sequence directly through `core:dynlib`, including casting the resolved symbol to `vs.VSGetVapourSynthAPI`.

## Negotiating a version establishes the table layout

The compile-time core request is:

```odin
vs.VAPOURSYNTH_API_VERSION // (4 << 16) | 2
```

The major number occupies the high 16 bits and the minor number the low 16 bits. Always test the returned API pointer for `nil` before reading fields or calling a procedure through it. A runtime that cannot supply the requested version returns `nil`.

The root declarations are pinned to the API 4.2 layout from VapourSynth R76. Successful negotiation is what permits code to use that layout. Do not change the request to an older minor version merely to obtain a non-nil pointer while continuing to access API 4.2 fields.

`easy.create_core` assumes the pointer already came from a successful API 4.2 request. It checks for `nil`, but it does not independently negotiate the table's version. This matters when you supply a pointer from a linked entry point or custom loader.

The API table belongs to the library. Keep it as a borrowed pointer: do not allocate it yourself, copy its contents into a replacement table, modify its procedure entries, or free it. The table and the native code it points to must remain available through all resource destruction.

The experimental graph inspection extension has a stricter compatibility rule. It requires an exact `getAPIVersion()` match, additional core flags, and restricted execution conditions. It is not a general extension to assume after ordinary stable-API negotiation. See [the raw API reference](../reference/raw-api.md).

## Linking the core entry point

Import `link` when you want the compiler and platform linker to resolve the native entry point. This complete program assumes the dependency layout from [installation](../getting-started/installation.md):

```odin
package main

import "core:fmt"
import vs "deps:vapoursynth-odin"
import vs_link "deps:vapoursynth-odin/link"
import easy "deps:vapoursynth-odin/easy"

main :: proc() {
    api := vs_link.getVapourSynthAPI(vs.VAPOURSYNTH_API_VERSION)
    if api == nil {
        fmt.eprintln("VapourSynth API 4.2 is unavailable.")
        return
    }

    core, err := easy.create_core(api)
    if err != .None {
        fmt.eprintln("Create core:", err)
        return
    }
    defer easy.destroy_core(&core)

    info, info_error := easy.core_info(&core)
    if info_error != .None {
        fmt.eprintln("Read core information:", info_error)
        return
    }
    fmt.println(info.versionString)
}
```

The program uses the same `easy.Core` operations as a dynamically loaded host. It has no `easy.Library` owner to unload because it did not call `easy.load_library`.

The linked package's default foreign library configuration is `system:vapoursynth.lib` on Windows and `system:vapoursynth` elsewhere. Override it at build time when the required library is outside the normal linker search location:

=== "Windows"

    ```powershell
    odin build . -collection:deps=vendor "-define:VAPOURSYNTH_LIBRARY=C:/path/to/vapoursynth.lib"
    ```

=== "Linux"

    ```console
    odin build . -collection:deps=vendor -define:VAPOURSYNTH_LIBRARY=/absolute/path/to/libvapoursynth.so
    ```

=== "macOS"

    ```console
    odin build . -collection:deps=vendor -define:VAPOURSYNTH_LIBRARY=/absolute/path/to/libvapoursynth.dylib
    ```

The Windows `.lib` file is an import library used during linking; the corresponding runtime DLL remains necessary when the executable runs. Providing an import-library path does not make the executable self-contained. Dynamic loading avoids the import-library requirement because the program resolves the export at runtime.

Likewise, a successful build on Unix does not by itself configure the deployed program's runtime library search. Package the application and configure the loader according to your platform and deployment requirements.

## Plugins receive their APIs

A plugin exports `VapourSynthPluginInit2`. VapourSynth calls that entry point with a plugin handle and `^VSPLUGINAPI`, which the plugin uses to configure itself and register functions. Registered functions and frame-processing callbacks receive `^VSAPI` as specified by their callback signatures.

This separates two tables with different responsibilities: `VSPLUGINAPI` is the registration interface; `VSAPI` is the core operations table. Do not treat one as the other or call an exported getter unnecessarily from a plugin callback.

Declare exported entry points and callbacks with `proc "system"`, as in the [identity plugin](../examples/identity-plugin.md). This matches the upstream `VS_CC` convention: `stdcall` on Windows x86, and the C convention on the other supported targets.

Foreign callbacks do not receive Odin's implicit context. If callback code uses Odin operations that need a context, establish one in that callback, for example with `context = runtime.default_context()` after importing `base:runtime`. The raw VapourSynth calls themselves use their declared context-free foreign convention. The [invert plugin](../examples/invert-plugin.md) shows callback and instance lifetimes in a complete filter.

Build the minimal example from the repository root:

```console
uv run tools/examples.py build plugin
```

This writes `.build/examples/plugin` with the platform's shared-library extension.
The resulting plugin must match the architecture of the VapourSynth process that
loads it. The [identity tutorial](../examples/identity-plugin.md) also shows the
direct Odin compiler command for this layout.

## VSScript is a separate loading decision

VSScript supplies script evaluation and output enumeration through `VSSCRIPTAPI`. Its linked package defaults to `system:vsscript.lib` on Windows and `system:vsscript` elsewhere. The corresponding build override is `VSSCRIPT_LIBRARY`.

Request `vsscript.VSSCRIPT_API_VERSION` from `getVSScriptAPI` and check for `nil`. Then request the desired core API separately through the script table's `getVSAPI`. The shared minor number in these packages does not make those negotiations interchangeable.

When dynamically loading VSScript on Unix, use `dynlib.load_library(path, global_symbols = true)` so Python extension modules can resolve their symbols. This requirement belongs to embedding the script runtime; the core-only `easy.load_library` helper does not provide VSScript loading or script-environment ownership.

A script environment can consume a supplied core, and that transfer applies even if `createScript` fails. Do not leave an `easy.Core` wrapper scheduled to destroy a core after transferring that same core into VSScript. Design the integration around the [VSScript ownership contract](../reference/vsscript.md) before combining the two interfaces.

## Unload only after the final dependent resource

Library lifetime is the outermost runtime scope. Destroy maps, node references, and frame references; finish requests; destroy cores; then unload. Unloading while any dependent callback or cleanup can still execute leaves procedure pointers referring to unavailable native code.

`easy.unload_library` returns `.Library_Unload_Failed` and preserves its owner on failure. It clears the owner after a successful release and treats a nil or already-cleared owner as successfully unloaded. During `load_library`, a library rejected for an absent entry point or incompatible API is released before returning; failed mandatory release uses `ensure` to stop rather than silently leak a rejected library.

The examples place deferred cleanup in a `run` procedure and report its final result from `main`, so early operational failures still leave scope through the normal cleanup path. That same structure scales to an application with explicit initialization and shutdown phases. The [ownership guide](ownership.md) explains how to keep those phases consistent as maps, nodes, and frames are added.
