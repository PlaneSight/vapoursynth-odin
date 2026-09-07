// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:c"
import vs "vapoursynth:."
import script "vapoursynth:vsscript"

filter_callback: vs.VSFilterGetFrame = proc "system" (
    n, activation_reason: c.int,
    instance_data: rawptr,
    frame_data: ^rawptr,
    frame_context: ^vs.VSFrameContext,
    core: ^vs.VSCore,
    api: ^vs.VSAPI,
) -> ^vs.VSFrame {
    if n != 1234567 || activation_reason != vs.arError || frame_context != nil {
        return nil
    }
    if (^i64)(instance_data)^ != -0x123456789abcdef || frame_data^ != instance_data {
        return nil
    }
    frame_data^ = api
    return cast(^vs.VSFrame)core
}

test_calls :: proc() {
    api := abi_get_api()
    assert(api != nil)

    audio: vs.VSAudioFormat
    assert(api.queryAudioFormat(&audio, vs.stFloat, 64, 0x8000000100000003, nil) == 1)
    assert(audio.sampleType == vs.stFloat && audio.bitsPerSample == 64)
    assert(audio.numChannels == 4 && audio.channelLayout == 0x8000000100000003)

    error: c.int = -1
    assert(api.mapGetInt(nil, "integer", -17, &error) == -0x123456789abcdef)
    assert(error == vs.peIndex)
    assert(api.mapSetInt(nil, "integer", -0x123456789abcdef, vs.maAppend) == 1)
    assert(api.mapGetFloat(nil, "double", 19, &error) == -1234567.25)
    assert(error == vs.peSuccess)
    assert(api.mapGetFloatSaturated(nil, "float", 23, &error) == 123.5)
    assert(error == vs.peSuccess)
    when size_of(c.ptrdiff_t) == 8 {
        assert(api.getStride(nil, -2) == -0x100000002)
    } else {
        assert(api.getStride(nil, -2) == -123456)
    }

    video := vs.VSVideoFormat{colorFamily = vs.cfYUV}
    frame := abi_get_frame()
    sources := [2]^vs.VSFrame{nil, frame}
    planes := [2]c.int{2, 1}
    assert(api.newVideoFrame2(&video, 1920, 1080, &sources[0], &planes[0], nil, nil) == frame)

    info: vs.VSCoreInfo2
    api.getCoreInfo2(nil, &info)
    assert(info.apiVersion == vs.VAPOURSYNTH_API_VERSION && info.coreVersion == 76)
    assert(info.creationFlags == vs.ccfEnableFrameRefDebug && info.numThreads == 7)
    assert(info.maxFramebufferSize == 0x123456789abcdef)
    assert(info.usedFramebufferSize == 0x100000001)
    assert(info.versionString == "ABI shim")
    assert(abi_test_filter_callback(filter_callback) == 1)

    outputs: [2]c.int
    script_api := abi_get_script_api()
    assert(script_api.getAvailableOutputNodes(nil, 2, &outputs[0]) == 5)
    assert(outputs == [2]c.int{3, 11})
}
