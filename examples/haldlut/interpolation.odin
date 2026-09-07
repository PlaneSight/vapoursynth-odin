// SPDX-License-Identifier: LGPL-2.1-or-later
package haldlut

// Decoded RGB16 triples are immutable and owned by stb_image until image_free.
Hald_Table :: struct {
	pixels: [^][3]u16,
	edge:   int,
}

interpolate :: proc "contextless"(table: ^Hald_Table, coordinates: [3]f64) -> [3]f64 {
	base: [3]int
	fraction: [3]f64
	for channel in 0..<3 {
		position := clamp(coordinates[channel], 0, f64(table.edge - 1))
		base[channel] = min(int(position), table.edge - 2)
		fraction[channel] = position - f64(base[channel])
	}

	// Three comparisons select one of six tetrahedra, with stable RGB tie order.
	order := [3]int{0, 1, 2}
	if fraction[order[0]] < fraction[order[1]] { order[0], order[1] = order[1], order[0] }
	if fraction[order[1]] < fraction[order[2]] { order[1], order[2] = order[2], order[1] }
	if fraction[order[0]] < fraction[order[1]] { order[0], order[1] = order[1], order[0] }

	steps := [3]int{1, table.edge, table.edge * table.edge}
	index := base[0] + table.edge * (base[1] + table.edge * base[2])
	first := fraction[order[0]]
	second := fraction[order[1]]
	third := fraction[order[2]]
	weights := [4]f64{1 - first, first - second, second - third, third}
	indices := [4]int{
		index,
		index + steps[order[0]],
		index + steps[order[0]] + steps[order[1]],
		index + steps[0] + steps[1] + steps[2],
	}
	result: [3]f64
	for vertex in 0..<4 {
		color := table.pixels[indices[vertex]]
		for channel in 0..<3 {
			result[channel] += weights[vertex] * f64(color[channel])
		}
	}
	return result
}
