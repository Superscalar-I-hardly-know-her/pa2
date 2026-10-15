#!/usr/bin/env python3
"""Plot the statistics the assignment asks each task to report.

All numbers come from the Region of Interest Statistics section.

Task 1, configs baseline / ip_stride / spp (L2 replacement LRU):
  IPC, speedup versus no-prefetch LRU, L1D load MPKI,
  L1D prefetch accuracy, L1D load coverage.

Task 2, configs baseline / irrip / dyn_irrip (no L1D prefetcher):
  IPC, speedup versus no-prefetch LRU, L2C load MPKI,
  L2 instruction load MPKI, L2 data load MPKI.

Task 3, spp_dyn_irrip (SPP + dynamic I-RRIP, DYN_IRRIP_PREFETCH=1),
shown with standalone spp and dyn_irrip:
  IPC, speedup versus no-prefetch LRU, L1D prefetch accuracy,
  L1D load coverage, and load MPKI of L1D, L2C, L2 instruction, and L2 data.

Speedup is IPC divided by the no-prefetch LRU IPC.
Accuracy is the printed L1D ACCURACY, which is useful prefetches over
prefetches issued to the next level. Coverage is the reduction in L1D
load misses relative to no-prefetch LRU.
IPC, speedup, and MPKI summaries use a geometric mean. Accuracy and
coverage summaries use an arithmetic mean.
"""

import argparse
import csv
import math
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))

TASK1 = ["baseline", "ip_stride", "spp"]
TASK2 = ["baseline", "irrip", "dyn_irrip"]
TASK3 = ["baseline", "spp", "dyn_irrip", "spp_dyn_irrip"]

IPC_RE = re.compile(r"^CPU\s+0\s+cumulative IPC:\s+([0-9.eE+-]+)", re.M)
L1D_LOAD_RE = re.compile(
    r"^L1D LOAD\s+ACCESS:.*MISS:\s+(\d+)\s+.*MPKI:\s+([0-9.eE+-]+)", re.M)
L1D_ACC_RE = re.compile(
    r"^L1D USEFUL LOAD PREFETCHES:\s+\d+\s+PREFETCH ISSUED TO LOWER LEVEL:\s+(\d+)\s+ACCURACY:\s+([0-9.eE+-]+|nan|inf|-nan)",
    re.M)
L2C_LOAD_RE = re.compile(
    r"^L2C LOAD\s+ACCESS:.*MPKI:\s+([0-9.eE+-]+)", re.M)
L2C_DATA_RE = re.compile(r"^L2C DATA LOAD MPKI:\s+([0-9.eE+-]+)", re.M)
L2C_INSTR_RE = re.compile(r"^L2C INSTRUCTION LOAD MPKI:\s+([0-9.eE+-]+)", re.M)


def roi_text(path):
    text = path.read_text(errors="replace")
    mark = text.rfind("Region of Interest Statistics")
    if mark < 0:
        raise ValueError("no ROI section in %s" % path)
    return text[mark:]


def parse_log(path):
    roi = roi_text(path)
    ipc = float(IPC_RE.search(roi).group(1))
    l1d_miss, l1d_mpki = L1D_LOAD_RE.search(roi).groups()
    issued, accuracy = L1D_ACC_RE.search(roi).groups()
    row = {
        "ipc": ipc,
        "l1d_load_miss": int(l1d_miss),
        "l1d_load_mpki": float(l1d_mpki),
        "l1d_pf_lower": int(issued),
        "l1d_accuracy": float(accuracy) if issued != "0" else None,
        "l2c_load_mpki": float(L2C_LOAD_RE.search(roi).group(1)),
        "l2_data_mpki": float(L2C_DATA_RE.search(roi).group(1)),
        "l2_instruction_mpki": float(L2C_INSTR_RE.search(roi).group(1)),
    }
    return row


def geomean(values):
    vals = [v for v in values if v is not None and v > 0]
    if not vals:
        return None
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def arithmean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def load_logs(log_root):
    rows = {}
    for config_dir in sorted(Path(log_root).iterdir()):
        if not config_dir.is_dir():
            continue
        for log in sorted(config_dir.glob("*.log")):
            rows[(log.stem, config_dir.name)] = parse_log(log)
    return rows


def with_derived(rows):
    out = {}
    for (trace, config), row in rows.items():
        base = rows.get((trace, "baseline"))
        item = dict(row)
        item["trace"] = trace
        item["config"] = config
        if base:
            item["speedup"] = row["ipc"] / base["ipc"]
            if base["l1d_load_miss"]:
                item["coverage"] = 100.0 * (base["l1d_load_miss"] - row["l1d_load_miss"]) / base["l1d_load_miss"]
            else:
                item["coverage"] = None
        else:
            item["speedup"] = None
            item["coverage"] = None
        out[(trace, config)] = item
    return out


def traces_for(rows, configs):
    names = sorted({trace for (trace, config) in rows if config in configs})
    return [trace for trace in names if all((trace, config) in rows for config in configs)]


