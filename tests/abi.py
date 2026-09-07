#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compare the bindings with pinned C headers, then exercise the C/Odin ABI.

Requires Python 3.14+, Odin, and a native C compiler (MSVC, Clang, or GCC).
No VapourSynth installation is required. Generated files stay in .build/abi.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
HEADERS = ROOT / "tests" / "headers"
BUILD = ROOT / ".build" / "abi"
INCLUDES = '#include "VapourSynth4.h"\n#include "VSConstants4.h"\n#include "VSScript4.h"\n'
MACROS = (
    "VAPOURSYNTH_API_MAJOR", "VAPOURSYNTH_API_MINOR", "VAPOURSYNTH_API_VERSION",
    "VS_AUDIO_FRAME_SAMPLES", "VSSCRIPT_API_MAJOR", "VSSCRIPT_API_MINOR",
    "VSSCRIPT_API_VERSION",
)


def run(command: list[str] | str, *, env: dict[str, str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        display = command if isinstance(command, str) else subprocess.list2cmdline(command)
        raise RuntimeError(
            f"Command failed ({result.returncode}): {display}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result.stdout


def find_compiler(requested: str | None) -> str:
    if requested:
        return shutil.which(requested) or str(Path(requested).resolve())
    if os.environ.get("CC"):
        return find_compiler(os.environ["CC"])
    if os.name == "nt":
        if compiler := shutil.which("cl"):
            return compiler
        visual_studio = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio"
        candidates = sorted(visual_studio.glob("*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"))
        if candidates:
            return str(candidates[-1])
    for name in ("cc", "clang", "gcc"):
        if compiler := shutil.which(name):
            return compiler
    raise RuntimeError("No C compiler found; select one with --cc.")


def compiler_environment(compiler: str) -> dict[str, str]:
    env = os.environ.copy()
    if Path(compiler).stem.lower() != "cl" or env.get("INCLUDE"):
        return env
    for parent in Path(compiler).parents:
        vcvars = parent / "Auxiliary" / "Build" / "vcvars64.bat"
        if not vcvars.is_file():
            continue
        # Capture the developer environment in this child process only.
        output = run(
            f'cmd.exe /d /s /c ""{vcvars}" >nul && set"',
            env=env, cwd=ROOT,
        )
        env.update(line.split("=", 1) for line in output.splitlines() if "=" in line and not line.startswith("="))
        return env
    raise RuntimeError("MSVC needs a developer command prompt or a compiler inside a Visual Studio installation.")


class Compiler:
    def __init__(self, executable: str):
        self.executable = executable
        self.msvc = Path(executable).stem.lower() == "cl"
        self.env = compiler_environment(executable)

    def flags(self, graph: bool) -> list[str]:
        definitions = ["VS_USE_API_42", "VSSCRIPT_USE_API_42"]
        if graph:
            definitions.append("VS_GRAPH_API")
        if self.msvc:
            return ["/nologo", "/TC", "/std:c11", "/W4", "/WX", f"/I{HEADERS}"] + [f"/D{name}" for name in definitions]
        return ["-std=c11", "-Wall", "-Wextra", "-Werror", f"-I{HEADERS}"] + [f"-D{name}" for name in definitions]

    def preprocess(self, source: Path, graph: bool) -> str:
        flags = ["/EP"] if self.msvc else ["-E", "-P"]
        return run([self.executable, *self.flags(graph), *flags, str(source)], env=self.env, cwd=source.parent)

    def compile(self, source: Path, destination: Path, *, graph: bool, object_only: bool = False) -> None:
        if self.msvc:
            flags = ["/c", f"/Fo{destination}"] if object_only else [f"/Fe{destination}", f"/Fo{destination.with_suffix('.obj')}"]
        else:
            flags = (["-c"] if object_only else []) + ["-o", str(destination)]
        run([self.executable, *self.flags(graph), str(source), *flags], env=self.env, cwd=destination.parent)


def declarations(header: str) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Read names only; the C compiler evaluates all types and expressions."""
    structures = {}
    for name, body in re.findall(r"\bstruct\s+(VS\w*)\s*\{([^{}]*)\}", header):
        fields = []
        for declaration in body.split(";"):
            if not declaration.strip():
                continue
            pointer = re.search(r"\(\s*(?:__stdcall\s+)?\*\s*(\w+)\s*\)", declaration)
            scalar = re.search(r"\b(\w+)\s*$", declaration)
            if not pointer and not scalar:
                raise RuntimeError(f"Unrecognized C field in {name}: {declaration}")
            fields.append((pointer or scalar).group(1))
        structures[name] = fields
    enums = re.findall(r"\btypedef\s+enum\s+(VS\w*)\s*\{([^{}]*)\}", header)
    constants = [name for _, body in enums for name in re.findall(r"\b(\w+)\s*=", body)]
    callbacks = re.findall(r"\btypedef\s+[^;{}]+\(\s*(?:__stdcall\s+)?\*\s*(VS\w+)\s*\)", header)
    types = [*structures, *(name for name, _ in enums), *callbacks]
    if len(structures) != 10 or len(callbacks) != 9:
        raise RuntimeError(f"Unexpected pinned headers: found {len(structures)} concrete structs and {len(callbacks)} callbacks.")
    return structures, types, constants + list(MACROS)


def qualified(name: str, graph: bool) -> str:
    if name.startswith("VSSCRIPT"):
        return f"script.{name}"
    if graph and name == "VSAPI":
        return "vs.VSGraphAPI"
    return f"vs.{name}"


def probes(header: str, stable_fields: list[str], graph: bool) -> tuple[str, str, int]:
    structures, types, constants = declarations(header)
    c_lines = [INCLUDES, '#include <stdio.h>', "int main(void) {"]
    odin_lines = ["package main", 'import "core:fmt"', 'import vs "deps:vapoursynth"',
                  'import script "deps:vapoursynth/vsscript"', "main :: proc() {", "    test_calls()"]
    count = 0

    def value(key: str, c_expression: str, odin_expression: str) -> None:
        nonlocal count
        c_lines.append(f'    printf("{key}=%lld\\n", (long long)({c_expression}));')
        odin_lines.append(f'    fmt.printf("{key}=%d\\n", {odin_expression})')
        count += 1

    for name in types:
        value(f"sizeof.{name}", f"sizeof({name})", f"size_of({qualified(name, graph)})")
        value(f"alignof.{name}", f"_Alignof({name})", f"align_of({qualified(name, graph)})")
    for name, fields in structures.items():
        for field in fields:
            offset = f"offset_of({qualified(name, graph)}, {field})"
            if graph and name == "VSAPI" and field in stable_fields:
                offset = f"offset_of(vs.VSGraphAPI, api) + offset_of(vs.VSAPI, {field})"
            value(f"offsetof.{name}.{field}", f"offsetof({name}, {field})", offset)
    for name in constants:
        value(f"constant.{name}", name, qualified(name, graph))
    c_lines.extend(["    return 0;", "}"])
    odin_lines.append("}")
    return "\n".join(c_lines) + "\n", "\n".join(odin_lines) + "\n", count


def metrics(output: str) -> dict[str, int]:
    result = {}
    for line in output.splitlines():
        key, value = line.split("=", 1)
        if key in result:
            raise RuntimeError(f"Duplicate ABI measurement: {key}")
        result[key] = int(value)
    return result


def verify(compiler: Compiler, odin: str, graph: bool, stable_fields: list[str]) -> list[str]:
    mode = "graph" if graph else "stable"
    directory = BUILD / mode
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "layout.c"
    source.write_text(INCLUDES, encoding="utf-8")
    header = compiler.preprocess(source, graph)
    structures, _, _ = declarations(header)
    c_probe, odin_probe, count = probes(header, stable_fields, graph)
    source.write_text(c_probe, encoding="utf-8")
    executable_suffix = ".exe" if os.name == "nt" else ""
    c_executable = directory / f"c_layout{executable_suffix}"
    compiler.compile(source, c_executable, graph=graph)
    expected = metrics(run([str(c_executable)], env=compiler.env, cwd=directory))

    odin_directory = directory / "odin"
    odin_directory.mkdir(exist_ok=True)
    shim = odin_directory / ("abi_shim.obj" if os.name == "nt" else "abi_shim.o")
    compiler.compile(ROOT / "tests" / "abi_shim.c", shim, graph=graph, object_only=True)
    (odin_directory / "main.odin").write_text(odin_probe, encoding="utf-8")
    shutil.copyfile(ROOT / "tests" / "abi_calls.odin", odin_directory / "calls.odin")
    (odin_directory / "shim.odin").write_text(
        'package main\nimport "core:c"\nimport vs "deps:vapoursynth"\nimport script "deps:vapoursynth/vsscript"\n'
        f'foreign import shim "{shim.name}"\n'
        'foreign shim {\n'
        '    abi_get_api :: proc "system" () -> ^vs.VSAPI ---\n'
        '    abi_get_frame :: proc "system" () -> ^vs.VSFrame ---\n'
        '    abi_test_filter_callback :: proc "system" (callback: vs.VSFilterGetFrame) -> c.int ---\n'
        '    abi_get_script_api :: proc "system" () -> ^script.VSSCRIPTAPI ---\n'
        '}\n', encoding="utf-8",
    )
    odin_executable = directory / f"odin_layout{executable_suffix}"
    run([odin, "build", str(odin_directory), f"-out:{odin_executable}", f"-collection:deps={ROOT / 'src'}"],
        env=compiler.env, cwd=directory)
    actual = metrics(run([str(odin_executable)], env=compiler.env, cwd=directory))
    differences = [f"{key}: C={expected.get(key)}, Odin={actual.get(key)}"
                   for key in sorted(expected.keys() | actual.keys()) if expected.get(key) != actual.get(key)]
    if differences:
        raise RuntimeError(f"{mode} ABI mismatch:\n" + "\n".join(differences))
    if len(expected) != count:
        raise RuntimeError(f"Expected {count} measurements, received {len(expected)}.")
    print(f"PASS {mode}: {count} sizes, alignments, field offsets and constants; C/Odin calls passed.")
    return structures["VSAPI"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", help="C compiler executable; defaults to CC, MSVC on Windows, or cc/clang/gcc")
    parser.add_argument("--odin", default="odin", help="Odin compiler executable (default: odin)")
    args = parser.parse_args()
    try:
        compiler = Compiler(find_compiler(args.cc))
        odin = shutil.which(args.odin) or str(Path(args.odin).resolve())
        print(f"C compiler: {compiler.executable}")
        fields = verify(compiler, odin, graph=False, stable_fields=[])
        verify(compiler, odin, graph=True, stable_fields=fields)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ABI verification failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
