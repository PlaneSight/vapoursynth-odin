# Raw core API

The raw package is a direct translation of the VapourSynth R76 headers with core API 4.2 selected. `VSAPI` contains **117 stable function pointers** in ABI order and ends at `getCoreInfo2`. `VSPLUGINAPI` supplies three functions for plugin initialization. The experimental `VSGraphAPI` appends four inspection entries separately.

Raw calls retain their C names, parameter types, status conventions, and ownership rules. They do not receive the validation or typed errors of [`easy`](easy.md). Invalid raw arguments can cause a fatal error; check media types, indices, formats, keys, and buffer capacities before crossing the boundary.

## Obtaining and keeping the table

Hosts call the exported `getVapourSynthAPI` with `vs.VAPOURSYNTH_API_VERSION`, either through their loader or the optional `link` package. The corresponding function-pointer type is `VSGetVapourSynthAPI`. Check for nil before dereferencing the result. Keep the library loaded until no table entry, callback, core, or dependent object can be used again.

Plugins receive their tables from VapourSynth through initialization and callbacks. They do not need to load a second core library. A table is a borrowed, read-only pointer: do not allocate, copy, modify, or free it. See [loading and linking](../guides/loading-and-linking.md) for complete acquisition choices.

## Reading the return values

| Convention | Functions | Caller action |
| --- | --- | --- |
| Owned pointer | Maps, reference getters, node/frame creation, frame requests | Check failure where the function permits it; release or transfer every successful acquisition. |
| Borrowed pointer | Information, formats, frame storage, property maps, plugins | Respect the owner and invalidation rules; do not free. |
| Zero is success | Map setters/consumers, `mapSetEmpty` | A nonzero result indicates failure. Consuming operations still consume on failure. |
| Nonzero is success | Plugin configuration/registration, format-name and format-query operations, `removeLogHandler` | Do not reuse the map-setter convention. |
| Separate `^c.int` status | Typed map getters | Inspect the `pe*` status before using the result. Supply the error pointer for recoverable failures. |
| Result is a value | Counts, media types, limits, versions, timing | Interpret that entry's sentinel or unit; it is not a generic status code. |

