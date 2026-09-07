---
title: Build and publish these docs
description: Preview the Zensical site, validate source includes and links, and deploy it with GitHub Pages.
---

# Build and publish these docs

This site is built with [Zensical](https://zensical.org/docs/), configured in
`zensical.toml`, and published as static HTML. Markdown lives in `docs/content/`
and theme templates live in `docs/overrides/`. The generated `.venv/site/`
directory is ignored by Git. The repository includes a GitHub
Actions workflow that validates pull requests and deploys the default branch
to GitHub Pages once Pages is enabled for the repository.

## Set up a local environment

Use the pinned **Python 3.14.7** environment, [uv](https://docs.astral.sh/uv/), and the
[Odin toolchain](../getting-started/installation.md). The repository's
Python project declares its documentation dependencies in the `docs` dependency
group in `pyproject.toml`; `uv.lock` records the resolved versions and hashes.
The `.python-version` file selects the interpreter for local and CI builds.
Run these commands from the repository root:

```console
uv sync --locked --group docs
uv run --group docs tools/docs.py serve
```

The first command creates or updates `.venv` from the committed lockfile. The
project sets `tool.uv.package = false`, so synchronization provisions the Python
environment without compiling or installing the native Odin examples. The
documentation command then compiles the eight examples and Dither Plus, evaluates the five
plugin preview scripts, renders their designated output frames, and starts
Zensical. Odin and the VapourSynth runtime are required because the illustrations
are actual native filter output. VSView and Qt are optional and are not installed
by the docs group.

Open the local address printed by Zensical, normally `http://127.0.0.1:8000`.
The development server reloads Markdown changes. After changing Odin code or a
demonstration script, stop it with `Ctrl+C` and rerun the command to rebuild the
plugins and regenerate their images. It does not publish the site or alter the
GitHub repository.

If another process is using port 8000, choose a free local address:

```console
uv run --group docs tools/docs.py serve --dev-addr 127.0.0.1:8001
```

The address is passed to Zensical after the examples and images are prepared.

## Build a release candidate

```console
uv run --locked --group docs tools/docs.py build
uv run --locked --group docs python -m unittest discover -s tests -p test_check_docs.py
```

The build command compiles the eight Odin examples and Dither Plus, executes every plugin
demonstration in a fresh process, and exports the selected first frames into
`docs/content/assets/generated`. It then runs Zensical with `--clean --strict` and checks
the generated links. A failed compilation, script, or frame request fails the
build before publication. Generated PNGs are ignored by Git; there is no
checked-in screenshot fallback.

Zensical's `--clean` replaces only `.venv/site`, leaving the Python environment
intact, and `--strict` makes reported
warnings fail the build. The checked-in configuration treats missing navigation entries,
unlisted pages, unresolved links, and missing anchors as warnings, so they must
be addressed before the build can pass.

The wrapper's final step independently checks the generated HTML. It resolves local
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
| `docs/content/index.md` | Landing page and learning paths |
| `docs/content/getting-started/` | Installation, first program, interface choice |
| `docs/content/guides/` | Concepts and ownership contracts across APIs |
| `docs/content/examples/` | Progressive explanations of the eight host and plugin examples |
| `docs/content/plugins/` | Standalone plugin guides and visual comparisons |
| `docs/content/reference/` | Public declarations, procedure behavior, types, and constants |
| `docs/content/maintenance/` | Verification, compatibility, and publishing |
| `docs/content/assets/` | Local logo and CSS; ignored `generated/` contains current filter outputs |
| `docs/overrides/404.html` | Accessible not-found page and recovery links |
| `zensical.toml` | Navigation, theme, extensions, and validation |
| `pyproject.toml` and `uv.lock` | Authoritative dependency declarations and resolved versions |
| `.python-version` | Shared interpreter pin for local and CI builds |
| `tools/docs.py` | Compile examples, render current images, then serve or validate the site |
| `tools/render_showcase.py` | Export the documentation outputs declared by the preview scripts |
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
`examples/core_info/src/main.odin` inside an Odin code fence.

This gives the reader the program that is built and tested. Keep tutorial prose
beside the inclusion to explain decisions, expected output, ownership, and
failure behavior. Including a source file does not explain its contract by itself.

Use short original fragments when isolating a concept helps. Identify the
necessary imports, values in scope, and enclosing return type; distinguish a
fragment from a complete program. Compile complete Odin snippets and execute
complete Python demonstrations when adding or changing them.

### Generate illustrations from the real scripts

Identity, invert, dither, Hald CLUT, and Dither Plus each have a checked-in `preview.vpy` used by
both VSView and the documentation renderer. Each script publishes named output
nodes and a `DOCUMENTATION_OUTPUTS` mapping selecting the nodes and filenames to
export. Shared input construction and display conversions live with the examples.
The renderer reads output frames from those graphs; it does not duplicate their
filter calls or rebuild an approximation in a separate image tool.

To inspect the generated files without building the website:

```console
uv run tools/render_showcase.py
```

This builds the plugins and exports the images with a record of the run under
`.build/showcase`. The documentation wrapper directs the same rendering process
to `docs/content/assets/generated`. PNGs embedded in Markdown therefore reflect the code
that was compiled for that build. A frame at index zero is exported for each
selected output. The exported nodes use static scenes; Dither Plus also provides
animated outputs for interactive playback. The mappings currently export
21 images: two each for identity, invert, and Hald, eight for the dither tutorial,
and seven for Dither Plus.

Keep image captions precise. The shallow-ramp dither illustration applies the
same 20× contrast gain to its rounding and dither views; the caption must disclose
that gain. The one-, two-, and four-bit RGB scene comparisons have no contrast
gain and use eight-bit storage for their reduced set of levels. Hald's source
and result use the same integer conversion to RGB8. Image
generation verifies that graphs can produce their displayed frames; the
[numerical suites](testing.md) separately validate values and error behavior.

Direct `zensical build` or `zensical serve` commands only process the existing
Markdown and assets. Use `tools/docs.py` for local builds from a clean checkout.
The deployed site is static: visitors read ordinary HTML and PNGs, with no native
compilation or VapourSynth execution in their browser.

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

The **build** job runs for pull requests, matching pushes, and manual dispatches
on Windows 2025. It installs the pinned Odin development toolchain after verifying
the archive's checksum, provisions the pinned Python 3.14.7 with the locked uv documentation
group, and executes the full documentation command. That command
builds the eight examples and Dither Plus, runs the five visual scripts, generates fresh PNGs,
performs a clean strict site build, and checks local links. The job stores the
`.venv/site` preview and generated images as artifacts and has read access to repository
contents. Windows is the native platform used for the verified plugin builds.

The **deploy** job runs after a successful build only for a non-pull-request
event on the repository's actual default branch. It has the Pages and identity
token permissions needed by GitHub's deployment actions. On Linux it uses the
same Python pin and `uv.lock`, installs only the `docs` dependency group, downloads the
generated images from the successful native build, configures Pages,
builds with the resulting URL metadata, validates the generated site, uploads a
Pages artifact, and deploys it. Deployments share a concurrency group to serialize
updates to the site.

The workflow performs a second static-site build for deployment, using the exact
image artifact generated by the native build. It does not require a Linux Odin
toolchain or independently rerender the filters there. Pull request
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
uv run --locked --only-group docs tools/pages_config.py
uv run --locked --only-group docs zensical build --clean --strict --config-file .zensical-pages.toml
uv run --locked --only-group docs tools/check_docs.py --base-path "$PAGES_BASE_PATH"
```

Those commands use the Linux workflow's shell syntax and assume the generated
image artifact has been restored and the required environment values have been
supplied by GitHub Actions. The prefix is needed
for the not-found page's root-absolute links; normal content pages use relative
links. For ordinary local editing, build with `zensical.toml` instead.
Do not commit a generated overlay containing temporary test URLs.

## Diagnose a documentation failure

| Symptom | Check |
| --- | --- |
| Python version or dependency resolution fails | Select Python 3.12 or newer, matching the project's declared minimum |
| `uv sync --locked` reports an outdated lockfile | Update `uv.lock` after changing `pyproject.toml` |
| Image generation fails | Read the first compiler or script error; run `uv run tools/examples.py check` to exercise the graphs without the site |
| PNGs are missing after a direct Zensical build | Run `uv run --group docs tools/docs.py build` to generate the ignored assets from current code |
| Preview images do not reflect a native edit | Stop and restart `tools/docs.py serve`; Markdown live reload does not recompile plugins |
| Source inclusion fails | Run from the repository root; confirm the included path exists and the file is tracked |
| Strict build fails after adding a page | Add it to navigation and resolve all warnings in the build log |
| Local link checker reports a fragment | Inspect the generated heading ID; update the source link or retain a stable anchor |
| Pages setup fails | Select GitHub Actions in Settings → Pages and inspect repository policy |
| Build succeeds but deployment is skipped | Confirm the event is not a pull request and the branch is the actual default branch |
| Site uses the wrong repository path | Inspect the configure-pages output and generated overlay; avoid hardcoded root-absolute internal links |

## Update documentation dependencies

`pyproject.toml` and `uv.lock` are the source of truth. Change the desired pin
in the `docs` dependency group, resolve the lockfile, and sync:

```console
uv lock
uv sync --locked --group docs
uv run --locked --group docs tools/docs.py build
```

Commit the changed declaration and lockfile together. Update `.python-version`
when deliberately upgrading the interpreter; both CI jobs read that same file.
After an upgrade, inspect navigation, search, diagrams, and source listings.
See [Zensical's documentation](https://zensical.org/docs/publish-your-site/)
for version-sensitive configuration and deployment guidance.
