// SPDX-License-Identifier: LGPL-2.1-or-later
package haldlut

import "core:c"
import "core:c/libc"
import stbi "stb:image"

import vs "../../src/vapoursynth"

Hald :: struct {
	source:     ^vs.VSNode,
	video_info: vs.VSVideoInfo,
	table:      Hald_Table,
	strength:   f64,
	sample_max: u16,
}

@(export)
VapourSynthPluginInit2 :: proc "system"(plugin: ^vs.VSPlugin, api: ^vs.VSPLUGINAPI) {
	if api.configPlugin(
		"org.vapoursynth.odin.hald", "odin_hald", "Odin Hald CLUT color grading example",
		1 << 16, vs.VAPOURSYNTH_API_VERSION, 0, plugin,
	) == 0 {
		return
	}
	api.registerFunction("HaldCLUT", "clip:vnode;path:data;strength:float:opt;", "clip:vnode;", create_hald, nil, plugin)
}

create_hald :: proc "system"(
	input, output: ^vs.VSMap,
	user_data: rawptr,
	core: ^vs.VSCore,
	api: ^vs.VSAPI,
) {
	property_error: c.int
	strength := api.mapGetFloat(input, "strength", 0, &property_error)
	if property_error == vs.peUnset {
		strength = 1
	} else if property_error != vs.peSuccess {
		api.mapSetError(output, "HaldCLUT: strength must be a floating-point value.")
		return
	}
	if strength != strength || strength < 0 || strength > 1 {
		api.mapSetError(output, "HaldCLUT: strength must be finite and between 0 and 1.")
		return
	}

	source := api.mapGetNode(input, "clip", 0, &property_error)
	if property_error != vs.peSuccess || source == nil {
		api.mapSetError(output, "HaldCLUT: expected a video clip.")
		return
	}
	info := api.getVideoInfo(source)
	if info == nil || info.width <= 0 || info.height <= 0 ||
	   info.format.colorFamily != vs.cfRGB || info.format.sampleType != vs.stInteger ||
	   info.format.bitsPerSample < 8 || info.format.bitsPerSample > 16 || info.format.numPlanes != 3 {
		api.freeNode(source)
		api.mapSetError(output, "HaldCLUT: expected constant-format, constant-dimension RGB with 8-16 bit integer samples.")
		return
	}

	table, message := load_hald(input, api)
	if message != nil {
		api.freeNode(source)
		api.mapSetError(output, message)
		return
	}
	instance := cast(^Hald)libc.malloc(size_of(Hald))
	if instance == nil {
		stbi.image_free(table.pixels)
		api.freeNode(source)
		api.mapSetError(output, "HaldCLUT: could not allocate filter data.")
		return
	}
	instance^ = Hald{
		source = source,
		video_info = info^,
		table = table,
		strength = strength,
		sample_max = u16((u32(1) << u32(info.format.bitsPerSample)) - 1),
	}
	dependency := vs.VSFilterDependency{source = source, requestPattern = vs.rpStrictSpatial}
	node := api.createVideoFilter2(
		"HaldCLUT", &instance.video_info, get_frame, free_hald, vs.fmParallel,
		cast([^]vs.VSFilterDependency)&dependency, 1, instance, core,
	)
	if node == nil {
		free_hald(instance, core, api)
		api.mapSetError(output, "HaldCLUT: could not create the filter.")
		return
	}
	// The node owns the instance; consuming its reference also releases it on failure.
	if api.mapConsumeNode(output, "clip", node, vs.maReplace) != 0 {
		api.mapSetError(output, "HaldCLUT: could not return the clip.")
	}
}

get_frame :: proc "system"(
	n, activation_reason: c.int,
	instance_data: rawptr,
	frame_data: ^rawptr,
	frame_context: ^vs.VSFrameContext,
	core: ^vs.VSCore,
	api: ^vs.VSAPI,
) -> ^vs.VSFrame {
	instance := cast(^Hald)instance_data
	switch activation_reason {
	case vs.arInitial:
		api.requestFrameFilter(n, instance.source, frame_context)
		return nil
	case vs.arAllFramesReady:
	case:
		return nil
	}
	source := api.getFrameFilter(n, instance.source, frame_context)
	if source == nil {
		api.setFilterError("HaldCLUT: the requested source frame is unavailable.", frame_context)
		return nil
	}
	if instance.strength == 0 {
		return source
	}
	defer api.freeFrame(source)
	output := api.copyFrame(source, core)
	if output == nil {
		api.setFilterError("HaldCLUT: could not copy the source frame.", frame_context)
		return nil
	}
	input_data, output_data: [3][^]u8
	input_stride, output_stride: [3]int
	for plane in 0..<3 {
		input_data[plane] = api.getReadPtr(source, c.int(plane))
		output_data[plane] = api.getWritePtr(output, c.int(plane))
		input_stride[plane] = int(api.getStride(source, c.int(plane)))
		output_stride[plane] = int(api.getStride(output, c.int(plane)))
	}
	for y in 0..<int(instance.video_info.height) {
		input_rows, output_rows: [3][^]u8
		for plane in 0..<3 {
			input_rows[plane] = cast([^]u8)&input_data[plane][y * input_stride[plane]]
			output_rows[plane] = cast([^]u8)&output_data[plane][y * output_stride[plane]]
		}
		if instance.video_info.format.bytesPerSample == 1 {
			grade_row(instance, input_rows, output_rows, u8)
		} else {
			grade_row(instance, input_rows, output_rows, u16)
		}
	}
	return output
}

grade_row :: proc "contextless"(instance: ^Hald, input_bytes, output_bytes: [3][^]u8, $T: typeid)
	where T == u8 || T == u16 {
	input, output: [3][^]T
	for channel in 0..<3 {
		input[channel] = cast([^]T)input_bytes[channel]
		output[channel] = cast([^]T)output_bytes[channel]
	}
	maximum := f64(instance.sample_max)
	coordinate_scale := f64(instance.table.edge - 1) / maximum
	output_scale := maximum / 65535.0
	for x in 0..<int(instance.video_info.width) {
		original := [3]f64{f64(input[0][x]), f64(input[1][x]), f64(input[2][x])}
		coordinates := original * coordinate_scale
		graded := interpolate(&instance.table, coordinates) * output_scale
		mixed := original + instance.strength * (graded - original)
		for channel in 0..<3 {
			output[channel][x] = T(clamp(mixed[channel], 0, maximum) + 0.5)
		}
	}
}

free_hald :: proc "system"(instance_data: rawptr, core: ^vs.VSCore, api: ^vs.VSAPI) {
	instance := cast(^Hald)instance_data
	stbi.image_free(instance.table.pixels)
	api.freeNode(instance.source)
	libc.free(instance)
}
