# SPDX-License-Identifier: LGPL-2.1-or-later
"""Minimal source trees for exercising the real standalone build entry point."""

from pathlib import Path
import shutil


REPOSITORY = Path(__file__).resolve().parent.parent


def create_project(root: Path, relative: str) -> None:
    project = root / relative
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "plugin.odin").write_text("package example\n", encoding="utf-8")
    for filename in ("build.py", "pyproject.toml"):
        shutil.copyfile(REPOSITORY / relative / filename, project / filename)
    (root / "src" / "vapoursynth").mkdir(parents=True, exist_ok=True)
    (root / "src" / "vapoursynth" / "api.odin").touch()
    (root / "tools").mkdir(exist_ok=True)
    (root / "tools" / "native_build.py").write_text(
        "from tools.native_build import native_target, prepare_stb_image\n", encoding="utf-8",
    )
