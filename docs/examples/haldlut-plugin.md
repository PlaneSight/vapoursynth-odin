---
title: Hald CLUT color grading with stb_image
description: Load a 16-bit Hald PNG through Odin's stb_image binding and apply a cached color cube using tetrahedral interpolation.
---

# Hald CLUT color grading with stb_image

`odin_hald.HaldCLUT` applies a three-dimensional color lookup table stored in a
PNG image. It combines VapourSynth's planar frame API with Odin's
bundled stb image binding, loads the table once during filter creation, and
uses tetrahedral interpolation to grade 8–16 bit integer RGB video.

The [invert filter](invert-plugin.md) introduces the callback lifecycle. This
example adds a bounded external-file load, foreign allocation ownership,
interleaved lookup-table storage, and a color transform whose output depends on
all three input channels.

## See the color transform

This synthetic RGB16 scene contains shaded colored spheres and a neutral ramp.
The graded view is actual native filter output using the generated level-4
RGB16 cinematic LUT at `strength=1.0`. Both views use the same conversion from
sixteen-bit samples to RGB8 for display, so their differences come from the LUT.

=== "Original scene"

    ![Original synthetic scene with red, green, and blue shaded spheres above a neutral grayscale ramp](../assets/generated/hald-source.png){ width="768" height="320" }

