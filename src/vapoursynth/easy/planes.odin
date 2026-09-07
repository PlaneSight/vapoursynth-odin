package easy

import "core:c"
import vs ".."

read_plane :: proc(frame: ^Frame, index: int) -> (Plane_View, Error) {
	if frame == nil || frame.api == nil || frame.handle == nil {
		return {}, .Invalid_Handle
	}
	if frame.api.getFrameType(frame.handle) != vs.mtVideo {
		return {}, .Wrong_Media_Type
	}
	format := frame.api.getVideoFrameFormat(frame.handle)
	if index < 0 || index >= int(format.numPlanes) {
		return {}, .Index_Out_Of_Range
	}
	width := int(frame.api.getFrameWidth(frame.handle, c.int(index)))
	height := int(frame.api.getFrameHeight(frame.handle, c.int(index)))
	stride := int(frame.api.getStride(frame.handle, c.int(index)))
	bytes := int(format.bytesPerSample)
	if width <= 0 || height <= 0 || bytes <= 0 || width > max(int)/bytes {
		return {}, .Unsupported_Format
	}
	row_bytes := width * bytes
	if stride < row_bytes || height-1 > (max(int)-row_bytes)/stride {
		return {}, .Unsupported_Format
	}
	data := frame.api.getReadPtr(frame.handle, c.int(index))
	if data == nil {
		return {}, .Invalid_Handle
	}
	return Plane_View{
		data = data,
		width = width,
		height = height,
		stride = stride,
		bytes_per_sample = bytes,
		bits_per_sample = int(format.bitsPerSample),
		sample_type = format.sampleType,
	}, .None
}

// The returned bytes are borrowed and read-only, even though Odin slices are mutable.
plane_row :: proc(plane: ^Plane_View, row: int) -> ([]u8, Error) {
	if plane == nil || plane.data == nil {
		return nil, .Invalid_Handle
	}
	if row < 0 || row >= plane.height {
		return nil, .Index_Out_Of_Range
	}
	if plane.width <= 0 || plane.bytes_per_sample <= 0 || plane.width > max(int)/plane.bytes_per_sample {
		return nil, .Unsupported_Format
	}
	row_bytes := plane.width * plane.bytes_per_sample
	if plane.stride < row_bytes || row > (max(int)-row_bytes)/plane.stride {
		return nil, .Unsupported_Format
	}
	start := row * plane.stride
	return plane.data[start:start+row_bytes], .None
}

// Typed access validates representation and alignment before constructing a view.
plane_row_as :: proc(plane: ^Plane_View, row: int, $T: typeid) -> ([]T, Error)
	where T == u8 || T == u16 || T == u32 || T == f32 {
	bytes, err := plane_row(plane, row)
	if err != .None {
		return nil, err
	}
	expected_sample_type: c.int = vs.stInteger
	when T == f32 {
		expected_sample_type = vs.stFloat
	}
	if plane.bytes_per_sample != size_of(T) || plane.sample_type != expected_sample_type ||
	   uintptr(raw_data(bytes)) % align_of(T) != 0 {
		return nil, .Unsupported_Format
	}
	return (cast([^]T)raw_data(bytes))[:plane.width], .None
}