The [ownership guide](../guides/ownership.md) explains how to express these obligations with `defer`. The tables below account for all stable entries by responsibility; the [complete declaration](#complete-function-table-declaration) preserves their actual ABI order and signatures.

## Core and logging

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `createCore` | `^VSCore`; create using combined `ccf*` flags | Own the returned core; flags zero selects defaults. |
| `freeCore` | Release core | Complete outstanding requests and release frames, nodes, functions, and dependent maps first. |
| `setMaxCacheSize` | `i64`; configure cache pressure target in bytes | The target is not a hard memory ceiling. |
| `setThreadCount` | `c.int`; configure worker count | Zero requests automatic selection. |
| `getCoreInfo` | Fill caller's `VSCoreInfo` | Version text remains borrowed. |
| `getCoreInfo2` | Fill caller's `VSCoreInfo2` | API 4.2 entry; includes creation flags and explicit version field names. |
| `getAPIVersion` | Packed highest supported core API version | This is a core API version, not a VSScript version. |
| `logMessage` | Send a message with `VSMessageType` severity | `mtFatal` terminates the process. |
| `addLogHandler` | `^VSLogHandle`; register callbacks and `userData` | Keep callback state valid until removal/cleanup. |
| `removeLogHandler` | Nonzero success | Use the token with its originating core; the free callback releases handler state. |

`setMaxCacheSize` returns the resulting byte limit and `setThreadCount` returns the actual worker count. These return values may differ from a caller's requested configuration. [Upstream core operations](https://www.vapoursynth.com/doc/api/vapoursynth4.h.html#setmaxcachesize).

## Filter construction and node lifetime

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `createVideoFilter` | Create video filter and write node/error into `out` | The result map carries the returned clip. Provide valid video metadata, callbacks, dependencies, and instance state. |
| `createVideoFilter2` | Owned `^VSNode`, or nil | Caller handles node insertion and creation failure explicitly. |
| `createAudioFilter` | Create audio filter and write node/error into `out` | Audio counterpart with `VSAudioInfo`. |
| `createAudioFilter2` | Owned `^VSNode`, or nil | Audio counterpart returning its node directly. |
| `setLinearFilter` | `c.int`; opt into linear-filter cache support | Call immediately after creation; required before `cacheFrame`. |
| `setCacheMode` | Set `VSCacheMode` policy | Advanced node cache control. |
| `setCacheOptions` | Set fixed size, maximum size, and history size | Apply after the cache mode. |
| `freeNode` | Release one node reference | May trigger filter-instance cleanup when no references remain. |
| `addNodeRef` | Owned `^VSNode` | Another reference to the same node, not another filter instance. |
| `getNodeType` | `mtVideo` or `mtAudio` | Select the matching information accessor. |
| `getVideoInfo` | Borrowed `^VSVideoInfo` | Read-only node metadata; do not free or mutate. |
| `getAudioInfo` | Borrowed `^VSAudioInfo` | Read-only node metadata; do not free or mutate. |

A filter owns its persistent instance state after successful creation and releases it through `VSFilterFree`. For the R76 implementation used by these bindings, a nil `createVideoFilter2` result does not invoke the free callback on the validation failure path; the constructor must clean up its untransferred state and input references. The [invert example](../examples/index.md) implements that failure path. This behavior is verified against the [pinned constructor and creation code](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vscore.cpp#L2107).

The scheduling mode and dependency request patterns describe real behavior. A parallel filter must keep mutable request state in the per-request `frameData` slot or otherwise synchronize it; storing it in shared instance fields changes the concurrency contract.

## Frame allocation and reference lifetime

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `newVideoFrame` | Owned video `^VSFrame` | Valid format/dimensions required; `propSrc` optionally supplies properties. |
| `newVideoFrame2` | Owned video `^VSFrame` assembled using plane sources | `planeSrc` is `[^]^VSFrame` and `planes` is `[^]c.int`; arrays describe the destination planes. |
| `newAudioFrame` | Owned audio `^VSFrame` | Supply valid format and sample count; optional property source. |
| `newAudioFrame2` | Owned audio `^VSFrame` assembled using channel sources | Channel indices select stored channels; they are not `ac*` speaker bit positions. |
| `freeFrame` | Release one frame reference | Invalidates borrows when the frame is no longer alive. |
| `addFrameRef` | Owned reference to the same frame | Adds a reference; does not duplicate the frame object. |
| `copyFrame` | Owned frame copy | Use when producing a writable result while preserving the source. |

Newly allocated pixel/sample storage must be initialized before returning or exposing the frame. Plane-source and channel-source arrays are C arrays of pointers, not Odin slices passed by value. Keep each source live through construction, and observe the format compatibility requirements. The [frame guide](../guides/frames.md) shows how allocation, source properties, sample storage, and row padding fit together.

## Frame storage and properties

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `getFramePropertiesRO` | Borrowed read-only `^VSMap` | Belongs to the frame; never `freeMap` it. |
| `getFramePropertiesRW` | Borrowed writable `^VSMap` | Belongs to a writable frame; never `freeMap` it. |
| `getStride` | `c.ptrdiff_t` byte distance between video rows | Use it for row addressing; do not assume tightly packed pixels. |
| `getReadPtr` | Borrowed read-only `[^]u8` for plane/channel | Odin cannot enforce the read-only contract. |
| `getWritePtr` | Borrowed writable `[^]u8` for plane/channel | Invalidates earlier read pointers to this frame; reacquire them if needed. |
| `getVideoFrameFormat` | Borrowed `^VSVideoFormat` | Call for a video frame. |
| `getAudioFrameFormat` | Borrowed `^VSAudioFormat` | Call for an audio frame. |
| `getFrameType` | `mtVideo` or `mtAudio` | Choose the matching accessors. |
| `getFrameWidth` | Plane width in samples | Use the selected plane's dimensions, including chroma subsampling. |
| `getFrameHeight` | Plane height in rows | Use the selected plane's height. |
| `getFrameLength` | Audio frame length in samples | The last audio frame can be shorter than `VS_AUDIO_FRAME_SAMPLES`. |

Keep a frame reference alive while reading its storage, formats, or property maps. A reference keeps the resource alive; it does not make concurrent writes safe. Metadata-only changes and raw writable access also need careful borrow management.

## Format queries

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `getVideoFormatName` | Nonzero success; writes video format name | Caller buffer must contain at least 32 bytes including terminator capacity. |
| `getAudioFormatName` | Nonzero success; writes audio format name | Same 32-byte minimum. |
| `queryVideoFormat` | Nonzero success; fills `VSVideoFormat` | Inputs describe color family, sample type, meaningful bits, and subsampling. |
| `queryAudioFormat` | Nonzero success; fills `VSAudioFormat` | Channel layout is a `u64` mask. |
| `queryVideoFormatID` | `u32` format ID | Zero indicates an invalid/unsupported combination. |
| `getVideoFormatByID` | Nonzero success; fills `VSVideoFormat` | Accepts a preset or queried format ID. |

Format outputs belong to the caller when passed as output structures. Do not confuse them with the borrowed pointers returned by node/frame information accessors. The [type reference](types-and-constants.md) explains storage bits versus bytes and the audio channel layout mask.

## Frame requests and callback scheduling

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `getFrame` | Owned frame or nil; synchronous request | Host/constructor use only; supply an error buffer and its `c.int` capacity. |
| `getFrameAsync` | Start request using `VSFrameDoneCallback` | Keep callback code and state alive until completion. |
| `requestFrameFilter` | Register an upstream dependency for a filter request | Use inside the filter's callback with its `VSFrameContext`. |
| `getFrameFilter` | Owned upstream frame reference | Retrieve a dependency after it becomes available; release after use. |
| `releaseFrameEarly` | Release scheduler-held dependency storage early | Does not release a separate frame reference that your code acquired. |
| `cacheFrame` | Submit an extra frame to a linear filter's cache | Retains a reference; caller still owns and releases its original reference. |
| `setFilterError` | Report failure through the frame context | Use the filter failure path and return no output frame. |

`getFrame` and `getFrameAsync` are not filter dependency primitives. A filter requests inputs during `arInitial`, reads them during `arAllFramesReady`, and handles `arError` cleanup. The raw [invert example](../examples/index.md) demonstrates this protocol.

An asynchronous completion callback receives an owned successful `f` and a borrowed `node` identifying the request. On failure `f` is nil, and `errorMsg` is borrowed only during the callback. Copy the diagnostic before returning if it must survive. The R76 [callback dispatch](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vsthreadpool.cpp#L378) adds the frame reference explicitly.

`cacheFrame` keeps its own reference, as shown by the [pinned implementation](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vscore.cpp#L1128). It requires a filter configured with `setLinearFilter`. That configuration call returns an upper bound for extra frames worth submitting; cache tuning can be ignored by the core, and `setCacheMode` resets earlier cache-option changes. [Upstream cache contract](https://www.vapoursynth.com/doc/api/vapoursynth4.h.html#setlinearfilter).

## External functions

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `createFunction` | Owned `^VSFunction` wrapping `VSPublicFunction` | `userData` survives until its `VSFreeFunctionData` callback. |
| `freeFunction` | Release one function reference | Final release ends callback-state ownership. |
| `addFunctionRef` | Owned additional reference | Caller must eventually release it. |
| `callFunction` | Call using input and output maps | Caller owns its maps; inspect the output error state. |

These callable values can be stored in maps and passed to plugin functions. They are distinct from `VSPluginFunction`, which is borrowed metadata describing a registered plugin entry.

## Maps and properties

Raw map access has two independent failure channels: an error-state map, and a typed getter's property status. Check `mapGetError` before ordinary property access. Supply a `^c.int` error output to a getter when you want to handle missing keys, wrong types, and invalid indices rather than relying on fatal raw behavior.

### Map lifecycle and inspection

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `createMap` | Owned empty `^VSMap` | No core argument at this raw layer. |
| `freeMap` | Free owned map | Also releases object references held by its properties. |
| `clearMap` | Remove all properties and clear error state | Invalidates map borrows. |
| `copyMap` | Merge source properties into destination | Matching keys are replaced; destination-only keys survive. |
| `mapSetError` | Replace contents with a copied error message | Puts the map into the error state. |
| `mapGetError` | Borrowed error `cstring`, or nil | Copy before mutation/destruction when retaining the message. |
| `mapNumKeys` | Number of property keys | Use with `mapGetKey` for enumeration. |
| `mapGetKey` | Borrowed key at index | Keep map live and unmodified while using it. |
| `mapDeleteKey` | Remove one property | Nonzero when a key was removed. |
| `mapNumElements` | Number of elements for a key | Negative if the key is absent; zero can mean a present typed empty property. |
| `mapGetType` | `VSPropertyType` value | `ptUnset` means no such property. |
| `mapSetEmpty` | Create typed empty property | Zero success; preserve the distinction between empty and absent. |

`copyMap` is a property merge, not assignment and not a way to clone a failed invocation. In R76 it neither copies nor clears the destination error flag. `clearMap` is the explicit reset operation. These details follow the [pinned map implementation](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vscore.h#L328).

### Integer and float properties

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `mapGetInt` | `i64` element plus status | Check the status even when a zero value is plausible. |
| `mapGetIntSaturated` | `c.int` element plus status | Explicit narrowing alternative to the full-width getter. |
| `mapGetIntArray` | Borrowed `[^]i64` plus status | Obtain count separately; treat storage as read-only. |
| `mapSetInt` | Set/append `i64` | `maReplace` or `maAppend`; zero success. |
| `mapSetIntArray` | Replace with counted integer array | Input is copied; size is `c.int`. |
| `mapGetFloat` | `f64` element plus status | Maps use double-precision values. |
| `mapGetFloatSaturated` | `f32` element plus status | Explicit narrower result. |
| `mapGetFloatArray` | Borrowed `[^]f64` plus status | Obtain count separately; treat storage as read-only. |
| `mapSetFloat` | Set/append `f64` | Zero success. |
| `mapSetFloatArray` | Replace with counted float array | Input is copied; size is `c.int`. |

Check the property's type and count before constructing an Odin slice from an array pointer, including the empty-array case. The [`easy` array getters](easy.md#numeric-arrays) implement these boundary checks and return an empty successful slice for a present empty property.

### Data properties

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `mapGetData` | Borrowed `cstring` plus status | May contain binary zero bytes; do not infer length by scanning. |
| `mapGetDataSize` | Stored byte length plus status | Excludes the extra terminator. |
| `mapGetDataTypeHint` | `dtUnknown`, `dtBinary`, or `dtUtf8`, plus status | Metadata about interpretation, not validation. |
| `mapSetData` | Set/append copied bytes with length and hint | Use an explicit length for binary or embedded-zero text. |

Although the pointer is spelled `cstring`, a data property is a sized byte sequence. After successfully obtaining its pointer and size, `(cast([^]u8)data)[:int(size)]` describes all stored bytes. Keep that slice read-only, and do not let it outlive a mutation or destruction of the map. See [maps](../guides/maps.md) for complete examples.

### Object properties

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `mapGetNode` | Owned `^VSNode` plus status | Release with `freeNode`; independent of the map's reference. |
| `mapSetNode` | Set/append node | Map acquires its own reference; caller keeps its reference. |
| `mapConsumeNode` | Set/append using caller's node reference | Consumes even when the insertion fails. |
| `mapGetFrame` | Owned `^VSFrame` plus status | Release with `freeFrame`. |
| `mapSetFrame` | Set/append frame | Map acquires its own reference. |
| `mapConsumeFrame` | Set/append using caller's frame reference | Consumes even when the insertion fails. |
| `mapGetFunction` | Owned `^VSFunction` plus status | Release with `freeFunction`. |
| `mapSetFunction` | Set/append callable function | Map acquires its own reference. |
| `mapConsumeFunction` | Set/append using caller's function reference | Consumes even when the insertion fails. |

!!! warning "Consumption happens on failure too"

    After a raw `mapConsumeNode`, `mapConsumeFrame`, or `mapConsumeFunction` call, the supplied reference is no longer yours. Clear your local owner even if the return value indicates a type error. A second release would double-release that reference.

## Plugin discovery and invocation

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `registerFunction` | Nonzero success; register public callback and schema | API-table counterpart of the initialization-table entry. |
| `getPluginByID` | Borrowed plugin by unique identifier | Nil if absent. |
| `getPluginByNamespace` | Borrowed plugin by namespace | Nil if absent. |
| `getNextPlugin` | Borrowed next plugin | Start enumeration with nil; nil ends it. |
| `getPluginName` | Borrowed display name | Valid with its plugin/core. |
| `getPluginID` | Borrowed unique identifier | Suitable for ID lookup. |
| `getPluginNamespace` | Borrowed namespace | Used for namespace-based invocation. |
| `getNextPluginFunction` | Borrowed next function metadata | Start with nil; nil ends enumeration. |
| `getPluginFunctionByName` | Borrowed function metadata | Nil if absent. |
| `getPluginFunctionName` | Borrowed function name | Describes a registered public function. |
| `getPluginFunctionArguments` | Borrowed input schema string | Interpret the plugin argument declaration. |
| `getPluginFunctionReturnType` | Borrowed result schema string | Describes expected result properties. |
| `getPluginPath` | Borrowed plugin-library path | Inspect while the plugin/core remains alive. |
| `getPluginVersion` | Packed plugin version | Separate from core API version. |
| `invoke` | Owned result `^VSMap` | Inspect its error state; free it on both success and error. |

The function metadata pointers and strings are borrowed; there are no `freePlugin` or `freePluginFunction` entries. Invocation does not transfer the argument map. A node extracted with `mapGetNode` has its own reference and can remain after you free the invocation result map.

## Plugin initialization table

The core calls the exported `VapourSynthPluginInit2` entry point with a plugin handle and `^VSPLUGINAPI`. Export a `proc "system"` matching `VSInitPlugin`; retain no ownership of either borrowed argument.

| `VSPLUGINAPI` entry | Role |
| --- | --- |
| `getAPIVersion` | Query the available packed core API version. |
| `configPlugin` | Set unique identifier, namespace, display name, plugin version, required API version, and flags. Nonzero means success. |
| `registerFunction` | Register a name, input schema, return schema, callback, and optional callback state. Nonzero means success. |

For an input clip and output clip, the schemas use declarations such as `"clip:vnode;"`. The [identity and invert examples](../examples/index.md) show exact registration code and the callback lifetime that follows it.

## Stable inspection and timing

These ten entries were added in core API 4.1 and remain part of stable 4.2. Upstream marks this area for host inspection and cache management, with a direction not to use it inside filters.

| Entry | Result and purpose | Ownership or boundary |
| --- | --- | --- |
| `clearNodeCache` | Clear one node's cache | Host-side cache management. |
| `clearCoreCaches` | Clear caches across a core | Host-side cache management. |
| `getNodeName` | Borrowed filter name | Keep the node alive. |
| `getNodeFilterMode` | `VSFilterMode` value | Describes the node's scheduling mode. |
| `getNumNodeDependencies` | Dependency count | Use before indexed inspection. |
| `getNodeDependency` | Borrowed `^VSFilterDependency`, or nil | The contained source pointer is borrowed too. |
| `getCoreNodeTiming` | Nonzero if timing is enabled | Query collection state. |
| `setCoreNodeTiming` | Enable or stop timing collection | Disabling stops increments; it does not reset counters. |
| `getNodeProcessingTime` | `i64` nanoseconds for the node | Nonzero `reset` resets its counter. |
| `getFreedNodeProcessingTime` | `i64` nanoseconds for destroyed nodes | Core aggregate; nonzero `reset` resets it. |

`getNodeDependency` returns an entry stored inside the inspected node, and does not add a reference to its source. Call `addNodeRef` if you need the source independently. This follows the [pinned dependency accessor](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vscore.h#L896).

## Experimental graph extension

`VSGraphAPI` embeds `VSAPI` at offset zero and adds four functions. It represents the header's conditional `VS_GRAPH_API` extension without changing the stable `VSAPI` size.

All three preconditions are required before casting or using the extension:

1. `api.getAPIVersion() == vs.VAPOURSYNTH_API_VERSION`: both major and minor versions must match exactly.
2. The inspected core was created with `ccfEnableGraphInspection`.
3. No frame request or other API call runs concurrently with inspection.

This fragment belongs inside a procedure returning `bool`, with a non-nil, already negotiated `^vs.VSAPI` named `api` and the raw package imported as `vs`. The core-creation flag and absence of concurrent API use are preconditions established by the host.

```odin
if api.getAPIVersion() != vs.VAPOURSYNTH_API_VERSION {
    return false
}
// This core was created with ccfEnableGraphInspection, and API use is quiescent.
graph := cast(^vs.VSGraphAPI)api
```

| Extension entry | Result |
| --- | --- |
| `getNodeCreationFunctionName` | Borrowed function name at a creation-call level. |
| `getNodeCreationPluginID` | Borrowed plugin identifier at that level. |
| `getNodeCreationPluginNS` | Borrowed plugin namespace at that level. |
| `getNodeCreationFunctionArguments` | Borrowed read-only map of recorded creation arguments. |

Level zero inspects the function that created the node; higher levels walk outward through the recorded call stack. An unavailable level returns nil. The argument map belongs to the recorded creation frame; do not free it. Its borrowed ownership is confirmed by the [R76 accessor](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vscore.cpp#L961) and [owning structure](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/src/core/vscore.h#L629).

Use this extension for controlled debugging and graph visualization. It is unsuitable for plugins or filters, and a newer compatible stable API table does not guarantee an identically laid-out experimental tail. The constraints are explicit in the [pinned extension declaration](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VapourSynth4.h#L514).

## Complete function-table declaration

This listing is included directly from `src/vapoursynth/api.odin`. It is the complete signature reference for the 117 stable core entries, three initialization entries, and four graph entries described above. Callback typedefs and concrete layouts are in [types and constants](types-and-constants.md).

```odin title="src/vapoursynth/api.odin"
--8<-- "src/vapoursynth/api.odin"
```

For upstream parameter details, consult the [official core API reference](https://www.vapoursynth.com/doc/api/vapoursynth4.h.html). The checked-in [R76 header](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VapourSynth4.h) remains the authority for the exact ABI selected by this package.
