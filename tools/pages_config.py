#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Write a disposable Pages configuration from GitHub Actions metadata."""

import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit

import tomli_w


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    base_url = os.environ["PAGES_BASE_URL"].rstrip("/") + "/"
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("PAGES_BASE_URL must be an absolute HTTPS site URL")
    repository = os.environ["GITHUB_REPOSITORY"]
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))
    project = config["project"]
    project.update(site_url=base_url, repo_url=f"{server}/{repository}", repo_name=repository)
    # This file stays beside the source config, preserving all relative paths.
    (ROOT / ".zensical-pages.toml").write_text(tomli_w.dumps(config), encoding="utf-8")


if __name__ == "__main__":
    main()
