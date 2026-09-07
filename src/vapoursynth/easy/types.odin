package easy

import "core:c"
import "core:dynlib"
import vs ".."

Error :: enum {
	None,
	Invalid_Handle,
	Invalid_Argument,
	Missing_Key,
	Wrong_Type,
	Index_Out_Of_Range,
	Map_Error,
	Allocation_Failed,
	Plugin_Not_Found,
	Invocation_Failed,
	Frame_Request_Failed,
	Wrong_Media_Type,
	Unsupported_Format,
	Different_Core,
	Unsupported_API,
	Library_Load_Failed,
	Symbol_Not_Found,
	Library_Unload_Failed,
}

Append_Mode :: enum c.int {
	Replace = vs.maReplace,
	Append = vs.maAppend,
}

// The diagnostic owns its bytes. diagnostic_text borrows them until reuse.
// truncated also reports a completely filled frame-error buffer, where the API
// cannot tell us whether the original message was longer.
Diagnostic :: struct {
	buffer: [1024]u8,
	length: int,
	truncated: bool,
}

// These values each own one resource. Assignment does not acquire a reference:
// do not copy an owner and destroy both copies. Use retain_node/retain_frame.
// Keep the library and core alive until every dependent owner has been destroyed.
Library :: struct {
	handle: dynlib.Library,
	api: ^vs.VSAPI,
}

Core :: struct {
	api: ^vs.VSAPI,
	handle: ^vs.VSCore,
}

Map :: struct {
	api: ^vs.VSAPI,
	handle: ^vs.VSMap,
	core: ^vs.VSCore,
}

Node :: struct {
	api: ^vs.VSAPI,
	handle: ^vs.VSNode,
	core: ^vs.VSCore,
}

Frame :: struct {
	api: ^vs.VSAPI,
	handle: ^vs.VSFrame,
	core: ^vs.VSCore,
}

// A read-only borrow from a Frame. Rows exclude padding; stride is in bytes.
// The view expires when the frame is destroyed or modified through the raw API.
Plane_View :: struct {
	data: [^]u8,
	width: int,
	height: int,
	stride: int,
	bytes_per_sample: int,
	bits_per_sample: int,
	sample_type: c.int,
}
