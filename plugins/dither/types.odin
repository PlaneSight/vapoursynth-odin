// SPDX-License-Identifier: LGPL-2.1-or-later
package dither_plus

Mode :: enum {
	Blue_Noise,
	Bayer,
	Nearest,
	Floyd_Steinberg,
	Sierra_Lite,
}

Scale :: enum {
	Power_Of_Two,
	Full_Range,
}

Kernel_Parameters :: struct {
	input_bits: u32,
	shift: u32,
	input_max: u32,
	output_max: u32,
	expansion_multiplier: u32,
}

Row_Kernel :: proc "contextless"(
	input: rawptr,
	output: rawptr,
	width: int,
	thresholds: [^]u16,
	phase_x: int,
	parameters: ^Kernel_Parameters,
)
