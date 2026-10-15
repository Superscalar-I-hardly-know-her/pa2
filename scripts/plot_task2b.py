#!/usr/bin/env python3
"""Plot Dynamic I-RRIP threshold sensitivity and compare with Task 2A baselines."""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
from sweep_task2b import THRESHOLDS, TRACES

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "start-irrip", "persistent"], default="original")
    args = parser.parse_args()
    experiment = ROOT / "results/task2b"
    if args.variant != "original":
        experiment /= args.variant
    source = experiment / "full/results.csv"
    rows = [r for r in csv.DictReader(source.open()) if r["status"] == "ok"]
    assert rows, "No completed Dynamic I-RRIP results"
    data = {(r["trace"], float(r["threshold"])): r for r in rows}
    baselines = {(r["trace"], r["name"]): r for r in csv.DictReader(
        (ROOT / "results/task2/full/results.csv").open()) if r["status"] == "ok"}
    output = experiment / "plots"
    output.mkdir(exist_ok=True)
    status = f"{args.variant}: {'Complete' if len(rows) == 15 else 'Partial'} sweep: {len(rows)}/15 runs"
    colors = ["#0072B2", "#D55E00", "#009E73"]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.18, "axes.axisbelow": True})
    metrics = [("ipc", "IPC"), ("speedup", "Speedup vs LRU"), ("l2_load_mpki", "L2 load MPKI"),
               ("instruction_mpki", "L2 instruction load MPKI"), ("data_mpki", "L2 data load MPKI")]

    def save(fig, name):
        fig.text(0.01, 0.006, status, fontsize=9, color="#555555")
        for suffix in ("png", "pdf"):
            fig.savefig(output / f"{name}.{suffix}", dpi=180, facecolor="white")
        plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, (metric, label) in zip(axes.flat, metrics + [("roi_irrip_fraction", "Follower ROI loads using I-RRIP (%)")]):
        for trace, color in zip(TRACES, colors):
            ys = [float(data[trace, t][metric]) if (trace, t) in data else math.nan for t in THRESHOLDS]
            if metric == "roi_irrip_fraction":
                ys = [100*y for y in ys]
            ax.plot(THRESHOLDS, ys, "o-", color=color, label=trace)
        if metric == "speedup":
            ax.axhline(1, color="black", linestyle=":", linewidth=0.8)
        ax.set_xticks(THRESHOLDS)
        ax.set(xlabel="Instruction-miss-share threshold", ylabel=label)
        ax.ticklabel_format(axis="y", useOffset=False)
    fig.legend(*axes.flat[0].get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 0.025))
    fig.suptitle("Dynamic I-RRIP: threshold sensitivity")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    save(fig, "threshold_sensitivity")

    ranking = []
    for t in THRESHOLDS:
        if all((trace, t) in data for trace in TRACES):
            ranking.append((t, math.exp(sum(math.log(float(data[trace, t]["speedup"])) for trace in TRACES)/3)))
    ranking.sort(key=lambda x: x[1], reverse=True)
    chosen = ranking[0][0] if len(rows) == 15 else 0.25
    selected = [("lru", "LRU", "#888888"), ("i2-h0-a0-b0", "SRRIP", colors[0]),
                ("i2-h1-a1-b2", "Selected static I-RRIP", colors[1]),
                (None, f"Dynamic (threshold {chosen:.2f})", colors[2])]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, (metric, label) in zip(axes.flat, metrics):
        for i, (name, legend, color) in enumerate(selected):
            ys = []
            for trace in TRACES:
                row = baselines.get((trace, name)) if name else data.get((trace, chosen))
                v = float(row["ipc"])/float(baselines[trace, "lru"]["ipc"]) if row and metric == "speedup" else float(row[metric]) if row else math.nan
                ys.append(v)
            x = [j-0.3+i*0.2 for j in range(3)]
            if metric == "speedup":
                ax.plot(x, ys, "o", color=color, label=legend)
            else:
                ax.bar(x, ys, 0.2, color=color, label=legend)
        if metric == "speedup":
            ax.axhline(1, color="black", linestyle=":", linewidth=0.8)
        ax.set_xticks(range(3))
        ax.set_xticklabels(["Trace 1", "Trace 2", "Trace 3"])
        ax.set_ylabel(label)
        ax.ticklabel_format(axis="y", useOffset=False)
    axes.flat[-1].axis("off")
    axes.flat[-1].legend(*axes.flat[0].get_legend_handles_labels(), loc="upper left", frameon=False)
    axes.flat[-1].text(0, 0.4, f"32 RRIP leaders\n4096-observation windows\nStatic: insert 2, data hit 1, bias 2\n{'Best threshold across all three traces' if len(rows) == 15 else 'Default threshold; missing marks pending'}",
                       transform=axes.flat[-1].transAxes, va="top", fontsize=10)
    fig.suptitle("Dynamic versus static L2 replacement")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    save(fig, "policy_comparison")

    fig, axes = plt.subplots(3, 1, figsize=(12, 9))
    for ax, trace in zip(axes, TRACES):
        path = experiment / "full" / trace / f"threshold-{chosen:.2f}.log"
        windows = []
        if path.exists():
            for line in path.read_text().splitlines():
                if line.startswith("DYN_WINDOW "):
                    windows.append(dict(part.split("=", 1) for part in line.split()[1:]))
        for w in windows:
            if w["mode"] == "IRRIP":
                index = int(w["index"])
                ax.axvspan(index, index+1, color=colors[0], alpha=0.12)
        ax.plot([int(w["index"]) for w in windows], [float(w["share"]) for w in windows], "o-", color=colors[0], label="Leader instruction-miss share")
        ax.axhline(chosen, color="black", linestyle="--", label="Threshold")
        roi = next((int(w["index"]) for w in windows if w["phase"] == "roi"), None)
        if roi is not None:
            ax.axvline(roi, color=colors[1], linestyle=":", label="First decision in ROI")
        ax.set(title=trace, ylabel="Instruction-miss share", ylim=(-0.03, 1.03), xlim=(0, max(2, len(windows)+1)))

    axes[-1].set_xlabel("Decision window (warmup and ROI; each window = 4096 leader loads)")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.025))
    fig.suptitle(f"Controller decisions at threshold {chosen:.2f}; shading = I-RRIP selected after decision")
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    save(fig, "controller_decisions")
    shutil.copyfile(source, output / "snapshot.csv")
    (output / "README.txt").write_text(status + f"\nComparison/controller threshold: {chosen:.2f}\n" +
        "Figures: threshold_sensitivity, policy_comparison, controller_decisions (PNG and PDF).\n"
        "Threshold is selected by geometric-mean speedup across all three traces after all 15 runs.\n")
    print(f"{status}; generated three PNG/PDF figures in {output}")


if __name__ == "__main__":
    main()
