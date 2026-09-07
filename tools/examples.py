#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the Odin examples, check their output frames, or open them in VSView."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from collections.abc import Iterable, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.native_build import native_target


ROOT = Path(__file__).resolve().parent.parent
HOST_NAMES = ("core_info", "properties", "easy_host", "host")
PLUGIN_NAMES = ("plugin", "invert", "dither", "haldlut")
EXAMPLES = {name: ROOT / "examples" / name for name in (*HOST_NAMES, *PLUGIN_NAMES)}
CHECK_TIMEOUT = 120


def selected_examples(names: Iterable[str], *, plugins_only: bool = False) -> tuple[str, ...]:
    available = PLUGIN_NAMES if plugins_only else tuple(EXAMPLES)
    selected = tuple(dict.fromkeys(names))
    unknown = [name for name in selected if name not in available]
    if unknown:
        raise ValueError(f"Unknown example: {', '.join(unknown)}. Choose from: {', '.join(available)}")
    return selected or available


def build_examples(names: Iterable[str], odin: str = "odin") -> dict[str, Path]:
    """Compile selected examples and publish artifacts only after all builds succeed."""
    selected = selected_examples(names)
    compiler = shutil.which(odin)
    if compiler is None:
        raise RuntimeError(f"Cannot find Odin compiler: {odin}. Install Odin or pass --odin PATH.")
    target = native_target(sysconfig.get_platform())
    for name in selected:
        source = EXAMPLES[name]
        if not (source / "build.py").is_file() or not any((source / "src").glob("*.odin")):
            raise RuntimeError(f"Missing Odin example sources: {source}")

    build_directory = ROOT / ".build" / "examples"
    build_directory.mkdir(parents=True, exist_ok=True)
    artifacts = {
        name: build_directory / f"{name}{target.extension if name in PLUGIN_NAMES else target.executable_suffix}"
        for name in selected
    }
    with tempfile.TemporaryDirectory(prefix="compile-", dir=build_directory) as directory:
        staging = Path(directory)
        for name, artifact in artifacts.items():
            output = staging / artifact.name
            print(f"Building {name}", flush=True)
            project = runpy.run_path(str(EXAMPLES[name] / "build.py"))
            project["build"](compiler, bindings=ROOT, output=output, target=target)
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(f"Odin did not produce a nonempty artifact: {output}")
        for name, artifact in artifacts.items():
            try:
                (staging / artifact.name).replace(artifact)
            except PermissionError as error:
                raise RuntimeError(
                    f"Cannot replace {artifact}. Close any preview or process using this example, then rebuild."
                ) from error
            print(f"Built {name}: {artifact}", flush=True)
            local = EXAMPLES[name] / ".build" / artifact.name
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, local)
    return artifacts


def example_scripts(names: Iterable[str]) -> list[Path]:
    scripts = [EXAMPLES[name] / "preview.vpy" for name in selected_examples(names, plugins_only=True)]
    for script in scripts:
        if not script.is_file():
            raise RuntimeError(f"Missing preview script: {script}")
    return scripts


def check_script(script: Path) -> None:
    """Execute one graph and request its boundary frames in an isolated process."""
    import vapoursynth as vs

    try:
        runpy.run_path(str(script), run_name="__main__")
        outputs = vs.get_outputs()
        if not outputs:
            raise RuntimeError("the script did not register any outputs")
        for index, output in sorted(outputs.items()):
            clip = output.clip if isinstance(output, vs.VideoOutputTuple) else output
            if not isinstance(clip, vs.VideoNode):
                raise RuntimeError(f"output {index} is not a video node")
            if clip.format is None or clip.width <= 0 or clip.height <= 0 or clip.num_frames <= 0:
                raise RuntimeError(f"output {index} must have a fixed format, dimensions, and positive frame count")
            for frame_number in dict.fromkeys((0, clip.num_frames - 1)):
                with clip.get_frame(frame_number) as frame:
                    if (frame.width, frame.height, frame.format.id) != (clip.width, clip.height, clip.format.id):
                        raise RuntimeError(f"output {index}, frame {frame_number} differs from its declared video format")
            print(
                f"{script.relative_to(ROOT).as_posix()}: output {index}: {clip.width} x {clip.height} {clip.format.name}, "
                f"{clip.num_frames} frames; first and last frames passed",
                flush=True,
            )
    except Exception as error:
        raise RuntimeError(f"Cannot render {script}: {error}") from error
    finally:
        vs.clear_outputs()


def check_examples(names: Iterable[str]) -> None:
    for script in example_scripts(names):
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "_check-script", str(script)],
            cwd=ROOT, check=True, timeout=CHECK_TIMEOUT,
        )


def require_dependency(module: str) -> None:
    if importlib.util.find_spec(module) is not None:
        return
    if module == "vsview":
        raise RuntimeError(
            "VSView is not installed in this environment. "
            "Run: uv run --group preview tools/examples.py preview"
        )
    raise RuntimeError("VapourSynth is not installed in this environment. Run this command with uv run.")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, description in (
        ("build", "Compile the eight binding examples, or only the selected names."),
        ("check", "Build and render every output of the plugin demonstrations without a GUI."),
        ("preview", "Build and open the plugin demonstrations in VSView; pass its options after --."),
    ):
        subparser = subparsers.add_parser(command, help=description, description=description)
        available = tuple(EXAMPLES) if command == "build" else PLUGIN_NAMES
        subparser.add_argument("examples", nargs="*", metavar="EXAMPLE", help=f"Choices: {', '.join(available)}")
        subparser.add_argument("--odin", default="odin", help="Odin compiler executable")
        if command != "build":
            subparser.add_argument("--no-build", action="store_true", help="Use previously compiled example libraries")

    try:
        if len(arguments) == 2 and arguments[0] == "_check-script":
            check_script(Path(arguments[1]))
            return 0
        forwarded: list[str] = []
        if "--" in arguments:
            separator = arguments.index("--")
            arguments, forwarded = arguments[:separator], arguments[separator + 1:]
        args = parser.parse_args(arguments)
        if forwarded and args.command != "preview":
            parser.error("Only preview accepts VSView options after --")
        try:
            names = selected_examples(args.examples, plugins_only=args.command != "build")
        except ValueError as error:
            parser.error(str(error))
        if args.command == "build":
            build_examples(names, args.odin)
            return 0
        require_dependency("vsview" if args.command == "preview" else "vapoursynth")
        scripts = example_scripts(names)
        if not args.no_build:
            build_examples(names, args.odin)
        if args.command == "check":
            check_examples(names)
            return 0
        command = [sys.executable, "-m", "vsview", *map(str, scripts), *forwarded]
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except subprocess.TimeoutExpired as error:
        print(f"Error: command timed out after {error.timeout} seconds: {error.cmd}", file=sys.stderr)
    except subprocess.CalledProcessError as error:
        print(f"Error: command failed with exit status {error.returncode}: {error.cmd}", file=sys.stderr)
    except (OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
