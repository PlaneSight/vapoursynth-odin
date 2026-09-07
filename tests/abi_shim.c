// SPDX-License-Identifier: LGPL-2.1-or-later
#include "VapourSynth4.h"
#include "VSScript4.h"

#include <string.h>

static int frame_token;
static int core_token;

static int VS_CC test_query_audio_format(VSAudioFormat *format, int sample_type,
                                        int bits, uint64_t channels, VSCore *core) {
    if (sample_type != stFloat || bits != 64 || channels != UINT64_C(0x8000000100000003) || core)
        return 0;
    format->sampleType = sample_type;
    format->bitsPerSample = bits;
    format->bytesPerSample = 8;
    format->numChannels = 4;
    format->channelLayout = channels;
    return 1;
}

static int64_t VS_CC test_map_get_int(const VSMap *map, const char *key, int index, int *error) {
    if (map || strcmp(key, "integer") || index != -17)
        return 0;
    *error = peIndex;
    return -INT64_C(0x123456789abcdef);
}

static int VS_CC test_map_set_int(VSMap *map, const char *key, int64_t value, int append) {
    return !map && !strcmp(key, "integer") && value == -INT64_C(0x123456789abcdef) && append == maAppend;
}

static double VS_CC test_map_get_float(const VSMap *map, const char *key, int index, int *error) {
    if (map || strcmp(key, "double") || index != 19)
        return 0;
    *error = peSuccess;
    return -1234567.25;
}

static float VS_CC test_map_get_float_saturated(const VSMap *map, const char *key, int index, int *error) {
    if (map || strcmp(key, "float") || index != 23)
        return 0;
    *error = peSuccess;
    return 123.5f;
}

static ptrdiff_t VS_CC test_get_stride(const VSFrame *frame, int plane) {
    if (frame || plane != -2)
        return 0;
#if PTRDIFF_MAX > INT32_MAX
    return -(ptrdiff_t)INT64_C(0x100000002);
#else
    return -(ptrdiff_t)123456;
#endif
}

static VSFrame *VS_CC test_new_video_frame(const VSVideoFormat *format, int width, int height,
                                          const VSFrame **sources, const int *planes,
                                          const VSFrame *props, VSCore *core) {
    if (format->colorFamily != cfYUV || width != 1920 || height != 1080 || props || core)
        return NULL;
    if (sources[0] || sources[1] != (const VSFrame *)&frame_token || planes[0] != 2 || planes[1] != 1)
        return NULL;
    return (VSFrame *)&frame_token;
}

static void VS_CC test_get_core_info(VSCore *core, VSCoreInfo2 *info) {
    if (core)
        return;
    info->versionString = "ABI shim";
    info->coreVersion = 76;
    info->apiVersion = VAPOURSYNTH_API_VERSION;
    info->creationFlags = ccfEnableFrameRefDebug;
    info->numThreads = 7;
    info->maxFramebufferSize = INT64_C(0x123456789abcdef);
    info->usedFramebufferSize = INT64_C(0x100000001);
}

static VSAPI api = {
    .newVideoFrame2 = test_new_video_frame,
    .getStride = test_get_stride,
    .queryAudioFormat = test_query_audio_format,
    .mapGetInt = test_map_get_int,
    .mapSetInt = test_map_set_int,
    .mapGetFloat = test_map_get_float,
    .mapGetFloatSaturated = test_map_get_float_saturated,
    .getCoreInfo2 = test_get_core_info,
};

const VSAPI *VS_CC abi_get_api(void) {
    return &api;
}

const VSFrame *VS_CC abi_get_frame(void) {
    return (const VSFrame *)&frame_token;
}

int VS_CC abi_test_filter_callback(VSFilterGetFrame callback) {
    int64_t instance = -INT64_C(0x123456789abcdef);
    void *frame_data = &instance;
    const VSFrame *result = callback(1234567, arError, &instance, &frame_data,
                                     NULL, (VSCore *)&core_token, &api);
    return result == (const VSFrame *)&core_token && frame_data == &api;
}

static int VS_CC test_available_outputs(VSScript *handle, int size, int *destination) {
    if (handle || size != 2)
        return -1;
    destination[0] = 3;
    destination[1] = 11;
    return 5;
}

static VSSCRIPTAPI script_api = {
    .getAvailableOutputNodes = test_available_outputs,
};

const VSSCRIPTAPI *VS_CC abi_get_script_api(void) {
    return &script_api;
}
