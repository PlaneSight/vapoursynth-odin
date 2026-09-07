// SPDX-License-Identifier: LGPL-2.1-or-later
package haldlut

import "core:c"
import "core:c/libc"
import "core:hash"
import stbi "stb:image"

import vs "deps:vapoursynth"

MAX_FILE_BYTES :: 16 * 1024 * 1024
MAX_PATH_BYTES :: 32767
MAX_LEVEL :: 8

load_hald :: proc "contextless"(input: ^vs.VSMap, api: ^vs.VSAPI) -> (Hald_Table, cstring) {
	property_error: c.int
	path_size := api.mapGetDataSize(input, "path", 0, &property_error)
	if property_error != vs.peSuccess || path_size <= 0 || path_size > MAX_PATH_BYTES {
		return {}, "HaldCLUT: path must contain 1-32767 bytes."
	}
	path_data := api.mapGetData(input, "path", 0, &property_error)
	if property_error != vs.peSuccess || path_data == nil {
		return {}, "HaldCLUT: expected a file path."
	}
	path_bytes := (cast([^]u8)path_data)[:int(path_size)]
	for value in path_bytes {
		if value == 0 {
			return {}, "HaldCLUT: path must not contain embedded zero bytes."
		}
	}
	path: [MAX_PATH_BYTES + 1]u8
	libc.memcpy(raw_data(path[:]), raw_data(path_bytes), c.size_t(len(path_bytes)))
	encoded, message := read_file(cast(cstring)raw_data(path[:]))
	if message != nil {
		return {}, message
	}
	defer libc.free(raw_data(encoded))

	edge, png_error := validate_png(encoded)
	if png_error != nil {
		return {}, png_error
	}
	width, height, channels: c.int
	pixels := stbi.load_16_from_memory(raw_data(encoded), c.int(len(encoded)), &width, &height, &channels, 3)
	if pixels == nil {
		// stb's global failure_reason is deliberately not read from concurrent creators.
		return {}, "HaldCLUT: stb_image could not decode the validated PNG."
	}
	if int(width) * int(height) != edge * edge * edge || channels < 3 || channels > 4 {
		stbi.image_free(pixels)
		return {}, "HaldCLUT: decoded PNG does not match its Hald layout."
	}
	return Hald_Table{pixels = cast([^][3]u16)pixels, edge = edge}, nil
}

read_u32_be :: proc "contextless"(data: []u8) -> u32 {
	return u32(data[0]) << 24 | u32(data[1]) << 16 | u32(data[2]) << 8 | u32(data[3])
}

validate_png :: proc "contextless"(data: []u8) -> (int, cstring) {
	signature := [8]u8{137, 80, 78, 71, 13, 10, 26, 10}
	if len(data) < 33 {
		return 0, "HaldCLUT: expected a PNG image."
	}
	for value, index in signature {
		if data[index] != value {
			return 0, "HaldCLUT: expected a PNG image."
		}
	}
	if read_u32_be(data[8:12]) != 13 || read_u32_be(data[12:16]) != 0x49484452 {
		return 0, "HaldCLUT: PNG must start with a valid IHDR chunk."
	}
	if hash.crc32(data[12:29]) != read_u32_be(data[29:33]) {
		return 0, "HaldCLUT: corrupt PNG chunk (CRC mismatch)."
	}
	width := read_u32_be(data[16:20])
	height := read_u32_be(data[20:24])
	level: int
	for candidate in 2..=MAX_LEVEL {
		if width == u32(candidate * candidate * candidate) {
			level = candidate
			break
		}
	}
	if width != height || level == 0 {
		return 0, "HaldCLUT: expected a square Hald PNG with side level^3, for level 2-8."
	}
	depth := data[24]
	color_type := data[25]
	if (depth != 8 && depth != 16) || (color_type != 2 && color_type != 6) ||
	   data[26] != 0 || data[27] != 0 || data[28] != 0 {
		return 0, "HaldCLUT: PNG must be non-interlaced RGB or RGBA with 8 or 16 bits per channel."
	}
	channels := 3 if color_type == 2 else 4
	expected_bytes := int(height) * (1 + int(width) * channels * int(depth / 8))

	// Bound inflation before the allocating PNG decoder sees the same immutable bytes.
	compressed := cast([^]u8)libc.malloc(c.size_t(len(data)))
	if compressed == nil {
		return 0, "HaldCLUT: could not allocate PNG validation data."
	}
	defer libc.free(compressed)
	compressed_size := 0
	position := 33
	ended := false
	for position < len(data) {
		if len(data) - position < 12 {
			return 0, "HaldCLUT: truncated PNG chunk."
		}
		length_u32 := read_u32_be(data[position:position+4])
		if u64(length_u32) > u64(len(data) - position - 12) {
			return 0, "HaldCLUT: invalid PNG chunk length."
		}
		length := int(length_u32)
		if hash.crc32(data[position+4:position+8+length]) != read_u32_be(data[position+8+length:position+12+length]) {
			return 0, "HaldCLUT: corrupt PNG chunk (CRC mismatch)."
		}
		tag := read_u32_be(data[position+4:position+8])
		switch tag {
		case 0x49444154: // IDAT
			libc.memcpy(&compressed[compressed_size], &data[position+8], c.size_t(length))
			compressed_size += length
		case 0x49454e44: // IEND
			if length != 0 || position + 12 != len(data) {
				return 0, "HaldCLUT: invalid PNG end chunk."
			}
			ended = true
		case 0x504c5445: // PLTE is optional for truecolor PNGs.
			if length > 768 || length % 3 != 0 {
				return 0, "HaldCLUT: invalid PNG palette chunk."
			}
		case:
			if data[position+4] & 32 == 0 {
				return 0, "HaldCLUT: unsupported critical PNG chunk."
			}
		}
		position += length + 12
	}
	if !ended || compressed_size == 0 {
		return 0, "HaldCLUT: PNG is missing image data or its end chunk."
	}
	expanded := cast([^]u8)libc.malloc(c.size_t(expected_bytes))
	if expanded == nil {
		return 0, "HaldCLUT: could not allocate PNG validation data."
	}
	defer libc.free(expanded)
	decoded_bytes := stbi.zlib_decode_buffer(expanded, c.int(expected_bytes), compressed, c.int(compressed_size))
	if decoded_bytes != c.int(expected_bytes) {
		return 0, "HaldCLUT: invalid or oversized PNG image stream."
	}
	return level * level, nil
}
