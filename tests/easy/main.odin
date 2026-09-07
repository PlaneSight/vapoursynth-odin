// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:fmt"
import "core:os"

import vs "../.."
import easy "../../easy"

main :: proc() {
	if !run() {
		os.exit(1)
	}
}

run :: proc() -> bool {
	if len(os.args) > 2 {
		fmt.eprintln("Usage: easy-tests [path-to-vapoursynth-library]")
		return false
	}
	path := easy.DEFAULT_LIBRARY
	if len(os.args) == 2 {
		path = os.args[1]
	}
	diagnostic: easy.Diagnostic
	library, err := easy.load_library(path, &diagnostic)
	if err != .None {
		fmt.eprintf("Could not load VapourSynth: %v: %s\n", err, easy.diagnostic_text(&diagnostic))
		return false
	}
	defer expect(easy.unload_library(&library), .None)
	core, core_err := easy.create_core(library.api, vs.ccfDisableAutoLoading)
	if core_err != .None {
		fmt.eprintln("Could not create a VapourSynth core:", core_err)
		return false
	}
	defer easy.destroy_core(&core)

	test_map_values(&core)
	test_empty_arrays(&core)
	test_map_error_state(&core)
	test_invocation_diagnostics(&core)
	test_node_ownership(&core)
	test_different_core(&core)
	test_frame_views(&core)
	test_wrong_media(&core)
	test_typed_rows()
	test_mock_failures()
	fmt.println("Easy API tests passed: map values, ownership, diagnostics, frame views, and allocation failures.")
	return true
}

expect :: proc(actual, expected: easy.Error) {
	assert(actual == expected, fmt.tprintf("expected %v, got %v", expected, actual))
}

new_map :: proc(core: ^easy.Core) -> easy.Map {
	result, err := easy.create_map(core)
	expect(err, .None)
	return result
}

blank_clip :: proc(core: ^easy.Core) -> easy.Node {
	args := new_map(core)
	defer easy.destroy_map(&args)
	expect(easy.map_set_int(&args, "width", 65), .None)
	expect(easy.map_set_int(&args, "height", 7), .None)
	expect(easy.map_set_int(&args, "length", 1), .None)
	expect(easy.map_set_int(&args, "format", vs.pfGray8), .None)
	expect(easy.map_set_float(&args, "color", 17), .None)
	result, err := easy.invoke(core, "std", "BlankClip", &args)
	expect(err, .None)
	defer easy.destroy_map(&result)
	node, node_err := easy.map_get_node(&result, "clip")
	expect(node_err, .None)
	return node
}

test_map_values :: proc(core: ^easy.Core) {
	values := new_map(core)
	defer easy.destroy_map(&values)
	expect(easy.map_set_int(&values, "integer", min(i64)+1), .None)
	expect(easy.map_set_int(&values, "integer", max(i64), .Append), .None)
	integer, err := easy.map_get_int(&values, "integer")
	expect(err, .None)
	assert(integer == min(i64)+1)
	integer, err = easy.map_get_int(&values, "integer", 1)
	expect(err, .None)
	assert(integer == max(i64))
	expect(easy.map_set_float(&values, "float", 1.25), .None)
	float, float_err := easy.map_get_float(&values, "float")
	expect(float_err, .None)
	assert(float == 1.25)

	_, err = easy.map_get_int(&values, "missing")
	expect(err, .Missing_Key)
	_, err = easy.map_get_int(&values, "float")
	expect(err, .Wrong_Type)
	_, err = easy.map_get_int(&values, "integer", 2)
	expect(err, .Index_Out_Of_Range)
	_, err = easy.map_get_int(&values, "integer", -1)
	expect(err, .Index_Out_Of_Range)
	expect(easy.map_set_float(&values, "integer", 2.5, .Append), .Wrong_Type)

	bytes := [?]u8{0, 1, 255, 0}
	expect(easy.map_set_bytes(&values, "bytes", bytes[:]), .None)
	read_bytes, bytes_err := easy.map_get_bytes(&values, "bytes")
	expect(bytes_err, .None)
	assert(len(read_bytes) == len(bytes))
	for value, i in read_bytes {
		assert(value == bytes[i])
	}
	_, err = easy.map_get_string(&values, "bytes")
	expect(err, .Wrong_Type)
	text :: "Odin\x00VapourSynth"
	expect(easy.map_set_string(&values, "text", text), .None)
	read_text, text_err := easy.map_get_string(&values, "text")
	expect(text_err, .None)
	assert(read_text == text)
	expect(easy.map_set_bytes(&values, "empty_bytes", nil), .None)
	read_bytes, err = easy.map_get_bytes(&values, "empty_bytes")
	expect(err, .None)
	assert(len(read_bytes) == 0)
	expect(easy.map_set_string(&values, "empty_text", ""), .None)
	read_text, err = easy.map_get_string(&values, "empty_text")
	expect(err, .None)
	assert(len(read_text) == 0)
}

