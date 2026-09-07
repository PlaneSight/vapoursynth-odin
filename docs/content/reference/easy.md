# Idiomatic host interface

`easy` adds checked synchronous host operations to the raw core API 4.2 bindings. It makes common ownership changes explicit, translates raw map statuses into an `Error` enum, and returns borrowed frame rows with their dimensions and representation checked. It does not introduce a global library, a global core, implicit initialization, or automatic destruction.

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

Use the [examples](../examples/index.md) for complete programs and the [ownership guide](../guides/ownership.md) for lifecycle diagrams. This page covers every public procedure in the package. The `vs` qualifier in signatures refers to the raw package, and `c` refers to `core:c`.

## Owner and view types

| Type | Stored state | Contract |
| --- | --- | --- |
| `Library` | `dynlib.Library` handle and borrowed `^vs.VSAPI` | Owns one dynamically loaded library. Keep it alive until all dependent resources are gone. |
| `Core` | API pointer and core handle | Owns one core. Does not retain or own a `Library` wrapper. |
| `Map` | API pointer, map handle, originating core handle | Owns one map; the core field records association for validation. It does not acquire a core reference. |
| `Node` | API pointer, node handle, originating core handle | Owns one node reference. |
| `Frame` | API pointer, frame handle, originating core handle | Owns one frame reference. |
| `Plane_View` | Data pointer, dimensions, stride, sample representation | Read-only borrow from a frame; no reference is acquired. |
| `Diagnostic` | Inline `[1024]u8` buffer, `length`, `truncated` | Owns its diagnostic bytes and requires no allocator or cleanup. |
| `Append_Mode` | `enum c.int` with `.Replace` and `.Append` | Restricts the usual raw append choices; invalid cast-in values are rejected. |

Ordinary assignment copies these values without acquiring references. Destroying two copies of the same owner double-releases the underlying resource. Pass `^Node` or `^Frame` to borrow an existing owner; call `retain_node` or `retain_frame` to acquire a second independently destructible reference. There is no clone operation for a library, core, or map owner.

The destruction procedures clear the owner passed to them. Repeating destruction on that same cleared value is harmless. This does not make a different copy safe, and it does not invalidate borrowed views or other copies in the language's type system.

Construct owners through these public acquisition procedures. The exposed `api` and `handle` fields permit raw interoperability, but changing them bypasses the wrapper's invariants. In particular, passing a different core's node into a map through the raw API makes the map's recorded association inaccurate.

## Error results

Procedures return either `Error` or `(value, Error)`. Read the value only after checking for `.None`. A failure result generally contains the zero value or a nil slice; zero is also a valid successful scalar, so it is not an error indicator.

| Error member | Meaning |
| --- | --- |
| `.None` | Operation succeeded. |
| `.Invalid_Handle` | A required wrapper, API pointer, resource handle, or view data pointer is nil or invalid for the checked operation. |
| `.Invalid_Argument` | Invalid key/name/path, unsupported append enum value, or input length that cannot fit the C parameter. |
| `.Missing_Key` | The map does not contain the requested property. |
| `.Wrong_Type` | Property representation differs from the requested type; includes a text read without the UTF-8 hint and a raw append type failure. |
| `.Index_Out_Of_Range` | Negative, too large, or out-of-bounds property, frame, plane, or row index. |
| `.Map_Error` | A map is in the upstream error state or returned inconsistent/unrecognized property information. |
| `.Allocation_Failed` | An API acquisition returned nil where a new core, map, reference, or result map was expected. |
| `.Plugin_Not_Found` | The requested plugin namespace is absent from the core. |
| `.Invocation_Failed` | The invoked plugin returned a map containing an error. |
| `.Frame_Request_Failed` | The synchronous upstream frame request returned nil. |
| `.Wrong_Media_Type` | A procedure received an unsupported node/frame media type, or a video-only operation received audio. |
| `.Unsupported_Format` | The row representation, alignment, dimensions, stride, or offset arithmetic is unsupported. |
| `.Different_Core` | API table or originating core differs between objects that must share a core. |
| `.Unsupported_API` | The loaded library rejected core API 4.2 negotiation. |
| `.Library_Load_Failed` | The platform loader could not load the requested library. |
| `.Symbol_Not_Found` | The loaded library has no `getVapourSynthAPI` export. |
| `.Library_Unload_Failed` | The platform could not unload the owned library; ownership is preserved. |

