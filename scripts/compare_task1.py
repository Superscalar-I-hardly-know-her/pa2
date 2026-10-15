#!/usr/bin/env python3
"""Run supplied IP-stride, then compare all three Task 1 schemes."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/task1/comparison'
COUNT = 25_000_000


def assert_lru(text, path):
    """Reject mixed replacement policies in standalone prefetcher comparisons."""
    policies = dict(re.findall(r'^(\w+) has (\S+) replacement policy$', text, re.M))
    for cache in ['BTB', 'ITLB', 'DTLB', 'STLB', 'L1I', 'L1D', 'L2C', 'LLC']:
        if policies.get(cache) != 'LRU':
            raise ValueError(f'{path}: {cache} must use LRU, found {policies.get(cache)}')


def read_stats(path, require_lru=False):
    text = path.read_text()
    if require_lru:
        assert_lru(text, path)
    if 'Finished CPU 0 instructions:' not in text or 'Region of Interest Statistics' not in text:
        raise ValueError(f'Incomplete run: {path}')
    roi = text.split('Region of Interest Statistics')[-1]
    def values(pattern):
        match = re.search(pattern, roi, re.M)
        if not match:
            raise ValueError(f'Missing {pattern} in {path}')
        return match.groups()
    retired, cycles = map(int, values(r'^CPU 0 cumulative IPC: .* instructions: (\d+) cycles: (\d+)'))
    assert retired >= COUNT
    result = dict(instructions=retired, cycles=cycles, ipc=retired/cycles)
    caches = []
    for match in re.finditer(r'^(\w+)\s+(.+?)\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+)\s+HIT %:\s+([\d.eE+-]+)\s+MISS %:\s+([\d.eE+-]+)\s+MPKI:\s+([\d.eE+-]+)', roi, re.M):
        cache, kind, accesses, hits, misses, hit_pct, miss_pct, mpki = match.groups()
        caches.append(dict(cache=cache, type=kind, accesses=int(accesses), hits=int(hits),
                           misses=int(misses), hit_pct=float(hit_pct), miss_pct=float(miss_pct),
                           mpki=1000*int(misses)/retired))
    for cache in ['L1D', 'L1I', 'L2C', 'LLC']:
        load = next(c for c in caches if c['cache'] == cache and c['type'] == 'LOAD')
        result[cache.lower()+'_load_mpki'] = load['mpki']
    requested, issued, useful, useless = map(int, values(r'^L1D PREFETCH\s+REQUESTED:\s+(\d+)\s+ISSUED:\s+(\d+)\s+USEFUL:\s+(\d+)\s+USELESS:\s+(\d+)'))
    lower = int(values(r'^L1D USEFUL LOAD PREFETCHES:\s+\d+ PREFETCH ISSUED TO LOWER LEVEL:\s+(\d+)')[0])
    timely, late, dropped = map(int, values(r'^L1D TIMELY PREFETCHES:\s+(\d+) LATE PREFETCHES:\s+(\d+) DROPPED PREFETCHES:\s+(\d+)'))
    pf = next((c for c in caches if c['cache']=='L1D' and c['type']=='PREFETCH'), None)
    result.update(requested=requested, issued=issued, useful=useful, useless=useless,
                  lower_level_prefetches=lower, timely=timely, late=late, dropped=dropped,
                  simulator_accuracy=useful/lower if lower else None,
                  useful_per_issued=useful/issued if issued else None,
                  prefetch_accesses=pf['accesses'] if pf else 0,
                  prefetch_hits=pf['hits'] if pf else 0,
                  prefetch_misses=pf['misses'] if pf else 0,
                  prefetch_hit_fraction=pf['hits']/pf['accesses'] if pf and pf['accesses'] else None)
    # Preserve all printed key/value lines as well as normalized cache counters.
    printed = [line for line in roi.splitlines() if ':' in line]
    return result, caches, printed


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    binary = next((ROOT/'bin').glob('*-1core-task1-ip-stride'))
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    def run(trace):
        name = trace.name[:-3]
        directory = ROOT/'results/task1/full'/name
        log = directory/'ip_stride.log'
        record = directory/'ip_stride.json'
        signature = dict(binary_sha256=digest, trace=str(trace.relative_to(ROOT)),
                         trace_size=trace.stat().st_size, trace_mtime_ns=trace.stat().st_mtime_ns,
                         warmup=COUNT, measured=COUNT)
        cached = json.loads(record.read_text()) if record.exists() else {}
        if cached.get('signature') != signature or not log.exists():
            command = [str(binary), '-warmup_instructions', str(COUNT),
                       '-simulation_instructions', str(COUNT), '-traces', str(trace.relative_to(ROOT))]
            started = time.monotonic()
            with log.open('w') as f:
                subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
            read_stats(log, require_lru=True)
            record.write_text(json.dumps(dict(signature=signature, command=command,
                              seconds=time.monotonic()-started), indent=2)+'\n')
        print(f'{name}: IP-stride complete', flush=True)
        return name
    with ThreadPoolExecutor(max_workers=3) as pool:
        names = list(pool.map(run, sorted((ROOT/'traces').glob('*.gz'))))
    rows, cache_rows, raw = [], [], {}
    for name in names:
        baseline_path = ROOT/'results/task2/full'/name/'lru.log'
        baseline = read_stats(baseline_path, require_lru=True)[0]
        for scheme, path in [('none', baseline_path),
                             ('ip_stride', ROOT/'results/task1/full'/name/'ip_stride.log'),
                             ('spp', ROOT/'results/task1/full'/name/'spp.log')]:
            stats, caches, printed = read_stats(path, require_lru=True)
            row = dict(trace=name, scheme=scheme, **stats,
                       speedup=stats['ipc']/baseline['ipc'],
                       coverage=1-stats['l1d_load_mpki']/baseline['l1d_load_mpki'])
            rows.append(row)
            cache_rows.extend(dict(trace=name, scheme=scheme, **c) for c in caches)
            raw[name+'/'+scheme] = dict(log=str(path.relative_to(ROOT)), printed_statistics=printed)
    geomeans = {scheme: math.exp(sum(math.log(r['speedup']) for r in rows if r['scheme']==scheme)/len(names))
                for scheme in ['none','ip_stride','spp']}
    write_csv(OUT/'results.csv', rows)
    write_csv(OUT/'cache-statistics.csv', cache_rows)
    (OUT/'all-printed-statistics.json').write_text(json.dumps(raw, indent=2)+'\n')
    (OUT/'summary.json').write_text(json.dumps(dict(geomeans=geomeans, rows=rows), indent=2)+'\n')
    lines = ['Task 1 comparison', '=================', '',
        '25M warmup + 25M measured instructions per trace. LRU at all cache levels; only the L1D prefetcher changes. IP-stride is the supplied implementation unchanged (24 trackers, 8-bit IP identifier, fixed degree 3, L1/L2 destination based on MSHR occupancy). SPP uses its initial defaults. No-prefetch and SPP runs are reused.', '',
        '| Trace | Scheme | IPC | IPC change | L1D LOAD MPKI | Coverage | Simulator accuracy | Useful / issued |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    pct = lambda x: '—' if x is None else f'{100*x:.2f}%'
    for r in rows:
        lines.append(f"| {r['trace']} | {r['scheme']} | {r['ipc']:.6f} | {(r['speedup']-1)*100:+.3f}% | {r['l1d_load_mpki']:.4f} | {pct(r['coverage'])} | {pct(r['simulator_accuracy'])} | {pct(r['useful_per_issued'])} |")
    lines += ['', 'Geometric mean speedup: '+', '.join(f'{s} {g:.6f}x ({100*(g-1):+.3f}%)' for s,g in geomeans.items())+'.', '',
        'Coverage = 1 − prefetcher demand L1D LOAD MPKI / baseline demand L1D LOAD MPKI (net miss reduction, including pollution effects). Simulator accuracy = useful / prefetches issued to lower level, matching the printed ChampSim ACCURACY statistic. Useful / issued uses all accepted prefetch requests, including redundant requests; this is the initial SPP throttling signal and the quantity previously labeled accuracy in full/results.csv. The two denominators must not be mixed. Baseline prefetch accuracy is undefined.', '',
        'results.csv includes exact instruction/cycle IPC, L1D/L1I/L2/LLC load MPKI, coverage, both accuracy definitions, requested/issued/useful/unused/lower-level prefetch counts, timely/late/dropped counters, and L1D prefetch hit/miss counters. cache-statistics.csv includes every printed cache access type. all-printed-statistics.json preserves the remaining simulator output, including queues, DRAM, and printed latency counters. Raw logs remain at the referenced paths. Some printed diagnostics span warmup as well as ROI; they are preserved without treating them as ROI-normalized metrics.']
    (OUT/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(geomeans), flush=True)


if __name__ == '__main__':
    main()
