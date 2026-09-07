# 2. Read and write map properties

Create a map and round-trip integers, floating-point values, text, binary data,
and arrays. The binary payload contains a zero byte, demonstrating why map data
uses an explicit length. An existing empty array and an absent key produce
different results.

Run from the repository root:

```console
odin run examples/properties -- /absolute/path/to/libvapoursynth.dll
```

The library path is optional and defaults to `easy.DEFAULT_LIBRARY`.

The setters copy their inputs into the map, so the local arrays in
`write_properties` can go out of scope when that procedure returns. The strings
and slices returned by getters borrow the map's storage: treat them as read-only,
and consume or copy them before changing or destroying the map. The example reads
everything while the map is alive and performs no further mutations.