These checks protect ordinary application boundaries; they cannot prove that an arbitrary non-nil pointer is live. Destroying a core while a node remains, constructing a fake wrapper, or concurrently mutating a borrowed map can still violate the raw API contract. The [error guide](../guides/errors.md) explains how to keep failure paths explicit.

## Diagnostics

```odin
diagnostic_text :: proc(diagnostic: ^Diagnostic) -> string
```

`load_library`, `invoke`, and `get_frame` accept an optional `^Diagnostic`, defaulting to nil. Each clears the supplied diagnostic at the start of the operation. Validation failures may leave it empty; the enum remains the primary status. `diagnostic_text(nil)` returns an empty string.

The diagnostic stores at most **1023 message bytes**, leaving capacity for a terminator where the C frame API needs one. `invoke` copies the error before freeing its temporary result map, so the diagnostic remains available after cleanup and later VapourSynth calls. `diagnostic_text` itself returns a borrowed string into the diagnostic's buffer, valid until that value is reused, modified, or goes out of scope.

Inspect `truncated` when exact diagnostics matter. For a copied invocation message, the flag records omitted bytes. For a frame error, a completely filled buffer is conservatively marked truncated because the upstream function does not report the original length. Loader diagnostics also conservatively mark a filled output buffer. Truncation counts bytes and may split a multibyte UTF-8 sequence.

The following fragment belongs inside a procedure returning `bool`. It assumes a live `easy.Core` named `core`, an argument `easy.Map` named `args` created for that core, and an import of `core:fmt` as `fmt`.

```odin
diagnostic: easy.Diagnostic
result, err := easy.invoke(&core, "std", "BlankClip", &args, &diagnostic)
if err != .None {
    fmt.eprintln(err, easy.diagnostic_text(&diagnostic))
    return false
}
defer easy.destroy_map(&result)
```

## Library loading

```odin
load_library :: proc(path := DEFAULT_LIBRARY, diagnostic: ^Diagnostic = nil) -> (Library, Error)
unload_library :: proc(library: ^Library) -> Error
```

`DEFAULT_LIBRARY` is `libvapoursynth.dll` on Windows, `libvapoursynth.dylib` on Darwin, and `libvapoursynth.so` elsewhere. `path` is an Odin string. An explicit path is useful when several runtime installations exist; dependent libraries still follow platform loader rules.

`load_library` loads the file, resolves `getVapourSynthAPI`, and requests `vs.VAPOURSYNTH_API_VERSION`. On success, the returned `Library` owns the load and provides `library.api`. An empty path returns `.Invalid_Argument`. Loader failure, missing symbol, and rejected API negotiation have distinct errors.

When the symbol or API is rejected, the wrapper unloads the library before returning. Failure to release this rejected load is a hard `ensure` failure, because there is no returned owner through which the caller could safely manage it. For a successfully acquired owner, `unload_library` instead returns `.Library_Unload_Failed` and preserves the owner so the caller can decide how to handle or retry release.

`unload_library(nil)` and unloading an empty owner succeed. Otherwise, call it only after all dependent cores and objects are destroyed and every callback or pending request has finished. See [loading and linking](../guides/loading-and-linking.md) for alternatives that supply an API pointer without the `Library` wrapper.

## Core and map acquisition

```odin
create_core :: proc(api: ^vs.VSAPI, flags: c.int = 0) -> (Core, Error)
destroy_core :: proc(core: ^Core)
core_info :: proc(core: ^Core) -> (vs.VSCoreInfo2, Error)

create_map :: proc(core: ^Core) -> (Map, Error)
destroy_map :: proc(map_: ^Map)
```

