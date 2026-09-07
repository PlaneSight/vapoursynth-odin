# Choosing an interface

Use `easy` for synchronous host applications that build graphs, pass properties, and read output frames. Use the raw package for full API access, particularly filter implementations and asynchronous scheduling. Both interfaces use the same VapourSynth API 4.2 table and can coexist in one program.

The choice is about how much behavior your application wants to handle directly. It does not select a different runtime or change which format identifiers and frame-property constants apply.

## Package map

| Package | Responsibility | Obtains a library automatically? |
| --- | --- | --- |
| Root, conventionally imported as `vs` | C-compatible core types, constants, callbacks, `VSAPI`, and `VSPLUGINAPI`. | No. |
| `easy` | Checked map operations, explicit resource wrappers, plugin invocation, synchronous frame requests, and video row views. | No; call `load_library` explicitly if needed. |
| `link` | Linked declaration of `getVapourSynthAPI`. | Adds a linker dependency; the platform resolves the native library. |
| `vsscript` | Raw VSScript API 4.2 declarations. | No. |
| `vsscript/link` | Linked declaration of `getVSScriptAPI`. | Adds a linker dependency. |

The raw package retains C spellings such as `VSNode`, `getFrame`, and `pfGray8`. The host interface uses Odin-style procedure names such as `get_frame`, returns typed errors, and groups each owned handle with its API pointer and, where applicable, its associated core.

## Start with `easy` for hosting

A host is an application that controls a graph and asks VapourSynth for its outputs. The checked interface is useful when the host needs to:

- Construct arguments with `i64`, `f64`, strings, bytes, arrays, and node references.
- Invoke a plugin function and preserve its diagnostic after cleaning up a failed result.
- Extract an independently owned node from a result map.
- Request frames synchronously.
- Read video planes without assuming that rows are tightly packed.

`easy` removes repeated validation and error translation. It still makes acquisition and destruction explicit, and it exposes the raw `api` and `handle` fields when an operation falls outside its current scope. It does not add an application-wide current core, implicit reference counting on assignment, or automatic destruction.

For example, `map_get_node` returns `(Node, Error)`, where a successful `Node` owns a reference. A string getter returns `(string, Error)`, where a successful string borrows map storage. A uniform result shape helps with error handling, but you still need to understand the ownership of each returned value. The [ownership guide](../guides/ownership.md) lists those contracts explicitly.

## Use the raw API for filters

A filter runs inside VapourSynth's scheduling system. It declares dependencies, requests source frames using a frame context, responds to activation reasons, and returns a frame or signals an error. Those operations belong to the raw API.

The [invert example](../examples/invert-plugin.md) shows this lifecycle for 8–16 bit integer video. It also demonstrates why a callback should use `requestFrameFilter` and `getFrameFilter`: the scheduler needs to know which source frames are required before it invokes the processing phase.

!!! warning "Synchronous host requests are not filter requests"

    Do not call `easy.get_frame` from a filter's get-frame callback. It wraps the synchronous host API. Implement filter scheduling with the raw callback contract and frame-context operations.

The raw package also covers audio, frame construction and writes, asynchronous host requests, function references, cache controls, and other entries outside the high-level package. Use the [raw API reference](../reference/raw-api.md) as an index and the pinned upstream declarations as the ABI baseline.

## Mix the interfaces with explicit ownership

A host can create its `easy.Core` from an API pointer obtained through the linked entry point or a custom dynamic loader. `easy.load_library` is a convenience; it is not required by the other constructors. A plugin already receives the necessary API tables from VapourSynth and normally has no reason to load a second core library.

Raw interoperability does not transfer ownership by itself. Given an `easy.Node`, borrowing `node.handle` for a read-only raw call leaves ownership with the wrapper. Passing the handle to a raw consume operation changes ownership, and you must prevent the wrapper from releasing it again. Prefer the wrapper's `map_take_node` when that is the operation you need, because it records consumption by clearing the source wrapper.

The wrapper's core association must also remain accurate. `invoke`, `map_set_node`, and `map_take_node` reject mismatched API tables or cores. Inserting a foreign core's node through the raw map handle bypasses those checks and makes subsequent wrapper behavior unreliable. Treat exposed fields as an interoperability boundary, not as permission to assemble owners from unrelated handles.

## Keep VSScript separate

VSScript evaluates VapourSynth Python scripts and exposes their outputs to a host. Use it when your application should execute an existing script, instead of constructing the whole graph through maps and plugin invocations.

Core API 4.2 and VSScript API 4.2 are independent version requests. A script environment also has its own ownership and error-state rules: notably, `createScript` consumes a supplied core even on failure, and an evaluation error restricts which subsequent calls are valid. Those rules deserve an explicit integration boundary; see the [VSScript reference](../reference/vsscript.md).

For a first application, follow the [quickstart](quickstart.md). For a plugin, begin with the [identity example](../examples/identity-plugin.md) and then the invert filter. Both paths lead to the same raw API definitions, with a different amount of host-side convenience around them.
