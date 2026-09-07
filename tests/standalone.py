#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Copy projects outside the checkout, then build, render, and package them with uv."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parent.parent
PROJECTS = {
    **{name: ROOT / "examples" / name for name in (
        "core_info", "properties", "easy_host", "host", "plugin", "invert", "dither", "haldlut",
    )},
    "dither_plus": ROOT / "plugins" / "dither",
}


def check(name: str, python: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"odin standalone {name} ") as temporary:
        project = Path(temporary) / name
        shutil.copytree(
            PROJECTS[name], project,
            ignore=shutil.ignore_patterns(".build", ".deps", ".venv", "dist", "__pycache__"),
        )
        assert not project.resolve().is_relative_to(ROOT)
        manifest = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
        plugin = manifest["tool"]["odin"]["kind"] == "plugin"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("VIRTUAL_ENV", None)
        environment.pop("UV_PROJECT_ENVIRONMENT", None)
        environment.pop("UV_PYTHON_INSTALL_DIR", None)
        environment["UV_CACHE_DIR"] = str(Path(temporary) / "uv-cache")
        environment["UV_PYTHON"] = python

        def run(*arguments: str) -> None:
            subprocess.run(["uv", *arguments], cwd=project, env=environment, check=True, timeout=300)

        print(f"Checking copied project: {project}", flush=True)
        run("run", "--locked", "build.py", "--check" if plugin else "--run")
        revision = manifest["tool"]["odin"]["bindings"]["revision"]
        assert (project / ".deps" / revision / "src" / "vapoursynth" / "api.odin").is_file()
        if not plugin:
            return
        run("build")  # uv builds the wheel from the sdist, exercising its completeness too.
        wheels = list((project / "dist").glob("*.whl"))
        assert len(wheels) == 1, wheels
        with zipfile.ZipFile(wheels[0]) as wheel:
            libraries = [name for name in wheel.namelist() if name.endswith((".dll", ".so", ".dylib"))]
            assert len(libraries) == 1 and libraries[0].startswith("vapoursynth/plugins/"), libraries
            assert not any("/.deps/" in name or "/.venv/" in name for name in wheel.namelist())
        run("venv", "--python", python, ".build/wheel-env")
        wheel_python = project / ".build" / "wheel-env" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run("pip", "install", "--python", str(wheel_python), str(wheels[0]))
        probe = (
            "import vapoursynth as vs; "
            "plugins = [p for p in vs.core.plugins() if p.namespace.startswith('odin_')]; "
            "assert len(plugins) == 1, plugins; "
            "print('Isolated wheel autoload:', plugins[0].namespace)"
        )
        subprocess.run([str(wheel_python), "-c", probe], cwd=project, env=environment, check=True, timeout=60)
        print(f"PASS {name}: downloaded bindings, rendered preview, sdist, wheel, isolated autoload", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("projects", nargs="*", help="Project names; default: invert. Use --all for all nine.")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--python", default=sys.executable, help="Interpreter for copied projects and isolated wheels")
    args = parser.parse_args()
    selected = tuple(PROJECTS) if args.all else args.projects or ("invert",)
    for name in selected:
        if name not in PROJECTS:
            parser.error(f"Unknown project: {name}")
        check(name, args.python)