`create_core` requires the table obtained by requesting core API 4.2. It checks for a nil table but does not perform version negotiation itself. `flags` defaults to zero and is passed through to `createCore`; combine documented `ccf*` values with `|` as needed. Nil acquisition returns `.Allocation_Failed`.

`create_map` creates an empty owned map and associates it with the given core. Although the raw `createMap` entry takes no core argument, this association enables cross-core checks during invocation and node insertion. Keep that core alive through the map's use.

`core_info` returns a value copy of `VSCoreInfo2`. Numeric fields are independent of the borrowed C structure, but `versionString` remains a borrowed pointer. It is not converted into separately owned text.

Destroy dependent maps, nodes, and frames before `destroy_core`. All four resource destruction procedures accept nil or already-cleared owners and return without action.

## Node and frame references

```odin
retain_node :: proc(node: ^Node) -> (Node, Error)
retain_frame :: proc(frame: ^Frame) -> (Frame, Error)
destroy_node :: proc(node: ^Node)
destroy_frame :: proc(frame: ^Frame)
video_info :: proc(node: ^Node) -> (vs.VSVideoInfo, Error)
```

Each retain operation acquires one upstream reference and returns a new owner carrying the same API and core association. It leaves the original owner intact. A nil input returns `.Invalid_Handle`; a nil reference result returns `.Allocation_Failed`.

`video_info` first verifies `mtVideo`, returning `.Wrong_Media_Type` for an audio node. Its `VSVideoInfo` result is a full value copy, including the embedded format. A copied description does not promise that a variable-format node will produce every frame with those same dimensions or format.

`destroy_node` and `destroy_frame` release one reference and zero the wrapper. A borrowed plane or row does not retain a frame automatically; destruction still invalidates those views.

## Plugin invocation

```odin
invoke :: proc(
    core: ^Core,
    namespace, name: cstring,
    args: ^Map,
    diagnostic: ^Diagnostic = nil,
) -> (Map, Error)
```

`invoke` finds a plugin by namespace and invokes the named function. Both names must be non-nil, nonempty C strings. The argument map is borrowed for the call and remains owned by the caller.

The argument map must carry the same API pointer and core handle as `core`; mismatch returns `.Different_Core` before entering the plugin. A map already in the error state returns `.Map_Error`, with its message copied to the diagnostic when supplied.

| Result | Returned ownership |
| --- | --- |
| Success | New owned result `Map`; destroy it even after extracting a node. |
| Namespace absent | `.Plugin_Not_Found`, no result map. |
| Upstream invoke returned nil | `.Allocation_Failed`, no result map. |
| Upstream result contains an error | `.Invocation_Failed`; the wrapper copies the diagnostic and frees the failed result map. |

The wrapper does not pre-validate a plugin's argument schema. Missing functions, missing required arguments, and plugin-specific validation are reported by the invocation error. Extract a node with `map_get_node` to acquire an independent reference before destroying the result map.

## Map boundary rules

All typed map procedures validate the wrapper, require a core association, and check the upstream map error state before accessing properties. Keys must match `[A-Za-z_][A-Za-z0-9_]*`. Keys are `cstring`; a dynamic Odin string must be terminated explicitly and kept alive through the call.

Scalar, data, and node setters default to `.Replace`. `.Append` adds an element when the existing property's type is compatible; incompatible raw writes become `.Wrong_Type`. A cast-created `Append_Mode` outside the two documented values returns `.Invalid_Argument`.

Indexed getters default to index zero. Negative indices and values above `max(c.int)` are rejected before conversion; the raw accessor checks the property's actual bounds. Input byte lengths and numeric array lengths must fit `c.int`. On the supported targets this upper limit is `2_147_483_647`; the limit does not imply that such a large allocation is practical or available.

## Scalar properties

