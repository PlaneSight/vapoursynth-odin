// Translated from VapourSynth R76, commit aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7.
package vapoursynth

import "core:c"

VAPOURSYNTH_API_MAJOR :: 4
VAPOURSYNTH_API_MINOR :: 2
VAPOURSYNTH_API_VERSION :: (VAPOURSYNTH_API_MAJOR << 16) | VAPOURSYNTH_API_MINOR
VS_AUDIO_FRAME_SAMPLES :: 3072

// C enum typedefs remain C integers; the C API itself uses int for enum arguments.
// Untyped constants also fit mapSetInt's i64 and format IDs' u32 without casts.
VSColorFamily :: c.int
cfUndefined :: 0
cfGray :: 1
cfRGB :: 2
cfYUV :: 3

VSSampleType :: c.int
stInteger :: 0
stFloat :: 1

VSPresetVideoFormat :: c.int
pfNone :: 0
pfGray8 :: 0x10080000
pfGray9 :: 0x10090000
pfGray10 :: 0x100A0000
pfGray12 :: 0x100C0000
pfGray14 :: 0x100E0000
pfGray16 :: 0x10100000
pfGray32 :: 0x10200000
pfGrayH :: 0x11100000
pfGrayS :: 0x11200000
pfYUV410P8 :: 0x30080202
pfYUV411P8 :: 0x30080200
pfYUV440P8 :: 0x30080001
pfYUV420P8 :: 0x30080101
pfYUV422P8 :: 0x30080100
pfYUV444P8 :: 0x30080000
pfYUV420P9 :: 0x30090101
pfYUV422P9 :: 0x30090100
pfYUV444P9 :: 0x30090000
pfYUV420P10 :: 0x300A0101
pfYUV422P10 :: 0x300A0100
pfYUV444P10 :: 0x300A0000
pfYUV420P12 :: 0x300C0101
pfYUV422P12 :: 0x300C0100
pfYUV444P12 :: 0x300C0000
pfYUV420P14 :: 0x300E0101
pfYUV422P14 :: 0x300E0100
pfYUV444P14 :: 0x300E0000
pfYUV420P16 :: 0x30100101
pfYUV422P16 :: 0x30100100
pfYUV444P16 :: 0x30100000
pfYUV420PH :: 0x31100101
pfYUV420PS :: 0x31200101
pfYUV422PH :: 0x31100100
pfYUV422PS :: 0x31200100
pfYUV444PH :: 0x31100000
pfYUV444PS :: 0x31200000
pfRGB24 :: 0x20080000
pfRGB27 :: 0x20090000
pfRGB30 :: 0x200A0000
pfRGB36 :: 0x200C0000
pfRGB42 :: 0x200E0000
pfRGB48 :: 0x20100000
pfRGBH :: 0x21100000
pfRGBS :: 0x21200000

VSFilterMode :: c.int
fmParallel :: 0
fmParallelRequests :: 1
fmUnordered :: 2
fmFrameState :: 3

VSMediaType :: c.int
mtVideo :: 1
mtAudio :: 2

VSAudioChannels :: c.int
acFrontLeft :: 0
acFrontRight :: 1
acFrontCenter :: 2
acLowFrequency :: 3
acBackLeft :: 4
acBackRight :: 5
acFrontLeftOFCenter :: 6
acFrontRightOFCenter :: 7
acBackCenter :: 8
acSideLeft :: 9
acSideRight :: 10
acTopCenter :: 11
acTopFrontLeft :: 12
acTopFrontCenter :: 13
acTopFrontRight :: 14
acTopBackLeft :: 15
acTopBackCenter :: 16
acTopBackRight :: 17
acStereoLeft :: 29
acStereoRight :: 30
acWideLeft :: 31
acWideRight :: 32
acSurroundDirectLeft :: 33
acSurroundDirectRight :: 34
acLowFrequency2 :: 35

VSPropertyType :: c.int
ptUnset :: 0
ptInt :: 1
ptFloat :: 2
ptData :: 3
ptFunction :: 4
ptVideoNode :: 5
ptAudioNode :: 6
ptVideoFrame :: 7
ptAudioFrame :: 8

VSMapPropertyError :: c.int
peSuccess :: 0
peUnset :: 1
peType :: 2
peIndex :: 4
peError :: 3

VSMapAppendMode :: c.int
maReplace :: 0
maAppend :: 1

VSActivationReason :: c.int
arInitial :: 0
arAllFramesReady :: 1
arError :: -1

VSMessageType :: c.int
mtDebug :: 0
mtInformation :: 1
mtWarning :: 2
mtCritical :: 3
mtFatal :: 4

VSCoreCreationFlags :: c.int
ccfEnableGraphInspection :: 1
ccfDisableAutoLoading :: 2
ccfDisableLibraryUnloading :: 4
ccfEnableFrameRefDebug :: 8

VSPluginConfigFlags :: c.int
pcModifiable :: 1

VSDataTypeHint :: c.int
dtUnknown :: -1
dtBinary :: 0
dtUtf8 :: 1

VSRequestPattern :: c.int
rpGeneral :: 0
rpNoFrameReuse :: 1
rpStrictSpatial :: 2
rpFrameReuseLastOnly :: 3

VSCacheMode :: c.int
cmAuto :: -1
cmForceDisable :: 0
cmForceEnable :: 1

VS_MAKE_VERSION :: proc "contextless" (major, minor: c.int) -> c.int {
	return (major << 16) | minor
}
