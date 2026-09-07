// SPDX-License-Identifier: LGPL-2.1-or-later
package main

import "core:fmt"
import "core:os"

import vs "../.."
import easy "../../easy"

main :: proc() {
	if !run() {
		os.exit(1)
	}
}

run :: proc() -> bool {
	if len(os.args) > 2 {
		fmt.eprintln("Usage: properties [path-to-vapoursynth-library]")
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

	properties, map_error := easy.create_map(&core)
	if map_error != .None {
		fmt.eprintln("Create property map:", map_error)
		return false
	}
	defer easy.destroy_map(&properties)

	if !write_properties(&properties) {
		return false
	}
	return read_properties(&properties)
}

write_properties :: proc(properties: ^easy.Map) -> bool {
	if err := easy.map_set_int(properties, "frame_number", 42); err != .None {
		fmt.eprintln("Set frame number:", err)
		return false
	}
	if err := easy.map_set_float(properties, "exposure", 1.25); err != .None {
		fmt.eprintln("Set exposure:", err)
		return false
	}
	if err := easy.map_set_string(properties, "label", "example frame"); err != .None {
		fmt.eprintln("Set label:", err)
		return false
	}

	payload := [?]u8{65, 0, 66, 255}
	if err := easy.map_set_bytes(properties, "payload", payload[:]); err != .None {
		fmt.eprintln("Set binary payload:", err)
		return false
	}
	durations := [?]i64{1001, 1001, 1001}
	if err := easy.map_set_int_array(properties, "durations", durations[:]); err != .None {
		fmt.eprintln("Set durations:", err)
		return false
	}
	weights := [?]f64{0.25, 0.5, 0.25}
	if err := easy.map_set_float_array(properties, "weights", weights[:]); err != .None {
		fmt.eprintln("Set weights:", err)
		return false
	}
	if err := easy.map_set_int_array(properties, "empty", nil); err != .None {
		fmt.eprintln("Set empty integer array:", err)
		return false
	}
	return true
}

read_properties :: proc(properties: ^easy.Map) -> bool {
	frame_number, int_error := easy.map_get_int(properties, "frame_number")
	if int_error != .None {
		fmt.eprintln("Read frame number:", int_error)
		return false
	}
	exposure, float_error := easy.map_get_float(properties, "exposure")
	if float_error != .None {
		fmt.eprintln("Read exposure:", float_error)
		return false
	}
	label, string_error := easy.map_get_string(properties, "label")
	if string_error != .None {
		fmt.eprintln("Read label:", string_error)
		return false
	}
	payload, bytes_error := easy.map_get_bytes(properties, "payload")
	if bytes_error != .None {
		fmt.eprintln("Read binary payload:", bytes_error)
		return false
	}
	durations, ints_error := easy.map_get_int_array(properties, "durations")
	if ints_error != .None {
		fmt.eprintln("Read durations:", ints_error)
		return false
	}
	weights, floats_error := easy.map_get_float_array(properties, "weights")
	if floats_error != .None {
		fmt.eprintln("Read weights:", floats_error)
		return false
	}
	fmt.printf("Frame %d: %q; exposure: %.2f\n", frame_number, label, exposure)
	fmt.printf("Binary payload (%d bytes, including the embedded zero): %v\n", len(payload), payload)
	fmt.printf("Durations: %v; weights: %v\n", durations, weights)

	empty, empty_error := easy.map_get_int_array(properties, "empty")
	if empty_error != .None || len(empty) != 0 {
		fmt.eprintln("Expected an existing, empty integer array:", empty_error)
		return false
	}
	_, missing_error := easy.map_get_int(properties, "missing")
	if missing_error != .Missing_Key {
		fmt.eprintln("Expected a missing-key error:", missing_error)
		return false
	}
	fmt.printf("Existing empty array: %d elements; absent key: %v\n", len(empty), missing_error)
	return true
}