```odin
map_set_int :: proc(map_: ^Map, key: cstring, value: i64, mode: Append_Mode = .Replace) -> Error
map_set_float :: proc(map_: ^Map, key: cstring, value: f64, mode: Append_Mode = .Replace) -> Error
map_get_int :: proc(map_: ^Map, key: cstring, index: int = 0) -> (i64, Error)
map_get_float :: proc(map_: ^Map, key: cstring, index: int = 0) -> (f64, Error)
```

Integer properties preserve `i64` values; floating-point properties use `f64`. The wrapper does not silently narrow to Odin `int` or `f32` and does not convert an integer property into a float property. Perform any application-specific range checking before a subsequent cast.

The returned scalars are value copies. Missing properties, incompatible types, out-of-range indices, and map errors are returned distinctly. Scalar access to an existing empty typed array returns `.Index_Out_Of_Range`.

## Numeric arrays

```odin
map_set_int_array :: proc(map_: ^Map, key: cstring, values: []i64) -> Error
map_set_float_array :: proc(map_: ^Map, key: cstring, values: []f64) -> Error
map_get_int_array :: proc(map_: ^Map, key: cstring) -> ([]i64, Error)
map_get_float_array :: proc(map_: ^Map, key: cstring) -> ([]f64, Error)
```

Array setters replace the whole property and copy the input data into the map. Empty input creates or replaces the property with an empty array of the selected type. There is no append parameter for an array setter.

Array getters return borrowed read-only storage without allocation or copying. An existing typed empty array returns an empty slice and `.None`; an absent property returns `.Missing_Key`. The wrapper checks type and count before calling the raw array getter, including the empty-array case that raw indexed access would reject.

Do not mutate a returned slice. Any mutation or destruction of the map may invalidate it. Copy an array before modifying its contents or retaining it beyond the map's lifetime.

## Bytes and strings

```odin
map_set_bytes :: proc(map_: ^Map, key: cstring, value: []u8, mode: Append_Mode = .Replace) -> Error
map_set_string :: proc(map_: ^Map, key: cstring, value: string, mode: Append_Mode = .Replace) -> Error
map_get_bytes :: proc(map_: ^Map, key: cstring, index: int = 0) -> ([]u8, Error)
map_get_string :: proc(map_: ^Map, key: cstring, index: int = 0) -> (string, Error)
```

Both setters copy an explicitly sized byte sequence. Embedded zero bytes are preserved. `map_set_bytes` sets the `dtBinary` hint, while `map_set_string` sets `dtUtf8`; neither validates content encoding.

`map_get_bytes` accepts data regardless of the text/binary hint. `map_get_string` requires `dtUtf8` and otherwise returns `.Wrong_Type`. It uses the stored size, so a zero byte inside a string does not truncate the result. The extra terminator maintained by VapourSynth is excluded from both returned lengths.

Both getters borrow read-only map storage. An empty stored value succeeds with an empty result. Copy the returned bytes or string before modifying the map or keeping data after its destruction. See the [map guide](../guides/maps.md) for examples distinguishing empty data from missing properties.

## Node properties and reference transfer

```odin
map_get_node :: proc(map_: ^Map, key: cstring, index: int = 0) -> (Node, Error)
map_set_node :: proc(map_: ^Map, key: cstring, node: ^Node, mode: Append_Mode = .Replace) -> Error
map_take_node :: proc(map_: ^Map, key: cstring, node: ^Node, mode: Append_Mode = .Replace) -> Error
```

`map_get_node` returns a new owned reference independent of the map's reference. Destroying the map therefore does not destroy the returned owner. The map's recorded core association is copied into the `Node`.

`map_set_node` gives the map another reference while the caller keeps its owner. `map_take_node` gives the map the caller's reference and clears the source owner after calling the raw consuming operation.

| `map_take_node` outcome | Source `Node` |
| --- | --- |
| Invalid map/key/mode/node, error-state map, or different API/core | Unchanged; caller still owns the reference. |
| Raw consuming call succeeds | Cleared; reference has been transferred. |
| Raw consuming call fails, such as incompatible append type | Cleared; the raw API consumes the reference even on failure. |

