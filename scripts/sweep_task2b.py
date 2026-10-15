#!/usr/bin/env python3
"""Run five Dynamic I-RRIP thresholds, retaining Task 2A baselines for comparison."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from sweep_task2 import metrics

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = [0.10, 0.25, 0.50, 0.75, 0.90]
TRACES = ["Trace1-003", "Trace2-001", "Trace3-002"]


def diagnostics(log, threshold, variant="original"):
    if variant != "original":
        header = next(line for line in log.splitlines() if line.startswith("Dynamic I-RRIP "))
        assert "initial=IRRIP" in header
        assert f"persistent={int(variant == 'persistent')}" in header
    previous = "RRIP" if variant == "original" else "IRRIP"
    windows, switches, streak = 0, 0, 0
    summary = None
    for line in log.splitlines():
        if not line.startswith(("DYN_WINDOW ", "DYN_SUMMARY ")):
            continue
        fields = dict(part.split("=", 1) for part in line.split()[1:])
        if line.startswith("DYN_SUMMARY "):
            summary = {k: int(v) for k, v in fields.items()}
            continue
        windows += 1
        ia, da, im, dm = [int(fields[k]) for k in ("i_access", "d_access", "i_miss", "d_miss")]
        assert int(fields["index"]) == windows and ia + da == 4096
        assert 0 <= im <= ia and 0 <= dm <= da
        share = im/(im+dm) if im+dm else 0
        assert abs(float(fields["share"])-share) < 0.000001
        expected = "IRRIP" if share > threshold else "RRIP"
        if variant == "persistent":
            expected = previous
            if im+dm and share > threshold:
                expected, streak = "IRRIP", 0
            elif im+dm and share < threshold:
                streak = min(2, streak+1)
                if streak == 2:
                    expected = "RRIP"
            else:
                streak = 0
        assert int(fields.get("rrip_streak", 0)) == streak
        assert fields["mode"] == expected
        changed = expected != previous
        assert int(fields["switched"]) == changed
        switches += changed
        previous = expected
    assert summary is not None, "missing Dynamic I-RRIP summary"
    assert summary["windows"] == windows and summary["switches"] == switches
    assert summary["pending_i_access"] + summary["pending_d_access"] < 4096
    loads = summary["roi_rrip_loads"] + summary["roi_irrip_loads"]
    return dict(windows=windows, switches=switches,
                roi_irrip_fraction=summary["roi_irrip_loads"]/loads if loads else 0)


def write_results(output, rows):
    fields = ["trace", "threshold", "status", "seconds", "ipc", "instructions", "cycles",
              "l2_load_mpki", "instruction_mpki", "data_mpki", "speedup", "speedup_vs_rrip",
              "speedup_vs_static", "windows", "switches", "roi_irrip_fraction", "variant", "error"]
    with (output / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["trace"], r["threshold"])))
    ranking = []
    for threshold in THRESHOLDS:
        group = [r for r in rows if r["threshold"] == threshold and r["status"] == "ok"]
        if len(group) == 3 and all("speedup" in r for r in group):
            ranking.append(dict(threshold=threshold, geometric_mean_speedup=
                                math.exp(sum(math.log(r["speedup"]) for r in group)/3)))
    with (output / "ranking.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["threshold", "geometric_mean_speedup"])
        writer.writeheader()
        writer.writerows(sorted(ranking, key=lambda r: r["geometric_mean_speedup"], reverse=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="1M warmup + 1M measured; verify forced RRIP")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--variant", choices=["original", "start-irrip", "persistent"], default="original")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    experiment = ROOT / "results/task2b"
    if args.variant != "original":
        experiment /= args.variant
    output = experiment / ("smoke" if args.smoke else "full")
    label = "task2b-dyn-irrip" if args.variant == "original" else "task2b-dyn-irrip-variants"
    output.mkdir(parents=True, exist_ok=True)
    binaries = list((ROOT / "bin").glob("*-1core-" + label))
    if args.build or not binaries:
        with (output / "build.log").open("w") as log:
            subprocess.run(["bash", "build_champsim.sh", "no", "dyn_irrip", label], cwd=ROOT,
                           env={**os.environ, "TERM": "xterm"}, stdout=log, stderr=subprocess.STDOUT, check=True)
        binaries = list((ROOT / "bin").glob("*-1core-" + label))
    binary = binaries[0]
    binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    baseline_rows = list(csv.DictReader((ROOT / "results/task2/full/results.csv").open()))
    baselines = {(r["trace"], r["name"]): r for r in baseline_rows if r["status"] == "ok"}
    instructions = 1_000_000 if args.smoke else 25_000_000

    def run(trace, threshold):
        directory = output / trace
        directory.mkdir(exist_ok=True)
        stem = f"threshold-{threshold:.2f}"
        record_path, log_path = directory / (stem + ".json"), directory / (stem + ".log")
        original = ROOT / "traces" / trace
        alias = original.with_name(original.name + ".gz")
        assert alias.is_file(), f"missing gzip trace alias: {alias}"
        signature = dict(binary_sha256=binary_hash, threshold=threshold, warmup=instructions,
                         measured=instructions, trace=str(original), size=original.stat().st_size,
                         mtime_ns=original.stat().st_mtime_ns)
        if args.variant != "original":
            signature["variant"] = args.variant
        old = json.loads(record_path.read_text()) if record_path.exists() else {}
        if old.get("signature") == signature and old.get("row", {}).get("status") == "ok" and log_path.exists():
            text = log_path.read_text()
            metrics(text, instructions)
            diagnostics(text, threshold, args.variant)
            print(f"cached {trace} {threshold:.2f}", flush=True)
            return old["row"]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("IRRIP_", "DYN_IRRIP_"))}
        env["DYN_IRRIP_THRESHOLD"] = str(threshold)
        env["DYN_IRRIP_START"] = "0" if args.variant == "original" else "1"
        env["DYN_IRRIP_PERSIST"] = "1" if args.variant == "persistent" else "0"
        cmd = [str(binary), "-warmup_instructions", str(instructions), "-simulation_instructions",
               str(instructions), "-traces", alias.name]
        print(f"Running {trace} threshold={threshold:.2f}", flush=True)
        start = time.monotonic()
        row = dict(trace=trace, threshold=threshold, variant=args.variant, status="failed")
        try:
            with log_path.open("w") as log:
                subprocess.run(cmd, cwd=alias.parent, env=env, stdout=log, stderr=subprocess.STDOUT,
                               timeout=3600, check=True)
            text = log_path.read_text()
            row.update(metrics(text, instructions), **diagnostics(text, threshold, args.variant), status="ok")
            if not args.smoke:
                for name, field in [("lru", "speedup"), ("i2-h0-a0-b0", "speedup_vs_rrip"),
                                    ("i2-h1-a1-b2", "speedup_vs_static")]:
                    row[field] = row["ipc"] / float(baselines[trace, name]["ipc"])
        except (subprocess.SubprocessError, ValueError, AssertionError) as error:
            row["error"] = str(error)
            print(f"FAILED {trace} {threshold}: {error}", flush=True)
        row["seconds"] = round(time.monotonic()-start, 3)
        record_path.write_text(json.dumps(dict(signature=signature, row=row), indent=2) + "\n")
        return row

    thresholds = THRESHOLDS + ([1.0] if args.smoke and args.variant == "original" else [])
    rows = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run, trace, threshold) for trace in TRACES for threshold in thresholds]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            write_results(output, rows)
            print(f"Completed {len(rows)}/{len(futures)}: {row['trace']} {row['threshold']:.2f} {row['status']}", flush=True)
    assert all(r["status"] == "ok" for r in rows), "failed runs; see results.csv"
    if args.smoke and args.variant == "original":
        reference_binary = next((ROOT / "bin").glob("*-1core-task2-rrip"))
        for trace in TRACES:
            alias = ROOT / "traces" / (trace + ".gz")
            result = subprocess.run([str(reference_binary), "-warmup_instructions", str(instructions),
                                     "-simulation_instructions", str(instructions), "-traces", alias.name],
                                    cwd=alias.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
            (output / trace / "reference-rrip.log").write_text(result.stdout)
            reference = metrics(result.stdout, instructions)
            forced = next(r for r in rows if r["trace"] == trace and r["threshold"] == 1)
            assert all(forced[k] == v for k, v in reference.items()), f"forced RRIP mismatch: {trace}"
        print("Forced-RRIP runs exactly match standalone SRRIP on all three traces.", flush=True)
    print(f"Finished: {output / 'results.csv'}", flush=True)


if __name__ == "__main__":
    main()
