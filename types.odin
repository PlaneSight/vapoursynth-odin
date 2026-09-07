// SPDX-License-Identifier: LGPL-2.1-or-later
// Translated from VapourSynth R76, commit aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7.
// Copyright (c) 2012-2026 Fredrik Mellbin. See LICENSE and tests/headers/.
package vapoursynth

import "core:c"

// Opaque handles: use pointers returned by VapourSynth; never allocate these structs.
VSFrame :: struct {}
VSNode :: struct {}
VSCore :: struct {}
VSPlugin :: struct {}
VSPluginFunction :: struct {}
VSFunction :: struct {}
VSMap :: struct {}
VSLogHandle :: struct {}
VSFrameContext :: struct {}

VSVideoFormat :: struct {
	colorFamily: c.int,
	sampleType: c.int,
	bitsPerSample: c.int,
	bytesPerSample: c.int,
	subSamplingW: c.int,
	subSamplingH: c.int,
	numPlanes: c.int,
}

VSAudioFormat :: struct {
	sampleType: c.int,
	bitsPerSample: c.int,
	bytesPerSample: c.int,
	numChannels: c.int,
	channelLayout: u64,
}

VSCoreInfo :: struct {
	versionString: cstring,
	core: c.int,
	api: c.int,
	numThreads: c.int,
	maxFramebufferSize: i64,
	usedFramebufferSize: i64,
}

VSCoreInfo2 :: struct {
	versionString: cstring,
	coreVersion: c.int,
	apiVersion: c.int,
	creationFlags: c.int,
	numThreads: c.int,
	maxFramebufferSize: i64,
	usedFramebufferSize: i64,
}

VSVideoInfo :: struct {
	format: VSVideoFormat,
	fpsNum: i64,
	fpsDen: i64,
	width: c.int,
	height: c.int,
	numFrames: c.int,
}

VSAudioInfo :: struct {
	format: VSAudioFormat,
	sampleRate: c.int,
	numSamples: i64,
	numFrames: c.int,
}

VSFilterDependency :: struct {
	source: ^VSNode,
	requestPattern: c.int,
}

// VS_CC: stdcall on 32-bit Windows, the C calling convention elsewhere.
VSGetVapourSynthAPI :: #type proc "system" (version: c.int) -> ^VSAPI
VSPublicFunction :: #type proc "system" (in_: ^VSMap, out: ^VSMap, userData: rawptr, core: ^VSCore, vsapi: ^VSAPI)
VSInitPlugin :: #type proc "system" (plugin: ^VSPlugin, vspapi: ^VSPLUGINAPI)
VSFreeFunctionData :: #type proc "system" (userData: rawptr)
VSFilterGetFrame :: #type proc "system" (
	n: c.int,
	activationReason: c.int,
	instanceData: rawptr,
	frameData: ^rawptr,
	frameCtx: ^VSFrameContext,
	core: ^VSCore,
	vsapi: ^VSAPI,
) -> ^VSFrame
VSFilterFree :: #type proc "system" (instanceData: rawptr, core: ^VSCore, vsapi: ^VSAPI)
VSFrameDoneCallback :: #type proc "system" (userData: rawptr, f: ^VSFrame, n: c.int, node: ^VSNode, errorMsg: cstring)
VSLogHandler :: #type proc "system" (msgType: c.int, msg: cstring, userData: rawptr)
VSLogHandlerFree :: #type proc "system" (userData: rawptr)
