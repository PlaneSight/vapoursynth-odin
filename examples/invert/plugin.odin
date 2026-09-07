// SPDX-License-Identifier: LGPL-2.1-or-later
package invert

import "core:c"
import "core:c/libc"

import vs "../.."

// Immutable after construction, so separate frames can be processed in parallel.
Invert :: struct {
	source:     ^vs.VSNode,
	video_info: vs.VSVideoInfo,
	sample_max: u16,
}

@(export)
VapourSynthPluginInit2 :: proc "system"(plugin: ^vs.VSPlugin, api: ^vs.VSPLUGINAPI) {
	if api.configPlugin(
		"org.vapoursynth.odin.invert", "odin_invert", "Odin invert example",
		1 << 16, vs.VAPOURSYNTH_API_VERSION, 0, plugin,
	) == 0 {
		return
	}
	api.registerFunction("Invert", "clip:vnode;", "clip:vnode;", create_invert, nil, plugin)
}

create_invert :: proc "system"(
	input, output: ^vs.VSMap,
	user_data: rawptr,
	core: ^vs.VSCore,
	api: ^vs.VSAPI,
) {
	property_error: c.int
	source := api.mapGetNode(input, "clip", 0, &property_error)
	if property_error != vs.peSuccess || source == nil {
		api.mapSetError(output, "Invert: expected a video clip.")
		return
	}

	video_info := api.getVideoInfo(source)
	if video_info == nil || video_info.format.colorFamily == vs.cfUndefined ||
	   video_info.width == 0 || video_info.height == 0 {
		api.freeNode(source)
		api.mapSetError(output, "Invert: expected a clip with constant format and dimensions.")
		return
	}
	format := video_info.format
	if format.sampleType != vs.stInteger || format.bitsPerSample < 8 || format.bitsPerSample > 16 {
		api.freeNode(source)
		api.mapSetError(output, "Invert: expected 8-16 bit integer video (Gray, RGB, or YUV).")
		return
	}

	instance := cast(^Invert)libc.malloc(size_of(Invert))
	if instance == nil {
		api.freeNode(source)
		api.mapSetError(output, "Invert: could not allocate filter data.")
		return
	}
	instance^ = Invert{
		source     = source,
		video_info = video_info^,
		sample_max = u16((u32(1) << u32(format.bitsPerSample)) - 1),
	}
	dependency := vs.VSFilterDependency{source = source, requestPattern = vs.rpStrictSpatial}
	node := api.createVideoFilter2(
		"Invert", &instance.video_info, get_frame, free_invert, vs.fmParallel,
		cast([^]vs.VSFilterDependency)&dependency, 1, instance, core,
	)
	if node == nil {
		free_invert(instance, core, api)
		api.mapSetError(output, "Invert: could not create the filter.")
		return
	}

	// The filter now owns instance; consume transfers node even on failure.
	if api.mapConsumeNode(output, "clip", node, vs.maReplace) != 0 {
		api.mapSetError(output, "Invert: could not return the clip.")
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
	instance := cast(^Invert)instance_data
	switch activation_reason {
	case vs.arInitial:
		api.requestFrameFilter(n, instance.source, frame_context)
		return nil
	case vs.arAllFramesReady:
		// Continue below once the upstream frame is available.
	case:
		// No per-request resources survive a callback, including arError.
		return nil
	}

	source := api.getFrameFilter(n, instance.source, frame_context)
	if source == nil {
		api.setFilterError("Invert: the requested source frame is unavailable.", frame_context)
		return nil
	}
	defer api.freeFrame(source)

	// copyFrame preserves properties and shares pixels until getWritePtr detaches them.
	output := api.copyFrame(source, core)
	if output == nil {
		api.setFilterError("Invert: could not copy the source frame.", frame_context)
		return nil
	}
	for plane in 0..<instance.video_info.format.numPlanes {
		width := int(api.getFrameWidth(source, plane))
		height := int(api.getFrameHeight(source, plane))
		input_data := api.getReadPtr(source, plane)
		output_data := api.getWritePtr(output, plane)
		input_stride := int(api.getStride(source, plane))
		output_stride := int(api.getStride(output, plane))
		for y in 0..<height {
			input_row := &input_data[y * input_stride]
			output_row := &output_data[y * output_stride]
			if instance.video_info.format.bytesPerSample == 1 {
				input_samples := cast([^]u8)input_row
				output_samples := cast([^]u8)output_row
				for x in 0..<width {
					output_samples[x] = u8(instance.sample_max) - input_samples[x]
				}
			} else {
				input_samples := cast([^]u16)input_row
				output_samples := cast([^]u16)output_row
				for x in 0..<width {
					output_samples[x] = instance.sample_max - input_samples[x]
				}
			}
		}
	}

	// VapourSynth takes ownership of the frame returned by this callback.
	return output
}

free_invert :: proc "system"(instance_data: rawptr, core: ^vs.VSCore, api: ^vs.VSAPI) {
	instance := cast(^Invert)instance_data
	api.freeNode(instance.source)
	libc.free(instance)
}
