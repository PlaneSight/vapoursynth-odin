// Bindings to VapourSynth R76 include/VSScript4.h, with VSSCRIPT_USE_API_42.
package vsscript

import "core:c"
import vs ".."

VSSCRIPT_API_MAJOR :: 4
VSSCRIPT_API_MINOR :: 2
VSSCRIPT_API_VERSION :: (VSSCRIPT_API_MAJOR << 16) | VSSCRIPT_API_MINOR

// Opaque script environment. Obtain from createScript; release with freeScript.
VSScript :: struct {}

// Binding-provided function type for applications resolving getVSScriptAPI themselves.
// Pass VSSCRIPT_API_VERSION; nil means initialization failed or the API is unsupported.
VSGetVSScriptAPI :: proc "system" (version: c.int) -> ^VSSCRIPTAPI

// Borrowed function table owned by VSScript. Do not modify it or free it.
// An environment in the error state only permits getError and freeScript.
VSSCRIPTAPI :: struct {
	getAPIVersion: proc "system" () -> c.int,
	getVSAPI: proc "system" (version: c.int) -> ^vs.VSAPI,

	// Takes ownership of core even on failure. nil requests a default core.
	// Returns nil on failure; never free the supplied core after this call.
	createScript: proc "system" (core: ^vs.VSCore) -> ^VSScript,
	// Borrowed core valid until freeScript; nil indicates an error.
	getCore: proc "system" (handle: ^VSScript) -> ^vs.VSCore,

	// Return zero on success. After failure, only getError and freeScript are valid.
	evaluateBuffer: proc "system" (handle: ^VSScript, buffer: cstring, scriptFilename: cstring) -> c.int,
	evaluateFile: proc "system" (handle: ^VSScript, scriptFilename: cstring) -> c.int,
	// Borrowed until the next VSScript operation on handle; nil means success.
	getError: proc "system" (handle: ^VSScript) -> cstring,
	getExitCode: proc "system" (handle: ^VSScript) -> c.int,

	// Return zero on success. getVariable stores the result under name in dst.
	getVariable: proc "system" (handle: ^VSScript, name: cstring, dst: ^vs.VSMap) -> c.int,
	setVariables: proc "system" (handle: ^VSScript, vars: ^vs.VSMap) -> c.int,

	// Return owned references, or nil if the output is absent. Release each node
	// with VSAPI.freeNode before freeScript, including nodes derived from outputs.
	getOutputNode: proc "system" (handle: ^VSScript, index: c.int) -> ^vs.VSNode,
	getOutputAlphaNode: proc "system" (handle: ^VSScript, index: c.int) -> ^vs.VSNode,
	getAltOutputMode: proc "system" (handle: ^VSScript, index: c.int) -> c.int,

	// Finish pending frame requests and release all obtained frames and nodes first.
	// Frees the environment and its core; nil is accepted.
	freeScript: proc "system" (handle: ^VSScript),
	// Controls temporary working-directory changes during evaluateFile. Initially off.
	evalSetWorkingDir: proc "system" (handle: ^VSScript, setCWD: c.int),

	// API 4.2: writes at most size indices; returns the total number available.
	getAvailableOutputNodes: proc "system" (handle: ^VSScript, size: c.int, dst: [^]c.int) -> c.int,
}
