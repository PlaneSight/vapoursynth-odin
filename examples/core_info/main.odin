// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:fmt"
import "core:os"

import vs "../../src/vapoursynth"
import easy "../../src/vapoursynth/easy"

main :: proc() {
	if !run() {
		os.exit(1)
	}
}

run :: proc() -> bool {
	if len(os.args) > 2 {
		fmt.eprintln("Usage: core_info [path-to-vapoursynth-library]")
		return false
	}
	library_path := easy.DEFAULT_LIBRARY
	if len(os.args) == 2 {
		library_path = os.args[1]
	}

	diagnostic: easy.Diagnostic
	library, load_error := easy.load_library(library_path, &diagnostic)
	if load_error != .None {
		fmt.eprintln("Load core library:", load_error, easy.diagnostic_text(&diagnostic))
		return false
	}
	defer {
		unload_error := easy.unload_library(&library)
		ensure(unload_error == .None)
	}

	core, create_error := easy.create_core(library.api, vs.ccfDisableAutoLoading)
	if create_error != .None {
		fmt.eprintln("Create core:", create_error)
		return false
	}
	defer easy.destroy_core(&core)

	info, info_error := easy.core_info(&core)
	if info_error != .None {
		fmt.eprintln("Read core information:", info_error)
		return false
	}
	fmt.println(info.versionString)
	fmt.printf("Core version: %d; API: %d.%d; threads: %d\n",
		info.coreVersion, info.apiVersion >> 16, info.apiVersion & 0xffff, info.numThreads)
	return true
}
