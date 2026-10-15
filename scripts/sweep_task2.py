#!/usr/bin/env python3
"""Build three policies, then run/resume the Task 2A parameter sweep."""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def configurations():
    yield dict(name="lru", policy="lru")
    for insert, hit in itertools.product(range(3), range(2)):
        # Bias is irrelevant to ordinary eviction: run it only once.
        for aware, bias in [(0, 0), *((1, b) for b in range(4))]:
            yield dict(name=f"i{insert}-h{hit}-a{aware}-b{bias}", policy="irrip",
                       insert=insert, data_hit=hit, aware=aware, bias=bias)


def metrics(log, instructions):
    if "Finished CPU 0 instructions:" not in log or "Region of Interest Statistics" not in log:
        raise ValueError("simulation did not finish")
    roi = log.split("Region of Interest Statistics")[-1]
    def number(pattern):
        match = re.search(pattern, roi, re.M)
        if not match:
            raise ValueError(f"missing statistic: {pattern}")
        return float(match.group(1))
    retired = int(number(r"^CPU 0 cumulative IPC: .* instructions: (\d+)"))
    if retired < instructions:
        raise ValueError("too few measured instructions")
    return dict(ipc=number(r"^CPU 0 cumulative IPC: ([\d.eE+-]+)"),
                instructions=retired,
                cycles=int(number(r"^CPU 0 cumulative IPC: .* cycles: (\d+)")),
                l2_load_mpki=number(r"^L2C LOAD\s+.* MPKI: ([\d.eE+-]+)"),
                instruction_mpki=number(r"^L2C INSTRUCTION LOAD MPKI: ([\d.eE+-]+)"),
                data_mpki=number(r"^L2C DATA LOAD MPKI: ([\d.eE+-]+)"))


