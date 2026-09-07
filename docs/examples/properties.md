# Work with typed map properties

A `VSMap` carries plugin arguments, function results, and frame properties. Learning its type and lifetime rules pays off before you create a filter graph. This example writes and reads a standalone map using `easy`, including binary data, arrays, and an intentionally empty property.

The package is `examples/properties`. It reuses the library and core lifetime from [core information](core-info.md), then creates one owned map inside that lifetime. It needs no source clip or Python interpreter.

## Run and inspect the result

From the repository root:

=== "Windows"

    ```powershell
    odin run examples/properties -- "C:\path\to\libvapoursynth.dll"
    ```

=== "Linux"

    ```sh
    odin run examples/properties -- /absolute/path/to/libvapoursynth.so
    ```

=== "macOS"

    ```sh
    odin run examples/properties -- /absolute/path/to/libvapoursynth.dylib
    ```

Omit the argument when your platform loader can find the default core library. You can check the package without a runtime using `odin check examples/properties -vet`.

A successful run prints:

```text
Frame 42: "example frame"; exposure: 1.25
Binary payload (4 bytes, including the embedded zero): [65, 0, 66, 255]
Durations: [1001, 1001, 1001]; weights: [0.25, 0.5, 0.25]
Existing empty array: 0 elements; absent key: Missing_Key
```

The final line demonstrates two valid, distinct outcomes. An existing integer property can contain zero elements; an absent key produces `.Missing_Key`. Treating both as a zero-valued scalar would lose information.

## Establish one map owner

```odin
properties, map_error := easy.create_map(&core)
```

After checking `.None`, the example immediately registers `defer easy.destroy_map(&properties)`. The map is associated with the core passed to its constructor. That association lets later wrapper operations reject attempts to combine resources from different cores.

`write_properties` and `read_properties` receive `^easy.Map`. They borrow the owner; neither procedure destroys it or takes ownership. Their boolean result tells `run` whether to continue. This makes the lifetime independent of how many helper procedures operate on the map.

The resulting destruction order is map, core, library. Failure partway through writing still returns through the same cleanup path. The map can contain some successfully written properties when a later setter fails; the example discards that partial map instead of pretending the entire batch succeeded.

## Match types at the boundary

The example deliberately uses all of these forms:

| Key | Setter | Stored value |
| --- | --- | --- |
| `frame_number` | `map_set_int` | One `i64`, value `42` |
| `exposure` | `map_set_float` | One `f64`, value `1.25` |
| `label` | `map_set_string` | UTF-8-hinted data, `"example frame"` |
| `payload` | `map_set_bytes` | Binary data, `[65, 0, 66, 255]` |
| `durations` | `map_set_int_array` | Three `i64` elements |
| `weights` | `map_set_float_array` | Three `f64` elements |
| `empty` | `map_set_int_array` | Zero `i64` elements |

Each setter returns `easy.Error`; `.None` indicates success. The example reports the specific operation and returns early on failure. A map is typed at each key, so choose a getter matching the value that was stored. There is no implicit conversion from a floating-point property to an integer property.

Scalar and data setters replace existing values by default. Their optional `.Append` mode adds an element to a property of the appropriate type. Whole-array setters replace the property's entire list. See [maps](../guides/maps.md) for indexing, append behavior, and reference-valued properties.

Keys are `cstring` values. The literal keys in the example already satisfy the interface. For a dynamically produced Odin string, explicitly create a terminated string whose lifetime spans the call. `easy` validates key spelling; do not assume arbitrary human-readable labels are valid property keys.

## Preserve binary data exactly

```odin
payload := [?]u8{65, 0, 66, 255}
```

`map_set_bytes` passes the payload's explicit length. The byte at index 1 is zero, but it does not end the value. The following bytes, including `255`, survive the round trip. This is why binary map data must be read using the recorded size instead of a `cstring` conversion.

Text also uses explicit lengths. `map_set_string` adds the UTF-8 hint, while `map_get_string` expects that hint. The setter labels the data; it does not validate UTF-8 encoding. The byte getter can read either text or binary data when the application needs the raw bytes.

The inputs `payload`, `durations`, and `weights` are local arrays in `write_properties`. The setters copy their values into the map. The map remains readable after that procedure returns and those arrays leave scope.

## Borrow the values you read

The scalar getters return copied numbers. The string, bytes, and array getters return views of memory owned by the map:

```odin
durations, ints_error := easy.map_get_int_array(properties, "durations")
```

After a successful call, `durations` needs no release. It must be treated as read-only, even though Odin's slice type permits writes. Mutating or destroying the map can invalidate it. Copy any data that must survive such an operation into storage owned by your application.

The example's separation into a write phase followed by a read phase is useful here. No setter runs while `read_properties` holds borrowed views, and the map stays alive until reading and printing finish. Avoid returning one of these slices to a caller after deferring destruction of the map in the producing procedure.

These are different contracts from `map_get_node`, introduced in the [frame-host tutorial](easy-host.md): reading a node acquires an owned native reference rather than a borrowed slice.

## Preserve empty-versus-missing semantics

```odin
empty, empty_error := easy.map_get_int_array(properties, "empty")
```

This call succeeds with a zero-length slice. The example checks both the error and the length. Reading `"missing"` as an integer returns `.Missing_Key`, which is the expected result for that separate operation.

Three cases deserve separate handling in real argument parsing:

| Request | Result |
| --- | --- |
| Read all integers from existing `empty` | Empty slice and `.None` |
| Read scalar element zero from existing `empty` | `.Index_Out_Of_Range` |
| Read a property that does not exist | `.Missing_Key` |

For an optional argument, absence might select a default. An explicitly supplied empty array may have another meaning. Let the application's domain decide; retain the distinction until that decision is made.

## Useful changes to try

Read `"exposure"` with `map_get_int` and check that the result is `.Wrong_Type`. Read element zero from `"empty"` and check `.Index_Out_Of_Range`. These changes exercise meaningful boundaries without relying on a particular numeric fallback value after an error.

To practice copying, obtain a borrowed byte slice, clone it into application-owned storage, replace the map value, and inspect only the clone afterward. Keep the clone's allocator and cleanup visible. The [ownership guide](../guides/ownership.md) explains why keeping the old borrowed slice would be invalid.

If the binary output appears truncated in your adaptation, look for a conversion to `cstring`. If an integer getter reports a type error, inspect which setter last replaced that key. If a read works before a map update but fails unpredictably afterward, check whether your code retained a borrowed view across the mutation.

## Complete source

```odin title="examples/properties/main.odin"
--8<-- "examples/properties/main.odin"
```

Continue with [requesting and reading a frame](easy-host.md), where maps become the arguments and results of a plugin invocation.