test_empty_arrays :: proc(core: ^easy.Core) {
	values := new_map(core)
	defer easy.destroy_map(&values)
	integers := [?]i64{-2, 0, max(i64)}
	floats := [?]f64{-1.25, 0, 1.25}
	expect(easy.map_set_int_array(&values, "integers", integers[:]), .None)
	expect(easy.map_set_float_array(&values, "floats", floats[:]), .None)
	read_integers, err := easy.map_get_int_array(&values, "integers")
	expect(err, .None)
	assert(len(read_integers) == len(integers))
	for value, i in read_integers {
		assert(value == integers[i])
	}
	read_floats, float_err := easy.map_get_float_array(&values, "floats")
	expect(float_err, .None)
	assert(len(read_floats) == len(floats))
	for value, i in read_floats {
		assert(value == floats[i])
	}

	expect(easy.map_set_int_array(&values, "integers", nil), .None)
	expect(easy.map_set_float_array(&values, "floats", nil), .None)
	assert(core.api.mapGetType(values.handle, "integers") == vs.ptInt)
	assert(core.api.mapGetType(values.handle, "floats") == vs.ptFloat)
	read_integers, err = easy.map_get_int_array(&values, "integers")
	expect(err, .None)
	assert(len(read_integers) == 0)
	read_floats, err = easy.map_get_float_array(&values, "floats")
	expect(err, .None)
	assert(len(read_floats) == 0)
	_, err = easy.map_get_int(&values, "integers")
	expect(err, .Index_Out_Of_Range)
	_, err = easy.map_get_float(&values, "floats")
	expect(err, .Index_Out_Of_Range)
	_, err = easy.map_get_float_array(&values, "integers")
	expect(err, .Wrong_Type)
}

test_map_error_state :: proc(core: ^easy.Core) {
	values := new_map(core)
	defer easy.destroy_map(&values)
	core.api.mapSetError(values.handle, "error set through the raw API")
	_, err := easy.map_get_int(&values, "anything")
	expect(err, .Map_Error)
	_, err = easy.map_get_bytes(&values, "anything")
	expect(err, .Map_Error)
	_, err = easy.map_get_int_array(&values, "anything")
	expect(err, .Map_Error)
	expect(easy.map_set_int(&values, "anything", 1), .Map_Error)
	diagnostic: easy.Diagnostic
	result, invoke_err := easy.invoke(core, "std", "BlankClip", &values, &diagnostic)
	expect(invoke_err, .Map_Error)
	assert(result.handle == nil)
	assert(easy.diagnostic_text(&diagnostic) == "error set through the raw API")
}

test_invocation_diagnostics :: proc(core: ^easy.Core) {
	args := new_map(core)
	defer easy.destroy_map(&args)
	diagnostic: easy.Diagnostic
	result, err := easy.invoke(core, "std", "ThereIsNoSuchFunction", &args, &diagnostic)
	expect(err, .Invocation_Failed)
	assert(result.handle == nil)
	assert(diagnostic.length > 0 && !diagnostic.truncated)
	saved := diagnostic

	// Reuse the same arguments and allocate another result after the failure map was freed.
	expect(easy.map_set_int(&args, "length", 1), .None)
	result, err = easy.invoke(core, "std", "BlankClip", &args)
	expect(err, .None)
	easy.destroy_map(&result)
	assert(easy.diagnostic_text(&diagnostic) == easy.diagnostic_text(&saved))
	length, length_err := easy.map_get_int(&args, "length")
	expect(length_err, .None)
	assert(length == 1)
	result, err = easy.invoke(core, "std", "BlankClip", &args, &diagnostic)
	expect(err, .None)
	defer easy.destroy_map(&result)
	assert(diagnostic.length == 0 && !diagnostic.truncated)
}

