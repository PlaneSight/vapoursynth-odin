# Idiomatic Odin interface

`easy` provides synchronous host operations on top of the raw API 4.2 bindings.
It adds typed results, explicit ownership, checked map access, plugin invocation,
and row views for video frames. It has no global core and performs no loading or
initialization until you call a procedure.

```odin
import vs "deps:vapoursynth-odin"
import easy "deps:vapoursynth-odin/easy"
```

Start with [core information](../examples/core_info), then
[typed properties](../examples/properties) and
[frame reading](../examples/easy_host). All three are complete runnable programs.

## Resources and scope

| Acquire | Release | Notes |
| --- | --- | --- |
| `load_library` | `unload_library` | Explicit dynamic loading; requests core API 4.2. |
| `create_core` | `destroy_core` | Accepts an API pointer from dynamic loading, linked bindings, or your own loader. |
| `create_map`, `invoke` | `destroy_map` | Each result owns one map. |
| `map_get_node`, `retain_node` | `destroy_node` | Each result owns one node reference. |
| `get_frame`, `retain_frame` | `destroy_frame` | Each result owns one frame reference. |

Place a `defer` immediately after each successful acquisition. Destroy objects
before their core, and cores before their library. Destruction clears the wrapper
and is harmless if called again on that same cleared value. `unload_library`
returns an error and preserves the owner when unloading fails.

**Assignment does not acquire another reference.** These are ordinary Odin value
types, so copying an owner and destroying both copies would double-release the
resource. Pass pointers when borrowing an owner. Use `retain_node` or
`retain_frame` when you need another independently owned reference. Returning a
new owner by value transfers responsibility to the caller; do not also destroy
the returned resource in the producing scope.

The wrapper fields expose `api` and `handle` for raw API interoperability.
Populate wrappers through these constructors and getters, and preserve their
ownership when using those fields. The raw API cannot track wrapper copies or
protect a dependent object after its core has been destroyed.

Maps are associated with the core passed to `create_map`. Node setters and
`invoke` reject different cores/API tables before calling the raw API. When
mixing raw operations with wrappers, keep that association accurate; do not
insert another core's nodes through the raw handle.

The first version focuses on maps, nodes, synchronous requests, and video plane
access. Filter callbacks, asynchronous scheduling, frame writes, and VSScript
remain available through the raw packages. See the
[invert example](../examples/invert) for a complete raw filter.

## Errors and diagnostics

Operations return `Error` or `(value, Error)`. `.None` means success. Missing
keys, type mismatches, invalid indices, invalid handles, cross-core operations,
and upstream failures have distinct enum values.

`load_library`, `invoke`, and `get_frame` optionally accept `^Diagnostic`:

```odin
diagnostic: easy.Diagnostic
result, err := easy.invoke(&core, "std", "BlankClip", &args, &diagnostic)
if err != .None {
    fmt.eprintln(err, easy.diagnostic_text(&diagnostic))
    return false
}
defer easy.destroy_map(&result)
```

`Diagnostic` contains its own 1024-byte buffer. The wrapper copies an invocation
message before freeing its temporary error map. The message therefore survives
that map's destruction and subsequent API operations. `diagnostic_text` borrows
the diagnostic's buffer until you reuse or destroy the diagnostic value.

Messages hold at most 1023 bytes; inspect `truncated` if the entire message
matters. For frame errors, a full buffer is conservatively marked truncated
because the raw API does not report the original length. The buffer is cleared
at the start of each operation. Validation errors are explained by the enum and
may have no additional message. Diagnostics require no allocator or cleanup.

## Typed map properties

Keys, plugin namespaces, and function names are `cstring`, so string literals
need no conversion or allocation. If you have a dynamic Odin string, create a
terminated string explicitly and keep it alive through the call. Keys follow
`[A-Za-z_][A-Za-z0-9_]*`.

| Value | Set | Get |
| --- | --- | --- |
| `i64` | `map_set_int` | `map_get_int` |
| `f64` | `map_set_float` | `map_get_float` |
| `[]i64` | `map_set_int_array` | `map_get_int_array` |
| `[]f64` | `map_set_float_array` | `map_get_float_array` |
| `[]u8` binary data | `map_set_bytes` | `map_get_bytes` |
| `string` text | `map_set_string` | `map_get_string` |
| Node reference | `map_set_node` or `map_take_node` | `map_get_node` |

Scalar/data/node setters replace by default; pass `.Append` to add another
element. Scalar/data/node getters accept an element index, defaulting to zero.
Array setters replace the entire property, including with an empty typed array.
An empty array returns an empty slice with `.None`; an absent key returns
`.Missing_Key`; scalar access to an empty array returns `.Index_Out_Of_Range`.

Data setters pass explicit byte lengths. Strings and binary values preserve
embedded zero bytes. `map_set_string` marks its data as UTF-8; it does not validate
the encoding. `map_get_string` requires that hint, while `map_get_bytes` accepts
either text or binary data.

Array, string, and byte getters return **borrowed read-only views**, with no copy
or allocation. Do not modify them through Odin's mutable slice type. A map
mutation or destruction may invalidate them; copy data that must outlive the map.
The helpers check maps for error state before accessing their properties.

`map_set_node` gives the map an additional reference. `map_take_node` transfers
your reference and clears the source wrapper once `mapConsumeNode` is called,
including if an append fails with `.Wrong_Type`. Validation failures such as
`.Different_Core` leave the source owned by you. In both cases it is safe to
leave the source's ordinary deferred `destroy_node` in place.

## Frames and rows

`get_frame` validates the index against the node length and requests a frame
synchronously. Use it from a host application, never from a filter's get-frame
callback. `video_info` returns a copy of a video node's information.

`read_plane` returns a borrowed `Plane_View` containing the actual plane width,
height, stride in bytes, sample type, and sample size. Subsampled chroma planes
have their own dimensions. `plane_row` returns active row bytes, excluding
padding; it checks the row index and offset arithmetic.

For typed sample access:

```odin
row, err := easy.plane_row_as(&plane, y, u16)
if err != .None {
    return false
}
for sample in row {
    // Read one native-endian integer sample.
}
```

Supported element types are `u8`, `u16`, `u32`, and `f32`. The helper checks
storage width, integer/float representation, and pointer alignment before
constructing a view. A 10-bit integer plane uses `u16` storage. Half-float frames
can be accessed as bytes through `plane_row`; interpreting half floats is left
to the caller.

All views expire when their frame is destroyed or modified through the raw API.
Keep an owned frame reference for the complete duration of every read.

## Checking behavior

Compile without a runtime:

```console
odin check easy -no-entry-point -vet
```

Run the runtime and failure-boundary tests with your core library:

```console
odin run tests/easy -- /absolute/path/to/libvapoursynth.dll
```

The tests exercise empty values, map errors, binary data, reference transfer,
cross-core rejection, diagnostic lifetimes, stride/typed-row access, and injected
allocation and invocation failures.
