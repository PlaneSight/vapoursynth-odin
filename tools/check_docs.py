#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Check generated documentation links, assets, and fragment identifiers offline."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[tuple[int, str]] = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if identifier := attributes.get("id"):
            self.ids.add(identifier)
        if tag == "a" and (name := attributes.get("name")):
            self.ids.add(name)
        for attribute in ("href", "src"):
            if value := attributes.get(attribute):
                self.links.append((self.getpos()[0], value))


def check_site(directory: Path, base_path: str = "/") -> tuple[int, int, list[str]]:
    directory = directory.resolve()
    pages = {path.resolve(): Page(path) for path in directory.rglob("*.html")}
    errors: list[str] = []
    links = 0
    prefix = "/" + base_path.strip("/") + "/" if base_path.strip("/") else "/"
    if not pages:
        return 0, 0, [f"No HTML pages found in {directory}; build the site first."]
    for source, page in pages.items():
        for line, href in page.links:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or href == "#":
                continue
            links += 1
            path = unquote(parsed.path)
            label = f"{source.relative_to(directory)}:{line}: {href}"
            if path.startswith("/"):
                if not path.startswith(prefix):
                    errors.append(f"{label}: outside the site base path {prefix}")
                    continue
                target = directory / path[len(prefix):]
            else:
                target = source.parent / path if path else source
            target = target.resolve()
            if not target.is_relative_to(directory):
                errors.append(f"{label}: escapes the site directory")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{label}: missing local target")
                continue
            fragment = unquote(parsed.fragment)
            if fragment and target in pages and fragment not in pages[target].ids:
                errors.append(f"{label}: missing fragment #{fragment}")
    return len(pages), links, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=ROOT / "site")
    parser.add_argument("--base-path", default="/", help="Root URL path, e.g. /vapoursynth-odin/")
    args = parser.parse_args()
    page_count, link_count, errors = check_site(args.site_dir, args.base_path)
    for error in errors:
        print(error)
    if errors:
        print(f"FAILED: {len(errors)} broken local links or fragments")
        return 1
    print(f"PASS: {page_count} HTML pages, {link_count} local links and assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
