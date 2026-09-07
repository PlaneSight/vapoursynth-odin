// SPDX-License-Identifier: LGPL-2.1-or-later
package dither_plus

import "core:c"
import "core:c/libc"
import vs "../.."

Dither :: struct {
	source: ^vs.VSNode,
	video_info: vs.VSVideoInfo,
	parameters: Kernel_Parameters,
	kernel: Row_Kernel,
	mode: Mode,
	scale: Scale,
	seed: int,
	correlate_planes: bool,
	vary_by_frame: bool,
	scratch_bytes: uint,
	thresholds: [TILE_SIZE][2*TILE_SIZE]u16,
}

@(export)
VapourSynthPluginInit2 :: proc "system"(plugin: ^vs.VSPlugin, api: ^vs.VSPLUGINAPI) {
	if api.configPlugin(
		"org.vapoursynth.odin.dither_plus", "odin_dither_plus", "Odin DitherPlus",
		1 << 16, vs.VAPOURSYNTH_API_VERSION, 0, plugin,
	) == 0 {
		return
	}
	api.registerFunction(
		"Dither", "clip:vnode;bits:int:opt;mode:data:opt;seed:int:opt;simd:int:opt;scale:int:opt;corplane:int:opt;dyn:int:opt;",
		"clip:vnode;", create_dither, nil, plugin,
	)
}

read_mode :: proc "contextless"(input: ^vs.VSMap, api: ^vs.VSAPI) -> (Mode, cstring) {
	error: c.int
	data := api.mapGetData(input, "mode", 0, &error)
	if error == vs.peUnset {
		return .Blue_Noise, nil
	}
	message: cstring = "DitherPlus: mode must be blue_noise, bayer, none, floyd_steinberg, or sierra_lite."
	if error != vs.peSuccess || data == nil || api.mapNumElements(input, "mode") != 1 {
		return .Blue_Noise, message
	}
	length := api.mapGetDataSize(input, "mode", 0, &error)
	if error != vs.peSuccess || length < 1 || length > 16 {
		return .Blue_Noise, message
	}
	switch string((cast([^]u8)data)[:length]) {
	case "blue_noise": return .Blue_Noise, nil
	case "bayer": return .Bayer, nil
	case "none": return .Nearest, nil
	case "floyd_steinberg": return .Floyd_Steinberg, nil
	case "sierra_lite": return .Sierra_Lite, nil
	}
	return .Blue_Noise, message
}

create_dither :: proc "system"(
	input, output: ^vs.VSMap, user_data: rawptr,
	core: ^vs.VSCore, api: ^vs.VSAPI,
) {
	error: c.int
	source := api.mapGetNode(input, "clip", 0, &error)
	if error != vs.peSuccess || source == nil {
		api.mapSetError(output, "DitherPlus: expected a video clip.")
		return
	}
	defer {
		if source != nil {
			api.freeNode(source)
		}
	}
	info := api.getVideoInfo(source)
	if info == nil || info.width <= 0 || info.height <= 0 ||
	   (info.format.colorFamily != vs.cfGray && info.format.colorFamily != vs.cfRGB && info.format.colorFamily != vs.cfYUV) ||
	   info.format.sampleType != vs.stInteger || info.format.bitsPerSample < 8 || info.format.bitsPerSample > 16 {
		api.mapSetError(output, "DitherPlus: expected constant format and dimensions with 8-16 bit integer Gray, RGB, or YUV samples.")
		return
	}
	mode, message := read_mode(input, api)
	if message != nil {
		api.mapSetError(output, message)
		return
	}
	bits, seed, vectorized, scale, correlate_planes, vary_by_frame: i64
	options := [?]struct {key: cstring, fallback, minimum, maximum: i64, target: ^i64, message: cstring}{
		{"bits", 8, 1, i64(info.format.bitsPerSample), &bits, "DitherPlus: bits must be between 1 and the input bit depth."},
		{"seed", 0, 0, TILE_AREA-1, &seed, "DitherPlus: seed must be between 0 and 4095."},
		{"simd", 1, 0, 1, &vectorized, "DitherPlus: simd must be 0 or 1."},
		{"scale", 0, 0, 1, &scale, "DitherPlus: scale must be 0 (power of two) or 1 (full code range)."},
		{"corplane", 0, 0, 1, &correlate_planes, "DitherPlus: corplane must be 0 or 1."},
		{"dyn", 0, 0, 1, &vary_by_frame, "DitherPlus: dyn must be 0 or 1."},
	}
	for option in options {
		value := api.mapGetInt(input, option.key, 0, &error)
		if error == vs.peUnset {
			value = option.fallback
		} else if error != vs.peSuccess || api.mapNumElements(input, option.key) != 1 {
			api.mapSetError(output, option.message)
			return
		}
		if value < option.minimum || value > option.maximum {
			api.mapSetError(output, option.message)
			return
		}
		option.target^ = value
	}
	if vary_by_frame != 0 && mode != .Blue_Noise && mode != .Bayer {
		api.mapSetError(output, "DitherPlus: dyn=1 is only supported by blue_noise and bayer.")
		return
	}
	if bits == i64(info.format.bitsPerSample) {
		unchanged := source
		source = nil
		if api.mapConsumeNode(output, "clip", unchanged, vs.maReplace) != 0 {
			api.mapSetError(output, "DitherPlus: could not return the unchanged clip.")
		}
		return
	}
	output_info := info^
	if api.queryVideoFormat(
		&output_info.format, info.format.colorFamily, vs.stInteger, c.int(max(8, bits)),
		info.format.subSamplingW, info.format.subSamplingH, core,
	) == 0 {
		api.mapSetError(output, "DitherPlus: the core does not support the requested output format.")
		return
	}
	diffusion := mode == .Floyd_Steinberg || mode == .Sierra_Lite
	scratch_bytes: uint
	if diffusion {
		if int(info.width) > max(int)/(2*size_of(f64))-2 {
			api.mapSetError(output, "DitherPlus: frame width exceeds the diffusion scratch limit.")
			return
		}
		scratch_bytes = uint(2*(int(info.width)+2)*size_of(f64))
	}
	instance := cast(^Dither)libc.malloc(size_of(Dither))
	if instance == nil {
		api.mapSetError(output, "DitherPlus: could not allocate filter data.")
		return
	}
	instance^ = Dither{
		source = source, video_info = output_info,
		parameters = Kernel_Parameters{
			input_bits = u32(info.format.bitsPerSample),
			shift = u32(i64(info.format.bitsPerSample)-bits),
			input_max = (u32(1)<<u32(info.format.bitsPerSample))-1,
			output_max = (u32(1)<<u32(bits))-1,
		},
		mode = mode, scale = Scale(scale), seed = int(seed),
		correlate_planes = correlate_planes != 0, vary_by_frame = vary_by_frame != 0,
		scratch_bytes = scratch_bytes,
	}
	source = nil // The instance now owns the source reference.
	if bits < 8 {
		maximum := instance.parameters.output_max
		instance.parameters.expansion_multiplier = ((1<<24)+maximum-1)/maximum
	}
	if !diffusion {
		instance.kernel = select_kernel(int(bits), instance.scale, vectorized != 0)
		build_thresholds(&instance.thresholds, &instance.parameters, mode, instance.scale)
	}
	dependency := vs.VSFilterDependency{source = instance.source, requestPattern = vs.rpStrictSpatial}
	node := api.createVideoFilter2(
		"DitherPlus", &instance.video_info, get_frame, free_dither, vs.fmParallel,
		cast([^]vs.VSFilterDependency)&dependency, 1, instance, core,
	)
	if node == nil {
		free_dither(instance, core, api)
		api.mapSetError(output, "DitherPlus: could not create the filter.")
		return
	}
	if api.mapConsumeNode(output, "clip", node, vs.maReplace) != 0 {
		api.mapSetError(output, "DitherPlus: could not return the clip.")
	}
}

