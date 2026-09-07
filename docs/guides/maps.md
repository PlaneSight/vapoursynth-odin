# Maps, properties, and plugin arguments

VapourSynth uses maps to carry plugin arguments, plugin results, and frame
properties. A map associates each key with a **typed sequence of values**. What
looks like a scalar argument is a property containing one element; an array is
the same kind of property with several elements.

The `easy` package provides checked access to integers, floats, text, binary
data, numeric arrays, and node references. These helpers make type mismatches
and missing values explicit, but preserve VapourSynth's ownership rules.

This guide assumes you have loaded the core library and created an `easy.Core`,
as shown in the [quickstart](../getting-started/quickstart.md). For an executable
demonstration of the operations below, run the
[properties example](../examples/properties.md).

## Create a map within a core's lifetime

Create maps with `easy.create_map`, then release them with `easy.destroy_map`:

```odin
// Inside a procedure returning bool; core is a live easy.Core value.
properties, err := easy.create_map(&core)
if err != .None {
    return false
}
defer easy.destroy_map(&properties)
```

The snippet uses this import when the repository is available through the
`deps` collection:

```odin
import easy "deps:vapoursynth-odin/easy"
```

A wrapper map records the core and API table it belongs to. This association
lets `invoke` and the node setters reject incompatible objects with
`.Different_Core`. Preserve it when interoperating with the raw API. In
particular, inserting another core's node through `properties.handle` bypasses
the wrapper's check and breaks its assumptions.

Destroy dependent maps before destroying the core, and keep the library loaded
through all cleanup. Assignment copies the wrapper fields without acquiring
another owned map. Pass `^easy.Map` to helpers that borrow an existing map;
see [ownership](ownership.md) for the complete lifetime model.

## Keys are C strings; values have explicit types

Keys are `cstring` values following this grammar:

```text
[A-Za-z_][A-Za-z0-9_]*
```

`"width"`, `"frame_number"`, and `"_Range"` are valid keys. An empty key,
`"frame-number"`, and `"0width"` are invalid. The wrapper reports
`.Invalid_Argument` before calling the raw accessor.

String literals work directly at these call sites. A dynamic Odin `string`
must be converted to storage with a terminating zero, and that storage must
remain alive throughout the call. Casting a counted Odin string does not add a
terminator. The wrapper can validate key characters, but it cannot make an
invalid C pointer or an unterminated buffer safe to read.

Choose accessors by the property's declared type:

| Property value | Setter | Getter | Get result |
| --- | --- | --- | --- |
| Integer element | `map_set_int` | `map_get_int` | `i64` |
| Float element | `map_set_float` | `map_get_float` | `f64` |
| Integer sequence | `map_set_int_array` | `map_get_int_array` | `[]i64` |
| Float sequence | `map_set_float_array` | `map_get_float_array` | `[]f64` |
| Binary data element | `map_set_bytes` | `map_get_bytes` | `[]u8` |
| Text data element | `map_set_string` | `map_get_string` | `string` |
| Node element | `map_set_node`, `map_take_node` | `map_get_node` | Owned `Node` |

Numeric getters do not convert between integers and floats. A plugin argument
declared as a float needs `map_set_float`, even when the intended value is a
whole number. For example, the host example supplies BlankClip's `color` through
the float setter.

## Replace, append, and index

Scalar, data, and node setters default to `.Replace`: the new value replaces the
property with a one-element sequence. Pass `.Append` to extend it. Appending to
an absent key creates the property; appending an incompatible property type
returns `.Wrong_Type`.

This complete helper uses the `easy` import above:

```odin
write_durations :: proc(properties: ^easy.Map) -> easy.Error {
    if err := easy.map_set_int(properties, "durations", 1001); err != .None {
        return err
    }
    if err := easy.map_set_int(properties, "durations", 2002, .Append); err != .None {
        return err
    }
    return .None
}
```

After success, `"durations"` contains two integers. `map_get_int(properties,
"durations")` reads element zero. Supplying `1` as the third argument reads
`2002`. Supplying `2` returns `.Index_Out_Of_Range`. Always check the returned
error before interpreting the value: a returned zero with an error is not a
stored zero.

The array setters replace the entire sequence and have no append-mode
parameter. If all values are already available, one array setter expresses that
operation directly:

```odin
// Inside a procedure returning easy.Error; properties is ^easy.Map.
durations := [?]i64{1001, 1001, 2002}
if err := easy.map_set_int_array(properties, "durations", durations[:]); err != .None {
    return err
}
```

The map copies numeric arrays and data values during setters. The local
`durations` array can leave scope after the call.

## Empty is different from missing

A typed empty array is a present property with zero elements. This distinction
matters when a plugin or application uses presence to distinguish an explicit
empty selection from an omitted argument.

```odin
// Inside a procedure returning easy.Error; properties is ^easy.Map.
if err := easy.map_set_int_array(properties, "selection", nil); err != .None {
    return err
}

selection, err := easy.map_get_int_array(properties, "selection")
if err != .None {
    return err
}
// len(selection) is zero, and the property exists with integer type.
```

