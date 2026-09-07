# Types and constants

The raw package preserves upstream names and C layout. Names such as `VSVideoInfo`, `getVideoInfo`, and `pfGray8` intentionally remain familiar to readers of the VapourSynth headers. A parameter that would collide with an Odin keyword receives a trailing underscore, as in `in_`, `map_`, or `type_`.

## C to Odin mapping

| C representation | Odin representation | Boundary rule |
| --- | --- | --- |
| `int` and C enum typedefs | `c.int` | Preserve the C ABI width; do not substitute Odin's platform-sized `int` in foreign signatures. |
| `int64_t`, `uint64_t`, `uint32_t` | `i64`, `u64`, `u32` | Fixed-width integer values. Audio layouts require all 64 bits. |
| `float`, `double` | `f32`, `f64` | Sample representation and map representation differ: map floats are `f64`. |
| `ptrdiff_t` | `c.ptrdiff_t` | Signed, target-dependent byte stride. |
| `void *`, `void **` | `rawptr`, `^rawptr` | Keep callback state alive for the complete callback lifetime. |
| `const char *` | `cstring` | Usually terminated text, but map data must use its separate byte length. |
| Writable `char *` buffer | `[^]u8` | Caller supplies valid storage and the capacity required by the function. |
| Counted `T *` array | `[^]T` | The API carries the length separately. No Odin slice header crosses the ABI. |
| Opaque `VSNode *`, `VSFrame *`, etc. | `^VSNode`, `^VSFrame`, etc. | Obtain handles from VapourSynth. Never allocate an opaque struct yourself. |
| Function pointer using `VS_CC` | `proc "system"` | `stdcall` on Windows x86; the C calling convention on the other supported targets. |

Odin `int`, pointer size, struct padding, and alignment depend on the target. The ABI suite compares C and Odin layouts rather than assuming that a layout observed on Windows x64 also applies to Windows x86. Use `size_of`, `align_of`, and `offset_of` on the target when inspecting a declaration; see [compatibility](../maintenance/compatibility.md).

The bindings cannot enforce C `const`. API tables, read pointers, information pointers, and read-only property maps must remain read-only even when their Odin pointer or slice type allows a write. [Ownership and borrowing](../guides/ownership.md) describes the lifetimes behind these pointers.

## Opaque resources

| Type | Typical acquisition | Owner or lifetime |
| --- | --- | --- |
| `VSCore` | `createCore` | Host releases with `freeCore` after all dependent resources and requests finish. A VSScript-owned core follows its script lifetime. |
| `VSNode` | Filter creation, `mapGetNode`, `addNodeRef` | One reference per successful acquisition; release with `freeNode`. |
| `VSFrame` | Frame requests, frame creation, `mapGetFrame`, `addFrameRef` | One reference per successful acquisition; release with `freeFrame` or transfer through the appropriate API contract. |
| `VSMap` | `createMap`, `invoke` | Free owned maps with `freeMap`. Frame property maps are borrowed. |
| `VSFunction` | `createFunction`, `mapGetFunction`, `addFunctionRef` | Release each owned reference with `freeFunction`. |
| `VSPlugin`, `VSPluginFunction` | Plugin discovery | Borrowed from the core; there is no matching free operation. |
| `VSLogHandle` | `addLogHandler` | Registration token; remove with `removeLogHandler` while the core is alive. |
| `VSFrameContext` | Filter callback argument | Borrowed callback scheduling context. Do not retain or allocate it. |

An empty opaque declaration is a type marker, not a zero-byte VapourSynth object. A pointer to an Odin-allocated `VSNode{}` is not a valid node.

## Concrete structures

| Structure | Contents | Interpretation |
| --- | --- | --- |
| `VSVideoFormat` | Color family, sample type, meaningful bits, storage bytes, horizontal/vertical subsampling, plane count | Meaningful bits and storage width are separate: a 10-bit integer sample occupies two bytes. Subsampling values are shifts, not divisors. |
| `VSAudioFormat` | Sample type, meaningful bits, storage bytes, channel count, layout | Audio is planar. The layout identifies speakers; channel count describes the number of stored channels. |
| `VSVideoInfo` | Format, rational frame rate, dimensions, frame count | Copy this small structure if metadata must survive a borrowed information pointer. A node can have variable format or dimensions; inspect each frame before processing it. |
| `VSAudioInfo` | Format, sample rate, total sample count, frame count | Total samples use `i64`; frame count uses `c.int`. A final audio frame can be shorter than `VS_AUDIO_FRAME_SAMPLES`. |
| `VSCoreInfo` | Version text, core/API numbers, threads, cache usage | The original structure remains in the ABI. The string inside it is borrowed. |
| `VSCoreInfo2` | Version text, explicitly named core/API versions, creation flags, threads, cache usage | Filled by the API 4.2 `getCoreInfo2` entry. Cache byte fields are `i64`; copying the structure does not copy the version string. |
| `VSFilterDependency` | Source node and request pattern | Describes scheduling dependencies. It does not remove the filter instance's responsibility for its input references. |

The declarations below are included directly from `src/vapoursynth/types.odin`. They also provide the complete callback signatures.

```odin title="src/vapoursynth/types.odin"
--8<-- "src/vapoursynth/types.odin"
```

## Callback context

`VSPublicFunction`, `VSFilterGetFrame`, `VSFilterFree`, `VSFrameDoneCallback`, and the log callbacks use `proc "system"`. This is part of correctness on 32-bit Windows, not a style preference.

A foreign callback does not receive Odin's implicit context. If its implementation needs the allocator, logger, or another context-dependent Odin facility, establish an appropriate context inside the callback. The [invert example](../examples/index.md) demonstrates callback state, allocation, cleanup, and per-request data. Keep instance data distinct from `frameData`: an instance can serve several frame requests at once.

