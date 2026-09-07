// Bindings to VapourSynth R76 include/VSScript4.h, with VSSCRIPT_USE_API_42.
package vsscript_link

import "core:c"
import vsscript ".."

// Override with -define:VSSCRIPT_LIBRARY=<library path> when outside the linker search path.
VSSCRIPT_LIBRARY :: #config(
	VSSCRIPT_LIBRARY,
	"system:vsscript.lib" when ODIN_OS == .Windows else "system:vsscript",
)

foreign import lib {VSSCRIPT_LIBRARY}

foreign lib {
	// Pass vsscript.VSSCRIPT_API_VERSION. Returns nil if initialization fails
	// or the requested API is unavailable. The returned table belongs to VSScript.
	getVSScriptAPI :: proc "system" (version: c.int) -> ^vsscript.VSSCRIPTAPI ---
}
