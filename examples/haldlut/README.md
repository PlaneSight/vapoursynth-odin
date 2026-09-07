# Hald CLUT color-grading plugin

This advanced example implements `core.odin_hald.HaldCLUT(clip, path,
strength=1.0)`: an RGB color transform described by a Hald color lookup image.
It demonstrates loading external data through Odin's bundled `vendor:stb/image`,
validating that data before allocation-heavy decoding, caching immutable state,
tetrahedral interpolation, and processing three planar channels together.

## Build and generate a look

Run from the repository root:

```powershell
New-Item -ItemType Directory -Force .build | Out-Null
odin check examples/haldlut -no-entry-point -vet
odin build examples/haldlut -build-mode:dll -o:speed -out:.build/odin_hald.dll
python examples/haldlut/generate.py
```

On Linux or macOS, create the output directory with `mkdir -p .build` and use
`.so` or `.dylib` for the plugin extension. The Odin build mode remains `dll`.
The generator requires only Python's standard library and writes
`.build/haldlut-luts/identity.png` and `.build/haldlut-luts/cinematic.png`.
No PNG assets are checked into the repository.

Odin's Windows distribution includes the static stb libraries. On Linux/macOS,
if `vendor:stb/image` reports a missing compiled library, run the installed
compiler's build script with a native C compiler and archiver available:

```sh
sh /absolute/path/to/Odin/vendor/stb/src/build_stb.sh
```

This writes libraries into that Odin installation. The script selects the
native platform; a cross-compiled plugin needs a corresponding target library.
Runtime verification for this example was performed on Windows x64. The core
API is 4.2; no VapourSynth import library is needed because the host supplies
its API table to the plugin.

## Use it in a script

```python
from pathlib import Path
import sys

import vapoursynth as vs

suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
vs.core.std.LoadPlugin(path=str(Path(f".build/odin_hald{suffix}").resolve()))
source = vs.core.std.BlankClip(
    width=640, height=360, format=vs.RGB24, color=[32, 96, 160], length=24
)
graded = vs.core.odin_hald.HaldCLUT(
    source, path=str(Path(".build/haldlut-luts/cinematic.png").resolve()), strength=1.0
)
with graded.get_frame(0) as frame:
    print([frame[plane][0, 0] for plane in range(3)])
graded.set_output()
```

The default generated cinematic table maps this input to `[32, 91, 158]`.
The identity table returns `[32, 96, 160]`. The included `demo.vpy` generates a
spatial RGB gradient and publishes the source and graded result side by side.
Its output is 1280 × 360; the left half is the original gradient. The Python
gradient is demonstration input construction, not part of the native filter's
performance path.

## Input and file contract

| Input | Accepted values |
| --- | --- |
| Clip | Constant format and dimensions; planar RGB; integer samples with 8–16 significant bits |
| Strength | Finite floating-point value in `[0, 1]`; defaults to `1.0` |
| Image | Non-interlaced PNG, RGB or RGBA, 8 or 16 bits per channel; alpha ignored |
| Hald level | Integer level 2–8 inclusive |
| PNG dimensions | Square, with side length `level^3` |
| Encoded file size | 1–16,777,216 bytes, at most 16 MiB |
| Path | 1–32,767 bytes, without embedded zero bytes; UTF-8 on Windows |

Gray, YUV, float, variable-format, and variable-dimension clips are rejected
at filter construction. Convert the source deliberately into the RGB encoding
for which the LUT was authored. The filter maps numerical RGB code values; it
does not infer a transfer function, convert between color spaces, or apply PNG
ICC/gamma metadata. Existing frame properties are preserved.

The image is read and decoded during construction even when strength is zero.
A zero-strength frame request returns the acquired source frame directly. Once
construction succeeds, later edits, moves, or deletion of the PNG do not alter
the filter: create a new node to reload a changed look.

## Hald layout and interpolation

A Hald image stores a cubic RGB table in ordinary image raster order. At level
`L`, the image side is `L^3`, the cube edge is `L^2`, and the total number of RGB
triples is `L^6`. Red varies fastest, then green, then blue:

```text
cube index = red + edge * (green + edge * blue)
image x = cube index % image_width
image y = cube index / image_width
```

