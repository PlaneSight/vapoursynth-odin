---
title: Troubleshooting
description: Diagnose library loading, API negotiation, ownership, map errors, pixel layout, and plugin callback problems.
---

# Troubleshooting

Start with the failing boundary. A host first loads the shared library, resolves
an entry point, negotiates an API version, creates resources, and finally requests
work. Preserve the first useful diagnostic rather than continuing with a `nil`
handle or an error result map.

## Find the relevant symptom

| Symptom | Start here |
| --- | --- |
| Core library cannot be loaded | [Library paths and dependencies](#library-paths-and-dependencies) |
| Library loads but the API is unavailable | [API version negotiation](#api-version-negotiation) |
| Linker cannot find `vapoursynth` | [Linking and architecture](#linking-and-architecture) |
| Filter invocation fails | [Invocation and map errors](#invocation-and-map-errors) |
| Missing value appears indistinguishable from zero | [Map types and empty properties](#map-types-and-empty-properties) |
| Crash during cleanup or after returning a frame view | [Ownership and borrowed data](#ownership-and-borrowed-data) |
| Pixels are shifted, repeated, or corrupted | [Stride and sample representation](#stride-and-sample-representation) |
| Plugin loads but crashes when frames are requested | [Callbacks and frame scheduling](#callbacks-and-frame-scheduling) |
| Invert rejects a clip | [The invert example's input contract](#the-invert-examples-input-contract) |
| Documentation build or deployment fails | [Build and publish these docs](maintenance/documentation.md#diagnose-a-documentation-failure) |

## Library paths and dependencies

A library filename is resolved according to the operating system's loader
rules. It is not a search through the repository. To remove ambiguity, pass an
absolute path to the dynamic host example:

```console
odin run examples/core_info/src -collection:deps=src -- /absolute/path/to/core-library
```

Use `libvapoursynth.dll`, `libvapoursynth.so`, or `libvapoursynth.dylib` as
appropriate. The path above is a placeholder, not a literal installed location.
If the library exists but loading still fails, check its dependent libraries and
the process architecture. A 64-bit host cannot load a 32-bit core.

The standalone host examples use the core C API. They do not need the VapourSynth
Python module merely to construct `std.BlankClip`. The Python example test runner
and VSScript embedding have additional Python requirements. An `ImportError` from
`tests/examples.py` should be investigated in the Python environment printed or
selected by that command.

When passing `--runtime` to the test runner, name the directory containing the
existing VapourSynth module. The runner rejects an unrelated module imported
from elsewhere. It will not install a missing runtime for you.

See [loading and linking](guides/loading-and-linking.md) for default names,
loader behavior, and the separate VSScript library.

## API version negotiation

`getVapourSynthAPI` returning `nil` means the loaded library did not provide the
requested API. Request `VAPOURSYNTH_API_VERSION`, check the result, and use a
runtime that provides core API 4.2. R74 is the first release with that core API.

Do not request an older table and then read fields from the 4.2 declaration.
The final entries might not exist. Likewise, a newer runtime does not make its
experimental graph suffix safe to read through an older declaration. The
[compatibility guide](maintenance/compatibility.md) separates stable negotiation
from the graph extension's exact-version restriction.

With VSScript, check both `getVSScriptAPI(VSSCRIPT_API_VERSION)` and the returned
table's `getVSAPI(VAPOURSYNTH_API_VERSION)`. These are independent interfaces.

## Linking and architecture

The raw bindings and dynamic host examples do not require an import library.
Importing `link` selects normal linker resolution. On Windows the default is
`vapoursynth.lib`, and the runtime DLL is also required at execution time.
`-define:VAPOURSYNTH_LIBRARY=...` can override the linked library's path.

For a plugin, build a shared library and export `VapourSynthPluginInit2` with
the exact spelling and calling convention shown in the examples. Build for the
same architecture as the process loading the plugin. Start with the tested
[identity example](examples/identity-plugin.md) to isolate export or registration
problems before adding frame callbacks.

If Odin reports that a library package lacks `main`, check whether the command
needs `-no-entry-point` for type checking or `-build-mode:dll` for a plugin build.
Use the exact commands in the relevant example walkthrough.

## Invocation and map errors

A raw invocation can return a non-`nil` result map that contains an error.
Inspect `mapGetError` before extracting the output node. In `easy`, pass an
optional `Diagnostic` to `invoke` and report both the returned
`Error` and the copied message. The [error guide](guides/errors.md) gives complete
examples of preserving that diagnostic through cleanup.

Check the plugin namespace, function name, argument key spelling, property types,
and required arguments. For the built-in blank clip filter, the namespace is
`std`, the function is `BlankClip`, and the output node is stored under `clip`.
After a successful `invoke`, use `map_get_node(&result, "clip")` to acquire that
node reference. Other functions may return different keys or property types;
select the key and typed getter from the function's output contract.

Raw success conventions vary. `registerFunction` returns nonzero on success;
many map setters return zero on success. Do not reuse one Boolean test for every
C operation. Consult the [raw API reference](reference/raw-api.md).

An `easy.Diagnostic` is caller-owned storage. Its message view stays valid only
while that diagnostic's buffer remains alive and unchanged. Copy the message
if it must survive reuse of the same diagnostic for another operation.

## Map types and empty properties

Raw getters often return a zero-like value on failure and report the reason
through an error pointer. Reading only the returned integer or float loses the
distinction between a valid zero and a missing or wrongly typed property.

The `easy` getters return a typed `Error`. Handle `.Missing_Key`, `.Wrong_Type`,
and `.Index_Out_Of_Range` deliberately. An existing empty array is different from
a missing key; the wrapper checks its type and element count before calling
array accessors that would reject an empty value.

Map keys are zero-terminated C strings. String and byte **values** have explicit
lengths and can include zero bytes. If binary data appears truncated, inspect
whether application code converted it to a C string or ignored the stored length.
See [maps and properties](guides/maps.md) for borrowed arrays, replacement versus
append, and node transfer rules.

## Ownership and borrowed data

The `easy` structs are explicit owners. Copying one with ordinary assignment
copies its fields; it does not acquire another VapourSynth reference. Destroying
both copies can release the same resource twice. Use `retain_node` or
`retain_frame` when another independent owner is required.

Conversely, raw `mapGetNode`, raw `getFrame`, and their `easy` equivalents produce
owned references that must be released. A pointer's type alone does not establish
whether it is borrowed or acquired. Read the operation's ownership contract.

Destroying the same already-cleared `easy` owner is harmless, but that does not
make copied owner structs safe. Borrowed map arrays, metadata pointers, frame
planes, and row slices also do not keep their parent resource alive. Stop using
them before their parent is released or mutated in a way that invalidates them.

Release frames, nodes, and maps before freeing their core, and release the core
before unloading the library containing the API function pointers. If an
operation transfers a reference, follow its failure rule as carefully as its
success rule: `map_take_node` clears the source after calling the consuming raw
setter even if that setter reports failure. Pre-call validation failures leave
the source intact.

A `.Different_Core` error identifies an attempt to mix wrappers from different
cores. Keep an invocation's maps and nodes associated with the intended core.
Do not change the public `core` field to bypass the check; that falsifies the
provenance the wrapper relies on.

The [ownership guide](guides/ownership.md) diagrams these lifetimes and explains
safe teardown order.

## Stride and sample representation

VapourSynth frames are planar, and each row's allocated byte stride can exceed
its visible width. A 65-pixel Gray8 row is 65 bytes of image data even when the
next row starts 128 bytes later. Advancing by width alone reads padding as pixels.

Use the plane's byte stride to find each row and process only its visible sample
count. Query each plane's dimensions: subsampled chroma planes can be smaller
than the luma plane. Source and destination frames have independent strides.

The `easy` row helpers validate the row index and sample representation.
`plane_row` provides visible bytes; `plane_row_as` returns one typed element per
sample when the requested type matches the storage. Use `u16` for a 10-bit integer
format stored in two bytes. Its legal maximum is 1023, not 65535. Floating-point
formats require a different arithmetic interpretation.

Read-only source data must stay read-only even when the Odin pointer or slice
type permits assignment. Obtain a writable frame through the appropriate raw
API before modifying pixels. The [frame guide](guides/frames.md) and
[invert walkthrough](examples/invert-plugin.md) show stride, bit depth, and
copy-on-write together.

## Callbacks and frame scheduling

Foreign callbacks use `proc "system"`. VapourSynth does not pass an Odin
implicit context, so context-dependent formatting or allocation cannot be used
as if the callback were an ordinary Odin procedure. The plugin examples keep
their foreign boundary explicit and use compatible allocation and deallocation
for instance storage.

A filter's callback follows the activation protocol. Request upstream frames
during `arInitial`, consume the requested frames during `arAllFramesReady`, and
release any outstanding per-request state on `arError`. A synchronous host-side
`getFrame` is not a replacement for that protocol inside a filter callback.

`fmParallel` permits simultaneous callback execution. Shared mutable instance
data therefore needs synchronization or a design that avoids concurrent
mutation. The invert example's instance contains immutable configuration and
its input node; each callback operates on its own frames.

When reporting a callback failure, set the filter error through the supplied
frame context, release references acquired by that activation, and return `nil`.
Keep instance cleanup in the registered free callback. The full lifecycle is
explained in the [invert tutorial](examples/invert-plugin.md).

## The invert example's input contract

The example accepts constant-format, constant-dimension integer video with
8–16 significant bits, including planar Gray, RGB, and YUV. Floating-point and
variable-format inputs are rejected when constructing the filter. Convert a
clip deliberately if your intended pipeline requires another format; silently
interpreting float samples as integers would be incorrect.

For every visible sample, the filter computes:

```text
output = ((1 << bits_per_sample) - 1) - input
```

It applies that arithmetic to each plane and preserves frame properties. It is
a demonstration of API usage and full-range sample arithmetic, not a
color-managed or limited-range-aware visual negative. If a YUV result looks
different from a desired artistic inversion, first define the color and range
transformation you need, then implement that operation explicitly.

## Python environments and packaged plugins

`uv sync` provisions the Python dependencies. The root project's
`tool.uv.package = false` setting means it does not compile the example plugins.
Use `uv run tools/examples.py build` to compile the binding examples.
For the optional wheel-packaging lesson, run `uv build` inside a plugin example. Odin must be available on `PATH` for either build.

Test wheel installation in a separate environment: an exact `uv sync` can remove
a manually installed wheel that is not declared by the development project.
Start a fresh Python process after installation and inspect
`vapoursynth.get_plugin_dir()`. The example's native library belongs beneath that directory. A core created with `ccfDisableAutoLoading` will not discover them.
The [packaging guide](guides/python-packaging.md) describes the copied-project and isolated-wheel checks.

If Hald CLUT fails while preparing `stb`, check the reported native tool or
source file. The common build command reuses Odin's supplied image libraries;
on Unix it compiles missing archives privately under `.build` using `cc` and
`ar`. Install a native C compiler and archiver on Linux, or the Xcode command
line tools on macOS, then rerun the command. A missing Windows vendor library
indicates an incomplete Odin installation. The build never writes libraries
into the compiler installation. See the
[build guide](guides/previewing-examples.md#one-build-command-on-every-supported-platform)
for supported targets and native requirements.

## Preview and generated documentation images

Run `uv run --group preview tools/examples.py preview` to select the optional
VSView dependency group. Plain `uv sync` excludes VSView and Qt. The preview group
requires Python 3.14; select a compatible interpreter with
`uv sync --locked --group preview --python 3.14` if the current environment uses
a newer Python version. Keep `--group preview` on later viewer commands.

Close the viewer before rebuilding a loaded plugin. A live core retains its
original machine code, and Windows may keep its DLL locked. `--no-build` is
appropriate only when you deliberately want to reuse the existing binary.
If a preview fails before showing a frame, run `uv run tools/examples.py check`
to exercise the scripts without the GUI.

Build documentation with `uv run --group docs tools/docs.py build`. Direct
Zensical commands do not create the ignored PNGs under `docs/content/assets/generated`.
The wrapper builds the examples and renders their actual script outputs before
validating the site. It stops on a compiler, script, or frame error instead of
falling back to stale images. When using `tools/docs.py serve`, restart it after
editing native code or scripts; Markdown changes reload automatically.

The dither comparison intentionally applies the same 20× display contrast gain
to both sides. Its additional output nodes `3` and `4` expose the unamplified
source and native result. See the [preview guide](guides/previewing-examples.md)
for output selection and the documentation rendering contract.

## Capture a useful failure report

Include `odin version`, operating system and architecture, the runtime release
and loaded library path, the exact build or test command, and the first error
message. Reduce a plugin issue to a small generated clip where possible.
For an ABI failure, preserve the generated `.build/abi` probe and the named
measurement mismatch. For an ownership failure, describe which operation
acquired the reference and which code released or transferred it.

The [verification guide](maintenance/testing.md) provides repeatable commands
for establishing whether a failure belongs to the declarations, wrappers,
examples, or local runtime setup.
