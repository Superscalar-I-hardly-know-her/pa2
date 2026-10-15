#!/usr/bin/env python3
"""Compare the original controller, I-RRIP initialization, and persistent switching."""
import csv
import json
import math
import os
from pathlib import Path
from sweep_task2b import THRESHOLDS, TRACES, diagnostics

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

VARIANTS = [("original", "Start RRIP", "#777777"), ("start-irrip", "Start I-RRIP", "#0072B2"),
            ("persistent", "Start I-RRIP + persistent evidence", "#D55E00")]


def main():
    output = ROOT / "results/task2b/variant-comparison"
    output.mkdir(exist_ok=True)
    data, all_rows = {}, []
    paths = {}
    for variant, _, _ in VARIANTS:
        paths[variant] = ROOT / "results/task2b" / (variant if variant != "original" else "")
        rows = list(csv.DictReader((paths[variant] / "full/results.csv").open()))
        assert len(rows) == 15 and all(r["status"] == "ok" for r in rows), f"incomplete {variant}"
        for row in rows:
            threshold = float(row["threshold"])
            log = (paths[variant] / "full" / row["trace"] / f"threshold-{threshold:.2f}.log").read_text()
            diagnostics(log, threshold, variant)
            row["variant"] = variant
            data[variant, row["trace"], threshold] = row
            all_rows.append(row)
    baselines = {(r["trace"], r["name"]): r for r in csv.DictReader(
        (ROOT / "results/task2/full/results.csv").open()) if r["status"] == "ok"}
    def exact_ipc(row):
        return int(row["instructions"]) / int(row["cycles"])
    def ratio(variant, trace, threshold, reference):
        return exact_ipc(data[variant, trace, threshold]) / exact_ipc(baselines[trace, reference])
    static = math.exp(sum(math.log(exact_ipc(baselines[t, "i2-h1-a1-b2"]) /
                                   exact_ipc(baselines[t, "lru"])) for t in TRACES)/3)
    for row in all_rows:
        variant, trace, threshold = row["variant"], row["trace"], float(row["threshold"])
        row["ipc_exact"] = exact_ipc(row)
        row["speedup_exact"] = ratio(variant, trace, threshold, "lru")
        row["speedup_vs_static_exact"] = ratio(variant, trace, threshold, "i2-h1-a1-b2")

    def gmean(variant, threshold, field):
        reference = "lru" if field == "speedup" else "i2-h1-a1-b2"
        return math.exp(sum(math.log(ratio(variant, trace, threshold, reference)) for trace in TRACES)/3)

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.18, "axes.axisbelow": True})
    def save(fig, name):
        for suffix in ("png", "pdf"):
            fig.savefig(output / f"{name}.{suffix}", dpi=180, facecolor="white")
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, trace in zip(axes.flat, [None, *TRACES]):
        for variant, label, color in VARIANTS:
            ys = [100*((gmean(variant, t, "speedup_vs_static") if trace is None else
                        ratio(variant, trace, t, "i2-h1-a1-b2"))-1) for t in THRESHOLDS]
            ax.plot(THRESHOLDS, ys, "o-", label=label, color=color)
        ax.axhline(0, color="black", linestyle="--", linewidth=0.9)
        ax.set(title="Geometric mean across all three traces" if trace is None else trace,
               xlabel="Instruction-miss-share threshold", ylabel="IPC change vs static I-RRIP (%)")
        ax.set_xticks(THRESHOLDS)
    fig.legend(*axes.flat[0].get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 0.015))
    fig.suptitle("Does starting in I-RRIP and requiring persistent evidence help?")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    save(fig, "controller_comparison")

    # Common threshold makes the mode histories a controlled comparison.
    threshold = 0.25
    fig, axes = plt.subplots(3, 3, figsize=(15, 10))
    for col, (variant, label, color) in enumerate(VARIANTS):
        for row, trace in enumerate(TRACES):
            ax = axes[row, col]
            windows = [dict(p.split("=", 1) for p in line.split()[1:]) for line in
                       (paths[variant] / "full" / trace / "threshold-0.25.log").read_text().splitlines()
                       if line.startswith("DYN_WINDOW ")]
            if variant != "original":
                ax.axvspan(0, 1, color=color, alpha=0.14)
            for w in windows:
                if w["mode"] == "IRRIP":
                    ax.axvspan(int(w["index"]), int(w["index"])+1, color=color, alpha=0.14)
            ax.plot([int(w["index"]) for w in windows], [float(w["share"]) for w in windows], "o-", color=color, markersize=3)
            ax.axhline(threshold, color="black", linestyle="--", linewidth=0.8)
            roi = next((int(w["index"]) for w in windows if w["phase"] == "roi"), None)
            if roi is not None:
                ax.axvline(roi, color="#CC3311", linestyle=":")
            ax.set(ylim=(-0.03, 1.03), xlim=(0, len(windows)+1))
            if row == 0: ax.set_title(label)
            if col == 0: ax.set_ylabel(trace + "\nInstruction-miss share")
            if row == 2: ax.set_xlabel("Decision window (4096 leader loads)")
    handles = [Patch(facecolor="#999999", alpha=0.25, label="Shading: I-RRIP active"),
               Line2D([], [], color="black", linestyle="--", label="Threshold 0.25"),
               Line2D([], [], color="#CC3311", linestyle=":", label="First decision in ROI")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("Mode histories at the same threshold; decisions apply to the following interval")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    save(fig, "mode_histories")

    fields = list(all_rows[0])
    with (output / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    lines = ["# Dynamic controller experiments", "", "All variants use 32 permanent RRIP leaders, 4096-observation windows, five thresholds, and the fixed Task 2A I-RRIP configuration. Every full run uses 25M warmup + 25M measured instructions.", "",
             "1. **Start RRIP:** original controller; every window selects I-RRIP iff the score exceeds the threshold.",
             "2. **Start I-RRIP:** only initialization changes; all later decisions are identical in definition to the original controller.",
             "3. **Persistent evidence:** starts in I-RRIP, requires two consecutive below-threshold windows with misses to select RRIP, and returns to I-RRIP after one above-threshold window. No-miss or equality windows retain mode and break the low-score streak.", "",
             "## Best threshold for each method", "", "| Method | Best threshold | Speedup vs LRU | IPC change vs static I-RRIP |", "| --- | ---: | ---: | ---: |"]
    best_configs = []
    for variant, label, _ in VARIANTS:
        best = max(THRESHOLDS, key=lambda t: gmean(variant, t, "speedup"))
        ties = [t for t in THRESHOLDS if abs(gmean(variant, t, "speedup")-gmean(variant, best, "speedup")) < 1e-12]
        threshold_label = ", ".join(f"{t:.2f}" for t in ties)
        speedup = gmean(variant, best, "speedup")
        relative = gmean(variant, best, "speedup_vs_static")
        lines.append(f"| {label} | {threshold_label} | {speedup:.6f} ({100*(speedup-1):+.3f}%) | {100*(relative-1):+.4f}% |")
        best_configs.append(dict(variant=variant, threshold=best, tied_thresholds=ties, speedup_vs_lru=speedup, speedup_vs_static=relative))
    lines += ["", f"Selected static I-RRIP speedup vs LRU: **{static:.6f} ({100*(static-1):+.3f}%)**.", "",
              "## Matched-threshold comparisons", "", "These ratios isolate the two changes at the same threshold rather than comparing separately selected winners.", "",
              "| Threshold | Start I-RRIP vs original | Persistence vs initial-only |", "| --- | ---: | ---: |"]
    for t in THRESHOLDS:
        initial = gmean("start-irrip", t, "speedup") / gmean("original", t, "speedup")
        persistent = gmean("persistent", t, "speedup") / gmean("start-irrip", t, "speedup")
        lines.append(f"| {t:.2f} | {100*(initial-1):+.4f}% | {100*(persistent-1):+.4f}% |")
    best = max(best_configs, key=lambda x: x["speedup_vs_static"])
    lines += ["", "## Conclusion", "",
              (f"The best dynamic result is {best['variant']} at threshold {best['threshold']:.2f}, with {100*(best['speedup_vs_static']-1):+.4f}% IPC relative to selected static I-RRIP. " +
               ("It beats the static policy on the geometric mean." if best["speedup_vs_static"] > 1 else "None of these dynamic variants beats selected static I-RRIP on the geometric mean.")), "",
              "Comparison IPC is computed from exact retired-instruction and cycle counts, avoiding the simulator output’s six-digit IPC rounding. All decision windows were independently checked against their controller rules. Original results were retained; the two new sweeps ran sequentially. Different warmup behavior can affect ROI results even when ROI mode fractions match."]
    (output / "SUMMARY.md").write_text("\n".join(lines)+"\n")
    (output / "best-configs.json").write_text(json.dumps(best_configs, indent=2)+"\n")
    print("\n".join(lines[:17]))
    print(f"Comparison plots and report: {output}")


if __name__ == "__main__":
    main()