For example, level 4 produces a 64 × 64 image containing a 16 × 16 × 16 table.
See [ImageMagick's Hald CLUT reference](https://imagemagick.org/command-line-options/#hald-clut)
for the image representation used by other tools.

The decoder produces native RGB16 triples. Eight-bit PNG samples are promoted
to sixteen bits; the retained table uses six bytes per cube vertex. At the
maximum level 8, its 262,144 vertices occupy 1.5 MiB. The table is immutable and
shared by requests belonging to that filter instance.

For each input pixel, the filter scales its RGB values into cube coordinates.
It clamps the selected cell to leave a valid upper corner, including for an
input channel at its maximum. Three comparisons sort the fractional coordinates
and select one of the six tetrahedra inside the cube cell. Only four vertices
contribute; their nonnegative weights sum to one. Equal fractions have stable
RGB tie order, and the interpolation agrees on shared faces.

Interpolation and blending use `f64`:

```text
graded = interpolated_lut_value * source_max / 65535
mixed = original + strength * (graded - original)
output = truncate(clamp(mixed, 0, source_max) + 0.5)
```

Rounding is nearest with positive half values rounded upward. The table itself
is quantized to its PNG sample depth, so an identity LUT can introduce a small
quantization error at levels whose grid coordinates are not exactly representable
at that depth. The default level-4 identity has exactly representable grid values
in both the generated 8-bit and 16-bit forms.

## Validate before decoding

The PNG loader checks the signature, initial header, supported format, dimensions,
chunk lengths, and every chunk's CRC, including IHDR and IEND. A failed checksum
reports `HaldCLUT: corrupt PNG chunk (CRC mismatch).` Unsupported critical chunks,
truncated chunks, missing image data, and trailing data after IEND are rejected.

The encoded file is first copied into one bounded C allocation. IDAT chunks are
then concatenated into a separately bounded buffer and decompressed into a fixed
buffer sized for the exact expected scanlines. Only an exact match proceeds to
`stb_image.load_16_from_memory`. This preflight prevents a small, incorrectly
advertised image from making the allocating decoder expand an oversized stream.
Both passes inspect the same immutable file snapshot.

The file and temporary buffers are released before filter construction returns.
Only the decoded RGB table and the small filter instance remain. The code does
not read stb's global failure-message buffer or change its global decode options.
Errors are reported through the VapourSynth output map with stable messages.

## Ownership and parallel processing

`mapGetNode` acquires the source reference. Rejection frees it. On successful
construction, the instance owns both that reference and the decoded table;
`free_hald` releases them with `freeNode` and `stb_image.image_free`, then frees
the C-allocated instance. Failed filter creation uses that same cleanup function.
`mapConsumeNode` transfers the created node into the output map even if insertion
fails.

The filter declares `rpStrictSpatial`: output frame `n` needs input frame `n`.
Its `fmParallel` mode is safe because the source reference, table, configuration,
and sample maximum are immutable. `arInitial` requests the source frame;
`arAllFramesReady` reads it and computes the output. No per-request allocation
survives a callback return, so the error activation has no temporary state to free.

For nonzero strength, `copyFrame` preserves frame properties and `getWritePtr`
provides writable output planes without changing source pixels. Each channel
uses its own source and destination byte stride. The row loop visits only the
active width, leaving padding untouched. RGB channels are processed together
because each output channel can depend on all three input values.

All callbacks use `proc "system"`; private helpers use `proc "contextless"`.
File operations and allocations use explicit platform/C APIs, avoiding an
assumption that a VapourSynth worker thread has an Odin implicit context.

## Make your own reproducible look

```console
python examples/haldlut/generate.py --level 8 --bits 16 --look cinematic --output .build/haldlut-custom
```

The generator's `cinematic` function applies a modest contrast curve, lowers
saturation, cools shadows, and warms highlights. Edit that pure function to make
another transform. The writer applies it to every grid vertex and serializes
PNG chunks without timestamps or external libraries. Repeated runs with the
same options and Python/zlib environment produce the same file bytes.

Do not resize, blur, or JPEG-compress a LUT image: neighboring image pixels
encode different cube coordinates. Save a color transform in the required Hald
layout and preserve the image's dimensions and sample ordering.

The independent advanced tests exercise all tetrahedral orderings, PNG filters,
8/16-bit RGB/RGBA tables, 8–16 bit sources, fractional strengths, cached-file
lifetime, concurrent frames, properties, source immutability, and invalid input.
Use the root testing instructions for runtime selection and the shared runner.

## Third-party code

The built plugin statically links Odin's bundled stb_image. Preserve the notice
in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) when distributing this
example's binary under the included MIT option. The plugin source remains
LGPL-2.1-or-later, and the repository's root third-party notices cover the other
bundled runtime components.
