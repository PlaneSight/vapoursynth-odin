# Reference headers

These files are unmodified upstream headers from VapourSynth **R76**, commit
`aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7`:

- [VapourSynth4.h](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VapourSynth4.h)
- [VSConstants4.h](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSConstants4.h)
- [VSScript4.h](https://github.com/vapoursynth/vapoursynth/blob/aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7/include/VSScript4.h)

The ABI verifier selects `VS_USE_API_42` and `VSSCRIPT_USE_API_42` explicitly.
Without those defines the upstream headers default to older API revisions.
It also checks the experimental core table with `VS_GRAPH_API` enabled.

The headers and their Odin translations are covered by LGPL-2.1-or-later; the
upstream copyright notices are retained. See [LICENSE](../../LICENSE).
