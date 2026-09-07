// SPDX-License-Identifier: LGPL-2.1-or-later
package plugin

import "core:c"

import vs "deps:vapoursynth"

@(export)
VapourSynthPluginInit2 :: proc "system"(plugin: ^vs.VSPlugin, api: ^vs.VSPLUGINAPI) {
	if api.configPlugin(
		"org.vapoursynth.odin.example", "odin_example", "Odin identity example",
		1 << 16, vs.VAPOURSYNTH_API_VERSION, 0, plugin,
	) == 0 {
		return
	}
	api.registerFunction("Identity", "clip:vnode;", "clip:vnode;", identity, nil, plugin)
}

identity :: proc "system"(
	input, output: ^vs.VSMap,
	user_data: rawptr,
	core: ^vs.VSCore,
	api: ^vs.VSAPI,
) {
	property_error: c.int
	node := api.mapGetNode(input, "clip", 0, &property_error)
	if property_error != vs.peSuccess || node == nil {
		api.mapSetError(output, "Identity: expected a video clip.")
		return
	}

	// This transfers the reference returned by mapGetNode, including on failure.
	if api.mapConsumeNode(output, "clip", node, vs.maReplace) != 0 {
		api.mapSetError(output, "Identity: could not return the clip.")
	}
}
