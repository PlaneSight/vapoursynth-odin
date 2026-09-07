// SPDX-License-Identifier: LGPL-2.1-or-later
package dither_plus

import "base:intrinsics"

@(private="file", rodata)
blue_noise := BLUE_NOISE

// Recursive Bayer matrix: B(2n) = [[4B(n), 4B(n)+2], [4B(n)+3, 4B(n)+1]].
@(private="file", rodata)
bayer_8 := [8][8]u16{
	{ 0, 32,  8, 40,  2, 34, 10, 42},
	{48, 16, 56, 24, 50, 18, 58, 26},
	{12, 44,  4, 36, 14, 46,  6, 38},
	{60, 28, 52, 20, 62, 30, 54, 22},
	{ 3, 35, 11, 43,  1, 33,  9, 41},
	{51, 19, 59, 27, 49, 17, 57, 25},
	{15, 47,  7, 39, 13, 45,  5, 37},
	{63, 31, 55, 23, 61, 29, 53, 21},
}

// Threshold rows are duplicated so SIMD loads can cross the tile boundary.
build_thresholds :: proc "contextless"(
	thresholds: ^[TILE_SIZE][2*TILE_SIZE]u16,
	parameters: ^Kernel_Parameters,
	mode: Mode,
	scale: Scale,
) {
	if mode != .Blue_Noise && mode != .Bayer && mode != .Nearest {
		intrinsics.trap()
	}
	threshold_range := u32(1) << parameters.shift
	if scale == .Full_Range {
		threshold_range = parameters.input_max
	}
	for y in 0..<TILE_SIZE {
		for x in 0..<TILE_SIZE {
			threshold := u16(threshold_range / 2)
			switch mode {
			case .Blue_Noise:
				rank := u32(blue_noise[y*TILE_SIZE+x])
				threshold = u16(((2*rank+1)*threshold_range)/(2*TILE_AREA))
			case .Bayer:
				rank := u32(bayer_8[y&7][x&7])
				threshold = u16(((2*rank+1)*threshold_range)/128)
			case .Nearest:
			case .Floyd_Steinberg, .Sierra_Lite:
			}
			thresholds[y][x] = threshold
			thresholds[y][x+TILE_SIZE] = threshold
		}
	}
}
