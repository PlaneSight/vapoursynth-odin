# Register an identity plugin

The identity example is a minimal shared-library plugin. It registers `odin_example.Identity`, accepts one video node, and returns a reference to that same node. This isolates plugin registration and ownership transfer before the next tutorial introduces frame processing.

The package is `examples/plugin`. Its two foreign procedures are the exported initialization entry point and the registered function callback. It does not load the core library, create a core, or request a frame; the VapourSynth host owns that environment and supplies the API.

## See the pass-through

```console
uv run --group preview tools/examples.py preview plugin
```

This builds the plugin into `.build/examples` and opens the checked-in
`examples/plugin/preview.vpy` in VSView. Output `0` compares source and result side
by side; outputs `1` and `2` show them separately. They should match exactly.
The [preview guide](../guides/previewing-examples.md) explains the optional
dependency group and headless checks.

=== "Source"

    ![Synthetic source scene with shaded red, green, and blue spheres above a grayscale ramp](../assets/generated/identity-source.png){ width="768" height="320" }

=== "Identity output"

    ![The same scene returned unchanged by the native Odin identity plugin](../assets/generated/identity-output.png){ width="768" height="320" }

These images are exported from the demonstration's actual output nodes during
the documentation build. `uv run tools/render_showcase.py` reproduces them under
`.build/showcase` using the same script.

## Build the shared library

Build from the repository root with the same command on every supported platform:

```console
uv run tools/examples.py build plugin
```

