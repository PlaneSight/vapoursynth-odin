// SPDX-License-Identifier: LGPL-2.1-or-later
// Point quantization and SIMD kernels originate in examples/dither/src/kernels.odin.
package dither_plus

import "base:intrinsics"
import "core:simd"

select_kernel :: proc "contextless"(output_bits: int, scale: Scale, vectorized: bool) -> Row_Kernel {
	if vectorized && simd.HAS_HARDWARE_SIMD {
		when ODIN_ARCH == .amd64 {
			if kernel := select_avx2_kernel(output_bits, scale); kernel != nil {
				return kernel
			}
		}
		if output_bits < 8 {
			return full_simd_low if scale == .Full_Range else shift_simd_low
		}
		if output_bits == 8 {
			return full_simd_u8 if scale == .Full_Range else shift_simd_u8
		}
		return full_simd_u16 if scale == .Full_Range else shift_simd_u16
	}
	if output_bits < 8 {
		return full_scalar_low if scale == .Full_Range else shift_scalar_low
	}
	if output_bits == 8 {
		return full_scalar_u8 if scale == .Full_Range else shift_scalar_u8
	}
	return full_scalar_u16 if scale == .Full_Range else shift_scalar_u16
}

// The duplicated threshold row permits an unaligned sixteen-lane load across its wrap.
process_row :: #force_inline proc "contextless"(
	input: [^]$I,
	output: [^]$T,
	width: int,
	thresholds: [^]u16,
	phase_x: int,
	parameters: ^Kernel_Parameters,
	$VECTORIZED: bool,
	$FULL_RANGE: bool,
	$EXPAND: bool,
) where (I == u8 || I == u16) && (T == u8 || T == u16) {
	x := 0
	when VECTORIZED && simd.HAS_HARDWARE_SIMD {
		when EXPAND {
			expansion_bias := simd.u32x16(parameters.output_max / 2)
			expansion_multiplier := simd.u32x16(parameters.expansion_multiplier)
		}
		when FULL_RANGE {
			input_max := simd.u16x16(u16(parameters.input_max))
			input_bits := simd.u32x16(parameters.input_bits & 31)
			when T == u8 && !EXPAND {
				output_bits := simd.u32x16(8)
			} else {
				output_bits := simd.u32x16((parameters.input_bits - parameters.shift) & 31)
			}
		} else {
			input_max := simd.u16x16(u16(parameters.input_max))
			when T == u8 && !EXPAND {
				output_max := simd.u16x16(255)
			} else {
				output_max := simd.u16x16(u16(parameters.output_max))
			}
			// Construction bounds shifts to 1..15; expose that bound to vector lowering.
			shift := simd.u16x16(u16(parameters.shift & 15))
		}
		for ; x <= width-16; x += 16 {
			samples := intrinsics.unaligned_load(cast(^#simd[16]I)&input[x])
			noise := intrinsics.unaligned_load(cast(^simd.u16x16)&thresholds[(phase_x+x)&63])
			result: simd.u32x16
			when FULL_RANGE {
				values := cast(simd.u32x16)simd.min(cast(simd.u16x16)samples, input_max)
				numerator := simd.shl(values, output_bits) - values + cast(simd.u32x16)noise
				// Exact division by 2^input_bits-1 for this bounded reduction numerator.
				result = simd.shr(numerator + 1 + simd.shr(numerator, input_bits), input_bits)
			} else {
				values := simd.min(cast(simd.u16x16)samples, input_max)
				// Saturation is equivalent to the final clamp when a 16-bit sum overflows.
				result = cast(simd.u32x16)simd.min(simd.shr(simd.saturating_add(values, noise), shift), output_max)
			}
			when EXPAND {
				result = simd.shr((result * 255 + expansion_bias) * expansion_multiplier, 24)
			}
			intrinsics.unaligned_store(cast(^#simd[16]T)&output[x], cast(#simd[16]T)result)
		}
	}
	for ; x < width; x += 1 {
		value := min(u32(input[x]), parameters.input_max)
		noise := u32(thresholds[(phase_x+x)&63])
		result: u32
		when FULL_RANGE {
			numerator := value * parameters.output_max + noise
			result = (numerator + 1 + (numerator >> parameters.input_bits)) >> parameters.input_bits
		} else {
			result = min((value + noise) >> parameters.shift, parameters.output_max)
		}
		when EXPAND {
			result = ((result * 255 + parameters.output_max / 2) * parameters.expansion_multiplier) >> 24
		}
		output[x] = T(result)
	}
}

shift_scalar_u8 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, false, false, false)
}

shift_scalar_u16 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u16)output, width, thresholds, phase_x, parameters, false, false, false)
}

full_scalar_u8 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, false, true, false)
}

full_scalar_u16 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u16)output, width, thresholds, phase_x, parameters, false, true, false)
}

shift_simd_u8 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, true, false, false)
}

shift_simd_u16 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u16)output, width, thresholds, phase_x, parameters, true, false, false)
}

full_simd_u8 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, true, true, false)
}

full_simd_u16 :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_row(cast([^]u16)input, cast([^]u16)output, width, thresholds, phase_x, parameters, true, true, false)
}

process_low_row :: #force_inline proc "contextless"(
	input, output: rawptr, width: int, thresholds: [^]u16, phase_x: int,
	parameters: ^Kernel_Parameters, $VECTORIZED: bool, $FULL_RANGE: bool,
) {
	if parameters.input_bits == 8 {
		process_row(cast([^]u8)input, cast([^]u8)output, width, thresholds, phase_x, parameters, VECTORIZED, FULL_RANGE, true)
		return
	}
	process_row(cast([^]u16)input, cast([^]u8)output, width, thresholds, phase_x, parameters, VECTORIZED, FULL_RANGE, true)
}

shift_scalar_low :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_low_row(input, output, width, thresholds, phase_x, parameters, false, false)
}

full_scalar_low :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_low_row(input, output, width, thresholds, phase_x, parameters, false, true)
}

shift_simd_low :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_low_row(input, output, width, thresholds, phase_x, parameters, true, false)
}

full_simd_low :: proc "contextless"(input: rawptr, output: rawptr, width: int, thresholds: [^]u16, phase_x: int, parameters: ^Kernel_Parameters) {
	process_low_row(input, output, width, thresholds, phase_x, parameters, true, true)
}
