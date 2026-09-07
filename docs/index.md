---
title: VapourSynth for Odin
description: Build video applications and plugins with complete API 4.2 bindings and a practical idiomatic Odin interface.
hide:
  - navigation
  - toc
  - path
---

<div class="hero" markdown>

<p class="eyebrow">VapourSynth API 4.2 · Odin</p>

# From your first frame to your own filter.

<p class="lead">Complete C API bindings, an idiomatic host interface, and a practical path into video processing. Keep ownership explicit, understand each frame's layout, and build plugins that work with VapourSynth's scheduler.</p>

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[Explore the examples](examples/index.md){ .md-button }

<div class="capabilities">
  <span><strong>117</strong> stable core functions</span>
  <span><strong>8</strong> runnable examples</span>
  <span><strong>4.2</strong> core and script APIs</span>
  <span><strong>LGPL</strong> 2.1 or later</span>
</div>

</div>

## Start where you are

<div class="grid cards" markdown>

-   **Build a host application**

    Load the library, create a core, invoke filters, and read frames through the
    optional `easy` package. Typed errors and explicit cleanup keep the resource
    lifetime visible.

    [Write your first program →](getting-started/quickstart.md)

-   **Write a VapourSynth plugin**

    Begin with identity and invert, then explore SIMD blue-noise dithering and
    tetrahedral color grading with Odin's bundled image decoder.

    [Follow the plugin tutorials →](examples/identity-plugin.md)

-   **Work directly with the C API**

    Use the same procedure, constant, and field names as the official header.
    The raw package adds no loading or initialization, and plugins can use the
    table their host supplies.

    [Open the raw API reference →](reference/raw-api.md)

-   **Evaluate Python scripts**

    Use the separate VSScript 4.2 package to evaluate scripts and obtain output
    nodes. Understand the environment's ownership of its core and output lifetimes.

    [Read the VSScript reference →](reference/vsscript.md)

</div>

## Two interfaces, one API foundation

The root package translates the pinned VapourSynth R76 public headers into Odin.
It includes the complete stable core table, plugin initialization table, callback
types, format definitions, frame property constants, and a separate experimental
graph extension. C integer widths and table field order remain part of the ABI.

The `easy` package builds on those declarations. It provides explicit owners for
libraries, cores, maps, nodes, and frames; typed property operations; synchronous
invocation and frame requests; and borrowed row views. It performs work only
when called and keeps access to the raw table available through its owners.

| If your task is… | Begin with… |
| --- | --- |
| Request frames and inspect their pixels | [`easy`](reference/easy.md) |
| Implement a filter callback | [Raw `VSAPI`](reference/raw-api.md) |
| Evaluate a VapourSynth Python script | [`vsscript`](reference/vsscript.md) |
| Resolve the core through the linker | [`link`](guides/loading-and-linking.md) |
| Debug graph construction | [`VSGraphAPI`](reference/raw-api.md) and its exact-version restrictions |

[Compare the interfaces in detail](getting-started/choosing-an-interface.md).

## A runtime you can reproduce

Use uv to provision VapourSynth and run an Odin host with the selected core library:

```console
uv sync --locked
uv run tools/run_host.py easy_host
uv run tools/examples.py build
uv run --group preview tools/examples.py preview --no-build
```

The optional preview group adds VSView and Qt. The command reuses the build and opens the
five visual plugin demonstrations with named comparison, source, and result
outputs. Use `uv run tools/examples.py check --no-build` for a headless frame check. See
[Build and preview the examples](guides/previewing-examples.md) for setup and
selection. The tutorial images are rendered from these same scripts during
the documentation build.

An explicit `uv build` packages the five native plugins into a Python wheel that
VapourSynth can discover automatically. The Odin packages remain ordinary source
imports. Read [Python environments and wheels](guides/python-packaging.md) for
the build and distribution model.

For the advanced examples, start with [SIMD blue-noise dithering](examples/dither-plugin.md)
or [Hald CLUT color grading](examples/haldlut-plugin.md). Their walkthroughs connect
numerical algorithms with frame layout, immutable filter data, and native library use.

The standalone [Dither Plus plugin](plugins/dither-plus.md) extends the dithering
work into a five-method comparison with RGB threshold correlation and moving
masks. It has its own plugin guide and preview, keeping the eight examples a
focused learning sequence.

## Learn the contracts that matter

Reference ownership determines when an object can be released. Stride determines
how rows occupy memory. The frame activation protocol determines when a filter
may ask for and consume upstream frames. These guides explain the rules in
context, with concrete consequences for your code:

- [Ownership and lifetime](guides/ownership.md): acquisition, borrowing, retaining,
  transferring, and teardown order.
- [Errors and diagnostics](guides/errors.md): typed failures, copied messages,
  and the raw API's differing success conventions.
- [Maps and properties](guides/maps.md): arrays, binary data, empty values, and
  node references.
- [Frames and pixel layout](guides/frames.md): sample representation, row padding,
  chroma subsampling, and checked views.

## Built to be checked

The repository includes pinned C headers, a C/Odin ABI comparison, failure and
ownership tests for `easy`, and a runtime runner for every example. Verification
on Windows x64 with R76 and R79 covers the invert filter's pixels across Gray8, RGB24,
YUV420P10, and Gray16, including concurrent requests and unchanged source frames.
Other listed targets have compile checks; see the
[compatibility record](maintenance/compatibility.md) for the scope of that evidence.

[Run the verification suites](maintenance/testing.md), or visit
[troubleshooting](troubleshooting.md) when a library, version, or build step needs
attention.
