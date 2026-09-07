#+build windows
// SPDX-License-Identifier: LGPL-2.1-or-later
package haldlut

import "core:c"
import "core:c/libc"
import win "core:sys/windows"

// The caller owns the returned C allocation. Native wide paths preserve UTF-8 names.
read_file :: proc "contextless"(path: cstring) -> ([]u8, cstring) {
	wide: [MAX_PATH_BYTES + 1]u16
	if win.MultiByteToWideChar(win.CP_UTF8, win.MB_ERR_INVALID_CHARS, cast([^]u8)path, -1, raw_data(wide[:]), len(wide)) == 0 {
		return nil, "HaldCLUT: path is not valid UTF-8."
	}
	file := win.CreateFileW(cast(cstring16)raw_data(wide[:]), win.GENERIC_READ, win.FILE_SHARE_READ, nil, win.OPEN_EXISTING, win.FILE_ATTRIBUTE_NORMAL, nil)
	if file == win.INVALID_HANDLE_VALUE {
		return nil, "HaldCLUT: could not open the PNG file."
	}
	defer win.CloseHandle(file)
	length: win.LARGE_INTEGER
	if !win.GetFileSizeEx(file, &length) || length <= 0 || length > MAX_FILE_BYTES {
		return nil, "HaldCLUT: PNG file must contain 1-16777216 bytes (16 MiB maximum)."
	}
	data := cast([^]u8)libc.malloc(c.size_t(length))
	if data == nil {
		return nil, "HaldCLUT: could not allocate PNG file data."
	}
	read: win.DWORD
	if !win.ReadFile(file, data, win.DWORD(length), &read, nil) || read != win.DWORD(length) {
		libc.free(data)
		return nil, "HaldCLUT: could not read the complete PNG file."
	}
	return data[:int(length)], nil
}
