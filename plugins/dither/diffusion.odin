// SPDX-License-Identifier: LGPL-2.1-or-later
package dither_plus

import "base:intrinsics"
import "core:math"

diffusion_plane :: proc "contextless"(
	input, output: rawptr,
	width, height, input_stride, output_stride: int,
	parameters: ^Kernel_Parameters,
	scale: Scale,
	mode: Mode,
	errors: [^]f64,
) {
	if mode != .Floyd_Steinberg && mode != .Sierra_Lite {
		intrinsics.trap()
	}
	if width <= 0 || height <= 0 {
		return
	}
	if mode == .Sierra_Lite {
		diffusion_scale_dispatch(input, output, width, height, input_stride, output_stride, parameters, scale, errors, true)
		return
	}
	diffusion_scale_dispatch(input, output, width, height, input_stride, output_stride, parameters, scale, errors, false)
}

diffusion_scale_dispatch :: proc "contextless"(
	input, output: rawptr,
	width, height, input_stride, output_stride: int,
	parameters: ^Kernel_Parameters,
	scale: Scale,
	errors: [^]f64,
	$SIERRA_LITE: bool,
) {
	if scale == .Full_Range {
		diffusion_typed_dispatch(input, output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, true)
		return
	}
	diffusion_typed_dispatch(input, output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, false)
}

diffusion_typed_dispatch :: proc "contextless"(
	input, output: rawptr,
	width, height, input_stride, output_stride: int,
	parameters: ^Kernel_Parameters,
	errors: [^]f64,
	$SIERRA_LITE: bool,
	$FULL_RANGE: bool,
) {
	if parameters.input_bits == 8 {
		if parameters.output_max < 255 {
			diffusion_typed(cast([^]u8)input, cast([^]u8)output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, FULL_RANGE, true)
			return
		}
		diffusion_typed(cast([^]u8)input, cast([^]u8)output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, FULL_RANGE, false)
		return
	}
	if parameters.output_max < 255 {
		diffusion_typed(cast([^]u16)input, cast([^]u8)output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, FULL_RANGE, true)
		return
	}
	if parameters.output_max == 255 {
		diffusion_typed(cast([^]u16)input, cast([^]u8)output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, FULL_RANGE, false)
		return
	}
	diffusion_typed(cast([^]u16)input, cast([^]u16)output, width, height, input_stride, output_stride, parameters, errors, SIERRA_LITE, FULL_RANGE, false)
}

// Scratch owns two padded rows. Residuals use clamped quantizer coordinates,
// so clipping never sends an out-of-range source value into neighboring pixels.
diffusion_typed :: proc "contextless"(
	input: [^]$I,
	output: [^]$O,
	width, height, input_stride, output_stride: int,
	parameters: ^Kernel_Parameters,
	errors: [^]f64,
	$SIERRA_LITE: bool,
	$FULL_RANGE: bool,
	$EXPAND: bool,
) where (I == u8 || I == u16) && (O == u8 || O == u16) {
	row_length := width + 2
	for i in 0..<2*row_length {
		errors[i] = 0
	}
	current := errors
	next := cast([^]f64)&errors[row_length]
	input_bytes := cast([^]u8)input
	output_bytes := cast([^]u8)output
	maximum := f64(parameters.output_max)
	when FULL_RANGE {
		denominator := f64(parameters.input_max)
	} else {
		denominator := f64(u32(1) << parameters.shift)
	}
	for y in 0..<height {
		input_row := cast([^]I)&input_bytes[y*input_stride]
		output_row := cast([^]O)&output_bytes[y*output_stride]
		x, end, direction := 0, width, 1
		if y & 1 != 0 {
			x, end, direction = width-1, -1, -1
		}
		for ; x != end; x += direction {
			index := x + 1
			source := f64(min(u32(input_row[x]), parameters.input_max))
			when FULL_RANGE {
				coordinate := source * maximum / denominator
			} else {
				coordinate := source / denominator
			}
			value := clamp(coordinate + current[index], 0, maximum)
			quantized := math.floor(value + 0.5)
			residual := value - quantized
			when SIERRA_LITE {
				current[index+direction] += residual * 0.5
				next[index-direction] += residual * 0.25
				next[index] += residual * 0.25
			} else {
				current[index+direction] += residual * (7.0 / 16.0)
				next[index-direction] += residual * (3.0 / 16.0)
				next[index] += residual * (5.0 / 16.0)
				next[index+direction] += residual * (1.0 / 16.0)
			}
			result := u32(quantized)
			when EXPAND {
				result = (result * 255 + parameters.output_max / 2) / parameters.output_max
			}
			output_row[x] = O(result)
		}
		for i in 0..<row_length {
			current[i] = 0
		}
		current, next = next, current
	}
}
