// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:c"
import "core:dynlib"
import "core:fmt"
import "core:os"

import vs "../../src/vapoursynth"

main :: proc() {
	if !run() {
		os.exit(1)
	}
}

run :: proc() -> bool {
	when ODIN_OS == .Windows {
		library_path := "libvapoursynth.dll"
	} else when ODIN_OS == .Darwin {
		library_path := "libvapoursynth.dylib"
	} else {
		library_path := "libvapoursynth.so"
	}
	if len(os.args) > 2 {
		fmt.eprintln("Usage: host [path-to-vapoursynth-library]")
		return false
	}
	if len(os.args) == 2 {
		library_path = os.args[1]
	}

	library, loaded := dynlib.load_library(library_path)
	if !loaded {
		fmt.eprintf("Could not load %q: %s\n", library_path, dynlib.last_error())
		return false
	}
	defer dynlib.unload_library(library)

	symbol, found := dynlib.symbol_address(library, "getVapourSynthAPI")
	if !found {
		fmt.eprintln("Library does not export getVapourSynthAPI:", dynlib.last_error())
		return false
	}
	get_api := cast(vs.VSGetVapourSynthAPI)symbol
	api := get_api(vs.VAPOURSYNTH_API_VERSION)
	if api == nil {
		fmt.eprintln("The loaded VapourSynth library does not support API 4.2.")
		return false
	}

	core := api.createCore(vs.ccfDisableAutoLoading)
	if core == nil {
		fmt.eprintln("Could not create the VapourSynth core.")
		return false
	}
	defer api.freeCore(core)

	info: vs.VSCoreInfo2
	api.getCoreInfo2(core, &info)
	fmt.println(info.versionString)
	fmt.printf("Core version: %d; API: %d.%d; threads: %d\n",
		info.coreVersion, info.apiVersion >> 16, info.apiVersion & 0xffff, info.numThreads)

	std := api.getPluginByNamespace("std", core)
	if std == nil {
		fmt.eprintln("The core does not contain the std plugin.")
		return false
	}
	args := api.createMap()
	if args == nil {
		fmt.eprintln("Could not allocate the BlankClip argument map.")
		return false
	}
	defer api.freeMap(args)

	if api.mapSetInt(args, "width", 64, vs.maReplace) != 0 ||
	   api.mapSetInt(args, "height", 48, vs.maReplace) != 0 ||
	   api.mapSetInt(args, "length", 1, vs.maReplace) != 0 ||
	   api.mapSetInt(args, "format", vs.pfGray8, vs.maReplace) != 0 ||
	   api.mapSetFloat(args, "color", 17, vs.maReplace) != 0 {
		fmt.eprintln("Could not set the BlankClip arguments.")
		return false
	}
	result := api.invoke(std, "BlankClip", args)
	if result == nil {
		fmt.eprintln("BlankClip did not return a result map.")
		return false
	}
	defer api.freeMap(result)
	if message := api.mapGetError(result); message != nil {
		fmt.eprintln("BlankClip:", message)
		return false
	}

	property_error: c.int
	node := api.mapGetNode(result, "clip", 0, &property_error)
	if property_error != vs.peSuccess || node == nil {
		fmt.eprintln("BlankClip did not return a video node.")
		return false
	}
	defer api.freeNode(node)

	error_buffer: [1024]u8
	frame := api.getFrame(0, node, raw_data(error_buffer[:]), c.int(len(error_buffer)))
	if frame == nil {
		fmt.eprintln("Could not request frame 0:", cast(cstring)raw_data(error_buffer[:]))
		return false
	}
	defer api.freeFrame(frame)

	width := api.getFrameWidth(frame, 0)
	height := api.getFrameHeight(frame, 0)
	pixels := api.getReadPtr(frame, 0)
	if width != 64 || height != 48 || pixels == nil || pixels[0] != 17 {
		fmt.eprintln("BlankClip returned unexpected frame data.")
		return false
	}
	fmt.printf("Frame 0: %d x %d Gray8; stride: %d; first pixel: %d\n",
		width, height, api.getStride(frame, 0), pixels[0])
	return true
}
