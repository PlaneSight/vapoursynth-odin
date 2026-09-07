# SPDX-License-Identifier: LGPL-2.1-or-later
"""Exercise documentation export boundaries without compiling native plugins."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import docs, render_showcase

try:
    import numpy as np
    import vapoursynth as vs
except ImportError:
    np = None
    vs = None


class TemporaryProject(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.destination = self.root / "published"
        self.destination.mkdir()
        self.enterContext(patch.object(render_showcase, "ROOT", self.root))
        self.enterContext(redirect_stdout(io.StringIO()))


@unittest.skipIf(vs is None or np is None, "VapourSynth and NumPy are required: uv sync --group docs")
class RegisteredDocumentationOutputs(TemporaryProject):
    def setUp(self):
        super().setUp()
        vs.clear_outputs()
        self.addCleanup(vs.clear_outputs)
        self.script = self.root / "examples" / "fixture" / "preview.vpy"
        self.script.parent.mkdir(parents=True)
        self.enterContext(patch.object(render_showcase, "EXAMPLES", {"fixture": self.script.parent}))

    def write_script(self, exports, *, format_name="RGB24", suffix=""):
        self.script.write_text(
            "import vapoursynth as vs\n"
            f"clip = vs.core.std.BlankClip(width=5, height=3, format=vs.{format_name}, length=1)\n"
            "clip.set_output(0)\n"
            "clip.set_output(1)\n"
            f"DOCUMENTATION_OUTPUTS = {exports!r}\n"
            + suffix,
            encoding="utf-8",
        )

    def test_missing_empty_and_nonmapping_exports_are_rejected(self):
        for exports in (None, {}, [], "image"):
            with self.subTest(exports=exports):
                self.write_script(exports)
                with self.assertRaisesRegex(ValueError, "nonempty index-to-name mapping"):
                    render_showcase.render_script("fixture", self.destination)
                self.assertEqual(vs.get_outputs(), {})
                self.assertEqual(list(self.destination.iterdir()), [])

    def test_only_registered_nonnegative_integer_indices_are_accepted(self):
        for index in (-1, 2, "0", True):
            with self.subTest(index=index):
                self.write_script({index: "valid-name"})
                with self.assertRaisesRegex(ValueError, "is not registered"):
                    render_showcase.render_script("fixture", self.destination)
                self.assertEqual(vs.get_outputs(), {})

    def test_unsafe_image_names_are_rejected_before_writing(self):
        for basename in ("../outside", "nested/image", "nested\\image", "image.png", "", "Image", "two words", 123):
            with self.subTest(basename=basename):
                self.write_script({0: basename})
                with self.assertRaisesRegex(ValueError, "invalid documentation image name"):
                    render_showcase.render_script("fixture", self.destination)
                self.assertEqual(list(self.destination.iterdir()), [])
                self.assertEqual(vs.get_outputs(), {})

    def test_duplicate_names_cannot_produce_a_successful_manifest(self):
        self.write_script({0: "same-image", 1: "same-image"})
        with self.assertRaisesRegex(ValueError, "duplicate image name"):
            render_showcase.render_script("fixture", self.destination)
        self.assertFalse((self.destination / "fixture.json").exists())
        self.assertEqual(vs.get_outputs(), {})

    def test_non_rgb24_frames_are_rejected_without_overwriting_an_image(self):
        self.write_script({0: "image"}, format_name="RGB48")
        image = self.destination / "image.png"
        image.write_bytes(b"previous image")
        with self.assertRaisesRegex(ValueError, "must be RGB24"):
            render_showcase.render_script("fixture", self.destination)
        self.assertEqual(image.read_bytes(), b"previous image")
        self.assertEqual(vs.get_outputs(), {})

    def test_script_errors_release_registered_outputs(self):
        self.write_script({0: "image"}, suffix="raise RuntimeError('fixture failed')\n")
        with self.assertRaisesRegex(RuntimeError, "fixture failed"):
            render_showcase.render_script("fixture", self.destination)
        self.assertEqual(vs.get_outputs(), {})
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_rgb_frame_png_contains_exact_visible_samples_and_no_row_padding(self):
        clip = vs.core.std.BlankClip(width=5, height=3, format=vs.RGB24, length=1)
        expected = bytes((19 * plane + 37 * y + 11 * x) % 256
                         for y in range(3) for x in range(5) for plane in range(3))
        image = self.destination / "pixels.png"
        with clip.get_frame(0) as source:
            with source.copy() as frame:
                self.assertGreater(frame.get_stride(0), frame.width)
                for plane in range(3):
                    for y in range(frame.height):
                        for x in range(frame.width):
                            frame[plane][y, x] = (19 * plane + 37 * y + 11 * x) % 256
                render_showcase.write_rgb_frame(frame, image)

        encoded = image.read_bytes()
        self.assertEqual(encoded[:8], b"\x89PNG\r\n\x1a\n")
        position = 8
        chunks = []
        while position < len(encoded):
            length = int.from_bytes(encoded[position:position + 4], "big")
            kind = encoded[position + 4:position + 8]
            payload = encoded[position + 8:position + 8 + length]
            checksum = int.from_bytes(encoded[position + 8 + length:position + 12 + length], "big")
            self.assertEqual(checksum, zlib.crc32(kind + payload))
            chunks.append((kind, payload))
            position += 12 + length
        self.assertEqual(position, len(encoded))
        self.assertEqual([kind for kind, _ in chunks], [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(struct.unpack(">IIBBBBB", chunks[0][1]), (5, 3, 8, 2, 0, 0, 0))
        scanlines = zlib.decompress(chunks[1][1])
        self.assertEqual(len(scanlines), 3 * (1 + 5 * 3))
        self.assertEqual(scanlines[::16], b"\0\0\0")
        actual = b"".join(scanlines[row * 16 + 1:(row + 1) * 16] for row in range(3))
        self.assertEqual(actual, expected)


class DocumentationPublication(TemporaryProject):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(render_showcase, "PLUGIN_NAMES", ("first", "second")))
        (self.destination / "first-image.png").write_bytes(b"previous image")
        (self.destination / "showcase.json").write_bytes(b"previous manifest")

    def renderer_process(self, command, **kwargs):
        name = command[command.index("--script") + 1]
        staging = Path(command[command.index("--output") + 1])
        if name == "second":
            raise subprocess.CalledProcessError(1, command)
        (staging / "first-image.png").write_bytes(b"new image")
        (staging / "first.json").write_text(
            json.dumps({"images": [{"image": "first-image.png"}]}), encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0)

    def assert_previous_publication_is_intact(self):
        self.assertEqual((self.destination / "first-image.png").read_bytes(), b"previous image")
        self.assertEqual((self.destination / "showcase.json").read_bytes(), b"previous manifest")
        self.assertEqual(sorted(path.name for path in self.destination.iterdir()), ["first-image.png", "showcase.json"])
        self.assertEqual(list((self.root / ".build").iterdir()), [])

    def test_later_renderer_failure_preserves_published_images_and_manifest(self):
        with patch.object(render_showcase.subprocess, "run", side_effect=self.renderer_process) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                render_showcase.render_all(self.destination)
        self.assertEqual(run.call_count, 2)
        self.assert_previous_publication_is_intact()

    def test_renderer_failure_stops_zensical_and_link_checks(self):
        (self.root / "zensical.toml").write_text('[project]\ndocs_dir = "docs"\n', encoding="utf-8")
        generated = self.root / "docs" / "assets" / "generated"
        generated.parent.mkdir(parents=True)
        self.destination.rename(generated)
        self.destination = generated
        self.enterContext(patch.object(docs, "ROOT", self.root))
        self.enterContext(patch.object(docs, "build_examples"))
        self.enterContext(patch.object(sys, "argv", ["docs.py", "build"]))
        self.enterContext(redirect_stderr(io.StringIO()))
        with patch.object(render_showcase.subprocess, "run", side_effect=self.renderer_process) as run:
            self.assertEqual(docs.main(), 1)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertTrue(all("--script" in command for command in commands))
        self.assert_previous_publication_is_intact()

    def test_duplicate_exports_across_scripts_preserve_previous_publication(self):
        def duplicate_images(command, **kwargs):
            name = command[command.index("--script") + 1]
            staging = Path(command[command.index("--output") + 1])
            (staging / "first-image.png").write_bytes(b"replacement")
            (staging / f"{name}.json").write_text(
                json.dumps({"images": [{"image": "first-image.png"}]}), encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0)

        with patch.object(render_showcase.subprocess, "run", side_effect=duplicate_images):
            with self.assertRaisesRegex(ValueError, "same image name"):
                render_showcase.render_all(self.destination)
        self.assert_previous_publication_is_intact()


if __name__ == "__main__":
    unittest.main()
