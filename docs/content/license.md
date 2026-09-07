---
title: License and provenance
description: LGPL-2.1-or-later licensing, the pinned VapourSynth header sources, and upstream attribution.
---

# License and provenance

The repository uses **LGPL-2.1-or-later**. The root `LICENSE` contains the GNU
Lesser General Public License, version 2.1; the source notices permit version 2.1
or any later version. Preserve the applicable notices when redistributing the
source or translated declarations.

## Upstream header baseline

The raw Odin declarations are translated from VapourSynth **R76**, pinned to
commit `aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7`. The reference copies in
`tests/headers` are unmodified upstream files and retain their original
copyright and license notices.

| Checked-in header | Upstream source | Used for |
| --- | --- | --- |
| `VapourSynth4.h` | [Pinned header](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VapourSynth4.h) | Core API, plugin API, graph extension, types, callbacks, and formats |
| `VSConstants4.h` | [Pinned header](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSConstants4.h) | Frame property and color constants |
| `VSScript4.h` | [Pinned header](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSScript4.h) | Independent script API declarations |

The ABI verifier explicitly selects the 4.2 core and script versions rather
than relying on the headers' default preprocessor choices. It separately
checks the experimental graph layout. Read [compatibility and upgrades](maintenance/compatibility.md)
before changing that baseline.

`VSHelper4.h` contains C inline convenience functions and is outside the raw
ABI translation's scope. The optional Odin `easy` interface has its own explicit
ownership and error contracts; its documentation does not imply that it is a
direct translation of those C helpers.

## Documentation and attribution

This documentation explains the bindings and examples in this repository and
links to the official VapourSynth reference where upstream behavior matters.
The source-included reference listings carry the repository's source notices.
The site is built with [Zensical](https://zensical.org/); the logo, additional
styles are stored locally in `docs/content/assets`. Identity, invert, dither, and Hald
CLUT comparison images are generated during documentation builds by running
the repository's preview scripts. The inputs are generated locally, and
`tools/render_showcase.py` exports those scripts' actual output nodes into
`docs/content/assets/generated`. These PNGs are build artifacts, not checked-in assets.

VapourSynth and Odin are separate upstream projects. This repository's API
translation, convenience interface, examples, and documentation do not imply
endorsement by either project.

## Native wheel dependencies

Individual binding examples can package their compiled plugin as a wheel.
Their source retains the repository's LGPL-2.1-or-later notices. Compiling these
plugins also incorporates code from the Odin toolchain, and the Hald CLUT example
links the toolchain's bundled `stb_image` decoder. Their upstream notices are
collected in the root `THIRD_PARTY_LICENSES.md`. Each example retains its own
license and third-party notices for inclusion in its wheel's distribution metadata.

| Component | Provenance retained in `THIRD_PARTY_LICENSES.md` |
| --- | --- |
| Odin runtime and standard library | The compiler distribution's root license and the `core:c/libc` component copyright |
| `stb_image` | The full MIT alternative supplied with the bundled v2.27 decoder; the Hald example also retains its local notice |
| LLVM-derived runtime conversion routines | The complete `base/runtime/LICENSE-compiler-rt.txt` supplied by Odin, including the LLVM exceptions and historical notices |

The collected notices correspond to **Odin dev-2026-09-nightly:a2fb372**, used for
the verified Windows x64 build. When changing compilers or bundled libraries,
review the notices supplied with that toolchain and update the root notice file
to match. Upstream source is available from the
[Odin repository](https://github.com/odin-lang/Odin) and the
[stb repository](https://github.com/nothings/stb).

VapourSynth is a separately installed Python dependency. Its runtime is not
included in the example wheel; it retains its own upstream licensing and
distribution metadata. See [Python packaging](guides/python-packaging.md) for the
wheel layout and installation workflow.

## Full license text

The following is included directly from the repository's `LICENSE` file.

??? abstract "GNU Lesser General Public License, version 2.1"

    ```text
    --8<-- "LICENSE"
    ```

The following notices are included directly from the root
`THIRD_PARTY_LICENSES.md`.

??? abstract "Bundled third-party notices"

    ```text
    --8<-- "THIRD_PARTY_LICENSES.md"
    ```
