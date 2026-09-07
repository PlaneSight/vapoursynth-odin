---
title: Testing and verification
description: Reproduce compile checks, C/Odin ABI measurements, ownership tests, and the complete example runtime suite.
---

# Testing and verification

The repository checks three different boundaries: whether Odin accepts the
declarations, whether those declarations match the pinned C ABI, and whether
the resulting programs behave correctly with a real VapourSynth runtime.
Run the checks that exercise the boundary you changed. A successful compile
alone does not establish ABI compatibility or correct reference ownership.

All commands below run from the repository root. Generated probes, executables,
and plugin libraries belong in the ignored `.build` directory.

## Requirements by check

| Check | Required tools | VapourSynth installation |
| --- | --- | --- |
| Package and example type checking | Odin | None |
| C/Odin ABI verification | Python 3.10+, Odin, native C compiler | None; headers are checked in |
| `easy` ownership and error suite | Odin, matching core shared library | Core API 4.2 |
| All six example runtime checks | Python 3.10+, Odin, matching Python module and core | Core API 4.2 |
| Documentation | Python 3.11+, `requirements-docs.txt` | None |

See [installation](../getting-started/installation.md) for the compiler and runtime
setup, and [compatibility](compatibility.md) for the exact environment previously
verified. Do not infer runtime support on a target from another target's results.
The example runner's Python 3.10 syntax minimum does not override the installed
VapourSynth module's Python requirement; use a Python version supported by that
runtime distribution.

## Check the Odin packages

These checks do not load the core library:

```console
odin check . -no-entry-point -vet
odin check easy -no-entry-point -vet
odin check vsscript -no-entry-point -vet
odin check examples/core_info -vet
odin check examples/properties -vet
odin check examples/easy_host -vet
odin check examples/host -vet
odin check examples/plugin -no-entry-point -vet
odin check examples/invert -no-entry-point -vet
```

The library packages and plugins have no application `main`; this is why those
commands specify `-no-entry-point`. The optional `link` packages are exercised
by a consuming application when the platform's import library or shared library
is available. A dynamic host does not need that link-time dependency.

To type-check another target, add Odin's `-target` option. For example:

```console
odin check . -no-entry-point -vet -target:windows_i386
odin check easy -no-entry-point -vet -target:linux_amd64
odin check examples/invert -no-entry-point -vet -target:darwin_arm64
```

These commands check the selected target's declarations and conditional code.
They do not execute a program on that target, exercise its dynamic loader, or
verify a native C compiler's layout there.

## Compare the C and Odin ABI

```console
python tests/abi.py
```

The runner preprocesses the checked-in R76 headers twice: once with
`VS_USE_API_42` and `VSSCRIPT_USE_API_42`, then again with the experimental
`VS_GRAPH_API` extension. It generates independent C and Odin probes and compares:

- Integer constants and packed API versions.
- Struct sizes and alignments.
- Field offsets, including every stable core function slot and the graph suffix.
- Representative calls across C/Odin scalar, pointer, and callback boundaries.

The current reference produces **435 stable measurements** and **439 extended
measurements**. Both modes also run the C/Odin call probes. Successful output
includes lines of this form:

```text
PASS stable: 435 sizes, alignments, field offsets and constants; C/Odin calls passed.
PASS graph: 439 sizes, alignments, field offsets and constants; C/Odin calls passed.
```

This test needs no installed VapourSynth library. The C shim supplies the
representative API implementations. It catches declaration mistakes without
depending on a particular machine's multimedia setup.

### Select the toolchain

```console
python tests/abi.py --cc clang --odin odin
```

`--cc` accepts a compiler executable; the `CC` environment variable is also
recognized. Without either, the runner looks for MSVC on Windows, then `cc`,
`clang`, or `gcc`. When it discovers an installed MSVC compiler, it obtains the
Visual Studio developer environment for its child processes. It does not change
the parent shell's environment.

Use a native C compiler and an Odin compiler targeting the same architecture.
The probe executables are run locally. Keep `.build/abi` after a failure: its
generated source makes a mismatched offset or constant straightforward to inspect.

