"""Local synthetic scenes and output helpers for preview.vpy."""

from pathlib import Path
import runpy
import sys

import numpy as np
import vapoursynth as vs

ROOT = Path(__file__).resolve().parent
FRAME_COUNT = 48


def load_plugin(example: str, namespace: str) -> None:
    """Use the local build, refusing to silently preview an installed wheel instead."""
    project = runpy.run_path(str(ROOT / "build.py"))
    path = project["artifact_path"]()
    if not path.is_file():
        raise RuntimeError(
            f"Missing example plugin: {path}\nRun: uv run build.py"
        )

    for plugin in vs.core.plugins():
        if plugin.namespace != namespace:
            continue
        loaded = Path(plugin.plugin_path).resolve() if plugin.plugin_path else None
        if loaded == path.resolve():
            return
        raise RuntimeError(
            f"Namespace {namespace!r} is already loaded from {loaded}, "
            f"but this example requires {path.resolve()}. "
            "Use this project's uv environment without an installed example wheel, "
            "or remove its auto-loading copy and restart the previewer."
        )

    vs.core.std.LoadPlugin(path=str(path.resolve()))


def set_output(clip: vs.VideoNode, index: int, name: str) -> None:
    """Name VSView outputs while keeping headless scripts independent of Qt."""
    if "__vsview__" in sys.modules:
        from vsview import set_output as set_named_output

        set_named_output(clip, index, name)
        return
    clip.set_output(index)


def _rgb_blank(width: int, height: int, format: int, length: int) -> vs.VideoNode:
    return vs.core.std.BlankClip(
        width=width, height=height, format=format, length=length, keep=True,
        fpsnum=24, fpsden=1,
    ).std.SetFrameProps(_Matrix=0, _Transfer=13, _Primaries=1, _Range=1)


def clip_from_rgb(pixels: np.ndarray) -> vs.VideoNode:
    """Hold one immutable RGB8/RGB16 scene for a two-second, 24 fps clip."""
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("Expected an image shaped (height, width, 3)")
    formats = {np.dtype(np.uint8): vs.RGB24, np.dtype(np.uint16): vs.RGB48}
    if pixels.dtype not in formats:
        raise ValueError("Expected uint8 or uint16 RGB samples")
    height, width, _ = pixels.shape
    blank = _rgb_blank(width, height, formats[pixels.dtype], FRAME_COUNT)
    with blank.get_frame(0) as frame:
        scene = frame.copy()
    for plane in range(3):
        np.copyto(np.asarray(scene[plane]), pixels[:, :, plane])

    def reuse_scene(n, f):
        return scene

    return vs.core.std.ModifyFrame(blank, clips=blank, selector=reuse_scene)


def color_scene() -> np.ndarray:
    """An original RGB16 scene with shaded colors and a neutral ramp, encoded as sRGB."""
    width, height = 768, 320
    y, x = np.mgrid[0:height, 0:width].astype(np.float64)
    x /= width - 1
    y /= height - 1
    scene = np.empty((height, width, 3), dtype=np.float64)
    for channel, base in enumerate((0.15, 0.19, 0.25)):
        scene[:, :, channel] = base + 0.12 * x + 0.04 * y
    light = np.array([-0.4, -0.5, 0.7681145748])
    spheres = (
        (0.18, (0.85, 0.26, 0.11)),
        (0.50, (0.17, 0.72, 0.33)),
        (0.82, (0.19, 0.38, 0.90)),
    )
    for center, color in spheres:
        nx = (x - center) * width / 96
        ny = (y - 0.40) * height / 96
        radius = nx * nx + ny * ny
        mask = radius <= 1
        nz = np.sqrt(np.maximum(0, 1 - radius))
        diffuse = np.maximum(0, nx * light[0] + ny * light[1] + nz * light[2])
        reflected = np.maximum(0, 2 * nz * diffuse - light[2])
        for channel in range(3):
            shaded = color[channel] * (0.16 + 0.75 * diffuse) + 0.30 * reflected**18
            scene[:, :, channel][mask] = shaded[mask]
    ramp = y >= 0.82
    for channel in range(3):
        scene[:, :, channel][ramp] = x[ramp]
    return np.floor(np.clip(scene, 0, 1) * 65535 + 0.5).astype(np.uint16)


def dither_ramp() -> np.ndarray:
    """A shallow RGB16 ramp spanning approximately twelve eventual RGB8 code values."""
    row = np.linspace(100 * 256, 112 * 256 - 1, 768).astype(np.uint16)
    ramp = np.broadcast_to(row, (192, 768))
    return np.repeat(ramp[:, :, None], 3, axis=2)


def quantization_display(clip: vs.VideoNode) -> vs.VideoNode:
    """Magnify the red plane's steps equally for both dither comparison outputs."""
    if clip.format is None or clip.format.id != vs.RGB24:
        raise ValueError("Expected constant RGB8 video")

    def gain(n, f):
        output = f.copy()
        samples = np.asarray(f[0]).astype(np.int32)
        display = np.clip((samples - 100) * 20 + 8, 0, 255).astype(np.uint8)
        for plane in range(3):
            np.copyto(np.asarray(output[plane]), display)
        return output

    return vs.core.std.ModifyFrame(clip, clips=clip, selector=gain)
