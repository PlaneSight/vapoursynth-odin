// SPDX-License-Identifier: LGPL-2.1-or-later
package easy

diagnostic_text :: proc(diagnostic: ^Diagnostic) -> string {
	if diagnostic == nil {
		return ""
	}
	return string(diagnostic.buffer[:diagnostic.length])
}

@(private="package")
clear_diagnostic :: proc(diagnostic: ^Diagnostic) {
	if diagnostic != nil {
		diagnostic^ = {}
	}
}

@(private="package")
write_diagnostic :: proc(diagnostic: ^Diagnostic, message: string) {
	if diagnostic == nil {
		return
	}
	diagnostic^ = {}
	diagnostic.length = copy(diagnostic.buffer[:len(diagnostic.buffer)-1], message)
	diagnostic.truncated = len(message) > diagnostic.length
}