=== "Cinematic LUT"

    ![The same scene after native Hald CLUT processing, showing the cinematic table's contrast and color changes](../assets/generated/hald-cinematic.png){ width="768" height="320" }

Reproduce the scene, LUT, and filter-output images with:

```console
uv run tools/render_showcase.py
```

The renderer builds the plugins and exports these nodes from the checked-in
`examples/haldlut/demo.vpy` into `.build/showcase`, alongside the other plugin
comparisons and a record of the run. Each documentation build regenerates the
same images. To inspect the script interactively:

```console
uv run --group preview tools/examples.py preview haldlut
```

The command builds the canonical `.build/examples/haldlut` library and launches
VSView. The script generates its cinematic LUT automatically under
`.build/example-assets`; no separate asset preparation is needed. Output `0`
is the comparison, `1` the source, and `2` the result. See the
[preview guide](../guides/previewing-examples.md) for the optional dependency group.

## Build the plugin and generate a look

Provision the [uv environment](../guides/python-packaging.md), then create two
example LUTs with the standard-library-only generator:

```console
uv sync --locked
uv run examples/haldlut/generate.py
```

The default output directory, `.build/haldlut-luts`, receives `identity.png` and
`cinematic.png`. Both are level-4, 64 × 64 RGB PNGs with 16 bits per channel.
The cinematic transform combines a modest S-curve, reduced saturation, cool
shadows, and warm highlights. It is an example look, with no camera-specific
calibration.

Build the native library with the same command on every supported platform:

```console
uv run tools/examples.py build haldlut
```

The command creates `.build/examples/haldlut` with the correct native extension,
architecture, and optimized compiler flags. It reuses the stb image libraries
supplied by Odin's stb image package. If Unix archives are missing, it
builds the bundled C sources in a private staging directory under `.build` with
`cc` and `ar`. Install a native C compiler and archiver on Linux, or Xcode
command line tools on macOS, for that fallback. Windows uses the vendor
libraries shipped with Odin. The build does not modify the Odin installation.
The [build guide](../guides/previewing-examples.md#one-build-command-on-every-supported-platform)
explains target selection and platform prerequisites.

The repository also packages the compiled Hald plugin through `uv build --wheel`.
See [Python environments and wheels](../guides/python-packaging.md) for native
dependency notices and automatic discovery. The binary statically links stb_image;
its bundled third-party notice accompanies redistribution, as described in
[license and provenance](../license.md).

## Import an Odin vendor library

The plugin uses Odin's supplied stb image declarations through a small custom
collection:

```odin
import stbi "stb:image"
```

The common build helper maps `stb` to the compiler installation's `vendor/stb`
directory. If native archives are missing on Unix, it copies the image bindings
into a private build directory, compiles the missing archives there, and points
the same collection at that prepared package. The plugin calls the same Odin
stb API in either case.

This explicit collection keeps dependency preparation within the workspace;
Odin's built-in `vendor` collection cannot be replaced. The uv build, preview,
test, and wheel commands pass the collection automatically. If integrating this
example into a different build system, provide a `stb` collection pointing to
Odin's `vendor/stb` directory or an equivalent prepared copy containing native
libraries for your target.

## Apply a table

Save this as `hald_demo.py` in the repository root and run `uv run hald_demo.py`:

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/examples/haldlut{suffix}").resolve()))

source = vs.core.std.BlankClip(
    format=vs.RGB24, width=640, height=360,
    color=[32, 96, 160], length=1,
)
graded = vs.core.odin_hald.HaldCLUT(
    source,
    path=str(Path(".build/haldlut-luts/cinematic.png").resolve()),
    strength=1.0,
)

with graded.get_frame(0) as frame:
    print([frame[p][0, 0] for p in range(3)])
```

When using an installed example wheel, omit `LoadPlugin` and let VapourSynth
discover the native binary. The checked-in `demo.vpy` creates the shaded-sphere
scene shown above, with named original, graded, and side-by-side output nodes.

```python
result = core.odin_hald.HaldCLUT(clip, path="look.png", strength=1.0)
```

| Argument | Contract |
| --- | --- |
| `clip` | Constant-format, constant-dimension RGB with 8–16 bit integer samples |
| `path` | Existing Hald PNG; 1–32767 path bytes with no embedded zero |
| `strength` | Finite floating-point value from `0.0` through `1.0`; default `1.0` |

The output keeps the source format, dimensions, timing, and frame properties.
`strength=0.0` returns acquired source frames without pixel processing, but table
loading and validation still happen during construction. A missing or invalid
table therefore remains an invocation error at zero strength.

## Understand the Hald layout

A Hald image flattens a regular RGB cube into a square image. For level `L`:

```text
cube edge = L²
PNG side = L³
number of RGB entries = L⁶
entry index = red + edge × (green + edge × blue)
```

Red varies fastest, then green, then blue. PNG pixels are read in row order, so
the decoder's interleaved RGB triples already have the lookup order needed by
the interpolator. No second cube allocation or rearrangement is necessary.

| Level | PNG dimensions | RGB grid | Cached RGB16 data |
| ---: | --- | --- | ---: |
| 2 | 8 × 8 | 4 × 4 × 4 | 384 bytes |
| 4 | 64 × 64 | 16 × 16 × 16 | 24 KiB |
| 8 | 512 × 512 | 64 × 64 × 64 | 1.5 MiB |

The generator accepts `--level 2` through `--level 8`, `--bits 8` or `--bits 16`,
`--look identity`, `--look cinematic`, or `--look all`, and an `--output` directory.
A larger grid samples the transform more densely and costs more cache space.
A 16-bit PNG also preserves more precision in each lattice value; it does not
require 16-bit input video.

A LUT image encodes coordinates, so resizing, blurring, or JPEG compression
changes the transform itself. Author the look through operations on individual
colors and preserve the image's dimensions and channel ordering.

The native representation is explicit:

```odin
Hald_Table :: struct {
    pixels: [^][3]u16,
    edge:   int,
}
```

The PNG loader requests three output channels through
`stbi.load_16_from_memory`. An eight-bit table is promoted to sixteen-bit channel
storage by multiplying each value by 257; alpha, when present, is discarded. Input video remains planar, so the
frame loop reads one sample from each of the three source planes to form a
lookup coordinate.

## Interpolate four cube vertices

For source maximum `M = 2^bits - 1`, each channel becomes a cube coordinate:

```text
coordinate = source_sample × (edge - 1) / M
```

The interpolator clamps coordinates to the cube, selects the lower cell corner,
and computes three fractions within that cell. At the maximum endpoint it uses
the final cell with fraction one, keeping all vertex indices inside the table.

Sorting the fractions chooses one of six tetrahedra. For fractions
`red=0.8`, `green=0.5`, and `blue=0.2`, the four relative vertices are
`000`, `100`, `110`, and `111`, with weights:

```text
1 - 0.8 = 0.2
0.8 - 0.5 = 0.3
0.5 - 0.2 = 0.3
0.2       = 0.2
```

These nonnegative weights sum to one. Each vertex supplies an entire RGB triple,
so the same interpolation weights transform all three output channels. Three
comparisons select the fraction ordering, with a stable RGB order for ties.
The calculations use `f64`.

After interpolation, the filter scales the RGB16 result back to the source code
range, blends it with the original sample, clamps, and rounds:

```text
graded = interpolated_RGB16 × M / 65535
mixed = original + strength × (graded - original)
output = floor(clamp(mixed, 0, M) + 0.5)
```

An identity LUT approximates identity according to the precision of its stored
lattice values. Do not assume every identity image at every grid size produces
bit-exact output. Tests use exactly representable lattice values when asserting
that stronger property, and otherwise compare against the stored table's actual
interpolation result.

??? info "Complete tetrahedral interpolation"

    ```odin title="examples/haldlut/interpolation.odin"
    --8<-- "examples/haldlut/interpolation.odin"
    ```

## Bound decoding before handing memory to stb_image

The loader supports non-interlaced RGB or RGBA PNGs with 8 or 16 bits per channel,
levels 2–8, and encoded files no larger than 16 MiB. It rejects other image types,
palette or grayscale PNG input, unsupported dimensions, truncated chunks, and
invalid or oversized image streams. Every chunk's CRC, including the initial
header and final end chunk, is verified; a mismatch reports
`HaldCLUT: corrupt PNG chunk (CRC mismatch).`

Loading proceeds from one immutable copy of the encoded file. Header checks
establish the permitted dimensions and representation. The validator collects
image-data chunks and tests inflation into a buffer sized for the advertised
scanlines before invoking the allocating image decoder. It verifies the decoded
dimensions and channel count afterward. These checks establish this example's
accepted domain; they do not constitute a complete PNG conformance validator.

Windows paths are converted from UTF-8 to native wide strings before opening.
The Unix path implementation uses the platform C file functions. File handles
and temporary encoded or validation buffers remain local to creation and are
released on both success and failure.

## Cache data with explicit ownership

The decoded table belongs to `stb_image` and must be released with
`stbi.image_free`, not Odin's `delete` or an unrelated allocator. The instance
itself uses `libc.malloc` and `libc.free`, and owns one source-node reference.
Successful `createVideoFilter2` transfers the instance to the filter; failures
before that point release everything already acquired.

Every frame request reads the same immutable table. There is no per-frame file
I/O or decode, and concurrent requests need no shared scratch space. Replacing
or removing the file after creation does not alter the existing filter. Create
a new filter instance to pick up a different table.

VapourSynth callbacks use `proc "system"`; the helper computations are
`contextless`, and allocation uses the explicit C and stb APIs. The code never
assumes an Odin context is supplied by VapourSynth's worker threads. The loader
also avoids stb's global failure-reason string when reporting decode failures,
so a concurrent creator cannot replace the diagnostic being read.

As in invert, `rpStrictSpatial` requests source frame `n` for output `n`, and
`fmParallel` permits concurrent processing. `copyFrame` preserves properties;
writable output pointers keep source pixels unchanged. Every plane's stride is
read independently. The [ownership](../guides/ownership.md) and
[frame-layout](../guides/frames.md) guides explain those contracts.

## Scope and verification

The transform works directly on RGB code values. It does not apply an ICC
profile, interpret PNG color metadata, convert a transfer function, or convert
YUV into RGB. Prepare the clip in the color encoding expected by the LUT before
calling it. Floating-point and HDR-specific processing are outside this
example's supported domain.

```console
uv run tests/advanced.py --only haldlut
```

The independent reference calculations exercise nonlinear tables, all six
tetrahedral fraction orderings, boundary colors, strengths, input depths, RGB
and RGBA PNGs, PNG filtering, concurrent requests, preserved properties, and
unchanged retained sources. Separate cases reject invalid paths, files,
formats, and nonfinite strengths, and verify cached operation after removing
the LUT file. See [testing](../maintenance/testing.md) for the runtime options.

??? info "Complete loader and validation"

    ```odin title="examples/haldlut/png.odin"
    --8<-- "examples/haldlut/png.odin"
    ```

??? info "Complete plugin lifecycle and row processing"

    ```odin title="examples/haldlut/plugin.odin"
    --8<-- "examples/haldlut/plugin.odin"
    ```

??? info "Runnable gradient preview"

    ```python title="examples/haldlut/demo.vpy"
    --8<-- "examples/haldlut/demo.vpy"
    ```