The command writes the native library under `.build/examples`, selecting its
extension, architecture, and optimized compiler flags automatically. The
[build guide](../guides/previewing-examples.md#one-build-command-on-every-supported-platform)
covers platform prerequisites. The inline Python program below and the preview
script load the copy published into the example's local `.build` directory.

The plugin needs a host implementing core API 4.2. Build for the architecture used by that host. The raw bindings introduce no core-library linker dependency for this plugin because all core operations go through supplied function pointers.

## Load and exercise it

Save this Python example as `identity_demo.py` in the repository root, then run `uv run identity_demo.py`:

```python
from pathlib import Path
import runpy

import vapoursynth as vs

project = runpy.run_path("examples/plugin/build.py")
vs.core.std.LoadPlugin(path=str(project["artifact_path"]()))

source = vs.core.std.BlankClip(
    width=65, height=47, format=vs.GRAY8, color=[17], length=1
)
result = vs.core.odin_example.Identity(source)

with source.get_frame(0) as original, result.get_frame(0) as output:
    assert output.width == original.width
    assert output.height == original.height
    assert output[0].tolist() == original[0].tolist()
    print(f"Identity: {output.width} x {output.height}; first pixel: {output[0][0, 0]}")
```

Expected output:

```text
Identity: 65 x 47; first pixel: 17
```

For a preview application, call `result.set_output()` in a `.vpy` script instead of printing the frame. The pixel data and properties pass through because the function returns the original graph node.

## Export the initialization entry point

```odin
@(export)
VapourSynthPluginInit2 :: proc "system"(plugin: ^vs.VSPlugin, api: ^vs.VSPLUGINAPI)
```

The exported name is how VapourSynth locates plugin initialization. `@(export)` exposes the symbol from the shared library, and `proc "system"` matches the foreign calling convention used by the bindings.

The `api` parameter here is `^VSPLUGINAPI`, the small registration table. It differs from the full `^VSAPI` supplied to the function callback. Initialization uses the registration table to configure this plugin and declare its functions; frame and map operations use the full core table later.

The upstream [plugin API documentation](https://www.vapoursynth.com/doc/api/vapoursynth4.h.html) defines this entry point and registration contract. The [raw API reference](../reference/raw-api.md) maps it to the Odin types.

## Give the plugin a distinct identity

`configPlugin` sets these values:

| Field | Value in the example | Purpose |
| --- | --- | --- |
| Identifier | `org.vapoursynth.odin.example` | Distinguishes this plugin from other plugins. |
| Namespace | `odin_example` | Makes the function available as `core.odin_example.Identity`. |
| Display name | `Odin identity example` | Describes the plugin. |
| Plugin version | `1 << 16` | Encodes this plugin's version as 1.0. |
| Required API | `vs.VAPOURSYNTH_API_VERSION` | Requests core API 4.2. |
| Flags | `0` | Uses the default plugin configuration. |

The plugin version and required core API version are separate values. Changing the plugin's own version does not change which API table it expects.

If configuration returns zero, initialization stops. A successful configuration is followed by `registerFunction`:

```odin
api.registerFunction("Identity", "clip:vnode;", "clip:vnode;", identity, nil, plugin)
```

The argument and result strings each declare one video-node property named `clip`. The callback is `identity`; no per-function user data is required, so the value is nil. The minimal example does not branch on `registerFunction`'s return value. If expanding initialization to register several functions, handle each registration result deliberately; it uses nonzero for success.

Use your own unique identifier and namespace when turning this example into another plugin, so both can be loaded into the same core.

## Acquire the argument reference

The `identity` callback receives borrowed input and output maps, user data, the host's core, and the full API table. It must leave ownership of those supplied objects with the host.

```odin
property_error: c.int
node := api.mapGetNode(input, "clip", 0, &property_error)
```

A successful `mapGetNode` acquires a native reference. The callback checks the property error and pointer before using it. If the argument cannot be read, `mapSetError` puts a meaningful failure on the output map and the callback returns.

Although the function is named Identity, copying the input pointer straight into a result would not establish a correct ownership contract. The getter supplies one acquired reference that can then be transferred into the output map.

## Transfer exactly once, including failure

```odin
if api.mapConsumeNode(output, "clip", node, vs.maReplace) != 0 {
    api.mapSetError(output, "Identity: could not return the clip.")
}
```

`mapConsumeNode` transfers the getter's reference. Once called, the callback no longer owns that reference, including when insertion fails. It must not follow the call with `freeNode(node)` or a deferred free of the same acquired reference.

This is the reason the callback has no node cleanup defer. Its successful acquisition has one consuming endpoint, and that endpoint is reached on every path after acquisition. The output map's owner subsequently manages the returned reference.

`mapSetNode` has a different ownership shape: it adds a reference for the map while leaving the caller responsible for the original one. The [ownership guide](../guides/ownership.md) compares the two operations, and the [map guide](../guides/maps.md) explains their wrapper equivalents.

No filter instance is allocated here. There is no dependency declaration, frame callback, or free callback because the function does not create a new processing node. Those additional responsibilities appear in [invert](invert-plugin.md).

## Keep callbacks independent of implicit Odin context

Both procedures use `proc "system"` and perform operations available through explicit arguments. They do not assume an Odin caller has installed an implicit `context`. This keeps the entry boundary valid when a C host invokes the callback.

If you add allocation, logging, or other operations requiring context, establish an appropriate context explicitly or use context-free facilities. Do not assume ordinary Odin runtime state exists simply because the callback body is written in Odin. The invert example demonstrates checked C allocation for persistent instance data.

## Diagnose loading and registration

A missing-plugin-file error is a path problem: check the extension and resolved path printed or constructed by your script. A loader rejection can indicate a host/plugin architecture mismatch or unsupported required API. See upstream [LoadPlugin](https://www.vapoursynth.com/doc/functions/general/loadplugin.html) and the [loading guide](../guides/loading-and-linking.md).

If `odin_example` is absent after a load attempt, check the load error and the configured namespace. If loading reports a duplicate plugin identifier, start a fresh host process after rebuilding or give a distinct plugin its own identifier. Rebuilding a file does not replace an already loaded plugin inside a running core.

The complete example suite additionally checks that Identity preserves every pixel and a custom frame property. Run `python tests/examples.py` with the runtime arrangement described in the [testing guide](../maintenance/testing.md).

## Complete source

```odin title="examples/plugin/src/plugin.odin"
--8<-- "examples/plugin/src/plugin.odin"
```

??? example "Preview and documentation script"

    ```python title="examples/plugin/preview.vpy"
    --8<-- "examples/plugin/preview.vpy"
    ```

Continue with [a complete invert filter](invert-plugin.md), which retains this registration pattern and adds scheduled pixel processing.
