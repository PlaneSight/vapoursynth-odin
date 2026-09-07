// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:fmt"
import "core:os"

import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"

WIDTH  :: 65
HEIGHT :: 48
COLOR  :: 17

main :: proc() {
	if !run() {
		os.exit(1)
	}
}

run :: proc() -> bool {
	if len(os.args) > 2 {
		fmt.eprintln("Usage: easy_host [path-to-vapoursynth-library]")
		return false
	}
	library_path := easy.DEFAULT_LIBRARY
	if len(os.args) == 2 {
		library_path = os.args[1]
	}

	diagnostic: easy.Diagnostic
	library, load_error := easy.load_library(library_path, &diagnostic)
	if load_error != .None {
		fmt.eprintln("Load core library:", load_error, easy.diagnostic_text(&diagnostic))
		return false
	}
	defer {
		unload_error := easy.unload_library(&library)
		ensure(unload_error == .None)
	}

	core, create_error := easy.create_core(library.api, vs.ccfDisableAutoLoading)
	if create_error != .None {
		fmt.eprintln("Create core:", create_error)
		return false
	}
	defer easy.destroy_core(&core)

	node, made_clip := make_blank_clip(&core, &diagnostic)
	if !made_clip {
		return false
	}
	defer easy.destroy_node(&node)

	// Retain an independent reference before releasing the original owner.
	retained, retain_error := easy.retain_node(&node)
	if retain_error != .None {
		fmt.eprintln("Retain node:", retain_error)
		return false
	}
	defer easy.destroy_node(&retained)
	easy.destroy_node(&node)

	info, info_error := easy.video_info(&retained)
	if info_error != .None {
		fmt.eprintln("Read video information:", info_error)
		return false
	}
	fmt.printf("Clip: %d x %d; %d frame(s); %d/%d fps\n",
		info.width, info.height, info.numFrames, info.fpsNum, info.fpsDen)

	frame, frame_error := easy.get_frame(&retained, 0, &diagnostic)
	if frame_error != .None {
		fmt.eprintln("Request frame 0:", frame_error, easy.diagnostic_text(&diagnostic))
		return false
	}
	defer easy.destroy_frame(&frame)

	plane, plane_error := easy.read_plane(&frame, 0)
	if plane_error != .None {
		fmt.eprintln("Read plane 0:", plane_error)
		return false
	}
	if plane.width != WIDTH || plane.height != HEIGHT || plane.bytes_per_sample != 1 {
		fmt.eprintln("Expected a 65 x 48 Gray8 plane.")
		return false
	}

	checksum: u64
	for y in 0..<plane.height {
		row, row_error := easy.plane_row(&plane, y)
		if row_error != .None {
			fmt.eprintln("Read row:", y, row_error)
			return false
		}
		for sample in row {
			checksum += u64(sample)
		}
	}
	expected := u64(WIDTH * HEIGHT * COLOR)
	if checksum != expected {
		fmt.eprintf("Expected checksum %d, received %d.\n", expected, checksum)
		return false
	}
	fmt.printf("Frame 0: %d x %d Gray8; stride: %d bytes; checksum: %d\n",
		plane.width, plane.height, plane.stride, checksum)
	return true
}

make_blank_clip :: proc(core: ^easy.Core, diagnostic: ^easy.Diagnostic) -> (easy.Node, bool) {
	args, map_error := easy.create_map(core)
	if map_error != .None {
		fmt.eprintln("Create BlankClip arguments:", map_error)
		return {}, false
	}
	defer easy.destroy_map(&args)

	settings := [?]struct {key: cstring, value: i64}{
		{"width", WIDTH},
		{"height", HEIGHT},
		{"length", 1},
		{"format", vs.pfGray8},
	}
	for setting in settings {
		if err := easy.map_set_int(&args, setting.key, setting.value); err != .None {
			fmt.eprintln("Set BlankClip argument:", setting.key, err)
			return {}, false
		}
	}
	if err := easy.map_set_float(&args, "color", COLOR); err != .None {
		fmt.eprintln("Set BlankClip color:", err)
		return {}, false
	}

	result, invoke_error := easy.invoke(core, "std", "BlankClip", &args, diagnostic)
	if invoke_error != .None {
		fmt.eprintln("Invoke std.BlankClip:", invoke_error, easy.diagnostic_text(diagnostic))
		return {}, false
	}
	defer easy.destroy_map(&result)

	// map_get_node acquires a reference that survives destruction of result.
	node, node_error := easy.map_get_node(&result, "clip")
	if node_error != .None {
		fmt.eprintln("Read BlankClip result:", node_error)
		return {}, false
	}
	return node, true
}
