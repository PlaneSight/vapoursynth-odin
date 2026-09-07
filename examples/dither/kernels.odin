// SPDX-License-Identifier: LGPL-2.1-or-later
package dither

import "base:intrinsics"
import "core:simd"

Scale :: enum {
	Power_Of_Two,
	Full_Range,
}

Kernel_Parameters :: struct {
	input_bits: u32,
	shift: u32,
	input_max: u32,
	output_max: u32,
}

Row_Kernel :: proc "contextless"(
	input: [^]u16,
	output: rawptr,
	width: int,
	thresholds: [^]u16,
	phase_x: int,
	parameters: ^Kernel_Parameters,
)

select_kernel :: proc "contextless"(output_bits: int, scale: Scale, vectorized: bool) -> Row_Kernel {
	if vectorized && simd.HAS_HARDWARE_SIMD {
		if output_bits == 8 {
			return full_simd_u8 if scale == .Full_Range else shift_simd_u8
		}
		return full_simd_u16 if scale == .Full_Range else shift_simd_u16
	}
	if output_bits == 8 {
		return full_scalar_u8 if scale == .Full_Range else shift_scalar_u8
	}
	return full_scalar_u16 if scale == .Full_Range else shift_scalar_u16
}

// The duplicated threshold row permits an unaligned eight-lane load across its wrap.
process_row :: proc "contextless"(
	input: [^]u16,
	output: [^]$T,
	width: int,
	thresholds: [^]u16,
	phase_x: int,
	parameters: ^Kernel_Parameters,
	$VECTORIZED: bool,
	$FULL_RANGE: bool,
) where T == u8 || T == u16 {
	x := 0
	when VECTORIZED && simd.HAS_HARDWARE_SIMD {
		input_max := simd.u32x8(parameters.input_max)
		output_max := simd.u32x8(parameters.output_max)
		when FULL_RANGE {
			input_bits := simd.u32x8(parameters.input_bits)
		} else {
			shift := simd.u32x8(parameters.shift)
		}
		for ; x <= width-8; x += 8 {
			samples := intrinsics.unaligned_load(cast(^simd.u16x8)&input[x])
			noise := intrinsics.unaligned_load(cast(^simd.u16x8)&thresholds[(phase_x+x)&63])
			values := simd.min(cast(simd.u32x8)samples, input_max)
			result: simd.u32x8
			when FULL_RANGE {
				numerator := values * output_max + cast(simd.u32x8)noise
				// Exact division by 2^input_bits-1 for this bounded reduction numerator.
				result = simd.shr(numerator + 1 + simd.shr(numerator, input_bits), input_bits)
			} else {
				result = simd.min(simd.shr(values + cast(simd.u32x8)noise, shift), output_max)
			}
			intrinsics.unaligned_store(cast(^#simd[8]T)&output[x], cast(#simd[8]T)result)
		}
	}
	for ; x < width; x += 1 {
		value := min(u32(input[x]), parameters.input_max)
		noise := u32(thresholds[(phase_x+x)&63])
		when FULL_RANGE {
			numerator := value * parameters.output_max + noise
			output[x] = T((numerator + 1 + (numerator >> parameters.input_bits)) >> parameters.input_bits)
		} else {
			output[x] = T(min((value + noise) >> parameters.shift, parameters.output_max))
		}
	}
}

shift_scalar_u8 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u8)output, width, thresholds, phase_x, parameters, false, false)
}

shift_scalar_u16 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u16)output, width, thresholds, phase_x, parameters, false, false)
}

full_scalar_u8 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u8)output, width, thresholds, phase_x, parameters, false, true)
}

full_scalar_u16 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u16)output, width, thresholds, phase_x, parameters, false, true)
}

shift_simd_u8 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u8)output, width, thresholds, phase_x, parameters, true, false)
}

shift_simd_u16 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u16)output, width, thresholds, phase_x, parameters, true, false)
}

full_simd_u8 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u8)output, width, thresholds, phase_x, parameters, true, true)
}

full_simd_u16 :: proc "contextless"(input: [^]u16, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(input, cast([^]u16)output, width, thresholds, phase_x, parameters, true, true)
}
