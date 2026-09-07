"""Build this Odin project; uv supplies Python dependencies, Odin supplies the compiler."""

import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import tomllib
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parent
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
NATIVE = CONFIG["tool"]["odin"]


def validate_bindings(root: Path) -> Path:
    for relative in ("src/vapoursynth/api.odin", "tools/native_build.py"):
        if not (root / relative).is_file():
            raise RuntimeError(f"Incomplete bindings dependency: {root / relative}")
    return root


def bindings_root(override: Path | None = None) -> Path:
    """Use an explicit checkout, or the verified source archive pinned in pyproject.toml."""
    if override is not None:
        return validate_bindings(override.resolve())

    dependency = NATIVE["bindings"]
    revision, digest = dependency["revision"], dependency["sha256"]
    if not re.fullmatch(r"[a-f0-9]{40}", revision) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise RuntimeError("Bindings require a full Git commit and SHA-256 archive checksum")
    cache = ROOT / ".deps" / revision
    if (cache / ".sha256").is_file() and (cache / ".sha256").read_text() == digest:
        return validate_bindings(cache)
    if cache.exists():
        raise RuntimeError(f"Incomplete dependency cache: {cache}. Remove this directory and rebuild.")

    url = f"https://codeload.github.com/{dependency['repository']}/zip/{revision}"
    print(f"Fetching pinned bindings: {url}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        archive = response.read(32 * 1024 * 1024 + 1)
    if hashlib.sha256(archive).hexdigest() != digest:
        raise RuntimeError("Bindings archive checksum mismatch; no downloaded code was executed")

    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="download-", dir=cache.parent) as temporary:
        staged = Path(temporary) / "bindings"
        staged.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for entry in bundle.infolist():
                relative = PurePosixPath(entry.filename)
                if len(relative.parts) < 2 or entry.is_dir():
                    continue
                relative = PurePosixPath(*relative.parts[1:])
                wanted = relative.parts[0] == "src" or str(relative) in (
                    "tools/native_build.py", "LICENSE", "THIRD_PARTY_LICENSES.md",
                )
                if not wanted:
                    continue
                destination = staged.joinpath(*relative.parts).resolve()
                if not destination.is_relative_to(staged.resolve()) or "\\" in entry.filename:
                    raise RuntimeError(f"Unsafe archive path: {entry.filename}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.read(entry))
        validate_bindings(staged)
        (staged / ".sha256").write_text(digest)
        staged.replace(cache)
    return cache


def build(odin: str = "odin", *, bindings: Path | None = None, output: Path | None = None, target=None) -> Path:
    compiler = shutil.which(odin)
    if compiler is None:
        raise RuntimeError(f"Cannot find Odin compiler: {odin}. Install Odin or pass --odin PATH.")
    source = ROOT / "src"
    if not any(source.glob("*.odin")):
        raise RuntimeError(f"Missing Odin sources: {source}")
    name = NATIVE["name"]
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or NATIVE["kind"] not in ("plugin", "host"):
        raise RuntimeError("tool.odin requires a simple lowercase name and kind = plugin or host")

    dependency = bindings_root(bindings)
    native = runpy.run_path(str(dependency / "tools" / "native_build.py"))
    target = target or native["native_target"](sysconfig.get_platform())
    plugin = NATIVE["kind"] == "plugin"
    suffix = target.extension if plugin else target.executable_suffix
    artifact = output or ROOT / ".build" / f"{name}{suffix}"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compile-", dir=artifact.parent) as temporary:
        staged = Path(temporary) / artifact.name
        extra = native["prepare_stb_image"](compiler, target, Path(temporary)) if NATIVE.get("stb", False) else ()
        command = [
            compiler, "build", str(source), "-vet", "-o:speed", *target.flags,
            f"-collection:deps={dependency / 'src'}", *extra,
        ]
        if plugin:
            command.append("-build-mode:dll")
        command.append(f"-out:{staged}")
        subprocess.run(command, cwd=ROOT, check=True, timeout=300)
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError(f"Odin did not produce a nonempty artifact: {staged}")
        try:
            staged.replace(artifact)
        except PermissionError as error:
            raise RuntimeError(f"Cannot replace {artifact}. Close the preview or host using it and rebuild.") from error
    print(f"Built {artifact}", flush=True)
    return artifact


def check_preview() -> None:
    import vapoursynth as vs

    try:
        runpy.run_path(str(ROOT / "preview.vpy"))
        if not vs.get_outputs():
            raise RuntimeError("The preview did not register any outputs")
        for index, output in sorted(vs.get_outputs().items()):
            clip = output.clip
            for number in dict.fromkeys((0, clip.num_frames - 1)):
                with clip.get_frame(number):
                    pass
            print(f"Output {index}: {clip.width} x {clip.height} {clip.format.name}; boundary frames passed")
    finally:
        vs.clear_outputs()


def artifact_path() -> Path:
    """Locate this project's output using the same target selection as the build."""
    native = runpy.run_path(str(bindings_root() / "tools" / "native_build.py"))
    target = native["native_target"](sysconfig.get_platform())
    suffix = target.extension if NATIVE["kind"] == "plugin" else target.executable_suffix
    return ROOT / ".build" / f"{NATIVE['name']}{suffix}"


def run_host(artifact: Path, bindings: Path | None = None) -> None:
    import vapoursynth as vs

    native = runpy.run_path(str(bindings_root(bindings) / "tools" / "native_build.py"))
    library = native["core_library"](Path(vs.__file__).resolve().parent)
    subprocess.run([str(artifact), library], check=True, timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default="odin")
    parser.add_argument("--bindings", type=Path, help="Use this bindings checkout instead of the pinned release")
    action = "--check" if NATIVE["kind"] == "plugin" else "--run"
    parser.add_argument(action, action="store_true", dest="execute", help="Build and execute the preview or host")
    args = parser.parse_args()
    try:
        artifact = build(args.odin, bindings=args.bindings)
        if args.execute:
            check_preview() if NATIVE["kind"] == "plugin" else run_host(artifact, args.bindings)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