!!! warning "A cast can hide an ABI error"
    Do not fix a layout failure by forcing pointer casts or weakening the check.
    Compare the declaration to the pinned header. Field order, `c.int`, pointer
    indirection, and the `"system"` calling convention are part of the contract.

## Exercise the idiomatic interface

Pass the absolute path to the core library that will be used by the test process:

=== "Windows"

    ```powershell
    odin run tests/easy -- "C:/path/to/libvapoursynth.dll"
    ```

=== "Linux"

    ```sh
    odin run tests/easy -- /absolute/path/to/libvapoursynth.so
    ```

=== "macOS"

    ```sh
    odin run tests/easy -- /absolute/path/to/libvapoursynth.dylib
    ```

The suite combines real runtime calls with injected API behavior. This allows it
to cover allocation failure and ownership transfer precisely, alongside actual
map and frame operations. Coverage includes:

- Reference retention, destruction, and transfer on both success and failure.
- Cross-core rejection before references can be passed into an incompatible core.
- Missing, empty, and wrongly typed map properties; embedded zero bytes and arrays.
- Durable diagnostics, truncation, and cleanup of failed invocation results.
- Frame indices, media types, padded rows, typed sample validation, and alignment.

Keep assertions enabled for this test executable: the assertions express the
test expectations. If an assertion fails, record the compiler, runtime version,
architecture, and the failing procedure before changing the test or implementation.

## Run every example against a runtime

Use the Python environment in which `import vapoursynth` resolves to the runtime
you intend to test:

```console
python tests/examples.py
```

If the module lives in an isolated local directory, select that directory
explicitly. This command assumes it already exists:

```console
python tests/examples.py --runtime .build/runtime
```

The runner does not download or install packages. It verifies that an explicitly
selected directory actually supplied the imported module, and prints the module
path, core library, and version. To select a core library separately:

```console
python tests/examples.py --runtime .build/runtime --library /absolute/path/to/core-library
```

The library must match the Python runtime and the process architecture. An
unrelated DLL with the right filename is not a valid substitute.

The runner builds all six examples into `.build/examples`, checks the four host
programs' output, and loads both plugins through VapourSynth's Python API. It
then verifies the identity plugin and the invert filter against Gray8, RGB24,
YUV420P10, and Gray16 fixtures. The invert checks cover every visible pixel,
subsampled planes, padded layouts, retained frame properties, unchanged source
frames, and restoration after applying invert twice. It submits concurrent frame
requests before waiting for their results, and checks rejection diagnostics for
floating-point and variable-format clips.

This is a correctness suite, not a benchmark. It does not establish throughput,
exhaustively explore scheduler interleavings, or test every installed third-party
plugin.

## Validate documentation changes

After installing the documentation requirements in a virtual environment:

```console
python -m zensical build --clean --strict
python tools/check_docs.py
python -m unittest discover -s tests -p test_check_docs.py
```

The build includes the real Odin sources in reference pages and tutorials.
The offline checker resolves generated local links, assets, and heading fragments.
Its small test suite covers missing targets, encoded paths, site prefixes, and
directory traversal. It does not check availability of external websites.

Complete standalone programs introduced in documentation should also be compiled
or run with the documented toolchain. A syntax-highlighted code block has not
necessarily been type-checked. The [documentation guide](documentation.md)
describes previewing the rendered result and the GitHub Actions workflow.

## Choose checks for a change

| Change | Verification to perform |
| --- | --- |
| C-facing field, constant, callback, or calling convention | Package checks, native ABI suite, relevant target checks |
| Ownership, errors, maps, or row views in `easy` | Package checks, `tests/easy`, affected example runtime checks |
| Filter callbacks or pixel processing | Plugin check and complete example runtime suite |
| Runtime loading or linked declarations | Relevant host execution on the affected platform; linked consumer build when applicable |
| Prose, navigation, CSS, or source includes | Strict documentation build, local link checker, visual preview |
| Header baseline or API version | Full ABI and runtime suites, followed by the [upgrade procedure](compatibility.md#updating-the-header-baseline) |

When recording a result, include the actual compiler and runtime versions and
distinguish compile checks from native execution. That makes the compatibility
record useful to the next maintainer.
