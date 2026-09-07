# VapourSynth bindings for Odin

Odin bindings for **VapourSynth core API 4.2**, an optional idiomatic host interface,
and a separate companion package for **VSScript API 4.2**. The raw declarations are translated from
[VapourSynth R76](https://github.com/vapoursynth/vapoursynth/tree/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7),
and the exact reference headers are checked into `tests/headers`.

The root package includes all 117 stable `VSAPI` entries, `VSPLUGINAPI`, all
callback types, concrete structs, opaque handles, 45 preset-format constants,
audio channels, and the frame property constants from `VSConstants4.h`.
The experimental graph table is exposed separately as `VSGraphAPI`.
`VSHelper4.h` contains C inline convenience functions and is outside the scope
of these raw ABI bindings.

The optional [`easy` package](easy/README.md) adds typed map access, explicit
resource ownership, plugin invocation, synchronous frame requests, durable error
diagnostics, and stride-aware row views. Start with the
[eight examples](examples/README.md), which progress from core information and map
properties to parallel invert, SIMD blue-noise dither, and Hald CLUT color-grading
filters. The Hald example uses Odin's bundled `vendor:stb/image` library.

## Reproducible environment and plugin wheels

With [uv](https://docs.astral.sh/uv/) and Odin installed, compile all eight examples
and open the four visual demonstrations:

```console
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

`uv run` provisions the environment as needed. `build` writes the binaries into
`.build/examples`; `preview --no-build` reuses them and opens the `.vpy` scripts
in **VSView**, with named comparison, source, and filtered outputs. A standalone
`preview invert dither` command builds those selected filters before opening them.

For an optional headless frame check or an individual host:

```console
uv run tools/examples.py check --no-build
uv run tools/run_host.py core_info
uv run tools/run_host.py easy_host
```

The optional `preview` dependency group installs VSView and Qt only when selected.
It requires Python 3.12–3.14 and VapourSynth R78 or newer; ordinary `uv sync`
keeps the GUI dependencies out of the environment. See
[Build and preview the examples](docs/guides/previewing-examples.md) for the
complete workflow and output choices. All demonstration input is generated
locally, so no video downloads or source plugins are needed.

The lockfile selects VapourSynth R79; the raw declarations remain pinned to R76
API 4.2. Both runtimes have been exercised on Windows x64. Python 3.12 or newer is
required by the runtime distribution. Odin remains the native compiler.

Ordinary sync installs development dependencies. An explicit `uv build` compiles
the four native plugins and packages them as a platform-specific wheel under
`vapoursynth/plugins/odin_examples`, following VapourSynth's autoload convention.
The Python distribution is named `vapoursynth-odin-examples`; it distributes
native example filters. Odin applications import the source packages as usual.
See [Python environments and wheels](docs/guides/python-packaging.md) for the
layout, source builds, third-party notices, and installation verification.

## Documentation

The [documentation site](docs/index.md) includes installation and first-program
guides, ownership and error handling, maps and frame layout, all eight example
walkthroughs, complete API references, and testing and compatibility guidance.
It is built with [Zensical](https://zensical.org/) and includes the actual Odin
sources directly in tutorials and reference pages.

To preview it through the locked environment, run from the repository root:

```console
uv run --group docs tools/docs.py serve
```

For validation, run `uv run --group docs tools/docs.py build`. Both commands
compile the examples and render documentation images from the same `.vpy` scripts
used in VSView. A broken plugin build, script, or frame request fails the operation;
the site does not reuse stale screenshots. The build command also performs a
strict Zensical build and checks local links. Odin is required; VSView is optional.
Markdown changes reload while serving; restart the command after changing native
code or preview scripts to regenerate their images. A generated `requirements-docs.txt`
also supports pip-based builds. The [publishing guide](docs/maintenance/documentation.md)
explains the included GitHub Pages workflow, which validates pull requests and
deploys the repository's default branch once **Settings → Pages → GitHub Actions**
is enabled. The deployment derives its repository and site URLs from GitHub.

| Package | Purpose |
| --- | --- |
| Root | Complete raw core API 4.2 declarations; no automatic loading. |
| `easy` | Idiomatic synchronous hosting with typed errors and explicit cleanup. |
| `link` | Optional linked core entry point. |
| `vsscript`, `vsscript/link` | Raw script API 4.2 and its optional linked entry point. |

## Importing

Place this repository in your project, or add its parent directory as an Odin
library collection. For example, when the repository is in `vendor/vapoursynth-odin`:

```odin
import vs "deps:vapoursynth-odin"
```

```console
odin build . -collection:deps=vendor
```

Importing the root package adds no library dependency and performs no loading or
initialization. A plugin receives its API table from VapourSynth; a host obtains
one through `getVapourSynthAPI`. Keep that table as a borrowed pointer and request
`vs.VAPOURSYNTH_API_VERSION`, which is `(4 << 16) | 2`. Check the result for `nil`
before accessing any fields. Do not copy, modify, or free the API table.

### Host applications

The [host example](examples/host/main.odin) uses `core:dynlib` to load the core,
resolve `getVapourSynthAPI`, create a core, invoke `std.BlankClip`, and read a frame.
It releases its frames, nodes, maps, and core before unloading the library.

```console
odin run examples/host -- /absolute/path/to/libvapoursynth.dll
```

The path is optional. Defaults are `libvapoursynth.dll` on Windows,
`libvapoursynth.so` on Linux, and `libvapoursynth.dylib` on macOS. The file and its
dependencies must be available to the platform loader. Core API 4.2 requires
VapourSynth R74 or newer; older libraries return `nil` for this version request.

For applications that use normal linker resolution, import the optional `link`
package:

```odin
import vs "deps:vapoursynth-odin"
import vs_link "deps:vapoursynth-odin/link"

main :: proc() {
    api := vs_link.getVapourSynthAPI(vs.VAPOURSYNTH_API_VERSION)
    if api == nil {
        panic("VapourSynth API 4.2 is unavailable")
    }
    core := api.createCore(0)
    if core == nil {
        panic("Could not create a VapourSynth core")
    }
    defer api.freeCore(core)

    info: vs.VSCoreInfo2
    api.getCoreInfo2(core, &info)
}
```

The linker defaults are `system:vapoursynth.lib` on Windows and
`system:vapoursynth` elsewhere. Supply an SDK import library on Windows, or
override the path with `-define:VAPOURSYNTH_LIBRARY=/absolute/path/to/library`.
The runtime DLL is still required. The dynamic-loading example does not require
an import library.

### Plugins

The examples include both a minimal identity plugin and a full
[invert filter](examples/invert/README.md). Invert demonstrates dependencies,
activation reasons, frame lifetime, per-plane strides, and parallel frame
processing for 8–16 bit integer formats.

[The plugin example](examples/plugin/plugin.odin) exports `VapourSynthPluginInit2`
and registers `odin_example.Identity`, which returns a reference to its input clip:

```console
uv run tools/examples.py build plugin
```

Use the platform's shared-library extension for the output on Linux or macOS.
Load it from a VapourSynth Python script:

```python
import vapoursynth as vs

vs.core.std.LoadPlugin(path="/absolute/path/to/.build/examples/plugin.dll")
source = vs.core.std.BlankClip(width=64, height=48, length=1)
vs.core.odin_example.Identity(source).set_output()
```

Declare plugin entry points and callbacks with `proc "system"`. This maps to
`stdcall` on Windows x86 and the C calling convention on the other supported
targets, matching `VS_CC`. These callbacks do not receive Odin's implicit context.
If a callback uses Odin operations that require a context, establish one inside
that callback, for example `context = runtime.default_context()` after importing
`base:runtime`. The example only calls the context-free VapourSynth API.

## Type mapping and ownership

The bindings retain C type names, field names, function names, and constant names.
Only parameter names that are Odin keywords gain a trailing underscore.
C enum typedefs are aliases of `c.int`; their values are untyped constants, so
`vs.pfGray8` works with both a `u32` format ID and an `i64` map property.

| C declaration | Odin declaration |
| --- | --- |
| `int`, including status and enum parameters | `c.int` |
| `int64_t`, `uint64_t`, `uint32_t` | `i64`, `u64`, `u32` |
| `float`, `double`, `ptrdiff_t` | `f32`, `f64`, `c.ptrdiff_t` |
| Opaque `VSNode *`, `VSFrame *`, etc. | `^VSNode`, `^VSFrame`, etc. |
| `void *`, `void **` | `rawptr`, `^rawptr` |
| `const char *`, writable `char *` | `cstring`, `[^]u8` |
| Pointer to a counted array | `[^]T` |

Odin does not enforce C `const`. Treat `getReadPtr`, read-only frame properties,
format/info pointers, API tables, and other borrowed data as read-only, and follow
their upstream lifetimes. Opaque structs have no accessible contents: obtain
their pointers from the API instead of allocating them yourself.

`mapGetData` can return binary data containing zero bytes, despite its C string
pointer type. Read its length with `mapGetDataSize` and view it as
`(cast([^]u8)data)[:int(size)]`; converting it to an Odin string by scanning for a
terminating zero would truncate binary data. Supply the explicit length to
`mapSetData` when passing binary data, and keep the source buffer alive for the call.

| Operation | Ownership rule |
| --- | --- |
| `createMap`, `invoke` | Free the returned map with `freeMap`. |
| `mapGetNode`, `mapGetFrame`, `mapGetFunction`, `add*Ref` | Return owned references; release each one. |
| `getFrame`, `getFrameFilter`, frame constructors, `copyFrame` | Return owned frame references; release or transfer them as required by the callback contract. |
| `mapSetNode`, `mapSetFrame`, `mapSetFunction` | Retain their own reference; the caller keeps its reference. |
| `mapConsumeNode`, `mapConsumeFrame`, `mapConsumeFunction` | Consume the caller's reference even when the operation fails. |
| `getVideoInfo`, `getAudioInfo`, frame data and property getters | Return borrowed pointers; do not free them. |
| `freeCore` | Finish outstanding requests and release core-owned objects first. |

Status conventions vary across the C API. Map setters usually return **zero** on
success; `configPlugin`, `registerFunction`, and format queries return **nonzero**
on success. Check the individual function's documentation.

Audio channel values are bit positions, not masks. For example, stereo is
`(u64(1) << vs.acFrontLeft) | (u64(1) << vs.acFrontRight)`. A 64-bit value is
necessary because channel positions extend beyond 31.

`VS_MAKE_VERSION(major, minor)` is provided as a context-free runtime procedure.
Use `(major << 16) | minor` when a compile-time Odin constant is required.

### API 4.2 range properties

Use **`_Range`**, with `VSC_RANGE_LIMITED = 0` and `VSC_RANGE_FULL = 1`.
The old `_ColorRange` property used the reverse values. The bindings select the
API 4.2 branch of `VSConstants4.h` and expose `VSRange`.

### Experimental graph inspection

`VSAPI` ends at `getCoreInfo2`. `VSGraphAPI` embeds that stable table at offset zero
and appends the four functions guarded by `VS_GRAPH_API` in the C header.
Access this extension only after checking that `api.getAPIVersion()` equals
`vs.VAPOURSYNTH_API_VERSION` exactly, and cast with `cast(^vs.VSGraphAPI)api`.
Create the core with `ccfEnableGraphInspection` and perform no concurrent frame
requests or other API calls. Upstream designates this extension for debugging and
graph inspection; it is unsuitable for use inside filters.

## VSScript

Import `vapoursynth-odin/vsscript` for the 16-entry VSScript 4.2 table and
`VSGetVSScriptAPI` type, or `vapoursynth-odin/vsscript/link` for a linked
`getVSScriptAPI` declaration. Request `VSSCRIPT_API_VERSION` and check for `nil`.
VSScript and the core have independent version numbers; call `getVSAPI` with the
core's `VAPOURSYNTH_API_VERSION` separately.

The linked package accepts `-define:VSSCRIPT_LIBRARY=/absolute/path/to/library`.
Its defaults are `system:vsscript.lib` on Windows and `system:vsscript` elsewhere,
matching R76. When loading VSScript manually on Unix, use
`dynlib.load_library(path, global_symbols = true)` so Python extension modules can
resolve their symbols.

`createScript` consumes a supplied core even if it fails. `getCore` returns a
borrowed core owned by the environment. Release output node references and finish
frame requests before `freeScript`; do not free the core separately. Follow the
header's error-state restriction: after evaluation fails, use `getError` and
`freeScript` only. VSScript 4.3's extra exported error function is not part of this
4.2 package.

## Verification

Compile the raw bindings and examples without a VapourSynth installation:

```console
odin check . -no-entry-point -vet
odin check easy -no-entry-point -vet
odin check vsscript -no-entry-point -vet
odin check examples/host -vet
odin check examples/plugin -no-entry-point -vet
odin check examples/invert -no-entry-point -vet
```

Run the C ABI comparison and interop checks with Python 3.10+, Odin, and a C compiler:

```console
python tests/abi.py
```

Use `--cc` or `--odin` to select compiler executables explicitly. The runner can
discover MSVC on Windows and prepares its environment only in child processes.

The verifier uses the checked-in headers with explicit 4.2 preprocessor defines.
It compares sizes, alignments, field offsets, and constants, including the
experimental table, and exercises C/Odin calls across representative scalar,
pointer, and callback boundaries. Generated probes and binaries go in `.build`.
No VapourSynth runtime or Python VapourSynth module is required for these checks.

With a core runtime available, also run the high-level ownership/error tests and
the complete example suite:

```console
odin run tests/easy -- /absolute/path/to/libvapoursynth.dll
python tests/examples.py
```

The Python runner requires the VapourSynth Python module. Use
`--runtime .build/runtime` to select an existing local package directory, and
`--library` if the corresponding core library needs an explicit path.

Runtime verification on Windows x64 used VapourSynth R76 and Odin
`dev-2026-09-nightly:a2fb372`. All six examples passed, including parallel invert
requests for Gray8, RGB24, YUV420P10, and Gray16, preserved properties, and unchanged
source frames. The `easy` suite also passed runtime and injected failure tests
for ownership, diagnostics, maps, and typed row views. Compile checks cover
Windows x86, Linux x64, and macOS ARM64; those targets have not been runtime-tested
here. The C ABI suite still passes all 435 stable and 439 extended measurements.

The same introductory and `easy` suites also pass with the uv-provisioned R79
runtime. The advanced runner independently checks dither's exact integer results
and scalar/SIMD parity, plus Hald CLUT's tetrahedral interpolation, PNG decoding,
cached lookup data, frame properties, and failures:

```console
uv run tests/advanced.py
uv run tests/benchmark_dither.py
```

The benchmark reports measured end-to-end frame throughput using optimized
baseline CPU builds, verifies parity before timing, and includes scheduler and
frame-allocation overhead. See the [dither walkthrough](docs/examples/dither-plugin.md)
for the algorithm and measurement limits.

## References and license

- [Official core API documentation](https://www.vapoursynth.com/doc/api/vapoursynth4.h.html)
- [Official VSScript documentation](https://www.vapoursynth.com/doc/api/vsscript4.h.html)
- [Pinned reference headers and provenance](tests/headers/README.md)

The translated declarations and reference headers are licensed under
**LGPL-2.1-or-later**, preserving the upstream notices. See [LICENSE](LICENSE).
