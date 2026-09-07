// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:c"

import vs "../.."
import easy "../../easy"

test_typed_rows :: proc() {
	u8_samples := [?]u8{0, 255, 17, 99}
	u16_samples := [?]u16{0, 1023, 513, 99}
	u32_samples := [?]u32{0, max(u32), 1 << 31, 99}
	f32_samples := [?]f32{0, 1, -0.5, 99}
	_ = check_typed_row(u8_samples[:], vs.stInteger, 8)
	_ = check_typed_row(u16_samples[:], vs.stInteger, 10)
	integer_plane := check_typed_row(u32_samples[:], vs.stInteger, 32)
	float_plane := check_typed_row(f32_samples[:], vs.stFloat, 32)

	_, err := easy.plane_row_as(&integer_plane, 0, f32)
	expect(err, .Unsupported_Format)
	_, err = easy.plane_row_as(&float_plane, 0, u32)
	expect(err, .Unsupported_Format)

	half_samples := [?]u16{0x0000, 0x3c00, 0x3800}
	half_plane := easy.Plane_View{
		data = cast([^]u8)raw_data(half_samples[:]),
		width = len(half_samples), height = 1,
		stride = size_of(half_samples), bytes_per_sample = 2,
		bits_per_sample = 16, sample_type = vs.stFloat,
	}
	_, err = easy.plane_row_as(&half_plane, 0, f32)
	expect(err, .Unsupported_Format)
	_, err = easy.plane_row_as(&half_plane, 0, u16)
	expect(err, .Unsupported_Format)

	misaligned_plane := integer_plane
	integer_bytes := cast([^]u8)raw_data(u32_samples[:])
	misaligned_plane.data = cast([^]u8)&integer_bytes[1]
	_, err = easy.plane_row_as(&misaligned_plane, 0, u32)
	expect(err, .Unsupported_Format)
}

check_typed_row :: proc(samples: []$T, sample_type: c.int, bits: int) -> easy.Plane_View {
	// The last element is padding, so the returned view must exclude it.
	plane := easy.Plane_View{
		data = cast([^]u8)raw_data(samples),
		width = len(samples)-1, height = 1,
		stride = len(samples)*size_of(T), bytes_per_sample = size_of(T),
		bits_per_sample = bits, sample_type = sample_type,
	}
	row, err := easy.plane_row_as(&plane, 0, T)
	expect(err, .None)
	assert(len(row) == len(samples)-1)
	assert(uintptr(raw_data(row)) == uintptr(raw_data(samples)))
	for pixel, i in row {
		assert(pixel == samples[i])
	}
	return plane
}
