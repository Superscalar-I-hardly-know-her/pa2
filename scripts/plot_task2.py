#!/usr/bin/env python3
"""Plot a snapshot of the Task 2A sweep; safe to rerun while simulations continue."""
import argparse
import csv
import io
import math
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from sweep_task2 import configurations

CONFIGS = list(configurations())
TRACES = ["Trace1-003", "Trace2-001", "Trace3-002"]
SRRIP = "i2-h0-a0-b0"
DEFAULT = "i2-h1-a1-b2"
COLORS = ["#0072B2", "#D55E00", "#009E73"]


def read_results(path):
    # The active runner writes CSV snapshots. Retry if caught during a write.
    for _ in range(10):
        before = path.stat()
        text = path.read_text()
        after = path.stat()
        rows = list(csv.DictReader(io.StringIO(text)))
        if before.st_mtime_ns == after.st_mtime_ns and before.st_size == after.st_size and rows:
            if all(row.get("status") and row.get("cycles") for row in rows if row.get("status") == "ok"):
                return [r for r in rows if r.get("status") == "ok"]
        time.sleep(0.1)
    raise ValueError("No stable completed results available; rerun after another simulation finishes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/task2/full/results.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "results/task2/plots")
    args = parser.parse_args()
    rows = read_results(args.input)
    data = {(r["trace"], r["name"]): r for r in rows if r["name"] != "rrip"}
    traces = [t for t in TRACES if (t, "lru") in data]
    if not traces:
        parser.error("no completed LRU baseline available")
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.18, "axes.axisbelow": True})
    expected = len(TRACES) * len(CONFIGS)
    status = ("Complete sweep" if len(data) == expected else "Partial sweep") + f": {len(data)}/{expected} runs"
    if any(int(r["instructions"]) < 25_000_000 for r in rows):
        status = "SMOKE TEST — " + status
    generated = []

    def value(trace, name, metric):
        row = data.get((trace, name))
        if not row:
            return math.nan
        if metric == "speedup":
            return float(row["ipc"]) / float(data[trace, "lru"]["ipc"])
        return float(row[metric])

    def save(fig, name):
        fig.text(0.01, 0.006, status, fontsize=9, color="#555555")
        for suffix in ("png", "pdf"):
            fig.savefig(args.output / f"{name}.{suffix}", dpi=180, facecolor="white")
        plt.close(fig)
        generated.append(name)

    # Only compare suite-wide ranks when every trace is present for that configuration.
    ranking = []
    for cfg in CONFIGS[1:]:
        name = cfg["name"]
        if all((t, name) in data and (t, "lru") in data for t in TRACES):
            gmean = math.exp(sum(math.log(value(t, name, "speedup")) for t in TRACES) / len(TRACES))
            ranking.append((name, gmean))
    ranking.sort(key=lambda r: r[1], reverse=True)
    # Do not pick an apparent winner until every configuration has completed.
    best = ranking[0][0] if len(ranking) == 30 else None

    selected = [("lru", "LRU", "#888888"), (SRRIP, "SRRIP", COLORS[0]),
                (DEFAULT, "Selected I-RRIP", COLORS[1])]
    if best and best not in {s[0] for s in selected}:
        selected.append((best, "Best across traces", COLORS[2]))
    metrics = [("ipc", "IPC"), ("speedup", "Speedup vs LRU"), ("l2_load_mpki", "L2 load MPKI"),
               ("instruction_mpki", "L2 instruction load MPKI"), ("data_mpki", "L2 data load MPKI")]
    fig, axes = plt.subplots(2, 3, figsize=(13, 8))
    width = 0.8 / len(selected)
    for ax, (metric, label) in zip(axes.flat, metrics):
        for i, (name, legend, color) in enumerate(selected):
            x = [j - 0.4 + width*(i+0.5) for j in range(len(traces))]
            ys = [value(t, name, metric) for t in traces]
            if metric == "speedup":
                ax.plot(x, ys, "o", label=legend, color=color, markersize=7)
            else:
                ax.bar(x, ys, width, label=legend, color=color)
        ax.set_xticks(range(len(traces)))
        ax.set_xticklabels(traces)
        ax.set_ylabel(label)
        if metric == "speedup":
            ax.axhline(1, color="black", linewidth=0.8, linestyle="--")
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    axes.flat[-1].axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(handles, labels, loc="upper left", frameon=False)
    axes.flat[-1].text(0, 0.45, "Selected: insert 2, data hit 1, bias 2\nMissing marks = runs pending\nBest selected only after all 93 runs" + (f"\nBest config: {best}" if best else ""), transform=axes.flat[-1].transAxes,
                       fontsize=10, va="top")
    fig.suptitle("L2 replacement policies: performance and misses")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    save(fig, "policy_comparison")

    for trace in traces:
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        for ax, (metric, label) in zip(axes.flat, metrics[1:]):
            for insert in range(3):
                for hit in range(2):
                    names = [f"i{insert}-h{hit}-a1-b{b}" for b in range(4)]
                    ys = [value(trace, n, metric) for n in names]
                    ax.plot(range(4), ys, color=COLORS[insert], linestyle="-" if hit == 0 else "--",
                            marker="o" if hit == 0 else "s", markersize=4,
                            label=f"Insert {insert}, data hit {hit}")
            ax.axhline(value(trace, "lru", metric), color="#888888", linestyle=":", label="LRU")
            sr = value(trace, SRRIP, metric)
            if math.isfinite(sr):
                ax.axhline(sr, color="black", linestyle="-.", linewidth=0.9, label="SRRIP")
            ax.set_xticks(range(4))
            ax.set_xlabel("Eviction bias (0 = tie preference; 3 = strict data first)")
            ax.set_ylabel(label)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.025))
        fig.suptitle(f"{trace}: effect of instruction protection")
        fig.tight_layout(rect=(0, 0.13, 1, 0.95))
        save(fig, f"{trace}_bias")

        # Color shows whether trading data misses for instruction hits improves IPC.
        points = [r for (t, name), r in data.items() if t == trace and name != "lru"]
        if not points:
            continue
        changes = [100*(value(trace, r["name"], "speedup")-1) for r in points]
        limit = max(0.1, max(abs(x) for x in changes))
        norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
        fig, ax = plt.subplots(figsize=(9, 7))
        for aware, marker, label in [(0, "^", "Ordinary eviction"), (1, "o", "Instruction-aware eviction")]:
            group = [r for r in points if int(r["aware"]) == aware]
            ax.scatter([float(r["data_mpki"]) for r in group], [float(r["instruction_mpki"]) for r in group],
                       c=[100*(value(trace, r["name"], "speedup")-1) for r in group],
                       cmap="RdBu", norm=norm, marker=marker, s=65, edgecolors="#555555", linewidths=0.5, label=label)
        ax.scatter(value(trace, "lru", "data_mpki"), value(trace, "lru", "instruction_mpki"),
                   marker="*", s=160, color="black", label="LRU", zorder=5)
        for name, label, offset in [(SRRIP, "SRRIP", (8, 12)), (DEFAULT, "Selected I-RRIP", (8, -18))]:
            if (trace, name) in data:
                ax.annotate(label, (value(trace, name, "data_mpki"), value(trace, name, "instruction_mpki")),
                            xytext=offset, textcoords="offset points", fontsize=9)
        fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap="RdBu"), ax=ax, label="IPC change vs LRU (%)")
        ax.set(xlabel="L2 data load MPKI (lower is better)", ylabel="L2 instruction load MPKI (lower is better)",
               title=f"{trace}: instruction/data miss tradeoff")
        handles = [Line2D([], [], marker=m, linestyle="", color=c, markersize=size, label=label)
                   for m, c, size, label in [("^", "#777777", 7, "Ordinary eviction"),
                                            ("o", "#777777", 7, "Instruction-aware eviction"),
                                            ("*", "black", 11, "LRU")]]
        ax.legend(handles=handles, frameon=False)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        save(fig, f"{trace}_tradeoff")

    if ranking:
        fig, ax = plt.subplots(figsize=(10, max(4, len(ranking)*0.28+1.8)))
        changes = [100*(g-1) for _, g in ranking]
        ax.barh(range(len(ranking)), changes, color=["#009E73" if x >= 0 else "#D55E00" for x in changes])
        ax.set_yticks(range(len(ranking)))
        ax.set_yticklabels([name for name, _ in ranking])
        ax.invert_yaxis()
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set(xlabel="Geometric-mean IPC change vs LRU (%)", title="Performance across all three traces")
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        save(fig, "suite_ranking")

    # Preserve the plotted snapshot so plots can be matched to the exact input data.
    with (args.output / "snapshot.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "README.txt").write_text(status + "\n\n" + "\n".join(generated) +
        "\n\nIDs: i = instruction insertion RRPV, h = data-hit RRPV, a = aware eviction, b = eviction bias.\n"
        "Missing points/bars are pending runs. Ranking requires all three traces per configuration.\n"
        "Rerun this script to refresh after more simulations complete.\n")
    print(f"{status}; wrote {len(generated)} figures as PNG and PDF to {args.output}")


if __name__ == "__main__":
    main()
