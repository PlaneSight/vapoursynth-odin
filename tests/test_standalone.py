# SPDX-License-Identifier: LGPL-2.1-or-later
"""Check dependency trust boundaries before any downloaded helper can execute."""

from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from project_fixture import create_project


class PinnedDependency(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name).resolve()
        create_project(self.root, "examples/invert")
        self.project = self.root / "examples/invert"
        self.build = runpy.run_path(str(self.project / "build.py"))
        self.enterContext(redirect_stdout(io.StringIO()))

    def test_explicit_checkout_never_downloads(self):
        with patch("urllib.request.urlopen") as download:
            self.assertEqual(self.build["bindings_root"](self.root), self.root)
        download.assert_not_called()

    def test_checksum_failure_leaves_no_dependency_or_executable_code(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"wrong archive")):
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                self.build["bindings_root"]()
        self.assertFalse((self.project / ".deps").exists())

    def test_archive_paths_cannot_escape_the_dependency(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("repository/src/../../escape.py", "raise RuntimeError('escaped')")
        data = archive.getvalue()
        self.build["NATIVE"]["bindings"]["sha256"] = hashlib.sha256(data).hexdigest()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
            with self.assertRaisesRegex(RuntimeError, "Unsafe archive path"):
                self.build["bindings_root"]()
        self.assertFalse(list(self.project.rglob("escape.py")))


if __name__ == "__main__":
    unittest.main()
