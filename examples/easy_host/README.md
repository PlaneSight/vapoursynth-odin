# 3. Invoke a plugin and read a frame

Build a `std.BlankClip` argument map, invoke the built-in plugin, obtain a node,
request a frame synchronously, and compute a checksum over its visible samples.
The clip is 65 x 48 Gray8 with every sample set to 17, giving a checksum of 53040.

Run from the repository root:

```console
uv run tools/run_host.py easy_host
```

The helper builds the executable and selects the core library from the uv
environment on every supported platform. Use
`uv run tools/examples.py build easy_host` to compile without executing it.
No external plugins or source media are required. See the
[build guide](../../docs/content/guides/previewing-examples.md) for prerequisites.

`make_blank_clip` destroys its temporary maps before returning. `map_get_node`
acquires an independent reference, so the returned node remains valid. The host
also demonstrates `retain_node` and then releases the original reference. Copying
an owned wrapper value with assignment does not acquire a reference.

`read_plane` returns a borrowed view of the frame. `plane_row` exposes only the
visible bytes of a row, using the reported stride to find each row. The odd width
makes padding likely, and the checksum excludes any padding. Treat row slices as
read-only and keep the frame alive until all rows have been consumed.

Cleanup runs in reverse acquisition order: frame, node, core, library. Releasing
an already cleared wrapper is harmless, so the early explicit node release also
works with its deferred cleanup.
