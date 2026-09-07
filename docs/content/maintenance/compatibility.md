---
title: Compatibility and upgrades
description: The pinned API 4.2 contract, platform verification record, experimental graph restrictions, and header upgrade process.
---

# Compatibility and upgrades

These bindings target **VapourSynth core API 4.2** and, in a separate package,
**VSScript API 4.2**. Both tables are translated from the R76 public headers at
commit [`aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7`](https://github.com/vapoursynth/vapoursynth/tree/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7).
The exact headers are checked into `tests/headers`; the running library is a
separate dependency supplied by the application or host. Verification against
R79 does not change these declarations or the pinned R76 headers.

## Version numbers describe different things

| Version | Meaning | How this repository uses it |
| --- | --- | --- |
| VapourSynth release, such as R76 or R79 | A distributed implementation and its headers | R76 is the declaration baseline; R76 and R79 have recorded runtime checks |
| Core API 4.2 | The requested `VSAPI` ABI | `VAPOURSYNTH_API_VERSION` is `(4 << 16) \| 2` |
| VSScript API 4.2 | The script environment's separate ABI | `VSSCRIPT_API_VERSION` is `(4 << 16) \| 2` |
| Odin compiler build | Language, standard library, and code generator | Record `odin version` when reproducing a result |

Core API 4.2 is available starting with
[VapourSynth R74](https://github.com/vapoursynth/vapoursynth/releases/tag/R74).
A host must still ask the loaded library for that version and handle `nil`.
Finding a library file or loading a symbol does not establish API compatibility.

Core and script versions must be negotiated independently. Obtaining a VSScript
4.2 table does not let an application assume that its core is the same version;
request `VAPOURSYNTH_API_VERSION` through the script table's `getVSAPI` and check
the result. The [loading guide](../guides/loading-and-linking.md) explains both
entry points.

### Python tooling and preview requirements

The uv project requires Python 3.12 or newer and currently locks VapourSynth R79.
The optional `preview` group pins VSView 0.11.0 and narrows its interpreter range
to Python 3.12–3.14 for the current PySide6 dependency. VSView also requires
VapourSynth R78 or newer. These are preview-tool requirements; they do not change
the raw bindings' core API 4.2 contract or the recorded R76 filter tests.

The `docs` group includes VapourSynth and NumPy to render the checked-in preview
scripts without importing VSView or Qt. Full documentation builds require Odin
because they compile the examples before generating their images. The
[preview guide](../guides/previewing-examples.md) and
[documentation guide](documentation.md) give the supported commands.

The four preview scripts passed headless checks of the first and last frames of
all **24 output nodes**, including the expanded low-bit views, on Windows x64
with R76 and R79. Initial VSView loading of the four demonstrations was verified
with R79 before those additional views were added. These checks establish script and frame evaluation; the filter
pixel-oracle suites below provide separate numerical validation.

## Stable and experimental tables

The stable `VSAPI` contains **117 function pointers** in header order. Its 4.2
tail adds `getCoreInfo2`. The raw package does not enlarge
this stable table to include optional experimental functions.

`VSGraphAPI` exposes the same stable prefix followed by four graph inspection
entries. Upstream makes this extension available only under `VS_GRAPH_API` and
requires an **exact core API version match**. Treat access to that suffix as a
separate compatibility decision. A pointer cast cannot make the suffix available
on a library that did not provide it.

Use the stable table for ordinary hosting and plugin development. If an
application deliberately uses graph inspection, follow the pinned header's
restrictions and the [raw reference](../reference/raw-api.md#experimental-graph-extension).
Do not infer graph extension compatibility from a successful request for the
stable 4.2 API on a newer runtime.

VSScript's 4.2 table contains **16 entries**. Newer VSScript declarations, including
the extra exported error accessor introduced in 4.3, are outside this package's
contract. Consult the pinned source when the current upstream documentation
describes a function that does not appear here.

## ABI choices that must remain deliberate

- Raw names preserve the C header's spelling, including procedure names, enum
  constants, and struct fields.
- C `int` becomes `core:c.int`; an Odin machine-sized `int` is not an interchangeable
  ABI declaration on 64-bit platforms.
- C pointer types retain the same indirection. Opaque handles remain opaque.
- API procedures and callbacks use `proc "system"`, matching `VS_CC`, including
  the Windows x86 convention. They do not receive Odin's implicit context.
- Struct and function-table field order follows the header. Appending a method
  to the wrong table changes what memory callers believe is present.
- Pointers supplied as `const` by C carry a read-only contract even where Odin's
  pointer or slice type does not enforce it. See [ownership](../guides/ownership.md).

The idiomatic package can validate arguments and wrap ownership, but it cannot
repair a mismatched raw ABI. That is why the C/Odin comparison is a separate
verification layer.

## Verification record

The following records completed checks. It is evidence from these environments,
rather than a promise that every combination of runtime, compiler, and operating
system has been tested. Both R76 and R79 runtime checks request core API 4.2.

| Target | Compiler | Verification |
| --- | --- | --- |
| Windows x64 | Odin `dev-2026-09-nightly:a2fb372` | Native C/Odin ABI checks; `easy` runtime and injected failure suite; introductory examples and advanced dither/Hald suites with VapourSynth R76 and R79; native wheel build, installation, autoload, and package checks |
| Windows x86 | Same compiler build | Compile checks for raw declarations, `easy`, tests, invert, and dither; no runtime execution recorded |
| Linux x64 | Same compiler build | Compile checks for raw declarations, `easy`, tests, invert, and dither; no runtime execution recorded |
| macOS ARM64 | Same compiler build | Compile checks for raw declarations, `easy`, tests, invert, and dither; no runtime execution recorded |

The native ABI checks passed **435 stable and 439 graph-extension measurements**,
together with representative C/Odin calls. These compare against the pinned R76
headers; they do not validate a newer runtime's experimental graph suffix.

`tests/examples.py` builds and runs the six introductory examples: `core_info`,
`properties`, `easy_host`, `host`, `plugin`, and `invert`. Invert coverage includes
Gray8, RGB24, YUV420P10, and Gray16, concurrent requests, preserved properties,
unchanged retained source frames, double inversion, and rejected inputs.

`tests/advanced.py` passed **410 dither pixel-oracle cases and 28 exact-level
checks** on both R76 and R79; the Hald suite has **81 pixel-oracle cases** on both
runtimes. Dither checks cover both scaling modes, scalar/SIMD parity, input
depths 8–16 and effective depths down to one bit, vector tails, padded rows,
subsampled planes, seed boundaries, exact
endpoints, temporal stability, concurrent requests, malformed-sample clamping,
and rejected parameters. Hald checks cover
RGB/RGBA PNGs at 8 and 16 bits, all five row filters, all six tetrahedral
orderings, nonlinear tables, fractional strength, Unicode paths, and malformed
files, including CRC failures. Both suites also check preserved properties and
unchanged retained source frames.

Effective dither depths 1–7 use ordinary eight-bit output formats. The expanded
sample values, byte-reading path for eight-bit input, preserved endpoints, and
rejection of zero bits are covered by the numerical suite. This feature does not
change the API version or require a custom sub-eight-bit VapourSynth format.

Hald was built and tested natively on Windows x64. Its Odin stb image
dependency requires native libraries built for the target platform. The common
build helper supplies the `stb:image` collection and prepares missing Unix
archives inside the workspace; see the
[build guide](../guides/previewing-examples.md#one-build-command-on-every-supported-platform).
The tested
Windows Odin installation does not contain the Unix stb libraries, so the Linux
and macOS compile checks above do **not** include Hald. No Unix native execution
or wheel verification is recorded.

This project does not currently declare a minimum supported Odin release. Odin
is evolving, and the recorded compiler build is the known working point. When
using another version, run the package checks and native verification before
treating the result as supported in an application.

The API's audio declarations are included in the raw binding. The `easy` frame
row interface is for video, and the example suite does not establish end-to-end
audio processing coverage. Likewise, VSScript's ABI is checked, but a complete
Python embedding application is not part of the example runtime suite.

## Updating the header baseline

An upstream release does not automatically change this repository's target.
Before updating, decide whether the work fixes a translation at API 4.2 or
intentionally adopts a new API version. That decision determines which table
members, version constants, and runtime requirements may change.

1. Select an upstream release and immutable commit. Read its public headers and
   release notes, including the preprocessor defaults and experimental sections.
2. Replace the reference headers with unmodified copies from that commit. Update
   `tests/headers/README.md` and [license provenance](../license.md) together.
3. Compare the complete declarations: constants, enum values, callbacks, structs,
   table ordering, optional fields, and exported entry points. Preserve the
   distinction between core, script, and graph APIs.
4. Update the Odin translation and any explicitly selected API macros in the
   verifier. Do not let an upstream header's default version silently select
   a different layout from the one requested by the bindings.
5. Run the native ABI suite and package checks. Investigate changed measurements
   by name; a higher count is not itself proof of a correct upgrade.
6. Run the ownership and example suites with the intended runtime, then execute
   on additional supported platforms where possible.
7. Update the compatibility record, installation requirements, reference prose,
   and changed examples. Build the documentation strictly and inspect it.

Source declarations are included directly in the generated reference, so their
signatures update with the code. Ownership explanations, version claims, and
example outcomes still require review by a maintainer.
