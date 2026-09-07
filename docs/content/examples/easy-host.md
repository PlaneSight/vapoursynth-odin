# Request and read a frame

This example builds a one-frame Gray8 clip through `std.BlankClip`, keeps an independent node reference, requests frame zero, and checks every active pixel. It connects the map operations from the previous tutorial to a complete synchronous host workflow.

The package is `examples/easy_host`. Its width is deliberately 65 pixels, so assuming a row occupies exactly its active width is an unsafe shortcut. The code uses plane dimensions and row views to exclude padding from the checksum.

## Run the host

From the repository root:

```console
uv run tools/run_host.py easy_host
```

This builds the native executable under `.build/examples` and runs it with the
VapourSynth core library from the uv environment. The command is the same on
Windows, Linux, and macOS; see the [build guide](../guides/previewing-examples.md#one-build-command-on-every-supported-platform)
for supported targets. The executable itself uses the native core API and does
not embed Python.

To compile without executing the host, run `uv run tools/examples.py build easy_host`.
For a separate native runtime, pass its path as described in the
[loading guide](../guides/loading-and-linking.md#dynamic-loading-with-easy).

The output has this shape:

```text
Clip: 65 x 48; 1 frame(s); <numerator>/<denominator> fps
Frame 0: 65 x 48 Gray8; stride: <bytes> bytes; checksum: 53040
```

The frame rate comes from `BlankClip` defaults, and the stride is supplied by the runtime. The stable result is the checksum: `65 × 48 × 17 = 53040`. No padding byte contributes to it.

## Build arguments in a short-lived scope

The helper `make_blank_clip` receives a borrowed core and diagnostic. It creates its own argument map and defers destruction immediately. A small table supplies integer arguments:

```odin
settings := [?]struct {key: cstring, value: i64}{
    {"width", WIDTH},
    {"height", HEIGHT},
    {"length", 1},
    {"format", vs.pfGray8},
}
```

The loop checks every setter. The color argument uses `map_set_float`, matching the plugin's floating-point argument type even though this example's sample value, 17, is integral. Maps preserve types, so writing the same numeric value through an integer setter would not express the same argument.

`BlankClip` provides a controlled source: its format, dimensions, length, and sample values are known before processing begins. That lets the example test ownership and frame access without introducing file decoding or plugin installation. Consult the upstream [BlankClip reference](https://www.vapoursynth.com/doc/functions/video/blankclip.html) when extending the argument list.

## Separate invocation failure from result extraction

```odin
result, invoke_error := easy.invoke(core, "std", "BlankClip", &args, diagnostic)
```

`invoke` borrows the argument map. On success it returns a new owned result map; the example defers `destroy_map(&result)` in the helper. It resolves the plugin namespace and checks the returned map for a plugin error before reporting success.

On invocation failure, the wrapper copies the result's error text into the caller's diagnostic before freeing its temporary map. The helper can therefore report both `.Invocation_Failed` and the plugin's message without holding the failed result alive. The diagnostic still has a bounded lifetime and capacity; see [errors](../guides/errors.md).

Successful invocation does not imply that your chosen result key has the expected type. The example separately retrieves `"clip"`:

```odin
node, node_error := easy.map_get_node(&result, "clip")
```

This getter acquires an owned node reference. When the helper returns, its result and argument maps are destroyed, but the returned node remains valid. The caller receives responsibility for releasing that reference. Adding a deferred `destroy_node` inside the helper would incorrectly release the resource being returned.

## Retain a reference deliberately

Back in `run`, the node is first scheduled for cleanup. The example then calls `retain_node`, checks success, and schedules cleanup for the retained value too. It explicitly destroys the original wrapper before using the retained one.

This demonstrates that native reference ownership is independent of an Odin variable's storage. Two acquisitions refer to the same graph node but carry two independent release obligations. Ordinary assignment would only copy the wrapper fields and would not acquire the second reference.

The original deferred destruction remains in place. It is harmless because the earlier `destroy_node(&node)` cleared that same wrapper. This is not a general defense against copied owners: an independently copied wrapper would still contain the stale native pointer.

The [ownership guide](../guides/ownership.md) covers retaining, borrowing, transferring, and clearing owners in more detail.

## Distinguish the graph from evaluated data

`easy.video_info(&retained)` copies the node's video information so the host can inspect dimensions, frame count, and frame rate. A node is a reference to a graph, not a buffer of pixels. The actual frame is obtained by:

```odin
frame, frame_error := easy.get_frame(&retained, 0, &diagnostic)
```

This is a synchronous operation. The wrapper validates the index and waits for evaluation. If the upstream filter fails, `.Frame_Request_Failed` carries a diagnostic. Once acquired, the frame owns one native reference and receives its own deferred release.

Use this call from a host application's execution path. A filter's frame callback must participate in the scheduler using `requestFrameFilter` and `getFrameFilter`; it must not use this synchronous host helper. The [invert tutorial](invert-plugin.md) shows that different protocol.

## Read active rows

```odin
plane, plane_error := easy.read_plane(&frame, 0)
```

The resulting `Plane_View` borrows frame data. It records the actual width, height, stride in bytes, and sample representation. There is no separate plane allocation to free, but the owned frame must remain alive for every access.

The example first checks that the plane is 65 × 48 and uses one byte per sample. Only then does it treat each active byte as a Gray8 sample. For each row it calls:

```odin
row, row_error := easy.plane_row(&plane, y)
```

The row has `width × bytes_per_sample` active bytes. Its starting address is determined using the plane's byte stride. This is different from slicing `width × height` consecutive bytes from the plane base: that operation would include row padding and then miss some actual pixels.

The outer loop uses the plane's height, and the inner loop visits the returned row. The sum accumulates in `u64`. This makes the expected result easy to compute while avoiding a small accumulator that would overflow on even a modest image.

For 10-bit or 16-bit integer video, use a checked typed row view with `plane_row_as(..., u16)` and sum samples. A byte checksum would instead sum each sample's storage bytes. Chroma-subsampled video also needs separate plane dimensions; see [frames and rows](../guides/frames.md).

## Trace cleanup across both scopes

The helper releases its result and argument maps after returning an owned node. The caller's normal completion releases its resources in reverse acquisition order:

1. Release the frame, ending every borrowed plane and row view.
2. Release the retained node reference.
3. Run the original node's deferred destruction, which sees a cleared wrapper.
4. Destroy the core.
5. Unload the library that supplies the API table.

Early returns use the same registered cleanup. The code checks each acquisition before scheduling its release, so a failed acquisition introduces no cleanup obligation.

## Diagnose or extend the example

`.Plugin_Not_Found` identifies namespace lookup, while `.Invocation_Failed` means the plugin was located and rejected the call. Read the diagnostic for argument details. A missing `"clip"` result or wrong type appears at the later getter boundary; do not collapse these cases into a generic frame error.

If your checksum differs, first confirm the intended format and color, then inspect the row traversal. Do not fix a mismatch by incorporating padding into the expected sum. Padding is storage outside the active image and is not a useful observable output.

A focused extension is to use Gray16 with a nontrivial value such as 1000, switch the row access to `u16`, and update the expected sum. Another is to inspect all three RGB planes independently. Both require you to make sample representation explicit while preserving the frame's ownership.

## Complete source

```odin title="examples/easy_host/src/main.odin"
--8<-- "examples/easy_host/src/main.odin"
```

Continue with [the raw host](raw-host.md) to see the C-level operations that implement this workflow.
