---
title: Build and publish these docs
description: Preview the Zensical site, validate source includes and links, and deploy it with GitHub Pages.
---

# Build and publish these docs

This site is built with [Zensical](https://zensical.org/docs/), configured in
`zensical.toml`, and published as static HTML. Markdown lives in `docs/`; the
generated `site/` directory is ignored by Git. The repository includes a GitHub
Actions workflow that validates pull requests and deploys the default branch
to GitHub Pages once Pages is enabled for the repository.

## Set up a local environment

Use **Python 3.11 or newer**. The documentation tooling reads TOML with Python's
standard `tomllib`; the CI workflow uses Python 3.12. The directly required
packages are pinned in `requirements-docs.txt`:

```text
--8<-- "requirements-docs.txt"
```

Create a virtual environment from the repository root. Activation is optional
if you invoke its Python executable explicitly, as below.

=== "Windows PowerShell"

    ```powershell
    python -m venv .venv
    .venv/Scripts/python.exe -m pip install -r requirements-docs.txt
    .venv/Scripts/python.exe -m zensical serve
    ```

=== "Linux / macOS"

    ```sh
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements-docs.txt
    .venv/bin/python -m zensical serve
    ```

Open the local address printed by Zensical, normally `http://127.0.0.1:8000`.
The development server rebuilds when files change. Stop it with `Ctrl+C` when
finished. It does not publish the site or alter the GitHub repository.

The remaining commands use `python` to mean that virtual environment's Python.
Activate the environment or substitute its executable path.

## Build a release candidate

```console
python -m zensical build --clean --strict
python tools/check_docs.py
python -m unittest discover -s tests -p test_check_docs.py
```

`--clean` replaces the generated site, and `--strict` makes reported warnings fail
the build. The checked-in configuration treats missing navigation entries,
unlisted pages, unresolved links, and missing anchors as warnings, so they must
be addressed before the build can pass.

The second command independently checks the generated HTML. It resolves local
links, images, stylesheets, scripts, and heading fragments across the built site.
External URLs are skipped: a local validation pass does not certify a remote
website's uptime. The unit tests exercise the link checker's failure boundaries.

Preview the site in a browser before submitting a significant change. Inspect
the affected pages in both color schemes, follow their navigation, try a search
for an API name, and check wide tables and long code blocks on a narrow viewport.
The syntax highlighter supports Odin; source inclusion must produce highlighted
code, not a visible include directive.

## Where changes belong

| File or directory | Responsibility |
| --- | --- |
| `docs/index.md` | Landing page and learning paths |
| `docs/getting-started/` | Installation, first program, interface choice |
| `docs/guides/` | Concepts and ownership contracts across APIs |
| `docs/examples/` | Progressive explanations of the six host and plugin examples |
| `docs/reference/` | Public declarations, procedure behavior, types, and constants |
| `docs/maintenance/` | Verification, compatibility, and publishing |
| `docs/assets/` | Local logo and CSS |
| `overrides/404.html` | Accessible not-found page and recovery links |
| `zensical.toml` | Navigation, theme, extensions, and validation |
| `tools/check_docs.py` | Offline check of generated links and fragments |
| `tools/pages_config.py` | Deployment URL overlay derived from GitHub metadata |
| `.github/workflows/docs.yml` | Pull request validation and Pages deployment |

Add each new page to the explicit navigation in `zensical.toml`. Keep navigation
labels short enough to scan, and use the page's introduction to state what the
reader will accomplish and what it assumes. Link prose to another Markdown page
with a relative path; Zensical rewrites it to the generated URL.

Heading anchors are part of the site's usable interface. Renaming a heading
can break links elsewhere, even when its filename stays the same. Rebuild and
run the link checker after changing headings or moving a page.

## Include the real source

The tutorials and reference include repository files through
`pymdownx.snippets`. Its base path is the repository root and missing paths are
errors. For example, the first-program page includes the actual
`examples/core_info/main.odin` inside an Odin code fence.

This gives the reader the program that is built and tested. Keep tutorial prose
beside the inclusion to explain decisions, expected output, ownership, and
failure behavior. Including a source file does not explain its contract by itself.

Use short original fragments when isolating a concept helps. Identify the
necessary imports, values in scope, and enclosing return type; distinguish a
fragment from a complete program. Compile complete Odin snippets and execute
complete Python demonstrations when adding or changing them.

The theme enables code copying, linked platform tabs, expandable details,
admonitions, Mermaid diagrams, and search. Use those features to reduce reading
effort. Diagrams should clarify a lifecycle or dependency; important contracts
must also be explained in text. The custom assets are local and text uses system
fonts, so the site does not depend on Google Fonts. Zensical loads the Mermaid
renderer from a CDN when displaying diagrams; that rendering requires network
access.

## Enable GitHub Pages

The workflow is ready for a repository hosted on GitHub. If this checkout has
no remote yet, first create or choose the intended repository and push the
source there using your normal Git workflow. This documentation does not assume
a particular owner, repository name, default branch, or public site URL.

Then configure the repository:

1. Open **Settings → Pages**.
2. Under **Build and deployment**, select **GitHub Actions** as the source.
3. Ensure the documentation and workflow are present on the default branch.
4. Run the **Documentation** workflow from the Actions tab, or push a change to
   one of the paths monitored by the workflow.
5. Review the build and deployment jobs. The `github-pages` environment and
   deployment step expose the resulting site URL.

If the repository uses environment protection rules, its normal approval rules
apply to the `github-pages` environment. Review the Actions log when a deployment
waits for approval or lacks permission. GitHub's
[custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
describes the required Pages permissions and artifact/deployment sequence.

### What the workflow does

The **build** job runs for pull requests, matching pushes, and manual dispatches.
It installs the documentation requirements, performs a clean strict build, checks
local links, and stores a `documentation-preview` artifact for seven days. This
job has read access to repository contents.

The **deploy** job runs after a successful build only for a non-pull-request
event on the repository's actual default branch. It has the Pages and identity
token permissions needed by GitHub's deployment actions. It configures Pages,
builds with the resulting URL metadata, validates the generated site, uploads a
Pages artifact, and deploys it. Deployments share a concurrency group to serialize
updates to the site.

The workflow deliberately performs a second build for deployment. Pull request
validation remains independent of Pages setup, while the deployed HTML receives
the URL assigned by GitHub, including a repository subpath or configured domain.

### Repository and site URLs

The tracked `zensical.toml` has no invented `site_url` or repository URL. During
deployment, `tools/pages_config.py` reads:

| Environment value | Source and purpose |
| --- | --- |
| `PAGES_BASE_URL` | `actions/configure-pages` output; canonical site base URL |
| `PAGES_BASE_PATH` | `actions/configure-pages` output; URL prefix passed to the local link checker |
| `GITHUB_REPOSITORY` | GitHub Actions context; owner and repository name |
| `GITHUB_SERVER_URL` | GitHub Actions context; server origin |

The tool writes an ignored `.zensical-pages.toml` beside the source config and
adds `site_url`, `repo_url`, and `repo_name`. Keeping both configs in the same
directory preserves the documentation, source-include, CSS, and output paths.
The deployment builds with:

```console
python tools/pages_config.py
python -m zensical build --clean --strict --config-file .zensical-pages.toml
python tools/check_docs.py --base-path "$PAGES_BASE_PATH"
```

Those commands use the Linux workflow's shell syntax and assume the required
environment values have been supplied by GitHub Actions. The prefix is needed
for the not-found page's root-absolute links; normal content pages use relative
links. For ordinary local editing, build with `zensical.toml` instead.
Do not commit a generated overlay containing temporary test URLs.

## Diagnose a documentation failure

| Symptom | Check |
| --- | --- |
| `tomllib` cannot be imported | The selected Python is at least 3.11 |
| Source inclusion fails | Run from the repository root; confirm the included path exists and the file is tracked |
| Strict build fails after adding a page | Add it to navigation and resolve all warnings in the build log |
| Local link checker reports a fragment | Inspect the generated heading ID; update the source link or retain a stable anchor |
| Pages setup fails | Select GitHub Actions in Settings → Pages and inspect repository policy |
| Build succeeds but deployment is skipped | Confirm the event is not a pull request and the branch is the actual default branch |
| Site uses the wrong repository path | Inspect the configure-pages output and generated overlay; avoid hardcoded root-absolute internal links |

For dependency upgrades, change the version pin deliberately, make a clean build,
run the link checks, and inspect navigation, search, diagrams, and source listings.
Use [Zensical's documentation](https://zensical.org/docs/publish-your-site/) for
version-sensitive configuration and deployment guidance.
