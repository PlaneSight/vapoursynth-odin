# Frames, planes, and sample access

A node describes a clip and how to produce its frames. A frame is one evaluated
result. In a host application, `easy.get_frame` requests that result
synchronously and returns an owned frame reference. `easy.read_plane` then
exposes a borrowed view of one video plane, and the row helpers account for
padding and sample representation.

This guide builds on the [quickstart](../getting-started/quickstart.md) and
[map guide](maps.md). The [easy host example](../examples/easy-host.md) combines
these operations in a runnable program.

## Request a frame from a host

The snippets use these imports with the repository in the `deps` collection:

```odin
import "core:fmt"
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

Given an owned `easy.Node`, request frame zero and schedule cleanup immediately:

```odin
// Inside a procedure returning bool; node is a live easy.Node value.
diagnostic: easy.Diagnostic
frame, err := easy.get_frame(&node, 0, &diagnostic)
if err != .None {
    fmt.eprintln("Request frame:", err, easy.diagnostic_text(&diagnostic))
    return false
}
defer easy.destroy_frame(&frame)
```

Indices are zero-based. Before requesting work, the helper rejects a negative
index, an index outside the C API's signed 32-bit range, or an index at or beyond
the node's frame count with `.Index_Out_Of_Range`. The call blocks until
VapourSynth produces the frame or reports failure. An upstream filter error
becomes `.Frame_Request_Failed`; the optional diagnostic carries its message.

!!! warning "Use synchronous requests only from host code"

    Do not call `easy.get_frame` from a filter's get-frame callback. Filters
    participate in VapourSynth's request scheduler through `requestFrameFilter`
    and `getFrameFilter`, with work split across activation reasons. The
    [invert plugin](../examples/invert-plugin.md) demonstrates that lifecycle.

For asynchronous host requests, use the raw `getFrameAsync` API and implement
its callback and reference-lifetime contract. The `easy` package does not provide
an asynchronous request wrapper.

## Distinguish video and audio

`easy.Node` and `easy.Frame` can represent either media type. `get_frame` checks
the node type and validates the index against video or audio `numFrames`
accordingly. An audio frame index addresses a block of audio samples; it is not
a video frame index or an individual sample position.

The convenience views in this guide are specifically for video:

| Helper | Video | Audio |
| --- | --- | --- |
| `get_frame` | Requests a video frame | Requests an audio frame |
| `video_info` | Returns copied `VSVideoInfo` | `.Wrong_Media_Type` |
| `read_plane` | Returns a video `Plane_View` | `.Wrong_Media_Type` |
| `destroy_frame`, `retain_frame` | Supported | Supported |

Use raw audio-format, frame-length, and channel-data accessors for audio. Do not
pass an audio frame to video-specific raw accessors to work around the checked
view's type rejection. The [raw API reference](../reference/raw-api.md) covers
the available declarations.

For video, `easy.video_info` returns a copy of the node's `VSVideoInfo`, including
frame count and frame-rate numerator and denominator. Node information is
useful for planning requests. Read each returned frame's actual format and
plane dimensions before processing its memory, particularly for clips whose
dimensions or format may vary between frames.

## A plane has its own dimensions and stride

VapourSynth's video formats are planar: Gray has one image plane; RGB and YUV
store their components in separate planes. A pixel-processing loop should work
with the dimensions of its current plane.

```odin
// Inside a procedure returning bool; frame is a live easy.Frame value.
plane, err := easy.read_plane(&frame, 0)
if err != .None {
    fmt.eprintln("Read plane:", err)
    return false
}
fmt.printf("%d x %d samples; %d bytes between rows\n",
    plane.width, plane.height, plane.stride)
