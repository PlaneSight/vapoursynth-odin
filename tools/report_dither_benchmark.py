#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Generate documentation figures and tables from completed dither measurements."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import geometric_mean, median
import sys


ROOT = Path(__file__).resolve().parent.parent


def load_report(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("complete") is not True or not report.get("results"):
        raise ValueError(f"Refusing incomplete or empty benchmark: {path}")
    if report["runtime"]["num_threads"] != 1:
        raise ValueError(f"Expected one VapourSynth worker: {path}")
    for result in report["results"]:
        for metrics in result["metrics"].values():
            durations = metrics["seconds"]
            if len(durations) != report["options"]["runs"] or any(value <= 0 for value in durations):
                raise ValueError(f"Invalid timing samples: {path}")
    return report


def label(case: dict) -> str:
    family = case["family"]
    if family == "YUV":
        family += {(0, 0): "444", (1, 0): "422", (1, 1): "420"}[
            case["subsampling_w"], case["subsampling_h"]
        ]
    elif family == "GRAY":
        family = "Gray"
    scale = "full" if case["scale"] else "shift"
    return f"{family} {case['input_bits']}→{case['output_bits']} {scale}"


def export_data(report: dict, destination: Path, stem: str) -> None:
    # Retain measurement metadata while making repository-local paths portable.
    published = json.loads(json.dumps(report))
    for binary in published["binaries"].values():
        path = Path(binary["path"])
        binary["path"] = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
    published["runtime"].pop("module", None)
    (destination / f"{stem}.json").write_text(json.dumps(published, indent=2) + "\n", encoding="utf-8")
    with (destination / f"{stem}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("resolution", "conversion", "implementation", "median_ms_per_frame",
                         "fps", "ns_per_sample", "mad_percent", "run_seconds"))
        for result in report["results"]:
            for name, metrics in result["metrics"].items():
                writer.writerow((result["resolution"], label(result["case"]), name,
                                 metrics["median_ms_per_frame"], metrics["frames_per_second"],
                                 metrics["ns_per_sample"], metrics["mad_percent"],
                                 json.dumps(metrics["seconds"])))


def comparison_tables(report: dict, destination: Path) -> None:
    rows = report["results"]
    ratios = [row["odin_speedup_over_fmtconv"]["odin"] for row in rows]
    deviations = [row["metrics"]["odin"]["mad_percent"] for row in rows]
    summary = (
        f"Across **{len(rows)} matched cases**, Odin's median throughput relative to FMTConv "
        f"ranged from **{min(ratios):.2f}× to {max(ratios):.2f}×**, with a "
        f"**{geometric_mean(ratios):.2f}× geometric mean**. "
        f"Odin's median time was lower in **{sum(ratio > 1 for ratio in ratios)}/{len(rows)}** cases.\n\n"
    )
    if all("odin_baseline" in row["metrics"] for row in rows):
        improvements = [row["metrics"]["odin_baseline"]["median_ms_per_frame"]
                        / row["metrics"]["odin"]["median_ms_per_frame"] for row in rows]
        summary += (
            f"Relative to the original Odin binary, the improvement ranged from "
            f"**{min(improvements):.2f}× to {max(improvements):.2f}×** "
            f"(**{geometric_mean(improvements):.2f}× geometric mean**). "
        )
    summary += (
        f"Current Odin's median absolute deviation was **{median(deviations):.1f}%** "
        f"at the median case and **{max(deviations):.1f}%** in the noisiest case. "
        "Differences close to the observed variation should be treated as ties.\n"
    )
    (destination / "dither-summary.inc").write_text(summary, encoding="utf-8")

    sections = []
    for resolution in dict.fromkeys(row["resolution"] for row in rows):
        sections.extend((f"### {resolution}\n", "Median milliseconds per frame; lower is better.\n",
                         "| Conversion | Original Odin | Current Odin | FMTConv | Odin/FMT | Odin MAD |",
                         "| --- | ---: | ---: | ---: | ---: | ---: |"))
        for row in rows:
            if row["resolution"] != resolution:
                continue
            metrics = row["metrics"]
            current, reference = metrics["odin"], metrics["fmtconv"]
            original = metrics.get("odin_baseline")
            original_text = f"{original['median_ms_per_frame']:.3f}" if original else "—"
            sections.append(
                f"| {label(row['case'])} | {original_text} | {current['median_ms_per_frame']:.3f} "
                f"| {reference['median_ms_per_frame']:.3f} | {row['odin_speedup_over_fmtconv']['odin']:.2f}× "
                f"| {current['mad_percent']:.1f}% |"
            )
        sections.append("")
    (destination / "dither-tables.inc").write_text("\n".join(sections) + "\n", encoding="utf-8")