def write_csv(path, rows, traces, configs):
    fields = [
        "trace", "config", "ipc", "speedup", "l1d_load_mpki", "l1d_accuracy",
        "coverage", "l2c_load_mpki", "l2_instruction_mpki", "l2_data_mpki",
        "l1d_load_miss",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for trace in traces:
            for config in configs:
                writer.writerow(rows[(trace, config)])


def summarize(rows, traces, configs, metric, mean):
    return {config: mean(rows[(trace, config)][metric] for trace in traces) for config in configs}


def plot_group(rows, traces, configs, metrics, out_dir, prefix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]
    for metric, ylabel, zoom in metrics:
        fig, ax = plt.subplots(figsize=(8.2, 4.4))
        width = 0.8 / len(configs)
        xs = list(range(len(traces)))
        for i, config in enumerate(configs):
            vals = [rows[(trace, config)][metric] for trace in traces]
            offset = (i - (len(configs) - 1) / 2.0) * width
            # Baseline issues no prefetches, so its accuracy is undefined.
            heights = [float("nan") if v is None else v for v in vals]
            ax.bar([x + offset for x in xs], heights,
                   width=width * 0.92, label=config, color=colors[i % len(colors)])
        ax.set_xticks(xs)
        ax.set_xticklabels(traces, rotation=15, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(prefix + " " + ylabel)
        if zoom:
            present = [rows[(t, c)][metric] for t in traces for c in configs if rows[(t, c)][metric] is not None]
            if present:
                lo, hi = min(present), max(present)
                pad = max(0.005, (hi - lo) * 0.6)
                ax.set_ylim(min(lo, 1.0) - pad, max(hi, 1.0) + pad)
                ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=len(configs), frameon=False)
        fig.tight_layout()
        for suffix in ("png", "pdf"):
            fig.savefig(out_dir / ("%s_%s.%s" % (prefix, metric, suffix)), bbox_inches="tight")
        plt.close(fig)


def emit(rows, traces, configs, out_dir, prefix, metrics):
    if not traces:
        print("skip %s: logs are incomplete" % prefix)
        return
    write_csv(out_dir / ("%s.csv" % prefix), rows, traces, configs)
    plot_group(rows, traces, configs, metrics, out_dir / "plots", prefix)
    print(prefix, ", ".join(traces))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, default=ROOT / "results/pa2/logs")
    parser.add_argument("--out", type=Path, default=ROOT / "results/pa2")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        sample = ROOT / "results/task1/full/Trace1-003/spp.log"
        row = parse_log(sample)
        assert abs(row["ipc"] - 0.232519) < 1e-6
        assert row["l1d_load_miss"] == 260084
        assert abs(row["l1d_accuracy"] - 63.9061) < 1e-4
        assert abs(row["l2_data_mpki"] - 7.06916) < 1e-5
        assert abs(row["l2_instruction_mpki"] - 10.3652) < 1e-4
        print("self-test passed")
        return

    rows = with_derived(load_logs(args.logs))
    task1_metrics = [
        ("ipc", "IPC", False),
        ("speedup", "Speedup", True),
        ("l1d_load_mpki", "L1D load MPKI", False),
        ("l1d_accuracy", "L1D prefetch accuracy (%)", False),
        ("coverage", "L1D load coverage (%)", False),
    ]
    task2_metrics = [
        ("ipc", "IPC", False),
        ("speedup", "Speedup", True),
        ("l2c_load_mpki", "L2C load MPKI", False),
        ("l2_instruction_mpki", "L2 instruction load MPKI", False),
        ("l2_data_mpki", "L2 data load MPKI", False),
    ]
    task3_metrics = [
        ("ipc", "IPC", False),
        ("speedup", "Speedup", True),
        ("l1d_accuracy", "L1D prefetch accuracy (%)", False),
        ("coverage", "L1D load coverage (%)", False),
        ("l1d_load_mpki", "L1D load MPKI", False),
        ("l2c_load_mpki", "L2C load MPKI", False),
        ("l2_instruction_mpki", "L2 instruction load MPKI", False),
        ("l2_data_mpki", "L2 data load MPKI", False),
    ]
    emit(rows, traces_for(rows, TASK1), TASK1, args.out, "task1", task1_metrics)
    emit(rows, traces_for(rows, TASK2), TASK2, args.out, "task2", task2_metrics)
    emit(rows, traces_for(rows, TASK3), TASK3, args.out, "task3", task3_metrics)

    # Summaries are printed only; the per-trace CSV is the table source.
    for name, configs, metric, mean in (
        ("task1 ipc", TASK1, "ipc", geomean),
        ("task1 speedup", TASK1, "speedup", geomean),
        ("task1 l1d mpki", TASK1, "l1d_load_mpki", geomean),
        ("task1 accuracy", TASK1, "l1d_accuracy", arithmean),
        ("task1 coverage", TASK1, "coverage", arithmean),
        ("task2 ipc", TASK2, "ipc", geomean),
        ("task2 speedup", TASK2, "speedup", geomean),
        ("task2 l2c mpki", TASK2, "l2c_load_mpki", geomean),
        ("task2 l2 instruction mpki", TASK2, "l2_instruction_mpki", geomean),
        ("task2 l2 data mpki", TASK2, "l2_data_mpki", geomean),
    ):
        traces = traces_for(rows, configs)
        if traces:
            print(name, summarize(rows, traces, configs, metric, mean))


if __name__ == "__main__":
    main()
