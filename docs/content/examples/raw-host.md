# Host through the raw API

The raw host performs the same broad workflow as the `easy` host: load VapourSynth, create a core, invoke `std.BlankClip`, obtain a node, and read a frame. It spells out the C-level calls and error checks so you can see exactly what a wrapper must own and validate.

The package is `examples/host`. It uses only the raw bindings and Odin's standard library. The raw package provides types and tables without choosing a loader or creating a core for the application.

## Run and compare

From the repository root:

```console
uv run tools/run_host.py host
```

This builds the native executable under `.build/examples` and runs it with the
VapourSynth core library from the uv environment. The command is the same on
Windows, Linux, and macOS; see the [build guide](../guides/previewing-examples.md#one-build-command-on-every-supported-platform)
for supported targets. The executable itself uses the native core API and does
not embed Python.

To compile without executing the host, run `uv run tools/examples.py build host`.
For a separate native runtime, pass its path as described in the
[loading guide](../guides/loading-and-linking.md#dynamic-loading-with-easy).

After the core's version information, expect a line with this shape:

```text
Frame 0: 64 x 48 Gray8; stride: <bytes>; first pixel: 17
```

This example checks the dimensions and first sample. The [easy host](easy-host.md) uses a 65-pixel width and checks every active sample through row views. The different sizes and checks are deliberate; these are two focused demonstrations rather than identical performance comparisons.

## Resolve the entry point with its declared type

The host selects a default filename using compile-time `when ODIN_OS` branches, then calls `dynlib.load_library`. Once loading succeeds, a deferred unload keeps the library alive for the remainder of `run`.

```odin
symbol, found := dynlib.symbol_address(library, "getVapourSynthAPI")
```

A successful library load does not guarantee the expected symbol exists. The host checks symbol lookup before casting the address to the binding's `VSGetVapourSynthAPI` procedure type:

```odin
get_api := cast(vs.VSGetVapourSynthAPI)symbol
api := get_api(vs.VAPOURSYNTH_API_VERSION)
```

The declared procedure type carries the required foreign calling convention and argument representation. Avoid replacing it with an ordinary Odin procedure type. After calling the entry point, a nil API pointer means the runtime did not accept the requested version. The host stops before dereferencing the table.

The table contains function pointers and is borrowed from the loaded library. It has no separate `free` operation. Every API call, including cleanup, must complete before unloading that library. The [raw API reference](../reference/raw-api.md) describes the package boundary; [loading and linking](../guides/loading-and-linking.md) covers other acquisition strategies.

## Own the core, borrow the plugin

`api.createCore(vs.ccfDisableAutoLoading)` returns a core pointer, which the host checks and pairs with `defer api.freeCore(core)`. It then fills a `VSCoreInfo2` value to print runtime information.

```odin
std := api.getPluginByNamespace("std", core)
```

The `std` pointer identifies the built-in plugin owned by the core. It is borrowed, so the host checks that it exists but does not schedule a separate plugin release. This distinction matters when reading a sequence of pointer-returning calls: a pointer alone does not tell you whether the caller acquires ownership.

The argument map is different. `api.createMap()` returns an owned map, and the host must call `freeMap` after using it. The raw constructor has no core argument, while `easy.create_map` records a core association to validate later wrapper operations. Raw callers remain responsible for using compatible resources themselves.

## Check C success conventions individually

The argument setters use `maReplace` explicitly and return zero on success. The host tests them in one short-circuiting failure condition. If a setter fails, subsequent setters are skipped and the partially populated map is released by its defer.

Do not infer one universal success convention from the integer return type. The functions encountered across these examples use several forms:

| Operation | Success indicator | Failure detail |
| --- | --- | --- |
| `createCore`, `createMap` | Non-nil pointer | Nil pointer |
| `mapSetInt`, `mapSetFloat` | Zero return value | Nonzero return value |
| `mapGetNode` | Node plus `peSuccess` out parameter | Property error code |
| `invoke` | Result map with no map error | Nil result or `mapGetError` message |
| `getFrame` | Non-nil frame | Caller-provided error buffer |
| Plugin registration in the next tutorial | Nonzero return value | Zero return value |

The raw binding preserves those conventions. The optional wrapper translates them into `easy.Error` values, but the underlying API remains available unchanged.

## Inspect invocation results before their properties

```odin
result := api.invoke(std, "BlankClip", args)
```

The host checks for a nil result, then schedules `freeMap(result)`. Before reading `"clip"`, it calls `mapGetError`. A plugin can return a valid map object whose contents represent an error. Treating every non-nil map as success would miss that condition.

`mapGetError` returns borrowed message text. The example prints it while the result map is still alive. If you need to retain it after `freeMap`, copy it first; this is one of the lifetime details implemented by `easy.Diagnostic`.

The node getter requires an explicit C integer out parameter:

```odin
property_error: c.int
node := api.mapGetNode(result, "clip", 0, &property_error)
```

The code checks both `peSuccess` and a non-nil node. A successful getter acquires a node reference, so it adds `defer api.freeNode(node)`. Freeing the result map later releases the map's reference independently.

## Request a frame with owned error storage

The host places a 1024-byte array on its stack and passes both its pointer and its capacity to `getFrame`. The capacity uses `c.int`, matching the C signature. If evaluation fails, the frame is nil and the host prints the terminated message from that still-live array.

On success, the host schedules `freeFrame`, reads plane zero's dimensions and pointer, checks the pointer, and inspects its first sample. That pointer borrows storage from the frame. No separate deallocation is needed, and using it after `freeFrame` would be invalid.

This example only reads the first byte, so row padding cannot affect its sample check. When extending it to scan the image, use `getStride` to find each row and stop at the active width. For subsampled formats, obtain each plane's dimensions separately. The [frame guide](../guides/frames.md) provides the general rules.

## Keep release order visible

Successful completion releases the frame, node, result map, argument map, core, and library in that order. The map and node references could be scoped more tightly, but their dependencies are respected here. Early returns execute whichever releases have already been registered.

Raw pointers are not automatically cleared by `freeNode` or `freeFrame`. If you add an early manual release, also adjust the deferred release or replace the pointer with nil as appropriate. The code currently has one release path per acquired resource, which makes the obligations straightforward to audit.

If invocation fails after you modify arguments, print `mapGetError` before destroying the result. If output differs from the expected 64 × 48 Gray8 frame, confirm the argument types and values before investigating memory access. A library missing `getVapourSynthAPI` usually means the wrong kind of library was selected; the platform-specific loading guide covers that boundary.

## Complete source

```odin title="examples/host/main.odin"
--8<-- "examples/host/main.odin"
```

Continue with [the identity plugin](identity-plugin.md), where VapourSynth supplies the API table to your code.
