#!/usr/bin/env python3
"""Build Summary.pdf from the completed 25M ChampSim runs."""

import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF
from fpdf.fonts import FontFace

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "results" / "report" / "figures"
OUT = ROOT / "Summary.pdf"

COLORS = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]
HEAD = FontFace(emphasis="BOLD", size_pt=8, color=(255, 255, 255), fill_color=(44, 62, 80))
MEAN = FontFace(emphasis="BOLD", size_pt=8, fill_color=(232, 236, 241))


def read_csv(path):
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def fnum(text):
    if text is None or text == "":
        return None
    return float(text)


def geomean(values):
    vals = [v for v in values if v is not None and v > 0]
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def arithmean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def pct(ratio):
    return (ratio - 1.0) * 100.0


def trace_name(raw):
    return {"Trace1-003": "Trace 1", "Trace2-001": "Trace 2", "Trace3-002": "Trace 3"}[raw]


def traces_of(rows):
    order = ["Trace1-003", "Trace2-001", "Trace3-002"]
    present = {row["trace"] for row in rows}
    return [name for name in order if name in present]


class Report(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, "CS683 PA2  |  %d" % self.page_no(), align="C")
        self.set_text_color(0, 0, 0)


def paragraph(pdf, text, size=10, gap=2.2):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", size=size)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 4.8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(gap)


def heading(pdf, text, level=1):
    if pdf.get_y() > (250 if level == 1 else 255):
        pdf.add_page()
    size = 16 if level == 1 else 12
    pdf.ln(1 if level == 1 else 0.5)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", size)
    pdf.set_text_color(20, 33, 46)
    pdf.multi_cell(0, 7 if level == 1 else 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.2)
    pdf.set_text_color(20, 20, 20)


