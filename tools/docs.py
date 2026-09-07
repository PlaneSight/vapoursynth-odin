#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compile examples, render their preview outputs, and build or serve Zensical."""

import argparse
from pathlib import Path
import subprocess
import sys
import tomllib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.examples import EXAMPLES, ROOT, build_examples
from tools.render_showcase import render_all


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "serve"))
    parser.add_argument("--odin", default="odin", help="Odin compiler executable")
    parser.add_argument("--config-file", type=Path, help="Zensical configuration, such as the generated Pages overlay")
    parser.add_argument("--base-path", default="", help="Site URL prefix for the generated-link checker")
    parser.add_argument("--dev-addr", help="Serve on HOST:PORT instead of the default local address")
    args = parser.parse_args()
    if args.dev_addr is not None and args.command != "serve":
        parser.error("--dev-addr is only available with serve")
    try:
        config_path = args.config_file.resolve() if args.config_file else ROOT / "zensical.toml"
        with config_path.open("rb") as source:
            project = tomllib.load(source)["project"]
        docs_directory = (config_path.parent / project.get("docs_dir", "docs")).resolve()
        site_directory = (config_path.parent / project.get("site_dir", "site")).resolve()
        build_examples(tuple(EXAMPLES), odin=args.odin)
        render_all(docs_directory / "assets" / "generated")
        command = [sys.executable, "-m", "zensical", args.command]
        if args.command == "build":
            command.extend(("--clean", "--strict"))
        if args.config_file is not None:
            command.extend(("--config-file", str(args.config_file.resolve())))
        if args.dev_addr is not None:
            command.extend(("--dev-addr", args.dev_addr))
        subprocess.run(command, cwd=ROOT, check=True)
        if args.command == "build":
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "check_docs.py"),
                 "--site-dir", str(site_directory), "--base-path", args.base_path],
                cwd=ROOT, check=True,
            )
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Documentation {args.command} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
