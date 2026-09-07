package easy

import "core:dynlib"
import "core:fmt"
import vs ".."

DEFAULT_LIBRARY :: "libvapoursynth.dll" when ODIN_OS == .Windows else
	"libvapoursynth.dylib" when ODIN_OS == .Darwin else "libvapoursynth.so"

load_library :: proc(path := DEFAULT_LIBRARY, diagnostic: ^Diagnostic = nil) -> (Library, Error) {
	clear_diagnostic(diagnostic)
	if len(path) == 0 {
		return {}, .Invalid_Argument
	}
	library, loaded := dynlib.load_library(path)
	if !loaded {
		loader_error := dynlib.last_error()
		if diagnostic != nil {
			message := fmt.bprintf(diagnostic.buffer[:len(diagnostic.buffer)-1], "%v", loader_error)
			diagnostic.length = len(message)
			diagnostic.truncated = diagnostic.length == len(diagnostic.buffer)-1
		}
		return {}, .Library_Load_Failed
	}

	symbol, found := dynlib.symbol_address(library, "getVapourSynthAPI")
	if !found {
		unloaded := dynlib.unload_library(library)
		ensure(unloaded, "Could not unload the rejected library")
		write_diagnostic(diagnostic, "The library does not export getVapourSynthAPI.")
		return {}, .Symbol_Not_Found
	}
	get_api := cast(vs.VSGetVapourSynthAPI)symbol
	api := get_api(vs.VAPOURSYNTH_API_VERSION)
	if api == nil {
		unloaded := dynlib.unload_library(library)
		ensure(unloaded, "Could not unload the rejected library")
		write_diagnostic(diagnostic, "The library does not support VapourSynth API 4.2.")
		return {}, .Unsupported_API
	}
	return Library{handle = library, api = api}, .None
}

// Call only after destroying all cores and objects obtained from the library.
// On failure the owner is preserved so the caller can handle or retry unloading.
unload_library :: proc(library: ^Library) -> Error {
	if library == nil || library.handle == nil {
		return .None
	}
	if !dynlib.unload_library(library.handle) {
		return .Library_Unload_Failed
	}
	library^ = {}
	return .None
}