```

`read_plane` validates the frame, media type, and plane index. It queries actual
dimensions and stride, checks that the row layout and offset arithmetic are
representable, and obtains the read pointer. A `Plane_View` contains:

| Field | Meaning |
| --- | --- |
| `data` | Borrowed pointer to the plane's first byte |
| `width`, `height` | Dimensions of this plane, measured in samples and rows |
| `stride` | Byte distance between the start of consecutive rows |
| `bytes_per_sample` | Storage occupied by one sample |
| `bits_per_sample` | Number of significant sample bits |
| `sample_type` | Integer or floating-point representation |

For a 640 × 480 YUV420 frame, the luma plane is 640 × 480 and each chroma plane
is 320 × 240. Reading all three with luma's dimensions would cross the chroma
plane's valid area. Query every plane independently; avoid deriving its layout
from assumptions about the clip name or the previous plane.

The active byte count in one row is:

```text
row_bytes = width * bytes_per_sample
row_start = data + row_index * stride
```

Stride may exceed `row_bytes` because the allocation contains padding between
rows. The next row begins at `stride`, regardless of how many active bytes you
read. A tightly packed interpretation of `width * height` samples can silently
include padding and skip image data.

## Iterate active rows

`plane_row` returns exactly the active bytes in a requested row, excluding
padding. It checks the row index, sample-width arithmetic, and row offset
before constructing the slice.

```odin
// Inside a procedure returning bool; plane came from easy.read_plane.
checksum: u64
for y in 0..<plane.height {
    row, err := easy.plane_row(&plane, y)
    if err != .None {
        return false
    }
    for byte in row {
        checksum += u64(byte)
    }
}
fmt.println("Active-byte checksum:", checksum)
```

This sums stored bytes. For an 8-bit integer plane, each byte is also one sample.
For a 10-bit plane or a float plane, a byte sum does not represent the sum of
sample values. Use a typed row when the computation is defined in terms of
samples.

The example clip deliberately uses width 65, so its processing loop does not
depend on a conveniently aligned image width. The runtime chooses the actual
stride; the program prints that value and checks all active pixels.

## Significant bits and storage are separate

A 10-bit integer sample occupies two bytes. Its storage type is `u16`, even
though the valid integer range uses only ten bits. Likewise, 12-bit and 16-bit
integer planes use two-byte storage. Use `bits_per_sample` to select numerical
limits and `bytes_per_sample` to select a memory representation.

`plane_row_as` supports four Odin element types:

| Requested type | Required storage | Required sample type |
| --- | --- | --- |
| `u8` | 1 byte | `vs.stInteger` |
| `u16` | 2 bytes | `vs.stInteger` |
| `u32` | 4 bytes | `vs.stInteger` |
| `f32` | 4 bytes | `vs.stFloat` |

The helper checks storage width, integer-versus-float representation, and
pointer alignment. On success it returns `plane.width` native-representation
samples without conversion or allocation. Requesting an unsupported element
type is rejected by the procedure's compile-time type constraint; requesting a
supported type that mismatches the plane returns `.Unsupported_Format`.

```odin
// Inside a procedure returning bool; plane is an integer plane using u16 storage.
sample_sum: u64
for y in 0..<plane.height {
    row, err := easy.plane_row_as(&plane, y, u16)
    if err != .None {
        return false
    }
    for sample in row {
        sample_sum += u64(sample)
    }
}
fmt.println("Sample sum:", sample_sum)
```

This does not normalize values to a common bit depth, adjust limited range, or
perform color conversion. Those are separate operations with their own format
and frame-property requirements.

Half-float video uses two-byte floating-point storage. Asking for `u16` is
rejected because the sample type is float; asking for `f32` is rejected because
the storage width is two bytes. Use `plane_row` for access to its bytes and
perform an explicit half-float interpretation if the application needs one.
The wrapper provides no half-float conversion.

## A complete checked Gray8 reader

This helper requests a frame, verifies the intended format, and computes a
sample checksum. It uses `easy` and `vs` from the imports above; `fmt` is not
needed by the helper itself.

```odin
gray8_checksum :: proc(
    node: ^easy.Node,
    index: int,
    diagnostic: ^easy.Diagnostic,
) -> (u64, easy.Error) {
    frame, frame_error := easy.get_frame(node, index, diagnostic)
    if frame_error != .None {
        return 0, frame_error
    }
    defer easy.destroy_frame(&frame)

    plane, plane_error := easy.read_plane(&frame, 0)
    if plane_error != .None {
        return 0, plane_error
    }
    format := frame.api.getVideoFrameFormat(frame.handle)
    if format.colorFamily != vs.cfGray || plane.bits_per_sample != 8 {
        return 0, .Unsupported_Format
    }

    checksum: u64
    for y in 0..<plane.height {
        row, row_error := easy.plane_row_as(&plane, y, u8)
        if row_error != .None {
            return 0, row_error
        }
        for sample in row {
            checksum += u64(sample)
        }
    }
    return checksum, .None
}
```

Checking the color family prevents accidentally treating just the first plane
of RGB or YUV as a complete grayscale image. The typed row check verifies
integer representation and storage width. The raw format pointer is borrowed
and is read only while the owned frame is alive.

## Keep the frame alive for every view

`Plane_View`, byte rows, and typed rows all borrow storage from their frame. They
do not acquire a frame reference, and returning a view from a procedure does
not extend its lifetime. Obtain views through `read_plane` and preserve their
fields; constructing a view around arbitrary pointers bypasses the frame's
layout guarantees.

!!! warning "Read-only is a contract"

    Odin slices allow assignment, but rows returned by these helpers must not
    be modified. They point to VapourSynth's read-only frame storage. The view
    expires when its frame is destroyed or modified through the raw API.

If another component needs prolonged access, give it an independently owned
reference from `retain_frame`, and make its cleanup responsibility explicit.
Assignment of the `Frame` struct does not retain anything. Alternatively, copy
the required pixels into application-owned storage while the frame is alive.

The `easy` layer has no frame-writing helper. A filter that produces different
pixels should use the raw allocation or copy APIs and request a write pointer
on the resulting writable frame. The [invert plugin](../examples/invert-plugin.md)
shows source-frame ownership, copied frame properties, separate read and write
strides, and bit-depth-aware arithmetic. Its callback lifecycle is the next
step after synchronous host access.
