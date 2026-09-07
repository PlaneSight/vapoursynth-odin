# SPDX-License-Identifier: LGPL-2.1-or-later
"""Package only this project's native plugin, using its normal build entry point."""

from pathlib import Path
import runpy
import sysconfig

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        if version != "standard":
            raise RuntimeError("Use uv build for native wheels; uv sync only installs dependencies")
        project = runpy.run_path(str(Path(self.root) / "build.py"))
        dependency = project["bindings_root"]()
        native = runpy.run_path(str(dependency / "tools" / "native_build.py"))
        target = native["native_target"](sysconfig.get_platform())
        artifact = project["build"](bindings=dependency, target=target)
        package = project["CONFIG"]["project"]["name"].replace("-", "_")
        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{target.wheel_platform}"
        build_data["force_include"] = {str(artifact): f"vapoursynth/plugins/{package}/{artifact.name}"}
