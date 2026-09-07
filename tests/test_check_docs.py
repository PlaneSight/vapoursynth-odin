# SPDX-License-Identifier: LGPL-2.1-or-later
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from check_docs import check_site


class DocumentationLinks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name)

    def write(self, path, content):
        target = self.site / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_directory_encoded_fragments_and_assets(self):
        self.write("index.html", '<a href="guide/#a%20b">Guide</a><img src="asset%20name.svg">')
        self.write("guide/index.html", '<h1 id="a b">Guide</h1><a href="../">Home</a>')
        self.write("asset name.svg", "<svg/>")
        pages, links, errors = check_site(self.site)
        self.assertEqual((pages, links, errors), (2, 3, []))

    def test_missing_file_and_fragment(self):
        self.write("index.html", '<a href="missing/">Missing</a><a href="#absent">Anchor</a>')
        self.assertEqual(len(check_site(self.site)[2]), 2)

    def test_external_links_are_not_requested(self):
        self.write("index.html", '<a href="https://invalid.invalid/">Web</a><a href="mailto:a@b">Email</a>'
                   '<script src="//invalid.invalid/a.js"></script><img src="data:image/svg+xml,x">')
        self.assertEqual(check_site(self.site)[1:], (0, []))

    def test_pages_base_path(self):
        self.write("index.html", '<a href="/project/guide/#ok">Guide</a>')
        self.write("guide/index.html", '<h1 id="ok">OK</h1>')
        self.assertEqual(check_site(self.site, "/project/")[2], [])
        self.assertEqual(len(check_site(self.site, "/different/")[2]), 1)

    def test_parent_escape_is_rejected(self):
        self.write("index.html", '<a href="../outside.html">Escape</a>')
        self.assertIn("escapes", check_site(self.site)[2][0])

    def test_empty_site_is_a_failure(self):
        self.assertIn("No HTML", check_site(self.site)[2][0])


if __name__ == "__main__":
    unittest.main()
