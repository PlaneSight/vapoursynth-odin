# VSScript API 4.2

VSScript embeds the VapourSynth Python scripting environment. Use it when a host should evaluate a `.vpy` file and obtain the nodes registered by `set_output`, rather than constructing the graph entirely through core plugin calls.

The `vsscript` package contains the opaque `VSScript` handle, the `VSGetVSScriptAPI` entry-point type, version constants, and the **16-entry `VSSCRIPTAPI` table for API 4.2**. The `vsscript/link` package adds an optional linked entry-point declaration. Importing either declaration package does not itself create a script environment.

```odin
import "core:c"
import vs "deps:vapoursynth-odin"
import script "deps:vapoursynth-odin/vsscript"
import script_link "deps:vapoursynth-odin/vsscript/link"
```

Core API 4.2 and VSScript API 4.2 are independent contracts. A core table cannot be cast into a VSScript table, and one successful version request does not establish the other. The package deliberately excludes the separate exported `getVSScriptAPILastError` function introduced for VSScript API 4.3.

## Loading and version negotiation

The linked entry point is:

```odin
getVSScriptAPI :: proc "system" (version: c.int) -> ^script.VSSCRIPTAPI
```

Request `script.VSSCRIPT_API_VERSION`, whose value is `(4 << 16) | 2`, and check for nil. A nil result means initialization failed or the requested script API is unavailable. Then obtain the core table through `getVSAPI(vs.VAPOURSYNTH_API_VERSION)` and check that result separately.

```odin
script_api := script_link.getVSScriptAPI(script.VSSCRIPT_API_VERSION)
if script_api == nil {
    return false
}
api := script_api.getVSAPI(vs.VAPOURSYNTH_API_VERSION)
if api == nil {
    return false
}
```

The snippet above belongs inside a procedure returning `bool`. Both tables are borrowed from their loaded libraries; do not modify or free them. Obtaining the core table through VSScript avoids independently loading a second copy of the core.

The link package defaults to `system:vsscript.lib` on Windows and `system:vsscript` elsewhere. Override the library path with `-define:VSSCRIPT_LIBRARY=/absolute/path/to/library`. An import library satisfies the Windows linker; the runtime DLL and its dependencies must also be loadable when the application runs.

For explicit dynamic loading, resolve the symbol `getVSScriptAPI` and cast it to `script.VSGetVSScriptAPI`. On Unix, load VSScript with `dynlib.load_library(path, global_symbols = true)` so Python extension modules can resolve their symbols. Keep the load alive until every environment, output graph, frame, and callback has been released. See [loading and linking](../guides/loading-and-linking.md) for platform paths and loader behavior.

## Ownership and environment lifetime

| Operation | Ownership effect |
| --- | --- |
| `createScript(nil)` | Create an environment with its own default core. Caller owns the returned environment. |
| `createScript(core)` | Transfer ownership of the supplied core, **including when creation returns nil**. |
| `getCore(handle)` | Borrow the environment's core until `freeScript`. Never free it separately. |
| `getOutputNode`, `getOutputAlphaNode` | Acquire an owned node reference, or return nil when absent. |
| `getVariable` | Write a value into the caller's map under the requested name; ordinary map ownership rules apply. |
| `freeScript` | Release the environment and its owned core. |

A script output can depend on Python objects or callbacks held by the environment. Keeping a node reference alone does not permit destroying the environment early. Release frames, output nodes, nodes derived from those outputs, and any maps holding such references before `freeScript`. Complete all pending frame requests first.

For a successful environment, acquisition order normally becomes:

1. Load VSScript and negotiate both API tables.
2. Create the environment, optionally transferring a prepared core.
3. Set variables and evaluate the script.
4. Obtain output node references and request frames through `VSAPI`.
5. Release frames, derived objects, and output references.
6. Free the environment, then unload its library.

If you transfer a raw core into `createScript`, remove its earlier independent cleanup obligation before the call. For an `easy.Core` that owns the supplied handle, record the API pointer you still need, transfer the handle, and clear the wrapper so its deferred destructor cannot free the same core again. This ownership change happens even when script creation fails.

## Failure state and diagnostics

!!! warning "Evaluation failure restricts subsequent operations"

    When an environment enters the error state, only `getError` and `freeScript` are permitted on that handle. Do not inspect outputs, enumerate nodes, get the core, read an exit code, or retry evaluation on the failed handle. Free it and create a new environment for a retry.

