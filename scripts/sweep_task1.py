#!/usr/bin/env python3
"""Sweep SPP confidence and accuracy boundaries with four simulator workers."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from compare_task1 import ROOT, COUNT, read_stats, write_csv

OUT = ROOT/'results/task1/sweep'


def configurations():
    for accuracy, uniform, pattern in itertools.product([(25,50,75),(3,6,12),(1,2,4)], [2,4], [1,2]):
        yield dict(name=f'u{uniform}-p{pattern}-a'+ '-'.join(map(str,accuracy)),
                   uniform=uniform, pattern=pattern, accuracy=list(accuracy))


def summarize(rows):
    rows.sort(key=lambda r:(r['name'],r['trace']))
    write_csv(OUT/'results.csv',rows)
    ranking=[]
    for config in configurations():
        group=[r for r in rows if r['name']==config['name']]
        if len(group)!=3: continue
        gm=lambda key: math.exp(sum(math.log(r[key]) for r in group)/len(group))
        ranking.append(dict(**config, speedup=gm('speedup'), vs_default=gm('vs_default'),
                            vs_ip_stride=gm('vs_ip_stride'), l1d_load_mpki=gm('l1d_load_mpki'),
                            simulator_accuracy=gm('simulator_accuracy'),
                            useful_per_issued=gm('useful_per_issued'),
                            issued=gm('issued'), min_speedup=min(r['speedup'] for r in group)))
    ranking.sort(key=lambda r:r['speedup'], reverse=True)
    if ranking:
        write_csv(OUT/'ranking.csv',ranking)
        (OUT/'ranking.json').write_text(json.dumps(ranking,indent=2)+'\n')
    return ranking


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    if args.jobs<1: parser.error('--jobs must be positive')
    OUT.mkdir(parents=True,exist_ok=True)
    binary=next((ROOT/'bin').glob('*-1core-task1-spp-compiler-check'))
    digest=hashlib.sha256(binary.read_bytes()).hexdigest()
    compiler=Path(str(binary)+'.compiler.txt').read_text()
    configs=list(configurations())
    (OUT/'experiment.json').write_text(json.dumps(dict(warmup=COUNT,measured=COUNT,
        binary=str(binary.relative_to(ROOT)),binary_sha256=digest,compiler=compiler,
        accuracy_denominator='all issued prefetch requests',configurations=configs),indent=2)+'\n')
    traces=sorted((ROOT/'traces').glob('*.gz'))
    references={}
    for trace in traces:
        name=trace.name[:-3]
        references[name]={s:read_stats(p, require_lru=True)[0] for s,p in [
            ('baseline',ROOT/'results/task2/full'/name/'lru.log'),
            ('default',ROOT/'results/task1/full'/name/'spp.log'),
            ('ip_stride',ROOT/'results/task1/full'/name/'ip_stride.log')]}
    def run(trace,config):
        name=trace.name[:-3]
        directory=OUT/name
        directory.mkdir(exist_ok=True)
        log=directory/(config['name']+'.log')
        record=directory/(config['name']+'.json')
        signature=dict(config=config,binary_sha256=digest,trace=str(trace.relative_to(ROOT)),
                       size=trace.stat().st_size,mtime_ns=trace.stat().st_mtime_ns,
                       warmup=COUNT,measured=COUNT)
        cached=json.loads(record.read_text()) if record.exists() else {}
        seconds=cached.get('seconds',0)
        if cached.get('signature')!=signature or not log.exists():
            env={k:v for k,v in os.environ.items() if not k.startswith('SPP_')}
            env.update(SPP_UNIFORM_CONF=str(config['uniform']),SPP_PATTERN_CONF=str(config['pattern']),
                **dict(zip(['SPP_ACCURACY_LOW','SPP_ACCURACY_MID','SPP_ACCURACY_HIGH'],map(str,config['accuracy']))))
            command=[str(binary),'-warmup_instructions',str(COUNT),'-simulation_instructions',str(COUNT),
                     '-traces',str(trace.relative_to(ROOT))]
            started=time.monotonic()
            with log.open('w') as f:
                subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
            seconds=time.monotonic()-started
        stats=read_stats(log, require_lru=True)[0]
        text=log.read_text()
        header=f"SPP uniform_conf={config['uniform']} pattern_conf={config['pattern']} accuracy="+','.join(map(str,config['accuracy']))
        if header not in text: raise ValueError(f'Configuration mismatch: {log}')
        final_degree=int(re.search(r'^SPP degree=(\d+)',text,re.M).group(1))
        ref=references[name]
        row=dict(trace=name,name=config['name'],uniform=config['uniform'],pattern=config['pattern'],
                 accuracy='/'.join(map(str,config['accuracy'])),**stats,
                 speedup=stats['ipc']/ref['baseline']['ipc'],
                 vs_default=stats['ipc']/ref['default']['ipc'],
                 vs_ip_stride=stats['ipc']/ref['ip_stride']['ipc'],
                 coverage=1-stats['l1d_load_mpki']/ref['baseline']['l1d_load_mpki'],final_degree=final_degree)
        record.write_text(json.dumps(dict(signature=signature,seconds=seconds,row=row),indent=2)+'\n')
        return row,seconds
    tasks=[(t,c) for c in configs for t in traces]
    rows=[]
    started=time.monotonic()
    print(f'{len(configs)} configurations, {len(tasks)} runs, {args.jobs} workers',flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures=[pool.submit(run,*task) for task in tasks]
        for index,future in enumerate(as_completed(futures),1):
            row,seconds=future.result()
            rows.append(row)
            ranking=summarize(rows)
            print(f"[{index}/{len(tasks)}] {row['trace']} {row['name']}: {(row['speedup']-1)*100:+.3f}% IPC, degree {row['final_degree']}, {seconds:.1f}s; elapsed {time.monotonic()-started:.0f}s",flush=True)
    print('Best: '+json.dumps(ranking[0]),flush=True)


if __name__=='__main__':
    main()