get_frame :: proc "system"(
	n, activation_reason: c.int, instance_data: rawptr, frame_data: ^rawptr,
	frame_context: ^vs.VSFrameContext, core: ^vs.VSCore, api: ^vs.VSAPI,
) -> ^vs.VSFrame {
	instance := cast(^Dither)instance_data
	switch activation_reason {
	case vs.arInitial:
		api.requestFrameFilter(n, instance.source, frame_context)
		return nil
	case vs.arAllFramesReady:
	case: return nil
	}
	source := api.getFrameFilter(n, instance.source, frame_context)
	if source == nil {
		api.setFilterError("DitherPlus: the requested source frame is unavailable.", frame_context)
		return nil
	}
	defer api.freeFrame(source)
	errors: [^]f64
	if instance.scratch_bytes != 0 {
		errors = cast([^]f64)libc.malloc(instance.scratch_bytes)
		if errors == nil {
			api.setFilterError("DitherPlus: could not allocate diffusion scratch rows.", frame_context)
			return nil
		}
	}
	defer libc.free(errors)
	output := api.newVideoFrame(
		&instance.video_info.format, instance.video_info.width, instance.video_info.height, source, core,
	)
	if output == nil {
		api.setFilterError("DitherPlus: could not allocate the output frame.", frame_context)
		return nil
	}
	frame_phase := int(n & (TILE_SIZE-1)) if instance.vary_by_frame else 0
	for plane in 0..<instance.video_info.format.numPlanes {
		width := int(api.getFrameWidth(source, plane))
		height := int(api.getFrameHeight(source, plane))
		input_data := api.getReadPtr(source, plane)
		output_data := api.getWritePtr(output, plane)
		input_stride := int(api.getStride(source, plane))
		output_stride := int(api.getStride(output, plane))
		if errors != nil {
			diffusion_plane(input_data, output_data, width, height, input_stride, output_stride,
			                &instance.parameters, instance.scale, instance.mode, errors)
			continue
		}
		plane_phase := 0 if instance.correlate_planes else int(plane)
		phase_x := (instance.seed+17*plane_phase+13*frame_phase) & (TILE_SIZE-1)
		phase_y := ((instance.seed>>6)+29*plane_phase+37*frame_phase) & (TILE_SIZE-1)
		for y in 0..<height {
			thresholds := raw_data(instance.thresholds[(y+phase_y)&(TILE_SIZE-1)][:])
			instance.kernel(&input_data[y*input_stride], &output_data[y*output_stride],
			                width, thresholds, phase_x, &instance.parameters)
		}
	}
	return output
}

free_dither :: proc "system"(instance_data: rawptr, core: ^vs.VSCore, api: ^vs.VSAPI) {
	instance := cast(^Dither)instance_data
	api.freeNode(instance.source)
	libc.free(instance)
}
