package easy

import "core:c"

import vs ".."

map_set_int :: proc(map_: ^Map, key: cstring, value: i64, mode: Append_Mode = .Replace) -> Error {
	if err := map_write_check(map_, key, mode); err != .None {
		return err
	}
	return map_write_error(map_.api.mapSetInt(map_.handle, key, value, c.int(mode)))
}

map_set_float :: proc(map_: ^Map, key: cstring, value: f64, mode: Append_Mode = .Replace) -> Error {
	if err := map_write_check(map_, key, mode); err != .None {
		return err
	}
	return map_write_error(map_.api.mapSetFloat(map_.handle, key, value, c.int(mode)))
}

// Values are copied into the map, including embedded zero bytes.
map_set_bytes :: proc(map_: ^Map, key: cstring, value: []u8, mode: Append_Mode = .Replace) -> Error {
	return map_set_data(map_, key, value, vs.dtBinary, mode)
}

// Marks the bytes as UTF-8 without validating them. VapourSynth adds a zero
// terminator outside the stored length.
map_set_string :: proc(map_: ^Map, key: cstring, value: string, mode: Append_Mode = .Replace) -> Error {
	return map_set_data(map_, key, transmute([]u8)value, vs.dtUtf8, mode)
}

// Array setters replace the entire property, including when the array is empty.
map_set_int_array :: proc(map_: ^Map, key: cstring, values: []i64) -> Error {
	if err := map_access_check(map_, key); err != .None {
		return err
	}
	if len(values) > int(max(c.int)) {
		return .Invalid_Argument
	}
	placeholder: i64
	data := raw_data(values)
	if len(values) == 0 {
		data = cast([^]i64)&placeholder
	}
	return map_write_error(map_.api.mapSetIntArray(map_.handle, key, data, c.int(len(values))))
}

map_set_float_array :: proc(map_: ^Map, key: cstring, values: []f64) -> Error {
	if err := map_access_check(map_, key); err != .None {
		return err
	}
	if len(values) > int(max(c.int)) {
		return .Invalid_Argument
	}
	placeholder: f64
	data := raw_data(values)
	if len(values) == 0 {
		data = cast([^]f64)&placeholder
	}
	return map_write_error(map_.api.mapSetFloatArray(map_.handle, key, data, c.int(len(values))))
}

map_get_int :: proc(map_: ^Map, key: cstring, index: int = 0) -> (i64, Error) {
	if err := map_index_check(map_, key, index); err != .None {
		return 0, err
	}
	property_error: c.int
	value := map_.api.mapGetInt(map_.handle, key, c.int(index), &property_error)
	return value, map_read_error(property_error)
}

map_get_float :: proc(map_: ^Map, key: cstring, index: int = 0) -> (f64, Error) {
	if err := map_index_check(map_, key, index); err != .None {
		return 0, err
	}
	property_error: c.int
	value := map_.api.mapGetFloat(map_.handle, key, c.int(index), &property_error)
	return value, map_read_error(property_error)
}

// Data and array getters borrow read-only storage. Do not modify it. Any map
// mutation or destruction may invalidate the view; copy it first if needed.
map_get_bytes :: proc(map_: ^Map, key: cstring, index: int = 0) -> ([]u8, Error) {
	if err := map_index_check(map_, key, index); err != .None {
		return nil, err
	}
	property_error: c.int
	size := map_.api.mapGetDataSize(map_.handle, key, c.int(index), &property_error)
	if err := map_read_error(property_error); err != .None {
		return nil, err
	}
	if size < 0 {
		return nil, .Map_Error
	}
	if size == 0 {
		return nil, .None
	}
	data := map_.api.mapGetData(map_.handle, key, c.int(index), &property_error)
	if err := map_read_error(property_error); err != .None {
		return nil, err
	}
	if data == nil {
		return nil, .Map_Error
	}
	return (cast([^]u8)data)[:int(size)], .None
}

// Requires VapourSynth's UTF-8 hint. The hint is metadata, not validation.
// The borrowed string preserves embedded zero bytes and excludes any terminator.
map_get_string :: proc(map_: ^Map, key: cstring, index: int = 0) -> (string, Error) {
	if err := map_index_check(map_, key, index); err != .None {
		return "", err
	}
	property_error: c.int
	hint := map_.api.mapGetDataTypeHint(map_.handle, key, c.int(index), &property_error)
	if err := map_read_error(property_error); err != .None {
		return "", err
	}
	if hint != vs.dtUtf8 {
		return "", .Wrong_Type
	}
	data, err := map_get_bytes(map_, key, index)
	return transmute(string)data, err
}

map_get_int_array :: proc(map_: ^Map, key: cstring) -> ([]i64, Error) {
	count, count_error := map_array_count(map_, key, vs.ptInt)
	if count_error != .None {
		return nil, count_error
	}
	if count == 0 {
		return nil, .None
	}
	property_error: c.int
	data := map_.api.mapGetIntArray(map_.handle, key, &property_error)
	if err := map_read_error(property_error); err != .None {
		return nil, err
	}
	if data == nil {
		return nil, .Map_Error
	}
	return data[:count], .None
}

map_get_float_array :: proc(map_: ^Map, key: cstring) -> ([]f64, Error) {
	count, count_error := map_array_count(map_, key, vs.ptFloat)
	if count_error != .None {
		return nil, count_error
	}
	if count == 0 {
		return nil, .None
	}
	property_error: c.int
	data := map_.api.mapGetFloatArray(map_.handle, key, &property_error)
	if err := map_read_error(property_error); err != .None {
		return nil, err
	}
	if data == nil {
		return nil, .Map_Error
	}
	return data[:count], .None
}

