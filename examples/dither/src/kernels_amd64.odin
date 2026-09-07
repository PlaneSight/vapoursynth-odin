// SPDX-License-Identifier: LGPL-2.1-or-later
#+build amd64
package dither

import sysinfo "core:sys/info"

// Force the portable path for verification on machines that support AVX2.
ENABLE_AVX2 :: #config(DITHER_ENABLE_AVX2, true)

select_avx2_kernel :: proc "contextless"(output_bits: int, scale: Scale) -> Row_Kernel {
	// Odin checks CPUID and OS support for saving both XMM and YMM state.
	if !ENABLE_AVX2 || .avx2 not_in sysinfo.cpu_features() {
		return nil
	}
	if output_bits < 8 {
		return full_avx2_low if scale == .Full_Range else shift_avx2_low
	}
	if output_bits == 8 {
		return full_avx2_u8 if scale == .Full_Range else shift_avx2_u8
	}
	return full_avx2_u16 if scale == .Full_Range else shift_avx2_u16
}

@(enable_target_feature="avx2")
shift_avx2_u8 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, true, false, false)
}

@(enable_target_feature="avx2")
shift_avx2_u16 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u16)output, width, thresholds, phase_x, parameters, true, false, false)
}

@(enable_target_feature="avx2")
full_avx2_u8 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, true, true, false)
}

@(enable_target_feature="avx2")
full_avx2_u16 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u16)output, width, thresholds, phase_x, parameters, true, true, false)
}

@(enable_target_feature="avx2")
shift_avx2_low :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_low_row(input, output, width, thresholds, phase_x, parameters, true, false)
}

@(enable_target_feature="avx2")
full_avx2_low :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_low_row(input, output, width, thresholds, phase_x, parameters, true, true)
}
