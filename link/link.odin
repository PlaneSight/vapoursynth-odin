// SPDX-License-Identifier: LGPL-2.1-or-later
package vapoursynth_link

import "core:c"
import vs ".."

// Override with -define:VAPOURSYNTH_LIBRARY=/absolute/path/to/library.
VAPOURSYNTH_LIBRARY :: #config(
	VAPOURSYNTH_LIBRARY,
	"system:vapoursynth.lib" when ODIN_OS == .Windows else "system:vapoursynth",
)
foreign import library {VAPOURSYNTH_LIBRARY}

foreign library {
	// Pass vs.VAPOURSYNTH_API_VERSION and check for nil before using the table.
	getVapourSynthAPI :: proc "system" (version: c.int) -> ^vs.VSAPI ---
}