// Returns a new owned reference, independent of the reference held by the map.
map_get_node :: proc(map_: ^Map, key: cstring, index: int = 0) -> (Node, Error) {
	if err := map_index_check(map_, key, index); err != .None {
		return {}, err
	}
	property_error: c.int
	handle := map_.api.mapGetNode(map_.handle, key, c.int(index), &property_error)
	if err := map_read_error(property_error); err != .None {
		return {}, err
	}
	if handle == nil {
		return {}, .Map_Error
	}
	return Node{api = map_.api, handle = handle, core = map_.core}, .None
}

// The map acquires its own reference; the caller continues to own node.
map_set_node :: proc(map_: ^Map, key: cstring, node: ^Node, mode: Append_Mode = .Replace) -> Error {
	if err := map_node_write_check(map_, key, node, mode); err != .None {
		return err
	}
	return map_write_error(map_.api.mapSetNode(map_.handle, key, node.handle, c.int(mode)))
}

// Once passed to VapourSynth, node is consumed even if the insertion fails.
// Validation failures leave node owned by the caller.
map_take_node :: proc(map_: ^Map, key: cstring, node: ^Node, mode: Append_Mode = .Replace) -> Error {
	if err := map_node_write_check(map_, key, node, mode); err != .None {
		return err
	}
	result := map_.api.mapConsumeNode(map_.handle, key, node.handle, c.int(mode))
	node^ = {}
	return map_write_error(result)
}

@(private="file")
map_set_data :: proc(map_: ^Map, key: cstring, value: []u8, hint: c.int, mode: Append_Mode) -> Error {
	if err := map_write_check(map_, key, mode); err != .None {
		return err
	}
	if len(value) > int(max(c.int)) {
		return .Invalid_Argument
	}
	// Keep even an empty value's pointer non-null at the C boundary.
	data := cstring("")
	if len(value) != 0 {
		data = cast(cstring)raw_data(value)
	}
	return map_write_error(map_.api.mapSetData(map_.handle, key, data, c.int(len(value)), hint, c.int(mode)))
}

@(private="file")
map_access_check :: proc(map_: ^Map, key: cstring) -> Error {
	if map_ == nil || map_.api == nil || map_.handle == nil || map_.core == nil {
		return .Invalid_Handle
	}
	if !map_key_is_valid(key) {
		return .Invalid_Argument
	}
	// Some raw accessors terminate the process when the map contains an error.
	if map_.api.mapGetError(map_.handle) != nil {
		return .Map_Error
	}
	return .None
}

@(private="file")
map_key_is_valid :: proc(key: cstring) -> bool {
	if key == nil {
		return false
	}
	data := cast([^]u8)key
	first := data[0]
	if first != '_' && !(first >= 'A' && first <= 'Z') && !(first >= 'a' && first <= 'z') {
		return false
	}
	for i := 1; data[i] != 0; i += 1 {
		byte := data[i]
		if byte == '_' || (byte >= 'A' && byte <= 'Z') || (byte >= 'a' && byte <= 'z') || (byte >= '0' && byte <= '9') {
			continue
		}
		return false
	}
	return true
}

@(private="file")
map_array_count :: proc(map_: ^Map, key: cstring, expected_type: c.int) -> (int, Error) {
	if err := map_access_check(map_, key); err != .None {
		return 0, err
	}
	property_type := map_.api.mapGetType(map_.handle, key)
	if property_type == vs.ptUnset {
		return 0, .Missing_Key
	}
	if property_type != expected_type {
		return 0, .Wrong_Type
	}
	count := map_.api.mapNumElements(map_.handle, key)
	if count < 0 {
		return 0, .Map_Error
	}
	// Raw array getters check index zero and reject typed empty properties.
	return int(count), .None
}

@(private="file")
map_index_check :: proc(map_: ^Map, key: cstring, index: int) -> Error {
	if err := map_access_check(map_, key); err != .None {
		return err
	}
	if index < 0 || index > int(max(c.int)) {
		return .Index_Out_Of_Range
	}
	return .None
}

@(private="file")
map_write_check :: proc(map_: ^Map, key: cstring, mode: Append_Mode) -> Error {
	if err := map_access_check(map_, key); err != .None {
		return err
	}
	switch mode {
	case .Replace, .Append:
		return .None
	case:
		return .Invalid_Argument
	}
}

@(private="file")
map_node_write_check :: proc(map_: ^Map, key: cstring, node: ^Node, mode: Append_Mode) -> Error {
	if err := map_write_check(map_, key, mode); err != .None {
		return err
	}
	if node == nil || node.api == nil || node.handle == nil || node.core == nil {
		return .Invalid_Handle
	}
	if node.api != map_.api || node.core != map_.core {
		return .Different_Core
	}
	return .None
}

@(private="file")
map_read_error :: proc(property_error: c.int) -> Error {
	switch property_error {
	case vs.peSuccess:
		return .None
	case vs.peUnset:
		return .Missing_Key
	case vs.peType:
		return .Wrong_Type
	case vs.peIndex:
		return .Index_Out_Of_Range
	case:
		return .Map_Error
	}
}

@(private="file")
map_write_error :: proc(result: c.int) -> Error {
	if result != 0 {
		return .Wrong_Type
	}
	return .None
}
