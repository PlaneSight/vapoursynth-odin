#+build !windows
// SPDX-License-Identifier: LGPL-2.1-or-later
package haldlut

import "core:c"
import "core:c/libc"

// The caller owns the returned C allocation; the file never escapes this scope.
read_file :: proc "contextless"(path: cstring) -> ([]u8, cstring) {
	file := libc.fopen(path, "rb")
	if file == nil {
		return nil, "HaldCLUT: could not open the PNG file."
	}
	defer libc.fclose(file)
	if libc.fseek(file, 0, .END) != 0 {
		return nil, "HaldCLUT: could not determine PNG file size."
	}
	length := libc.ftell(file)
	if length <= 0 || length > MAX_FILE_BYTES {
		return nil, "HaldCLUT: PNG file must contain 1-16777216 bytes (16 MiB maximum)."
	}
	if libc.fseek(file, 0, .SET) != 0 {
		return nil, "HaldCLUT: could not seek in the PNG file."
	}
	data := cast([^]u8)libc.malloc(c.size_t(length))
	if data == nil {
		return nil, "HaldCLUT: could not allocate PNG file data."
	}
	if libc.fread(data, 1, c.size_t(length), file) != c.size_t(length) {
		libc.free(data)
		return nil, "HaldCLUT: could not read the complete PNG file."
	}
	return data[:int(length)], nil
}
