# Binding usage examples

These programs demonstrate the Odin bindings, introducing one set of API
responsibilities at a time. Their image-processing operations make frame and
callback contracts observable.

| Step | Example | Binding concepts |
| --- | --- | --- |
| 1 | [core_info](core_info/README.md) | Runtime loading, API negotiation, core ownership, and cleanup |
| 2 | [properties](properties/README.md) | Typed maps, borrowed data, arrays, and missing properties |
| 3 | [easy_host](easy_host/README.md) | Invocation, node references, frame requests, and row views |
| 4 | [host](host/README.md) | Host responsibilities through the raw function table |
| 5 | [plugin](plugin/README.md) | Plugin registration and transfer of a node reference |
| 6 | [invert](invert/README.md) | Activation callbacks, dependencies, frame ownership, and strides |
| 7 | [dither](dither/README.md) | Output-format negotiation, frame allocation, and sample storage |
| 8 | [haldlut](haldlut/README.md) | Foreign-library integration and persistent resource ownership |

From the repository root, with Odin and uv installed:

```console
uv run tools/run_host.py core_info
uv run tools/examples.py build
uv run tools/examples.py check --no-build
```

The optional `uv run --group preview tools/examples.py preview --no-build`
command opens the four plugin demonstrations in VSView. Inputs are generated
locally. Headless checks request their output frames without installing Qt.

Each directory is a standalone UV project that can be copied as a starting point:

```console
cd examples/invert
uv run build.py --check
uv run --group preview vsview preview.vpy
```

Hosts use `uv run build.py --run`. Plain `uv run build.py` compiles without
execution. Local builds download checksum-verified, pinned bindings; repository
builds explicitly use the current checkout. Individual plugin projects also
demonstrate native wheel packaging with `uv build`.

Read the [build guide](../docs/content/guides/previewing-examples.md) for native
prerequisites, dependency overrides, and scaffolding. The
[runtime tests](../docs/content/maintenance/testing.md) check reference lifetimes,
frame properties, sample boundaries, concurrent requests, and invalid inputs.