test_node_ownership :: proc(core: ^easy.Core) {
	node := blank_clip(core)
	defer easy.destroy_node(&node)
	retained, err := easy.retain_node(&node)
	expect(err, .None)
	defer easy.destroy_node(&retained)
	easy.destroy_node(&node)
	info, info_err := easy.video_info(&retained)
	expect(info_err, .None)
	assert(info.width == 65)
	values := new_map(core)
	defer easy.destroy_map(&values)
	expect(easy.map_set_node(&values, "clip", &retained), .None)
	easy.destroy_node(&retained)
	node, err = easy.map_get_node(&values, "clip")
	expect(err, .None)
	expect(easy.map_take_node(&values, "other_clip", &node), .None)
	assert(node.handle == nil && node.api == nil && node.core == nil)

	node, err = easy.map_get_node(&values, "clip")
	expect(err, .None)
	expect(easy.map_set_int(&values, "integer", 1), .None)
	// VapourSynth consumes a reference even when append rejects the property's type.
	expect(easy.map_take_node(&values, "integer", &node, .Append), .Wrong_Type)
	assert(node.handle == nil && node.api == nil && node.core == nil)
	retained, err = easy.map_get_node(&values, "other_clip")
	expect(err, .None)
	easy.destroy_map(&values)
	info, err = easy.video_info(&retained)
	expect(err, .None)
	assert(info.height == 7)
}

test_different_core :: proc(core: ^easy.Core) {
	other, err := easy.create_core(core.api, vs.ccfDisableAutoLoading)
	expect(err, .None)
	defer easy.destroy_core(&other)
	node := blank_clip(core)
	defer easy.destroy_node(&node)
	args := new_map(&other)
	defer easy.destroy_map(&args)
	node_handle := node.handle
	map_handle := args.handle
	expect(easy.map_set_node(&args, "clip", &node), .Different_Core)
	expect(easy.map_take_node(&args, "clip", &node), .Different_Core)
	assert(node.handle == node_handle)
	result, invoke_err := easy.invoke(core, "std", "BlankClip", &args)
	expect(invoke_err, .Different_Core)
	assert(result.handle == nil && args.handle == map_handle)
	info, info_err := easy.video_info(&node)
	expect(info_err, .None)
	assert(info.width == 65)
}

test_frame_views :: proc(core: ^easy.Core) {
	node := blank_clip(core)
	defer easy.destroy_node(&node)
	for index in ([?]int{-1, 1, max(int)}) {
		frame, err := easy.get_frame(&node, index)
		expect(err, .Index_Out_Of_Range)
		assert(frame.handle == nil)
	}
	frame, err := easy.get_frame(&node, 0)
	expect(err, .None)
	defer easy.destroy_frame(&frame)
	retained, retain_err := easy.retain_frame(&frame)
	expect(retain_err, .None)
	defer easy.destroy_frame(&retained)
	easy.destroy_frame(&frame)
	plane, plane_err := easy.read_plane(&retained, 0)
	expect(plane_err, .None)
	assert(plane.width == 65 && plane.height == 7)
	assert(plane.stride > plane.width)
	assert(plane.bytes_per_sample == 1 && plane.bits_per_sample == 8)
	for y in 0..<plane.height {
		row, row_err := easy.plane_row_as(&plane, y, u8)
		expect(row_err, .None)
		assert(len(row) == 65)
		assert(uintptr(raw_data(row)) == uintptr(plane.data) + uintptr(y*plane.stride))
		for pixel in row {
			assert(pixel == 17)
		}
	}
	_, err = easy.plane_row_as(&plane, 0, u16)
	expect(err, .Unsupported_Format)
	_, err = easy.plane_row(&plane, -1)
	expect(err, .Index_Out_Of_Range)
	_, err = easy.plane_row(&plane, plane.height)
	expect(err, .Index_Out_Of_Range)
	_, err = easy.read_plane(&retained, 1)
	expect(err, .Index_Out_Of_Range)
}

test_wrong_media :: proc(core: ^easy.Core) {
	format: vs.VSAudioFormat
	assert(core.api.queryAudioFormat(&format, vs.stInteger, 16, 1, core.handle) != 0)
	handle := core.api.newAudioFrame(&format, 16, nil, core.handle)
	assert(handle != nil)
	frame := easy.Frame{api = core.api, handle = handle, core = core.handle}
	defer easy.destroy_frame(&frame)
	_, err := easy.read_plane(&frame, 0)
	expect(err, .Wrong_Media_Type)
}