The array getter checks presence, type, and element count before asking the raw
API for an array pointer. This handles empty typed properties without trying
to read a nonexistent first element.

| State of `"selection"` | Operation | Result |
| --- | --- | --- |
| Integer array with zero elements | `map_get_int_array` | Empty slice, `.None` |
| Integer array with zero elements | `map_get_int` | `.Index_Out_Of_Range` |
| No such property | `map_get_int_array` | `.Missing_Key` |
| Float array with zero elements | `map_get_int_array` | `.Wrong_Type` |
| One empty binary data element | `map_get_bytes` | Empty slice, `.None` |

An empty binary or text value still occupies one data element. Its byte length
is zero; the property's element count is one. It is distinct from a property
with no elements.

## Text and binary data preserve embedded zeros

Both text and binary data use VapourSynth's data property type. Their additional
type hint identifies UTF-8 text or binary data. `map_set_string` applies the
UTF-8 hint, but does not validate the encoding. `map_get_string` requires that
hint; binary or unhinted data returns `.Wrong_Type` even if its bytes happen to
form readable text.

`map_get_bytes` accepts either hint. It obtains the stored byte length and
returns exactly that many bytes. This is useful for protocols, arbitrary
metadata, and text that you intend to validate yourself.

```odin
// Inside a procedure returning easy.Error; properties is ^easy.Map.
payload := [?]u8{65, 0, 66, 255}
if err := easy.map_set_bytes(properties, "payload", payload[:]); err != .None {
    return err
}

bytes, err := easy.map_get_bytes(properties, "payload")
if err != .None {
    return err
}
// bytes contains all four values, including the embedded zero.
```

The same explicit-length handling preserves an embedded zero in an Odin
`string`. Returned strings exclude VapourSynth's trailing terminator. Avoid
converting the raw `mapGetData` pointer using a zero-terminated string scan:
that would stop at the first embedded zero. The raw equivalent requires both
`mapGetDataSize` and `mapGetData`.

## Borrowed values require a stable map

The string, byte, and numeric-array getters return views of map-owned storage.
They do not allocate or copy. Their slice types are mutable in Odin, but the
storage is **read-only by contract**.

Use a view before any map mutation or destruction. Even a write to a different
key may invalidate a previous view; do not rely on a particular implementation's
storage behavior. If data must survive a write, a return from the owning scope,
or asynchronous work, copy it into storage owned by the receiving code first.
For a fixed-size protocol field, a caller-owned array and Odin's `copy` builtin
can do that without allocating. For variable-size data, choose an allocator
and explicit cleanup appropriate to the application.

Integer and float scalar getters return ordinary values, so those results are
independent of the map. Node getters follow a different rule: they acquire a
reference.

## Node references: retain or transfer

`map_get_node` returns a new owned reference. Releasing the source map does not
release that returned owner. The usual plugin-result pattern is:

```odin
// Inside a procedure returning (easy.Node, easy.Error).
// result is an owned easy.Map returned by a successful easy.invoke call.
defer easy.destroy_map(&result)

node, err := easy.map_get_node(&result, "clip")
if err != .None {
    return {}, err
}
return node, .None
```

The caller now owns `node` and must eventually call `destroy_node`. Do not also
defer destruction of `node` in the procedure that returns it.

Choose a node setter based on who should own the input reference afterward:

| Operation | Reference owned by the caller after the raw call |
| --- | --- |
| `map_set_node` | Preserved; the map acquires its own reference on success |
| `map_take_node` | Consumed, and the source wrapper is cleared |

!!! warning "Transfer can consume a node on failure"

    Once `map_take_node` calls `mapConsumeNode`, the node is consumed even if
    insertion fails. For example, an append to a property of the wrong type
    returns `.Wrong_Type` and clears the source owner. A validation failure
    before the raw call, such as `.Different_Core` or an invalid key, leaves
    ownership with the caller.

Keep the owner's normal `defer easy.destroy_node(&node)` in place around either
setter. Destruction of a cleared wrapper is harmless, so the same cleanup path
handles a successful transfer, a consumed reference after insertion failure,
and a validation failure that leaves the node intact. Do not infer ownership
solely from whether the setter returned `.None`.

## Error maps and the raw escape hatch

A raw map can contain an error message in place of usable properties. The
checked accessors detect that state and return `.Map_Error` before accessing
values. `easy.invoke` also checks result maps, copies an invocation error into
the optional diagnostic, and releases the failed result map. See
[errors and diagnostics](errors.md) for message lifetime and truncation.

The high-level map surface is deliberately focused. Key enumeration, deletion,
frame and function values, and direct frame-property access remain available
through the [raw API](../reference/raw-api.md). A frame's borrowed property map
must not be treated as an owned `easy.Map` and destroyed. Preserve the raw
operation's borrowing and mutability contract whenever you use `api` and
`handle` directly.

Continue with the [easy host example](../examples/easy-host.md) to build an
argument map, invoke `std.BlankClip`, extract a node, and request its first frame.