def caption(pdf, text):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(0, 4, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(20, 20, 20)


def draw_table(pdf, headers, rows, widths):
    pdf.set_font("Helvetica", size=8)
    needed = 6.2 * (len(rows) + 1) + 6
    remaining = pdf.page_break_trigger - pdf.get_y()
    page_body = pdf.page_break_trigger - pdf.t_margin
    if needed < page_body and needed > remaining:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    scale = pdf.epw / sum(widths)
    widths = [w * scale for w in widths]
    with pdf.table(
        width=pdf.epw,
        col_widths=tuple(widths),
        line_height=5.2,
        text_align="CENTER",
        first_row_as_headings=True,
        headings_style=HEAD,
    ) as table:
        head = table.row()
        for cell in headers:
            head.cell(cell)
        for i, values in enumerate(rows):
            style = MEAN if values[0] == "Mean" else None
            row = table.row()
            for cell in values:
                row.cell(str(cell), style=style)
    pdf.ln(1.5)


def fmt_ipc(value):
    return "%.4f" % value


def fmt_pct(value, signed=False):
    if value is None:
        return "-"
    return "%+.2f%%" % value if signed else "%.2f%%" % value


def fmt_mpki(value):
    return "%.3f" % value


def grouped(path, labels, series, ylabel, title, zoom=False):
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    count = len(series)
    width = 0.78 / count
    xs = list(range(len(labels)))
    for i, (name, values) in enumerate(series):
        offset = (i - (count - 1) / 2.0) * width
        heights = [float("nan") if v is None else v for v in values]
        ax.bar([x + offset for x in xs], heights, width=width * 0.92,
               label=name, color=COLORS[i % len(COLORS)])
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if zoom:
        present = [v for _, values in series for v in values if v is not None]
        lo, hi = min(present + [1.0]), max(present + [1.0])
        pad = max(0.004, (hi - lo) * 0.45)
        ax.set_ylim(lo - pad, hi + pad)
        ax.axhline(1.0, color="#666666", linestyle="--", linewidth=0.8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=count, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def lines(path, xs, series, xlabel, ylabel, title):
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    for i, (name, values) in enumerate(series):
        ax.plot(xs, values, marker="o", label=name, color=COLORS[i % len(COLORS)])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=min(4, len(series)), frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def place_image(pdf, path, width=180):
    if pdf.get_y() > 175:
        pdf.add_page()
    pdf.image(str(path), w=width)
    pdf.ln(2)


def load():
    comparison = read_csv(ROOT / "results/task1/comparison/results.csv")
    sweep = read_csv(ROOT / "results/task1/sweep/results.csv")
    task2 = read_csv(ROOT / "results/task2/full/results.csv")
    task2b = read_csv(ROOT / "results/task2b/full/results.csv")
    task3 = read_csv(ROOT / "results/task3/results.csv")
    return comparison, sweep, task2, task2b, task3


def index_rows(rows, *keys):
    return {tuple(row[key] for key in keys): row for row in rows}


def task1_tables(comparison, sweep):
    order = traces_of(comparison)
    by_cmp = index_rows(comparison, "trace", "scheme")
    selected = [row for row in sweep if row["name"] == "u2-p1-a1-2-4"]
    by_sel = {row["trace"]: row for row in selected}
    schemes = [
        ("No prefetch", "none", None),
        ("IP-stride", "ip_stride", None),
        ("SPP", None, by_sel),
    ]
    body = []
    summary_src = {name: [] for name, _, _ in schemes}
    for trace in order:
        for name, scheme, extra in schemes:
            if extra is None:
                row = by_cmp[(trace, scheme)]
                accuracy = fnum(row["simulator_accuracy"])
                coverage = fnum(row["coverage"])
            else:
                row = extra[trace]
                accuracy = fnum(row["simulator_accuracy"])
                coverage = fnum(row["coverage"])
            speedup = fnum(row["speedup"])
            summary_src[name].append({
                "ipc": fnum(row["ipc"]),
                "speedup": speedup,
                "mpki": fnum(row["l1d_load_mpki"]),
                "accuracy": None if accuracy is None else accuracy * 100.0,
                "coverage": None if coverage is None else coverage * 100.0,
            })
            body.append([
                trace_name(trace),
                name,
                fmt_ipc(fnum(row["ipc"])),
                fmt_pct(pct(speedup), signed=True),
                fmt_mpki(fnum(row["l1d_load_mpki"])),
                "-" if accuracy is None else fmt_pct(accuracy * 100.0),
                "-" if name == "No prefetch" else fmt_pct(coverage * 100.0),
            ])
    mean = ["Mean", ""]
    # One mean row per scheme would be clearer as its own rows.
    mean_rows = []
    for name, _, _ in schemes:
        items = summary_src[name]
        acc = arithmean(item["accuracy"] for item in items)
        cov = arithmean(item["coverage"] for item in items if item["coverage"] is not None and name != "No prefetch")
        mean_rows.append([
            "Mean",
            name,
            fmt_ipc(geomean(item["ipc"] for item in items)),
            fmt_pct(pct(geomean(item["speedup"] for item in items)), signed=True),
            fmt_mpki(geomean(item["mpki"] for item in items)),
            "-" if acc is None else fmt_pct(acc),
            "-" if name == "No prefetch" else fmt_pct(cov),
        ])
    ranking = []
    names = []
    for row in sweep:
        if row["name"] not in names:
            names.append(row["name"])
    for name in names:
        group = [row for row in sweep if row["name"] == name]
        ranking.append((geomean(fnum(row["speedup"]) for row in group), name, group[0]))
    ranking.sort(reverse=True)
    rank_rows = []
    for speedup, name, sample in ranking:
        group = [row for row in sweep if row["name"] == name]
        rank_rows.append([
            "u=%s, p=%s, a=%s" % (sample["uniform"], sample["pattern"], sample["accuracy"]),
            fmt_pct(pct(speedup), signed=True),
            fmt_mpki(geomean(fnum(row["l1d_load_mpki"]) for row in group)),
            fmt_pct(arithmean(fnum(row["simulator_accuracy"]) * 100.0 for row in group)),
            fmt_pct(arithmean(fnum(row["coverage"]) * 100.0 for row in group)),
        ])
    return body + mean_rows, rank_rows, summary_src, order, by_sel


def task2_table(task2):
    order = traces_of(task2)
    wanted = [("LRU", "lru"), ("SRRIP", "i2-h0-a0-b0"), ("I-RRIP", "i2-h1-a1-b2")]
    by_name = index_rows(task2, "trace", "name")
    rows = []
    summary = {label: [] for label, _ in wanted}
    for trace in order:
        for label, name in wanted:
            row = by_name[(trace, name)]
            item = {
                "ipc": fnum(row["ipc"]),
                "speedup": fnum(row["speedup"]),
                "l2": fnum(row["l2_load_mpki"]),
                "instr": fnum(row["instruction_mpki"]),
                "data": fnum(row["data_mpki"]),
            }
            summary[label].append(item)
            rows.append([
                trace_name(trace), label, fmt_ipc(item["ipc"]),
                fmt_pct(pct(item["speedup"]), signed=True),
                fmt_mpki(item["l2"]), fmt_mpki(item["instr"]), fmt_mpki(item["data"]),
            ])
    for label, _ in wanted:
        items = summary[label]
        rows.append([
            "Mean", label,
            fmt_ipc(geomean(item["ipc"] for item in items)),
            fmt_pct(pct(geomean(item["speedup"] for item in items)), signed=True),
            fmt_mpki(geomean(item["l2"] for item in items)),
            fmt_mpki(geomean(item["instr"] for item in items)),
            fmt_mpki(geomean(item["data"] for item in items)),
        ])
    return rows, summary, order


def task2b_tables(task2b, task2_summary):
    order = traces_of(task2b)
    thresholds = ["0.1", "0.25", "0.5", "0.75", "0.9"]
    by_key = index_rows(task2b, "trace", "threshold")
    rows = []
    chosen = []
    for threshold in thresholds:
        group = [by_key[(trace, threshold)] for trace in order]
        speedups = [fnum(row["speedup"]) for row in group]
        label = "0.10" if threshold == "0.1" else ("0.50" if threshold == "0.5" else threshold)
        rows.append([
            label,
            fmt_pct(pct(geomean(speedups)), signed=True),
            fmt_pct(pct(speedups[0]), signed=True),
            fmt_pct(pct(speedups[1]), signed=True),
            fmt_pct(pct(speedups[2]), signed=True),
        ])
        if threshold == "0.1":
            chosen = group
    detail = []
    for label in ("LRU", "I-RRIP"):
        items = task2_summary[label]
        detail.append([
            label, "-",
            fmt_pct(pct(geomean(item["speedup"] for item in items)), signed=True),
            fmt_mpki(geomean(item["l2"] for item in items)),
            fmt_mpki(geomean(item["instr"] for item in items)),
            fmt_mpki(geomean(item["data"] for item in items)),
        ])
    detail.append([
        "Dynamic 0.10", "100% I-RRIP in ROI",
        fmt_pct(pct(geomean(fnum(row["speedup"]) for row in chosen)), signed=True),
        fmt_mpki(geomean(fnum(row["l2_load_mpki"]) for row in chosen)),
        fmt_mpki(geomean(fnum(row["instruction_mpki"]) for row in chosen)),
        fmt_mpki(geomean(fnum(row["data_mpki"]) for row in chosen)),
    ])
    per_trace = []
    for row in chosen:
        per_trace.append([
            trace_name(row["trace"]),
            fmt_ipc(fnum(row["ipc"])),
            fmt_pct(pct(fnum(row["speedup"])), signed=True),
            fmt_mpki(fnum(row["l2_load_mpki"])),
            fmt_mpki(fnum(row["instruction_mpki"])),
            fmt_mpki(fnum(row["data_mpki"])),
        ])
    return rows, detail, per_trace, order, by_key


def task3_table(task3):
    order = traces_of(task3)
    schemes = [
        ("No prefetch", "none"),
        ("SPP", "spp"),
        ("Dynamic I-RRIP", "dynamic"),
        ("SPP + dynamic", "combined-aware"),
    ]
    by_key = index_rows(task3, "trace", "scheme")
    rows = []
    summary = {label: [] for label, _ in schemes}
    for trace in order:
        for label, scheme in schemes:
            row = by_key[(trace, scheme)]
            accuracy = fnum(row["simulator_accuracy"])
            item = {
                "ipc": fnum(row["ipc"]),
                "speedup": fnum(row["speedup"]),
                "l1d": fnum(row["l1d_load_mpki"]),
                "l2": fnum(row["l2c_load_mpki"]),
                "instr": fnum(row["l2_instruction_mpki"]),
                "data": fnum(row["l2_data_mpki"]),
                "accuracy": None if accuracy is None else accuracy * 100.0,
                "coverage": fnum(row["coverage"]) * 100.0,
            }
            summary[label].append(item)
            rows.append([
                trace_name(trace), label, fmt_ipc(item["ipc"]),
                fmt_pct(pct(item["speedup"]), signed=True),
                "-" if item["accuracy"] is None else fmt_pct(item["accuracy"]),
                "-" if label in ("No prefetch", "Dynamic I-RRIP") else fmt_pct(item["coverage"]),
                fmt_mpki(item["l1d"]), fmt_mpki(item["l2"]),
                fmt_mpki(item["instr"]), fmt_mpki(item["data"]),
            ])
    for label, _ in schemes:
        items = summary[label]
        acc = arithmean(item["accuracy"] for item in items)
        cov_items = [item["coverage"] for item in items]
        rows.append([
            "Mean", label,
            fmt_ipc(geomean(item["ipc"] for item in items)),
            fmt_pct(pct(geomean(item["speedup"] for item in items)), signed=True),
            "-" if acc is None else fmt_pct(acc),
            "-" if label in ("No prefetch", "Dynamic I-RRIP") else fmt_pct(arithmean(cov_items)),
            fmt_mpki(geomean(item["l1d"] for item in items)),
            fmt_mpki(geomean(item["l2"] for item in items)),
            fmt_mpki(geomean(item["instr"] for item in items)),
            fmt_mpki(geomean(item["data"] for item in items)),
        ])
    plain = [by_key[(trace, "combined-plain")] for trace in order]
    aware = [by_key[(trace, "combined-aware")] for trace in order]
    return rows, summary, order, plain, aware


def make_figures(task1_summary, task1_order, task2_summary, task2_order, task2b, task2b_order, task3_summary, task3_order):
    FIG.mkdir(parents=True, exist_ok=True)
    labels = [trace_name(trace) for trace in task1_order]
    names = ["No prefetch", "IP-stride", "SPP"]

    def series(summary, key, scale=1.0):
        out = []
        for name in names:
            out.append((name, [summary[name][i][key] * scale if summary[name][i][key] is not None else None
                                for i in range(len(labels))]))
        return out

    # task1_summary values are already in display units for accuracy/coverage
    grouped(FIG / "task1_speedup.png", labels,
            [(name, [item["speedup"] for item in task1_summary[name]]) for name in names],
            "Speedup", "Task 1 speedup", zoom=True)
    grouped(FIG / "task1_mpki.png", labels,
            [(name, [item["mpki"] for item in task1_summary[name]]) for name in names],
            "L1D load MPKI", "Task 1 L1D load MPKI")
    grouped(FIG / "task1_accuracy.png", labels,
            [(name, [item["accuracy"] for item in task1_summary[name]]) for name in names if name != "No prefetch"],
            "Accuracy (%)", "Task 1 prefetch accuracy")
    grouped(FIG / "task1_coverage.png", labels,
            [(name, [item["coverage"] for item in task1_summary[name]]) for name in names if name != "No prefetch"],
            "Coverage (%)", "Task 1 L1D load coverage")

    labels2 = [trace_name(trace) for trace in task2_order]
    names2 = ["LRU", "SRRIP", "I-RRIP"]
    grouped(FIG / "task2_speedup.png", labels2,
            [(name, [item["speedup"] for item in task2_summary[name]]) for name in names2],
            "Speedup", "Task 2A speedup", zoom=True)
    grouped(FIG / "task2_l2.png", labels2,
            [(name, [item["l2"] for item in task2_summary[name]]) for name in names2],
            "MPKI", "Task 2A L2C load MPKI")
    grouped(FIG / "task2_instr.png", labels2,
            [(name, [item["instr"] for item in task2_summary[name]]) for name in names2],
            "MPKI", "Task 2A L2 instruction load MPKI")
    grouped(FIG / "task2_data.png", labels2,
            [(name, [item["data"] for item in task2_summary[name]]) for name in names2],
            "MPKI", "Task 2A L2 data load MPKI")

    thresholds = [0.10, 0.25, 0.50, 0.75, 0.90]
    keys = ["0.1", "0.25", "0.5", "0.75", "0.9"]
    by_key = index_rows(task2b, "trace", "threshold")
    line_series = [("Geometric mean", [])]
    for trace in task2b_order:
        line_series.append((trace_name(trace), []))
    for key in keys:
        group = [fnum(by_key[(trace, key)]["speedup"]) for trace in task2b_order]
        line_series[0][1].append(geomean(group))
        for i, trace in enumerate(task2b_order):
            line_series[i + 1][1].append(fnum(by_key[(trace, key)]["speedup"]))
    lines(FIG / "task2b_threshold.png", thresholds, line_series,
          "Instruction-miss threshold", "Speedup vs LRU", "Task 2B threshold sensitivity")

    labels3 = [trace_name(trace) for trace in task3_order]
    names3 = ["No prefetch", "SPP", "Dynamic I-RRIP", "SPP + dynamic"]
    grouped(FIG / "task3_speedup.png", labels3,
            [(name, [item["speedup"] for item in task3_summary[name]]) for name in names3],
            "Speedup", "Task 3 speedup", zoom=True)
    grouped(FIG / "task3_accuracy.png", labels3,
            [(name, [item["accuracy"] for item in task3_summary[name]]) for name in ("SPP", "SPP + dynamic")],
            "Accuracy (%)", "Task 3 L1D prefetch accuracy")
    grouped(FIG / "task3_coverage.png", labels3,
            [(name, [item["coverage"] for item in task3_summary[name]]) for name in ("SPP", "SPP + dynamic")],
            "Coverage (%)", "Task 3 L1D load coverage")
    for key, title, filename in (
        ("l1d", "Task 3 L1D load MPKI", "task3_l1d.png"),
        ("l2", "Task 3 L2C load MPKI", "task3_l2.png"),
        ("instr", "Task 3 L2 instruction load MPKI", "task3_instr.png"),
        ("data", "Task 3 L2 data load MPKI", "task3_data.png"),
    ):
        grouped(FIG / filename, labels3,
                [(name, [item[key] for item in task3_summary[name]]) for name in names3],
                "MPKI", title)


def build(pdf, task1_rows, rank_rows, task2_rows, sens_rows, detail_rows, dyn_rows, task3_rows, prose):
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 33, 46)
    pdf.multi_cell(0, 8, "CS683 Programming Assignment 2", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 6, "Stride-pattern prefetching and instruction-conscious L2 replacement", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    heading(pdf, "Setup", 2)
    for text in prose["setup"]:
        paragraph(pdf, text)

    heading(pdf, "Task 1. Stride pattern prefetcher")
    for text in prose["task1_design"]:
        paragraph(pdf, text)
    heading(pdf, "Storage", 2)
    paragraph(pdf, prose["storage_intro"])
    draw_table(pdf,
               ["Structure", "Entry", "Bits / entry", "Entries", "Bits"],
               [
                   ["IP tracker", "valid, full IP, last line, stride, confidence, signature, history, LRU", "166", "64", "10,624"],
                   ["Pattern table", "valid, IP, signature, next stride, confidence", "102", "256", "26,112"],
                   ["Controller", "interval, degree, three thresholds", "42", "1", "42"],
               ],
               [32, 78, 28, 22, 22])
    caption(pdf, "Compact state is 36,778 bits, about 4.49 KiB, when the cache already exposes issued and useful counters. The supplied IP-stride table is 24 entries x 130 bits = 3,120 bits.")
    for text in prose["storage_rest"]:
        paragraph(pdf, text)

    heading(pdf, "Thresholds and degree", 2)
    for text in prose["task1_thresholds"]:
        paragraph(pdf, text)
    draw_table(pdf,
               ["Configuration", "Speedup", "L1D MPKI", "Accuracy", "Coverage"],
               rank_rows, [52, 28, 32, 32, 32])
    caption(pdf, "Geometric mean of IPC speedup and L1D load MPKI. Arithmetic mean of accuracy and coverage. Sorted by speedup. The first row is the configuration used below and in Task 3.")

    heading(pdf, "Task 1 results", 2)
    paragraph(pdf, prose["task1_results"])
    draw_table(pdf,
               ["Trace", "Config", "IPC", "Speedup", "L1D MPKI", "Accuracy", "Coverage"],
               task1_rows, [24, 28, 22, 24, 26, 26, 26])
    caption(pdf, "Mean IPC, speedup, and MPKI are geometric. Mean accuracy and coverage are arithmetic. Baseline accuracy is undefined because it issues no prefetches.")
    for name in ("task1_speedup.png", "task1_mpki.png", "task1_accuracy.png", "task1_coverage.png"):
        place_image(pdf, FIG / name, 175)

    heading(pdf, "Task 2A. Instruction-conscious RRIP")
    for text in prose["task2a"]:
        paragraph(pdf, text)
    draw_table(pdf,
               ["Trace", "Policy", "IPC", "Speedup", "L2C MPKI", "L2 inst. MPKI", "L2 data MPKI"],
               task2_rows, [24, 24, 22, 24, 28, 32, 32])
    caption(pdf, "Speedup is against no-prefetch LRU. Mean IPC, speedup, and MPKI are geometric. Instruction and data MPKI are L2 demand-load misses.")
    for name in ("task2_speedup.png", "task2_l2.png", "task2_instr.png", "task2_data.png"):
        place_image(pdf, FIG / name, 175)

    heading(pdf, "Task 2B. Dynamic I-RRIP")
    for text in prose["task2b"]:
        paragraph(pdf, text)
    draw_table(pdf,
               ["Threshold", "Geomean", "Trace 1", "Trace 2", "Trace 3"],
               sens_rows, [36, 36, 36, 36, 36])
    caption(pdf, "Speedup versus no-prefetch LRU. Five thresholds required by the sensitivity study.")
    place_image(pdf, FIG / "task2b_threshold.png", 175)
    paragraph(pdf, prose["task2b_choice"])
    draw_table(pdf,
               ["Trace", "IPC", "Speedup", "L2C MPKI", "L2 inst. MPKI", "L2 data MPKI"],
               dyn_rows, [28, 28, 28, 32, 34, 34])
    caption(pdf, "Dynamic I-RRIP at threshold 0.10, the best value in the sweep.")
    draw_table(pdf,
               ["Policy", "ROI mode", "Speedup", "L2C MPKI", "L2 inst. MPKI", "L2 data MPKI"],
               detail_rows, [36, 40, 26, 26, 32, 30])
    caption(pdf, "Geometric means. Dynamic I-RRIP stays just behind static I-RRIP because 32 sets never leave SRRIP.")

    heading(pdf, "Task 3. SPP with dynamic I-RRIP")
    for text in prose["task3"]:
        paragraph(pdf, text)
    draw_table(pdf,
               ["Trace", "Config", "IPC", "Speedup", "Acc.", "Cov.", "L1D", "L2C", "L2I", "L2D"],
               task3_rows, [18, 30, 17, 17, 15, 15, 17, 17, 18, 18])
    caption(pdf, "Accuracy and coverage refer to the L1D prefetcher. Dynamic I-RRIP alone issues no L1D prefetches. MPKI columns are demand-load MPKI. Means follow the same geometric and arithmetic split as Task 1.")
    for name in ("task3_speedup.png", "task3_accuracy.png", "task3_coverage.png",
                 "task3_l1d.png", "task3_l2.png", "task3_instr.png", "task3_data.png"):
        place_image(pdf, FIG / name, 175)


def main():
    plt.rcParams.update({
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.alpha": 0.28,
        "axes.axisbelow": True,
        "figure.facecolor": "white",
    })
    comparison, sweep, task2, task2b, task3 = load()
    task1_rows, rank_rows, task1_summary, task1_order, _ = task1_tables(comparison, sweep)
    task2_rows, task2_summary, task2_order = task2_table(task2)
    sens_rows, detail_rows, dyn_rows, task2b_order, _ = task2b_tables(task2b, task2_summary)
    task3_rows, task3_summary, task3_order, plain, aware = task3_table(task3)
    make_figures(task1_summary, task1_order, task2_summary, task2_order, task2b, task2b_order, task3_summary, task3_order)

    spp = geomean(item["speedup"] for item in task1_summary["SPP"])
    ip = geomean(item["speedup"] for item in task1_summary["IP-stride"])
    irrip = geomean(item["speedup"] for item in task2_summary["I-RRIP"])
    dyn = geomean(fnum(row["speedup"]) for row in task2b if row["threshold"] == "0.1")
    aware_speed = geomean(fnum(row["speedup"]) for row in aware)
    plain_speed = geomean(fnum(row["speedup"]) for row in plain)
    best_degree = {row["trace"]: row["final_degree"] for row in sweep if row["name"] == "u2-p1-a1-2-4"}

    prose = {
        "setup": [
            "Every reported run is a single-core ChampSim simulation with the hashed perceptron predictor. Warmup is 25 million instructions and measurement is the following 25 million. The three traces are Trace 1, Trace 2, and Trace 3. These tables use the completed runs already stored with the repository. The same policies build with GCC 7; those binaries were not re-simulated here.",
            "IPC is retired instructions divided by cycles in the region of interest. Speedup divides that IPC by the IPC of the same trace with no L1D prefetcher and LRU replacement. Load MPKI is the simulator's demand-load MPKI. Prefetch accuracy is the printed L1D ACCURACY: useful prefetches divided by prefetches sent to the next level. Coverage is the reduction in L1D demand-load misses against the no-prefetch LRU run. IPC, speedup, and MPKI are summarized by a geometric mean. Accuracy and coverage are summarized by an arithmetic mean.",
        ],
        "task1_design": [
            "The stride pattern prefetcher trains at the L1D on demand loads. A 16-set, 4-way table, indexed by a hash of the full instruction pointer, tracks each IP. An entry holds the last cache-line address, the last stride, a saturating uniform-stride confidence, and a signature of the four most recent strides. Each stride is stored as a 7-bit signed value from -63 to +63. A separate 256-entry direct-mapped table maps the pair (IP, signature) to the next stride and a 2-bit confidence.",
            "Uniform strides are preferred. Confidence rises when the observed stride repeats and falls back to 1 when it changes. At or above the uniform threshold the prefetcher repeats that stride. Otherwise, once four strides are in the signature, it looks up the pattern table and follows the stored next stride. Further degrees update a temporary signature, so a repeating sequence such as (+1, +2, +2, +2, +3) can be walked without training on the predictions themselves. Any prefetch that would leave the current 4 KB page is dropped, and a stride outside -63..+63 clears the history for that IP.",
            "The reported configuration is the best of the 12-point sweep: uniform confidence 2, pattern confidence 1, and accuracy boundaries 1%, 2%, and 4%. Those parameters are selected at run time. The source defaults remain uniform confidence 4, pattern confidence 2, and boundaries 25/50/75.",
        ],
        "storage_intro": "The table below counts compact state, not the padded C++ objects in the simulator. A full 64-bit IP is charged because the code compares the whole pointer. The set index is a hash, so it is not stored again.",
        "storage_rest": [
            "The degree register holds the values 1, 2, 4, and 8. The 12-bit demand counter walks 0..4095 and then resets. If the cache does not already expose issued and useful counts, those two 64-bit counters add 128 bits. The uniform-prediction and pattern-prediction counters are diagnostics and are not part of the predictor.",
        ],
        "task1_thresholds": [
            "Degree starts at 2. Every 4096 demand loads, once at least 128 prefetches have been issued, degree is chosen from useful prefetches divided by all issued prefetches. That ratio counts requests that hit a line already present, so it is harsher than the printed accuracy and reacts to wasted issue bandwidth. Below 1% the degree is 1, below 2% it is 2, below 4% it is 4, and otherwise it is 8.",
            "The steps are powers of two so each accuracy band looks one step farther along the same stride or signature. Degree 1 is the safe next line when the prefetcher is mostly missing. Degree 8 is the largest lookahead tested; it is used only after the issued stream has stayed useful. On the selected runs the final degree is %s on Trace 1, %s on Trace 2, and %s on Trace 3." % (best_degree["Trace1-003"], best_degree["Trace2-001"], best_degree["Trace3-002"]),
            "Uniform confidence 2 starts the constant-stride path after two repeats, which is early enough for short runs of the same stride and still gives the pattern table the accesses that break the constant. Pattern confidence 1 accepts a next stride after one confirmation. Both choices were tested against the stricter defaults. The strict defaults finish near degree 1 and gain only about two tenths of a percent. The looser gates issue more prefetches, give up some printed accuracy, and win IPC and coverage on every trace. The ranking is the reason for the reported thresholds; it is specific to these three traces.",
        ],
        "task1_results": "Selected SPP gains %.3f%% geometric-mean IPC over no prefetching, compared with %.3f%% for the supplied IP-stride prefetcher. It also lowers L1D load MPKI on every trace. Printed accuracy stays above IP-stride even in this more aggressive setting." % (pct(spp), pct(ip)),
        "task2a": [
            "I-RRIP is SRRIP with a sticky instruction bit on each L2 line. A fill is marked as an instruction only when the incoming packet is an instruction load or instruction prefetch. Hits keep the resident bit, including a line that is later touched as data. Translation requests do not mark a line as an instruction. RRPV still uses two bits, with 3 meaning ready for replacement.",
            "Insertion is unchanged from SRRIP: instruction and data fills both enter at RRPV 2. The sweep's best six configurations all insert at 2. Inserting instructions at 0 or 1 keeps them too long before they have shown reuse, and the best insertion-1 configuration is well behind the winner. Promotion is where instructions are preferred. An instruction hit sets RRPV to 0. A data hit sets RRPV to 1, so reused data is not immediately replaceable but remains behind a re-referenced instruction. Giving data hits RRPV 0 as well was slightly worse at the best eviction settings.",
            "Eviction still takes an invalid way first, then ages every line until some RRPV reaches 3. With bias 2, if any data line has RRPV at least 1, the victim is the data line with the highest RRPV; ties keep the earlier way. A data line at RRPV 0 is left alone, so a just-filled or just-hit data line can survive one aging step. Bias 3, which always prefers data when any data line exists, tied this result exactly. Bias 2 is kept because it is the less aggressive rule and matches the best IPC. Turning awareness off reproduces SRRIP and loses almost all of the gain.",
            "The IPC gain is %.3f%% over LRU. Most of it is on Trace 2, where L2 instruction MPKI falls from 18.809 to 7.719. Data MPKI rises on every trace, which is the cost of holding instructions. Overall L2 load MPKI still falls on Trace 2 and Trace 3." % pct(irrip),
        ],
        "task2b": [
            "Dynamic I-RRIP uses the same insertion, promotion, and bias as the selected static policy, but only on follower sets, and only while a sampled miss share says instructions are the problem. Thirty-two of the 1024 sets are permanent SRRIP leaders. Set 33k, for k from 0 to 31, is the leader of each 32-set group, so the sample is spread through the cache instead of sitting in one region. Leaders are 3.125% of the sets: enough to observe instruction and data misses, and small enough that the other 992 sets can follow the decision.",
            "Only demand loads train the counters, and the type comes from the incoming request rather than the sticky bit of the resident line. After every 4096 leader loads the controller computes instruction-load misses divided by all load misses. A share strictly above the threshold selects I-RRIP. Equality, and a window with no misses, stays on SRRIP. The four counters then reset. The decision applies to later accesses; it does not rewrite lines already in the cache. Learning runs through warmup and continues into the measured region.",
            "The static threshold in the assignment hint is 0.25. The required sweep also measures 0.10, 0.50, 0.75, and 0.90. Lower thresholds protect instructions more often. On Trace 1 the three lowest thresholds make the same decision. On Trace 2, moving from 0.90 to 0.10 is the difference between staying near SRRIP and keeping the large instruction-MPKI reduction.",
        ],
        "task2b_choice": "Threshold 0.10 is the best tested value, at %.3f%% geometric-mean IPC over LRU. Static I-RRIP is %.3f%%. Dynamic I-RRIP is %.3f%% behind that static policy. At 0.10 the follower sets use I-RRIP for the entire measured region on all three traces, so the remaining gap is the 32 SRRIP leaders and the warmup history. The source default stays 0.25. The reported dynamic runs set the threshold to 0.10. Two later controller variants, starting in I-RRIP and requiring two weak windows before leaving it, did not beat this result." % (pct(dyn), pct(irrip), (1.0 - dyn / irrip) * 100.0),
        "task3": [
            "Task 3 keeps the selected SPP and the threshold-0.10 dynamic I-RRIP, with no joint retuning. One extra rule applies in follower sets when prefetch awareness is enabled. A data prefetch fill is inserted at RRPV 3, and a data prefetch hit does not change RRPV. A later demand hit still uses the current mode: RRPV 0 in SRRIP, or RRPV 1 for data and 0 for instructions in I-RRIP. Leader sets keep ordinary SRRIP, including for prefetches. Prefetches do not train the miss-share counters.",
            "The reason is that a prefetched line has not been demanded yet. Inserting it near replacement lets a demand line or an instruction line win the victim choice, and ignoring prefetch hits stops a stream of speculative requests from refreshing a line that the program has not used. If the program does use it, the demand hit restores the normal priority. The risk is the opposite one: a useful prefetch can be evicted before the demand arrives. That is why the plain combination, with ordinary RRIP insertion of prefetches, is reported as well.",
            "The prefetch-aware combination gains %.3f%% geometric-mean IPC over no-prefetch LRU. Standalone SPP gains %.3f%% and standalone dynamic I-RRIP gains %.3f%%, so the combination beats both. The same policy without the prefetch rule gains %.3f%%. Awareness adds a small further gain on Trace 1 and Trace 2. On Trace 3 the two combinations are effectively tied, with the plain combination ahead by a few thousandths of a percent. L2 instruction MPKI stays near the dynamic-I-RRIP level, while L1D MPKI and coverage stay near standalone SPP." % (pct(aware_speed), pct(spp), pct(dyn), pct(plain_speed)),
        ],
    }

    pdf = Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(14, 14, 14)
    build(pdf, task1_rows, rank_rows, task2_rows, sens_rows, detail_rows, dyn_rows, task3_rows, prose)
    pdf.output(str(OUT))
    print("wrote %s (%d pages)" % (OUT, pdf.pages_count))


if __name__ == "__main__":
    main()