def write_tables(output, rows, trace_count):
    baselines = {r["trace"]: r["ipc"] for r in rows
                 if r["name"] == "lru" and r["status"] == "ok"}
    for row in rows:
        if row["status"] == "ok" and row["trace"] in baselines:
            row["speedup"] = row["ipc"] / baselines[row["trace"]]
    fields = ["trace", "name", "policy", "insert", "data_hit", "aware", "bias",
              "status", "seconds", "ipc", "speedup", "l2_load_mpki",
              "instruction_mpki", "data_mpki", "instructions", "cycles", "error"]
    with (output / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    rankings = []
    for name in sorted({r["name"] for r in rows if r["policy"] == "irrip"}):
        group = [r for r in rows if r["name"] == name and r["status"] == "ok"]
        if len(group) == trace_count and all("speedup" in r for r in group):
            rankings.append(dict(name=name, geometric_mean_speedup=
                                 math.exp(sum(math.log(r["speedup"]) for r in group) / trace_count)))
    rankings.sort(key=lambda r: r["geometric_mean_speedup"], reverse=True)
    with (output / "ranking.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "geometric_mean_speedup"])
        writer.writeheader()
        writer.writerows(rankings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="10K warmup + 10K measured; compare SRRIP")
    parser.add_argument("--build", action="store_true", help="rebuild even if binaries already exist")
    parser.add_argument("--traces-dir", type=Path, default=ROOT / "traces")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--jobs", type=int, default=1, help="concurrent simulations (default: 1)")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    output = (args.output or ROOT / "results/task2" / ("smoke" if args.smoke else "full")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    traces_dir = args.traces_dir.resolve()
    traces = sorted(p for p in traces_dir.iterdir() if p.is_file() and not p.is_symlink())
    if not traces:
        parser.error("no traces found")
    # Detect compression from its magic, then give the old simulator the extension it needs.
    aliases = []
    for trace in traces:
        with trace.open("rb") as f:
            magic = f.read(6)
        suffix = ".gz" if magic.startswith(b"\x1f\x8b") else ".xz" if magic == b"\xfd7zXZ\x00" else None
        if not suffix:
            parser.error(f"unrecognized compression: {trace}")
        alias = trace if trace.name.endswith(suffix) else trace.with_name(trace.name + suffix)
        if alias != trace:
            if alias.is_symlink():
                if alias.resolve() != trace:
                    parser.error(f"alias points to a different file: {alias}")
            elif alias.exists():
                parser.error(f"alias already exists: {alias}")
            else:
                alias.symlink_to(trace.name)
        aliases.append((trace, alias))

    binaries = {}
    for policy in ("irrip", "lru", "rrip"):
        label = "task2-" + policy
        found = list((ROOT / "bin").glob("*-1core-" + label))
        if args.build or not found:
            print(f"Building {policy}", flush=True)
            with (output / f"build-{policy}.log").open("w") as log:
                subprocess.run(["bash", "build_champsim.sh", "no", policy, label], cwd=ROOT,
                               env={**os.environ, "TERM": "xterm"}, stdout=log, stderr=subprocess.STDOUT,
                               check=True)
            found = list((ROOT / "bin").glob("*-1core-" + label))
        binaries[policy] = found[0]
    binary_hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in binaries.items()}
    instructions = 10_000 if args.smoke else 25_000_000
    configs = list(configurations())
    if args.smoke:
        configs.append(dict(name="rrip", policy="rrip"))
    rows = []
    total = len(traces) * len(configs)
    def run_one(index, trace, alias, config):
        directory = output / trace.name
        directory.mkdir(exist_ok=True)
        log_path = directory / (config["name"] + ".log")
        record_path = directory / (config["name"] + ".json")
        signature = dict(config=config, binary_sha256=binary_hashes[config["policy"]],
                         trace=str(trace), size=trace.stat().st_size, mtime_ns=trace.stat().st_mtime_ns,
                         warmup=instructions, measured=instructions)
        record = json.loads(record_path.read_text()) if record_path.exists() else {}
        cached = record.get("signature") == signature and record.get("row", {}).get("status") == "ok"
        if cached and log_path.exists():
            try:
                metrics(log_path.read_text(), instructions)
            except ValueError:
                cached = False
        else:
            cached = False
        if not cached:
            env = {k: v for k, v in os.environ.items() if not k.startswith("IRRIP_")}
            if config["policy"] == "irrip":
                for key, var in [("insert", "INSERT"), ("data_hit", "DATA_HIT"),
                                 ("aware", "AWARE"), ("bias", "BIAS")]:
                    env["IRRIP_" + var] = str(config[key])
            cmd = [str(binaries[config["policy"]]), "-warmup_instructions", str(instructions),
                   "-simulation_instructions", str(instructions), "-traces", alias.name]
            print(f"[{index+1}/{total}] {trace.name} {config['name']}", flush=True)
            start = time.monotonic()
            row = dict(trace=trace.name, **config, status="failed")
            try:
                with log_path.open("w") as log:
                    subprocess.run(cmd, cwd=traces_dir, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   timeout=120 if args.smoke else 3600, check=True)
                row.update(metrics(log_path.read_text(), instructions), status="ok")
            except (ValueError, subprocess.SubprocessError) as error:
                row["error"] = str(error)
                print(f"FAILED: {error}; see {log_path}", flush=True)
            row["seconds"] = round(time.monotonic()-start, 3)
            record = dict(signature=signature, row=row)
            record_path.write_text(json.dumps(record, indent=2) + "\n")
        else:
            print(f"[{index+1}/{total}] cached {trace.name} {config['name']}", flush=True)
        return record["row"]

    # Each worker owns its log/JSON; only this main thread writes summary tables.
    jobs = [(trace, alias, config) for trace, alias in aliases for config in configs]
    completed = {}
    print(f"Using {args.jobs} simulation workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_one, index, *job): index for index, job in enumerate(jobs)}
        try:
            for future in as_completed(futures):
                completed[futures[future]] = future.result()
                rows = [completed[index] for index in sorted(completed)]
                write_tables(output, rows, len(traces))
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    if any(r["status"] != "ok" for r in rows):
        return 1
    if args.smoke:
        for trace in traces:
            ordinary = next(r for r in rows if r["trace"] == trace.name and r["name"] == "i2-h0-a0-b0")
            rrip = next(r for r in rows if r["trace"] == trace.name and r["name"] == "rrip")
            for key in ("instructions", "cycles", "ipc", "l2_load_mpki", "instruction_mpki", "data_mpki"):
                if ordinary[key] != rrip[key]:
                    raise ValueError(f"SRRIP mismatch: {trace.name} {key}")
        print("All smoke runs passed; ordinary configuration matches SRRIP on all traces.", flush=True)
    print(f"Results: {output / 'results.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