def low_bit_table(report: dict, destination: Path) -> None:
    rows = report["results"]
    resolutions = list(dict.fromkeys(row["resolution"] for row in rows))
    lookup = {(row["case"]["name"], row["resolution"]): row for row in rows}
    cases = {row["case"]["name"]: row["case"] for row in rows}
    lines = ["Median milliseconds per frame, with median absolute deviation in parentheses.\n",
             "| Conversion | " + " | ".join(resolutions) + " |",
             "| --- | " + " | ".join("---:" for _ in resolutions) + " |"]
    for name, case in cases.items():
        cells = []
        for resolution in resolutions:
            metrics = lookup[name, resolution]["metrics"]["odin"]
            cells.append(f"{metrics['median_ms_per_frame']:.3f} ms ({metrics['mad_percent']:.1f}%)")
        lines.append(f"| {label(case)} | " + " | ".join(cells) + " |")
    (destination / "dither-low-bits.inc").write_text("\n".join(lines) + "\n", encoding="utf-8")


def figures(report: dict, destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    import numpy as np

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "svg.fonttype": "path", "svg.hashsalt": "odin-dither-benchmark",
                         "axes.spines.top": False, "axes.spines.right": False})
    rows = report["results"]
    resolutions = list(dict.fromkeys(row["resolution"] for row in rows))
    cases = {row["case"]["name"]: row["case"] for row in rows}
    lookup = {(row["case"]["name"], row["resolution"]): row for row in rows}
    ratios = np.array([[lookup[name, res]["odin_speedup_over_fmtconv"]["odin"]
                        for res in resolutions] for name in cases])
    fig, ax = plt.subplots(figsize=(9, 9), layout="constrained")
    normalization = TwoSlopeNorm(vmin=min(0.75, float(ratios.min())), vcenter=1,
                                 vmax=max(1.25, float(ratios.max())))
    heatmap = ax.imshow(ratios, cmap="BrBG", norm=normalization, aspect="auto")
    ax.set_xticks(range(len(resolutions)), resolutions)
    ax.set_yticks(range(len(cases)), [label(case) for case in cases.values()])
    ax.set_title("Odin / FMTConv throughput\nOne VapourSynth worker · values above 1 favor Odin", pad=18)
    for y in range(ratios.shape[0]):
        for x in range(ratios.shape[1]):
            value = ratios[y, x]
            color = "white" if normalization(value) > 0.82 or normalization(value) < 0.15 else "#17252b"
            ax.text(x, y, f"{value:.2f}×", ha="center", va="center", color=color)
    fig.colorbar(heatmap, ax=ax, shrink=0.6, label="FMTConv time / Odin time")
    fig.savefig(destination / "dither-speedup.svg", metadata={"Date": None})
    plt.close(fig)

    selected = ("gray16_8_shift", "yuv420p16_8_shift", "rgb16_8_full", "rgb16_12_full")
    selected = [name for name in selected if name in cases] or list(cases)[:4]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), layout="constrained")
    styles = (("odin_baseline", "Original Odin", "#9a6a47"),
              ("fmtconv", "FMTConv r31", "#626976"), ("odin", "Current Odin", "#087f7b"))
    for ax, name in zip(axes.flat, selected):
        for implementation, display, color in styles:
            if implementation not in lookup[name, resolutions[0]]["metrics"]:
                continue
            metrics = [lookup[name, res]["metrics"][implementation] for res in resolutions]
            times = [entry["median_ms_per_frame"] for entry in metrics]
            errors = [entry["median_ms_per_frame"] * entry["mad_percent"] / 100 for entry in metrics]
            ax.errorbar(range(len(resolutions)), times, yerr=errors, marker="o", markersize=4,
                        capsize=3, label=display, color=color, linewidth=1.8)
        ax.set_xticks(range(len(resolutions)), resolutions)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("Milliseconds per frame")
        ax.set_title(label(cases[name]))
        ax.grid(axis="y", alpha=0.2)
    for ax in list(axes.flat)[len(selected):]:
        ax.set_visible(False)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(
        "End-to-end frame time · one VapourSynth worker\n"
        f"Median of {report['options']['runs']} runs; error bars show median absolute deviation",
        fontsize=13,
    )
    fig.savefig(destination / "dither-times.svg", metadata={"Date": None})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("low_bits", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "assets" / "benchmarks")
    args = parser.parse_args()
    comparison, low_bits = load_report(args.comparison), load_report(args.low_bits)
    if any("fmtconv" not in row["metrics"] for row in comparison["results"]):
        raise ValueError("The comparison report must include FMTConv")
    args.output.mkdir(parents=True, exist_ok=True)
    export_data(comparison, args.output, "dither-fmtconv")
    export_data(low_bits, args.output, "dither-low-bits")
    comparison_tables(comparison, args.output)
    low_bit_table(low_bits, args.output)
    figures(comparison, args.output)
    print(f"Generated report assets in {args.output.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"Report generation failed: {error}", file=sys.stderr)
        sys.exit(1)
