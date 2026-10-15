#!/usr/bin/env python3
"""Evaluate default SPP against the completed no-prefetch LRU baseline."""
import csv
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from compare_task1 import assert_lru

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'results/task1/full'
COUNT = 25_000_000


def metrics(path):
    text = path.read_text()
    assert_lru(text, path)
    if 'Finished CPU 0 instructions:' not in text:
        raise ValueError(f'Incomplete simulation: {path}')
    roi = text.split('Region of Interest Statistics')[-1]
    def find(pattern):
        return re.search(pattern, roi, re.M).groups()
    instructions, cycles = map(int, find(r'^CPU 0 cumulative IPC: .* instructions: (\d+) cycles: (\d+)'))
    assert instructions >= COUNT
    issued, useful = map(int, find(r'^L1D PREFETCH\s+REQUESTED:\s+\d+\s+ISSUED:\s+(\d+)\s+USEFUL:\s+(\d+)'))
    return dict(instructions=instructions, cycles=cycles, ipc=instructions/cycles,
                l1d_load_mpki=float(find(r'^L1D LOAD\s+.* MPKI: ([\d.eE+-]+)')[0]),
                issued=issued, useful=useful, accuracy=useful/issued if issued else 0)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    binary = next((ROOT / 'bin').glob('*-1core-task1-spp'))
    binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    env = {k:v for k,v in os.environ.items() if not k.startswith('SPP_')}
    def run(trace):
        name = trace.name[:-3]
        directory = OUTPUT / name
        directory.mkdir(exist_ok=True)
        command = [str(binary), '-warmup_instructions', str(COUNT),
                   '-simulation_instructions', str(COUNT), '-traces', str(trace.relative_to(ROOT))]
        started = time.monotonic()
        log_path = directory / 'spp.log'
        with log_path.open('w') as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        baseline_path = ROOT / 'results/task2/full' / name / 'lru.log'
        spp, baseline = metrics(log_path), metrics(baseline_path)
        row = dict(trace=name, baseline_ipc=baseline['ipc'], spp_ipc=spp['ipc'],
                   speedup=spp['ipc']/baseline['ipc'],
                   baseline_l1d_load_mpki=baseline['l1d_load_mpki'],
                   spp_l1d_load_mpki=spp['l1d_load_mpki'],
                   prefetch_accuracy=spp['accuracy'], issued=spp['issued'], useful=spp['useful'],
                   coverage=1-spp['l1d_load_mpki']/baseline['l1d_load_mpki'])
        record = dict(command=command, binary_sha256=binary_hash, warmup=COUNT,
                      measured=COUNT, defaults=dict(uniform_conf=4, pattern_conf=2,
                      accuracy=[25,50,75]), seconds=time.monotonic()-started,
                      baseline=str(baseline_path.relative_to(ROOT)), row=row)
        (directory / 'spp.json').write_text(json.dumps(record, indent=2)+'\n')
        print(f"{name}: {row['speedup']:.6f}x ({(row['speedup']-1)*100:+.3f}%)", flush=True)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run, sorted((ROOT/'traces').glob('*.gz'))))
    with (OUTPUT/'results.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    geomean=math.exp(sum(math.log(r['speedup']) for r in rows)/len(rows))
    summary=dict(geometric_mean_speedup=geomean, rows=rows)
    (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'Geometric mean: {geomean:.6f}x ({(geomean-1)*100:+.3f}%)', flush=True)


if __name__ == '__main__':
    main()
