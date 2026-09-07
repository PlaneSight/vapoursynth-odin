# Installation

Install **uv and Odin**, then run the commands below. **uv downloads Python and
installs VapourSynth into the project's `.venv` automatically.** You do not need
a separate Python installation, a VapourSynth installer, or manual library paths
for the examples.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- [Odin and its native toolchain](https://odin-lang.org/docs/install/), available on `PATH`.

??? details "Platform toolchain details"

    Odin's native tools depend on the platform:

    | Platform | Native tools |
    | --- | --- |
    | Windows x64 | Visual Studio C++ Build Tools and Windows SDK, as required by Odin. Use a complete Odin distribution with its vendor libraries. |
    | Linux x64 or ARM64 | Odin's compiler dependencies, plus `cc` and `ar` for the Hald example's bundled C library. |
    | macOS x64 or ARM64 | Xcode Command Line Tools. Example builds target macOS 13 or newer. |

    uv manages the Python environment; Odin compiles the native code. The current
    CI checks Ubuntu x64 and Windows x64. See [compatibility](../maintenance/compatibility.md)
    for compiler versions and platform verification.

## Run this repository

Clone the repository, or download and extract its source archive:

```console
git clone https://github.com/PlaneSight/vapoursynth-odin.git
cd vapoursynth-odin
uv run --locked tools/run_host.py core_info
```

That one `uv run` command downloads the pinned Python **3.14.7** if needed,
creates `.venv`, installs the locked dependencies including **VapourSynth R79**,
builds the host, and runs it. It prints the core version, API version, and thread
count. There is no environment activation or separate `uv sync` step to remember.
The first run needs internet access to download missing dependencies.

VapourSynth is already declared in this repository, so **do not run `uv add`
here just to install it**. `uv run --locked` uses the committed dependency versions.

Optional tools are selected on the command that needs them:

| Task | Command |
| --- | --- |
| Build all eight binding examples | `uv run --locked tools/examples.py build` |
| Build and open Invert in VSView | `uv run --locked --group preview tools/examples.py preview invert` |
| Build and serve these docs | `uv run --locked --group docs tools/docs.py serve` |

The `preview` group adds VSView and Qt and needs a desktop session. The `docs`
group generates images headlessly. uv installs either group when selected;
keep its `--group` option on subsequent commands that use those tools.

Every example is also a copyable project: inside its directory, run
`uv run build.py` to build it. See [build and preview](../guides/previewing-examples.md)
for the example commands and [your first host](quickstart.md) for the API walkthrough.

## Use VapourSynth in a new uv project

For your own Python project, add the runtime as a normal dependency:

```console
uv init --bare --python 3.14 my-project
cd my-project
uv add vapoursynth
uv run python -c "import vapoursynth as vs; print(vs.core)"
```

`uv add vapoursynth` records the dependency, resolves it, and installs the package
and its bundled core runtime. In an existing uv project, start with `uv add`.
This installs VapourSynth; add the Odin binding sources separately as below.

## Add the packages to your application

Place this repository at `vendor/vapoursynth-odin`, then import its source packages:

```odin
import vs "deps:vapoursynth"
import easy "deps:vapoursynth/easy"
```

```console
odin build . -collection:deps=vendor/vapoursynth-odin/src
```

The collection points to `src`, and its name matches the imports. The bindings
require no installation into Odin's own directories. Their declarations target
core API 4.2 and VSScript API 4.2; using the R79 runtime does not change the pinned
R76 header baseline.

For embedding an existing native runtime, explicit library paths, or link-time
resolution, see [loading and linking](../guides/loading-and-linking.md). Those are
application integration choices, not additional steps for the uv examples.

## Python version files

The root project and every copied example require Python 3.14 or newer.
`.python-version` selects the exact tested interpreter for uv and CI;
`pyproject.toml` declares dependencies and compatibility; `uv.lock` records the
resolved packages. Keep all three when copying an example.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `uv` or `odin` is not found | Install the missing tool using the links above and reopen the terminal. |
| Python or VapourSynth appears missing | Run the command with `uv run` from the directory containing `pyproject.toml`. |
| VSView is missing | Include `--group preview` on the preview command. |
| Odin reports a missing compiler, linker, or vendor library | Check the native toolchain requirements above. |
| uv cannot find a compatible VapourSynth wheel | Check your OS and architecture against [VapourSynth's published files](https://pypi.org/project/VapourSynth/#files). |

For API, frame, and loader errors after setup, see [troubleshooting](../troubleshooting.md).