## Version constants

`VAPOURSYNTH_API_MAJOR` is `4`, `VAPOURSYNTH_API_MINOR` is `2`, and `VAPOURSYNTH_API_VERSION` is `(4 << 16) | 2`. Always negotiate using the packed version value before dereferencing a table. A non-nil table requested for an older API is not sufficient permission to access the 4.2 tail.

`VS_MAKE_VERSION(major, minor)` implements the same packing as a `proc "contextless"`. Use the expression `(major << 16) | minor` when an Odin compile-time constant is required, for example a plugin version in a constant declaration.

## Enumeration families

The C enum typedef names are aliases of `c.int`; individual values are untyped constants. This preserves the API's integer parameters while allowing a preset such as `pfGray8` to be passed directly to both a `u32` format-ID parameter and an `i64` map setter.

| Family | Prefix or values | Main use |
| --- | --- | --- |
| `VSColorFamily` | `cfUndefined`, `cfGray`, `cfRGB`, `cfYUV` | Video format description. |
| `VSSampleType` | `stInteger`, `stFloat` | Integer versus floating-point storage. |
| `VSPresetVideoFormat` | `pfNone`, `pfGray*`, `pfYUV*`, `pfRGB*` | 44 named nonzero format IDs and `pfNone`: 45 constants in total. |
| `VSFilterMode` | `fmParallel`, `fmParallelRequests`, `fmUnordered`, `fmFrameState` | Filter scheduling and callback concurrency contract. |
| `VSMediaType` | `mtVideo`, `mtAudio` | Distinguish video from audio before selecting a format accessor. |
| `VSPropertyType` | `ptUnset`, `ptInt`, `ptFloat`, `ptData`, object types | A map property's element type. |
| `VSMapPropertyError` | `peSuccess`, `peUnset`, `peType`, `peIndex`, `peError` | Raw map getter status output. Treat these as distinct statuses. |
| `VSMapAppendMode` | `maReplace`, `maAppend` | Replace a property or append an element of the existing type. |
| `VSActivationReason` | `arInitial`, `arAllFramesReady`, `arError` | Filter callback phase; the error phase is negative. |
| `VSMessageType` | `mtDebug` through `mtFatal` | Log severity. Fatal logging terminates the process. |
| `VSCoreCreationFlags` | `ccf*` | Bit flags combined with `|` when creating a core. |
| `VSPluginConfigFlags` | `pcModifiable` | Plugin registration behavior. |
| `VSDataTypeHint` | `dtUnknown`, `dtBinary`, `dtUtf8` | Interpretation metadata for byte data. A UTF-8 hint does not validate its contents. |
| `VSRequestPattern` | `rpGeneral`, `rpNoFrameReuse`, `rpStrictSpatial`, `rpFrameReuseLastOnly` | Describe actual upstream frame usage to the scheduler. |
| `VSCacheMode` | `cmAuto`, `cmForceDisable`, `cmForceEnable` | Node cache policy. |

Presets name planar formats. `pfRGB24`, for example, means three 8-bit planes, not one interleaved RGB byte array. Format names ending in `H` use half-precision floating-point samples; names ending in `S` use single precision. Query the format structure instead of inferring storage solely from a preset's name.

## Audio channels are bit positions

The `ac*` constants describe positions in a `u64` layout bitset. They are not ready-made masks. Front left has position zero; using `acFrontLeft` itself as a mask would set no bits.

```odin
stereo := (u64(1) << vs.acFrontLeft) | (u64(1) << vs.acFrontRight)
format: vs.VSAudioFormat
ok := api.queryAudioFormat(&format, vs.stInteger, 16, stereo, core)
```

Start with a `u64(1)` before shifting. Positions such as `acWideRight` and `acLowFrequency2` exceed 31. `VS_AUDIO_FRAME_SAMPLES` is `3072`; use the actual `getFrameLength` value when processing a returned audio frame.

## Complete core constant declarations

```odin title="src/vapoursynth/constants.odin"
--8<-- "src/vapoursynth/constants.odin"
```

## Frame property constants and API 4.2 range

These constants describe values stored in frame property maps. They do not automatically attach metadata, convert colors, rescale sample values, or validate that a frame's pixels agree with its metadata.

| Property | Constant family | Notes |
| --- | --- | --- |
| `_Range` | `VSRange`, `VSC_RANGE_*` | API 4.2: limited is **0**, full is **1**. |
| `_ChromaLocation` | `VSChromaLocation`, `VSC_CHROMA_*` | Chroma siting relative to the luma grid. |
| `_FieldBased` | `VSFieldBased`, `VSC_FIELD_*` | Progressive, bottom-field-first, or top-field-first metadata. |
| `_Matrix` | `VSMatrixCoefficients`, `VSC_MATRIX_*` | Color matrix metadata. |
| `_Transfer` | `VSTransferCharacteristics`, `VSC_TRANSFER_*` | Transfer characteristic metadata. |
| `_Primaries` | `VSColorPrimaries`, `VSC_PRIMARIES_*` | Color primary metadata. |

!!! warning "Do not reuse the old range values"

    `_ColorRange` used the reverse numeric convention. The API 4.2 bindings select `VSRange` and `_Range`, with `VSC_RANGE_LIMITED = 0` and `VSC_RANGE_FULL = 1`. Renaming a property without translating its value would invert its meaning.

```odin title="src/vapoursynth/frame_properties.odin"
--8<-- "src/vapoursynth/frame_properties.odin"
```

The local declarations are translated from the pinned [VapourSynth4.h](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VapourSynth4.h) and [VSConstants4.h](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSConstants4.h). Use the [raw map reference](raw-api.md#maps-and-properties) for property access and the [frame guide](../guides/frames.md) for sample interpretation.
