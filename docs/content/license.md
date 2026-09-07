# Header provenance

## Upstream header baseline

The raw Odin declarations are translated from VapourSynth **R76**, pinned to
commit `aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7`. The reference copies in
`tests/headers` are unmodified upstream files.

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
