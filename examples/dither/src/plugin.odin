package dither

import "core:c"
import "core:c/libc"

import vs "deps:vapoursynth"

@(private="file", rodata)
blue_noise := BLUE_NOISE

Dither :: struct {
	source: ^vs.VSNode,
	video_info: vs.VSVideoInfo,
	parameters: Kernel_Parameters,
	kernel: Row_Kernel,
	seed: int,
	thresholds: [TILE_SIZE][2*TILE_SIZE]u16,
}

@(export)
VapourSynthPluginInit2 :: proc "system"(plugin: ^vs.VSPlugin, api: ^vs.VSPLUGINAPI) {
	if api.configPlugin(
		"org.vapoursynth.odin.dither", "odin_dither", "Odin blue-noise dither",
		1 << 16, vs.VAPOURSYNTH_API_VERSION, 0, plugin,
	) == 0 {
		return
	}
	api.registerFunction(
		"Dither", "clip:vnode;bits:int:opt;seed:int:opt;simd:int:opt;scale:int:opt;",
		"clip:vnode;", create_dither, nil, plugin,
	)
}

create_dither :: proc "system"(
	input, output: ^vs.VSMap,
	user_data: rawptr,
	core: ^vs.VSCore,
	api: ^vs.VSAPI,
) {
	property_error: c.int
	source := api.mapGetNode(input, "clip", 0, &property_error)
	if property_error != vs.peSuccess || source == nil {
		api.mapSetError(output, "Dither: expected a video clip.")
		return
	}
	info := api.getVideoInfo(source)
	if info == nil || info.width == 0 || info.height == 0 || info.format.colorFamily == vs.cfUndefined {
		api.freeNode(source)
		api.mapSetError(output, "Dither: expected constant video format and dimensions.")
		return
	}
	format := info.format
	if format.sampleType != vs.stInteger || format.bitsPerSample < 8 || format.bitsPerSample > 16 {
		api.freeNode(source)
		api.mapSetError(output, "Dither: expected 8-16 bit integer video (Gray, RGB, or YUV).")
		return
	}
	bits, seed, vectorized, scale: i64
	options := [?]struct {key: cstring, fallback, minimum, maximum: i64, target: ^i64, message: cstring}{
		{"bits", 8, 1, i64(format.bitsPerSample), &bits, "Dither: bits must be between 1 and the input bit depth; zero is not a supported bit depth."},
		{"seed", 0, 0, TILE_AREA-1, &seed, "Dither: seed must be between 0 and 4095."},
		{"simd", 1, 0, 1, &vectorized, "Dither: simd must be 0 (scalar) or 1 (portable SIMD)."},
		{"scale", 0, 0, 1, &scale, "Dither: scale must be 0 (power of two) or 1 (full code range)."},
	}
	for option in options {
		value := api.mapGetInt(input, option.key, 0, &property_error)
		if property_error == vs.peUnset {
			value = option.fallback
		} else if property_error != vs.peSuccess {
			api.freeNode(source)
			api.mapSetError(output, option.message)
			return
		}
		if value < option.minimum || value > option.maximum {
			api.freeNode(source)
			api.mapSetError(output, option.message)
			return
		}
		option.target^ = value
	}
	if bits == i64(format.bitsPerSample) {
		if api.mapConsumeNode(output, "clip", source, vs.maReplace) != 0 {
			api.mapSetError(output, "Dither: could not return the unchanged clip.")
		}
		return
	}
	output_info := info^
	if api.queryVideoFormat(
		&output_info.format, format.colorFamily, vs.stInteger, c.int(max(8, bits)),
		format.subSamplingW, format.subSamplingH, core,
	) == 0 {
		api.freeNode(source)
		api.mapSetError(output, "Dither: the core does not support the requested output format.")
		return
	}
	instance := cast(^Dither)libc.malloc(size_of(Dither))
	if instance == nil {
		api.freeNode(source)
		api.mapSetError(output, "Dither: could not allocate filter data.")
		return
	}
	instance^ = Dither{
		source = source,
		video_info = output_info,
		parameters = Kernel_Parameters{
			input_bits = u32(format.bitsPerSample),
			shift = u32(i64(format.bitsPerSample)-bits),
			input_max = (u32(1) << u32(format.bitsPerSample))-1,
			output_max = (u32(1) << u32(bits))-1,
		},
		kernel = select_kernel(int(bits), Scale(scale), vectorized != 0),
		seed = int(seed),
	}
	if bits < 8 {
		// The 24-bit reciprocal exactly rounds all 2^bits output levels to 0..255.
		maximum := instance.parameters.output_max
		instance.parameters.expansion_multiplier = ((1 << 24) + maximum - 1) / maximum
	}
	threshold_range := u32(1) << instance.parameters.shift
	if Scale(scale) == .Full_Range {
		threshold_range = instance.parameters.input_max
	}
	for y in 0..<TILE_SIZE {
		for x in 0..<TILE_SIZE {
			rank := u32(blue_noise[y*TILE_SIZE+x])
			threshold := u16(((2*rank+1)*threshold_range)/(2*TILE_AREA))
			instance.thresholds[y][x] = threshold
			instance.thresholds[y][x+TILE_SIZE] = threshold
		}
	}
	dependency := vs.VSFilterDependency{source = source, requestPattern = vs.rpStrictSpatial}
	node := api.createVideoFilter2(
		"Dither", &instance.video_info, get_frame, free_dither, vs.fmParallel,
		cast([^]vs.VSFilterDependency)&dependency, 1, instance, core,
	)
	if node == nil {
		free_dither(instance, core, api)
		api.mapSetError(output, "Dither: could not create the filter.")
		return
	}
	// The filter owns instance; consuming node transfers its reference even on failure.
	if api.mapConsumeNode(output, "clip", node, vs.maReplace) != 0 {
		api.mapSetError(output, "Dither: could not return the clip.")
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
	instance := cast(^Dither)instance_data
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
		api.setFilterError("Dither: the requested source frame is unavailable.", frame_context)
		return nil
	}
	defer api.freeFrame(source)
	output := api.newVideoFrame(
		&instance.video_info.format, instance.video_info.width, instance.video_info.height, source, core,
	)
	if output == nil {
		api.setFilterError("Dither: could not allocate the output frame.", frame_context)
		return nil
	}
	for plane in 0..<instance.video_info.format.numPlanes {
		width := int(api.getFrameWidth(source, plane))
		height := int(api.getFrameHeight(source, plane))
		input_data := api.getReadPtr(source, plane)
		output_data := api.getWritePtr(output, plane)
		input_stride := int(api.getStride(source, plane))
		output_stride := int(api.getStride(output, plane))
		phase_x := (instance.seed+17*int(plane)) & (TILE_SIZE-1)
		phase_y := ((instance.seed>>6)+29*int(plane)) & (TILE_SIZE-1)
		for y in 0..<height {
			thresholds := raw_data(instance.thresholds[(y+phase_y)&(TILE_SIZE-1)][:])
			instance.kernel(
				&input_data[y*input_stride], &output_data[y*output_stride],
				width, thresholds, phase_x, &instance.parameters,
			)
		}
	}
	return output
}

free_dither :: proc "system"(instance_data: rawptr, core: ^vs.VSCore, api: ^vs.VSAPI) {
	instance := cast(^Dither)instance_data
	api.freeNode(instance.source)
	libc.free(instance)
}