`evaluateBuffer` and `evaluateFile` return zero on success. On failure, get the message promptly with `getError` and then free the environment. This restriction comes directly from the [pinned 4.2 header](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSScript4.h#L63).

`getError` returns borrowed text, or nil when no error is present. Its guarantee lasts only until the next VSScript operation on that handle. Copy it before calling another operation or freeing the environment if the diagnostic must survive. [Official diagnostic lifetime](https://www.vapoursynth.com/doc/api/vsscript4.h.html#geterror).

This raw package does not provide the inline owned `Diagnostic` used by `easy`. A host can print the borrowed error immediately or explicitly copy it using its chosen allocator and cleanup policy.

```odin
environment := script_api.createScript(nil)
if environment == nil {
    return false
}
defer script_api.freeScript(environment)

if script_api.evaluateFile(environment, "example.vpy") != 0 {
    message := script_api.getError(environment)
    if message != nil {
        fmt.eprintln(string(message))
    }
    return false
}
```

This fragment assumes the two negotiated tables and a procedure returning `bool`; `fmt` is `core:fmt`. Its deferred cleanup is valid on both the successful and failed evaluation paths.

## Complete table by responsibility

### Version and core access

| Entry | Signature summary | Result and restrictions |
| --- | --- | --- |
| `getAPIVersion` | `() -> c.int` | Highest supported packed VSScript version. |
| `getVSAPI` | `(version: c.int) -> ^vs.VSAPI` | Borrowed core table; pass the core version constant and check for nil. |
| `createScript` | `(core: ^vs.VSCore) -> ^VSScript` | Owned environment or nil; always consumes a non-nil core argument. |
| `getCore` | `(handle: ^VSScript) -> ^vs.VSCore` | Borrowed environment-owned core, or nil on error. |

A supplied core allows a host to configure flags, logging, or plugins before Python evaluation. Once supplied, it has exactly one owner: the script environment. `getCore` is for borrowing that core during the environment's valid lifetime.

### Evaluation and status

| Entry | Signature summary | Result and restrictions |
| --- | --- | --- |
| `evaluateBuffer` | `(handle, buffer, scriptFilename) -> c.int` | Evaluate terminated Python text; zero success. `scriptFilename` labels the script in diagnostics. |
| `evaluateFile` | `(handle, scriptFilename) -> c.int` | Load and evaluate a script file; zero success. |
| `getError` | `(handle) -> cstring` | Borrowed diagnostic or nil; allowed in the error state. |
| `getExitCode` | `(handle) -> c.int` | Script-reported exit code; does not override the error-state restriction. |
| `evalSetWorkingDir` | `(handle, setCWD: c.int)` | Control temporary working-directory changes during `evaluateFile`; initially off. |

Buffer contents and filenames use `cstring`. Convert dynamic Odin strings explicitly, preserve their terminators, and keep them alive through the call. `evaluateBuffer` does not load the file named by its label; `evaluateFile` does.

Working-directory behavior matters for scripts with relative paths. Enable it before evaluation only when that matches the host's intended script semantics. Changing a process working directory is a host-level concern; do not assume that a per-environment handle makes all process-global effects independent.

### Variable exchange

| Entry | Signature summary | Result and restrictions |
| --- | --- | --- |
| `getVariable` | `(handle, name: cstring, dst: ^vs.VSMap) -> c.int` | Zero success; writes the script variable under the same key in `dst`. |
| `setVariables` | `(handle, vars: ^vs.VSMap) -> c.int` | Zero success; makes each map key available as a script variable. |

Values must be representable by VapourSynth map types. The caller owns the input/output maps and must inspect statuses. If an exchanged value contains a node, frame, or function, apply the ordinary reference rules when extracting or releasing it. In particular, release maps holding script-dependent resources before destroying the environment.

### Outputs and cleanup

| Entry | Signature summary | Result and restrictions |
| --- | --- | --- |
| `getOutputNode` | `(handle, index: c.int) -> ^vs.VSNode` | Owned output reference, or nil if the index has no node. |
| `getOutputAlphaNode` | `(handle, index: c.int) -> ^vs.VSNode` | Owned alpha-node reference, or nil if absent. |
| `getAltOutputMode` | `(handle, index: c.int) -> c.int` | Output-mode metadata associated with an index. |
| `getAvailableOutputNodes` | `(handle, size: c.int, dst: [^]c.int) -> c.int` | API 4.2 enumeration; returns total available indices while writing at most `size`. |
| `freeScript` | `(handle: ^VSScript)` | Free environment and core after dependent work finishes; nil is accepted. |

Output indices are identifiers chosen by the script. Do not assume they are contiguous or that every script exposes only index zero. The optional alpha node is a separate reference and needs a separate release.

## Enumerating output indices

`getAvailableOutputNodes` separates the number available from the caller's storage capacity. It always returns the total number, even when the buffer is smaller. Never construct a slice of the returned total length over a smaller fixed buffer.

For a dynamic list, first request the count with size zero and a nil destination, allocate that many `c.int` elements with the host's allocator, and call again with the actual capacity. Check the second returned count against the allocation before reading. Keep the environment unchanged between the two calls; if a host permits changes, handle growth by resizing and retrying under an appropriate synchronization policy.

A fixed-capacity approach is also valid when the host explicitly handles overflow:

```odin
indices: [16]c.int
total := script_api.getAvailableOutputNodes(
    environment,
    c.int(len(indices)),
    raw_data(indices[:]),
)
if total < 0 || total > c.int(len(indices)) {
    return false
}
for index in indices[:int(total)] {
    output := script_api.getOutputNode(environment, index)
    if output == nil {
        return false
    }
    // Process this owned output while the environment remains alive.
    api.freeNode(output)
}
```

This fragment deliberately rejects more than 16 outputs. A general host should allocate sufficient storage instead of silently dropping outputs. Within the loop, a frame request uses `api.getFrame` or `api.getFrameAsync`, with the same frame ownership and completion rules as any other host.

## Complete declaration

The following source listing fixes the exact 4.2 table order and all C ABI types. It is included directly from the package, so documentation cannot silently add a newer table entry.

```odin title="vsscript/vsscript.odin"
--8<-- "vsscript/vsscript.odin"
```

The separate linking declaration is likewise included from source:

```odin title="vsscript/link/link.odin"
--8<-- "vsscript/link/link.odin"
```

Refer to the [pinned VSScript4.h](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSScript4.h) for the selected ABI and the [upstream VSScript documentation](https://www.vapoursynth.com/doc/api/vsscript4.h.html) for embedding details. The [compatibility page](../maintenance/compatibility.md) distinguishes script API versions, core API versions, compile checks, and actual runtime verification.
