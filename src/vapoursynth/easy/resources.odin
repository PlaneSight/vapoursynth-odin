package easy

import "core:c"
import vs ".."

// api must be the table obtained by requesting VAPOURSYNTH_API_VERSION.
create_core :: proc(api: ^vs.VSAPI, flags: c.int = 0) -> (Core, Error) {
	if api == nil {
		return {}, .Invalid_Handle
	}
	handle := api.createCore(flags)
	if handle == nil {
		return {}, .Allocation_Failed
	}
	return Core{api = api, handle = handle}, .None
}

// Finish requests and destroy every dependent map, node and frame first.
destroy_core :: proc(core: ^Core) {
	if core == nil || core.handle == nil {
		return
	}
	core.api.freeCore(core.handle)
	core^ = {}
}

core_info :: proc(core: ^Core) -> (vs.VSCoreInfo2, Error) {
	if core == nil || core.api == nil || core.handle == nil {
		return {}, .Invalid_Handle
	}
	info: vs.VSCoreInfo2
	core.api.getCoreInfo2(core.handle, &info)
	return info, .None
}

create_map :: proc(core: ^Core) -> (Map, Error) {
	if core == nil || core.api == nil || core.handle == nil {
		return {}, .Invalid_Handle
	}
	handle := core.api.createMap()
	if handle == nil {
		return {}, .Allocation_Failed
	}
	return Map{api = core.api, handle = handle, core = core.handle}, .None
}

destroy_map :: proc(map_: ^Map) {
	if map_ == nil || map_.handle == nil {
		return
	}
	map_.api.freeMap(map_.handle)
	map_^ = {}
}

destroy_node :: proc(node: ^Node) {
	if node == nil || node.handle == nil {
		return
	}
	node.api.freeNode(node.handle)
	node^ = {}
}

destroy_frame :: proc(frame: ^Frame) {
	if frame == nil || frame.handle == nil {
		return
	}
	frame.api.freeFrame(frame.handle)
	frame^ = {}
}

retain_node :: proc(node: ^Node) -> (Node, Error) {
	if node == nil || node.api == nil || node.handle == nil {
		return {}, .Invalid_Handle
	}
	handle := node.api.addNodeRef(node.handle)
	if handle == nil {
		return {}, .Allocation_Failed
	}
	return Node{api = node.api, handle = handle, core = node.core}, .None
}

retain_frame :: proc(frame: ^Frame) -> (Frame, Error) {
	if frame == nil || frame.api == nil || frame.handle == nil {
		return {}, .Invalid_Handle
	}
	handle := frame.api.addFrameRef(frame.handle)
	if handle == nil {
		return {}, .Allocation_Failed
	}
	return Frame{api = frame.api, handle = handle, core = frame.core}, .None
}

video_info :: proc(node: ^Node) -> (vs.VSVideoInfo, Error) {
	if node == nil || node.api == nil || node.handle == nil {
		return {}, .Invalid_Handle
	}
	if node.api.getNodeType(node.handle) != vs.mtVideo {
		return {}, .Wrong_Media_Type
	}
	info := node.api.getVideoInfo(node.handle)
	if info == nil {
		return {}, .Invalid_Handle
	}
	return info^, .None
}

// args is borrowed. On failure the temporary result map is freed after copying
// its error into diagnostic. A successful result is an owned Map.
invoke :: proc(
	core: ^Core,
	namespace, name: cstring,
	args: ^Map,
	diagnostic: ^Diagnostic = nil,
) -> (Map, Error) {
	clear_diagnostic(diagnostic)
	if core == nil || core.api == nil || core.handle == nil ||
	   args == nil || args.api == nil || args.handle == nil {
		return {}, .Invalid_Handle
	}
	if namespace == nil || name == nil || namespace == "" || name == "" {
		return {}, .Invalid_Argument
	}
	if core.api != args.api || core.handle != args.core {
		return {}, .Different_Core
	}
	if message := args.api.mapGetError(args.handle); message != nil {
		write_diagnostic(diagnostic, string(message))
		return {}, .Map_Error
	}
	plugin := core.api.getPluginByNamespace(namespace, core.handle)
	if plugin == nil {
		write_diagnostic(diagnostic, "The core does not contain the requested plugin namespace.")
		return {}, .Plugin_Not_Found
	}
	handle := core.api.invoke(plugin, name, args.handle)
	if handle == nil {
		return {}, .Allocation_Failed
	}
	if message := core.api.mapGetError(handle); message != nil {
		write_diagnostic(diagnostic, string(message))
		core.api.freeMap(handle)
		return {}, .Invocation_Failed
	}
	return Map{api = core.api, handle = handle, core = core.handle}, .None
}

// Synchronous host access. Do not call from a filter's get-frame callback.
get_frame :: proc(node: ^Node, index: int, diagnostic: ^Diagnostic = nil) -> (Frame, Error) {
	clear_diagnostic(diagnostic)
	if node == nil || node.api == nil || node.handle == nil {
		return {}, .Invalid_Handle
	}
	if index < 0 || i64(index) > 0x7fffffff {
		return {}, .Index_Out_Of_Range
	}
	frame_count: c.int
	switch node.api.getNodeType(node.handle) {
	case vs.mtVideo:
		frame_count = node.api.getVideoInfo(node.handle).numFrames
	case vs.mtAudio:
		frame_count = node.api.getAudioInfo(node.handle).numFrames
	case:
		return {}, .Wrong_Media_Type
	}
	if index >= int(frame_count) {
		return {}, .Index_Out_Of_Range
	}
	local_diagnostic: Diagnostic
	output := diagnostic
	if output == nil {
		output = &local_diagnostic
	}
	handle := node.api.getFrame(c.int(index), node.handle, raw_data(output.buffer[:]), c.int(len(output.buffer)))
	if handle == nil {
		output.length = len(string(cast(cstring)raw_data(output.buffer[:])))
		output.truncated = output.length == len(output.buffer)-1
		return {}, .Frame_Request_Failed
	}
	clear_diagnostic(diagnostic)
	return Frame{api = node.api, handle = handle, core = node.core}, .None
}
