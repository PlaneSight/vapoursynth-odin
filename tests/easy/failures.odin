// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:c"

import vs "../.."
import easy "../../easy"

// Only the mock callbacks see these tokens; no VapourSynth call dereferences them.
Mock_State :: struct {
	core_token, args_token, result_token, node_token, frame_token, plugin_token: u8,
	freed_cores, freed_maps, freed_nodes, freed_frames: int,
	freed_args, freed_results: int,
	unexpected_map_free: bool,
	invoke_nil: bool,
	message: [1300]u8,
}

mock: Mock_State

test_mock_failures :: proc() {
	mock = {}
	api := vs.VSAPI{
		createCore = mock_create_core,
		createMap = mock_create_map,
		addNodeRef = mock_add_node_ref,
		addFrameRef = mock_add_frame_ref,
		freeCore = mock_free_core,
		freeMap = mock_free_map,
		freeNode = mock_free_node,
		freeFrame = mock_free_frame,
		getPluginByNamespace = mock_get_plugin,
		invoke = mock_invoke,
		mapGetError = mock_map_error,
	}
	failed_core, err := easy.create_core(&api)
	expect(err, .Allocation_Failed)
	assert(failed_core.handle == nil && failed_core.api == nil)
	easy.destroy_core(&failed_core)
	assert(mock.freed_cores == 0)

	core := easy.Core{api = &api, handle = cast(^vs.VSCore)&mock.core_token}
	failed_map, map_err := easy.create_map(&core)
	expect(map_err, .Allocation_Failed)
	assert(failed_map.handle == nil && failed_map.api == nil)
	easy.destroy_map(&failed_map)
	assert(mock.freed_maps == 0)

	node := easy.Node{api = &api, handle = cast(^vs.VSNode)&mock.node_token, core = core.handle}
	failed_node, node_err := easy.retain_node(&node)
	expect(node_err, .Allocation_Failed)
	assert(failed_node.handle == nil && node.handle != nil)
	easy.destroy_node(&failed_node)
	assert(mock.freed_nodes == 0)
	frame := easy.Frame{api = &api, handle = cast(^vs.VSFrame)&mock.frame_token, core = core.handle}
	failed_frame, frame_err := easy.retain_frame(&frame)
	expect(frame_err, .Allocation_Failed)
	assert(failed_frame.handle == nil && frame.handle != nil)
	easy.destroy_frame(&failed_frame)
	assert(mock.freed_frames == 0)

	args := easy.Map{api = &api, handle = cast(^vs.VSMap)&mock.args_token, core = core.handle}
	diagnostic: easy.Diagnostic
	mock.invoke_nil = true
	failed_result, invoke_err := easy.invoke(&core, "mock", "Failure", &args, &diagnostic)
	expect(invoke_err, .Allocation_Failed)
	assert(failed_result.handle == nil && mock.freed_maps == 0)
	assert(args.handle != nil)

	mock.invoke_nil = false
	for &byte in mock.message[:len(mock.message)-1] {
		byte = 'x'
	}
	failed_result, err = easy.invoke(&core, "mock", "Failure", &args, &diagnostic)
	expect(err, .Invocation_Failed)
	assert(failed_result.handle == nil && mock.freed_maps == 1)
	assert(mock.freed_results == 1 && mock.freed_args == 0)
	assert(diagnostic.length == len(diagnostic.buffer)-1 && diagnostic.truncated)
	assert(args.handle != nil)
	// freeMap overwrites the source message, so this proves the diagnostic owns a copy.
	assert(mock.message[0] == 'z')
	for byte in easy.diagnostic_text(&diagnostic) {
		assert(byte == 'x')
	}
	easy.destroy_map(&failed_result)
	assert(mock.freed_maps == 1)

	easy.destroy_frame(&frame)
	easy.destroy_frame(&frame)
	easy.destroy_node(&node)
	easy.destroy_node(&node)
	easy.destroy_map(&args)
	easy.destroy_map(&args)
	easy.destroy_core(&core)
	easy.destroy_core(&core)
	assert(mock.freed_frames == 1 && mock.freed_nodes == 1)
	assert(mock.freed_maps == 2 && mock.freed_cores == 1)
	assert(mock.freed_args == 1 && mock.freed_results == 1 && !mock.unexpected_map_free)
	assert(frame.handle == nil && node.handle == nil && args.handle == nil && core.handle == nil)
}

mock_create_core :: proc "system" (flags: c.int) -> ^vs.VSCore {
	return nil
}

mock_create_map :: proc "system" () -> ^vs.VSMap {
	return nil
}

mock_add_node_ref :: proc "system" (node: ^vs.VSNode) -> ^vs.VSNode {
	return nil
}

mock_add_frame_ref :: proc "system" (frame: ^vs.VSFrame) -> ^vs.VSFrame {
	return nil
}

mock_free_core :: proc "system" (core: ^vs.VSCore) {
	mock.freed_cores += 1
}

mock_free_map :: proc "system" (map_: ^vs.VSMap) {
	mock.freed_maps += 1
	switch map_ {
	case cast(^vs.VSMap)&mock.result_token:
		mock.freed_results += 1
		for &byte in mock.message[:len(mock.message)-1] {
			byte = 'z'
		}
	case cast(^vs.VSMap)&mock.args_token:
		mock.freed_args += 1
	case:
		mock.unexpected_map_free = true
	}
}

mock_free_node :: proc "system" (node: ^vs.VSNode) {
	mock.freed_nodes += 1
}

mock_free_frame :: proc "system" (frame: ^vs.VSFrame) {
	mock.freed_frames += 1
}

mock_get_plugin :: proc "system" (namespace: cstring, core: ^vs.VSCore) -> ^vs.VSPlugin {
	return cast(^vs.VSPlugin)&mock.plugin_token
}

mock_invoke :: proc "system" (plugin: ^vs.VSPlugin, name: cstring, args: ^vs.VSMap) -> ^vs.VSMap {
	if mock.invoke_nil {
		return nil
	}
	return cast(^vs.VSMap)&mock.result_token
}

mock_map_error :: proc "system" (map_: ^vs.VSMap) -> cstring {
	if map_ == cast(^vs.VSMap)&mock.result_token {
		return cast(cstring)raw_data(mock.message[:])
	}
	return nil
}