An ordinary deferred `destroy_node(&node)` is safe in every row of this table: it releases a reference only if the source still holds one. Do not infer transfer solely from `.None`; inspect the operation's contract. Frame and function map operations remain available through the raw table.

## Synchronous frame requests

```odin
get_frame :: proc(node: ^Node, index: int, diagnostic: ^Diagnostic = nil) -> (Frame, Error)
```

`get_frame` accepts video or audio nodes, validates a nonnegative index no greater than `0x7fffffff`, checks it against `numFrames`, and requests the frame synchronously. Success returns an owned reference associated with the node's core. A failed upstream request returns `.Frame_Request_Failed` and an optional durable diagnostic.

Use this from a host, never from a filter's get-frame callback. A filter uses `requestFrameFilter` and `getFrameFilter` through the raw API so the scheduler can resolve dependencies without a nested synchronous host request.

## Video planes and rows

```odin
read_plane :: proc(frame: ^Frame, index: int) -> (Plane_View, Error)
plane_row :: proc(plane: ^Plane_View, row: int) -> ([]u8, Error)
plane_row_as :: proc(plane: ^Plane_View, row: int, $T: typeid) -> ([]T, Error)
    where T == u8 || T == u16 || T == u32 || T == f32
```

`read_plane` requires a video frame and a valid plane index. It records the actual plane width, height, positive byte stride, meaningful bits, storage bytes, and integer/float sample kind. It rejects zero or negative dimensions, impossible row widths, stride shorter than active row data, and offset arithmetic that would exceed Odin `int`.

`plane_row` returns exactly `width * bytes_per_sample` active bytes for the selected row, excluding padding. It checks the row bounds and its byte-offset arithmetic. A row's start is `data + row * stride`; the next row is not necessarily adjacent to the last active sample.

`plane_row_as` first performs the byte-row checks, then requires the requested element width, sample kind, and pointer alignment to match:

| Element type | Required storage | Examples |
| --- | --- | --- |
| `u8` | One-byte integer samples | Gray8 and 8-bit RGB/YUV planes. |
| `u16` | Two-byte integer samples | 9–16 bit integer formats, including 10-bit samples stored in 16 bits. |
| `u32` | Four-byte integer samples | 32-bit integer storage. |
| `f32` | Four-byte floating-point samples | Single-precision float formats. |

The helper reinterprets a compatible native sample representation; it does not normalize integer ranges, change endianness, convert a 10-bit sample to a different bit depth, or decode half floats. Unsupported element types fail the compile-time `where` constraint. A supported type with incompatible storage or misalignment returns `.Unsupported_Format`. Half-float rows are still available as bytes through `plane_row`.

All plane and row results are read-only borrows even though Odin's slice type is mutable. Retain the source frame for the full duration of every read. Destroying the frame or modifying it through the raw API expires these views; requesting a raw write pointer can invalidate previously acquired read pointers.

## Scope of the wrapper

The current package covers synchronous requests, video metadata and rows, integer/float/data/node map properties, invocation, and explicit ownership. Audio sample access, writable frames, filter callbacks, asynchronous requests, function/frame map values, and VSScript use the raw packages. This keeps the ownership boundary visible while allowing a host to adopt helpers incrementally.

The [raw API reference](raw-api.md) lists every available table entry. When mixing the layers, preserve the wrapper's API/core association and its single owned reference; the wrapper cannot observe a raw free or acquire references on your behalf.

## Complete public type declarations

This listing is included directly from `src/vapoursynth/easy/types.odin` and gives the exact fields of the owners, diagnostic, view, and enums discussed above. A field's presence supports interoperability; it does not change the documented ownership contract.

```odin title="src/vapoursynth/easy/types.odin"
--8<-- "src/vapoursynth/easy/types.odin"
```
