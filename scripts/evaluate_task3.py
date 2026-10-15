#!/usr/bin/env python3
"""Evaluate fixed SPP + dynamic I-RRIP, with one prefetch-awareness ablation."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from compare_task1 import ROOT, COUNT, read_stats, write_csv
from sweep_task2b import diagnostics

OUT=ROOT/'results/task3'
SPP=dict(SPP_UNIFORM_CONF='2',SPP_PATTERN_CONF='1',SPP_ACCURACY_LOW='1',
         SPP_ACCURACY_MID='2',SPP_ACCURACY_HIGH='4')
DYNAMIC=dict(DYN_IRRIP_THRESHOLD='0.10',DYN_IRRIP_START='0',DYN_IRRIP_PERSIST='0')


def metrics(path):
    stats=read_stats(path)[0]
    roi=path.read_text().split('Region of Interest Statistics')[-1]
    for kind in ['INSTRUCTION','DATA']:
        stats['l2_'+kind.lower()+'_mpki']=float(re.search(
            r'^L2C '+kind+r' LOAD MPKI: ([\d.eE+-]+)',roi,re.M).group(1))
    return stats


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    binary=next((ROOT/'bin').glob('*-1core-task3-combined'))
    digest=hashlib.sha256(binary.read_bytes()).hexdigest()
    compiler=Path(str(binary)+'.compiler.txt').read_text()
    (OUT/'experiment.json').write_text(json.dumps(dict(warmup=COUNT,measured=COUNT,
        spp=SPP,dynamic=DYNAMIC,compiler=compiler,binary_sha256=digest,
        awareness='Follower data prefetch insertion at RRPV 3, no promotion on prefetch hits; leaders unchanged'),indent=2)+'\n')
    traces=sorted((ROOT/'traces').glob('*.gz'))
    def run(trace,aware):
        name=trace.name[:-3]
        scheme='combined-aware' if aware else 'combined-plain'
        directory=OUT/name
        directory.mkdir(exist_ok=True)
        log=directory/(scheme+'.log')
        record=directory/(scheme+'.json')
        env={k:v for k,v in os.environ.items() if not k.startswith(('SPP_','DYN_IRRIP_'))}
        parameters={**SPP,**DYNAMIC,'DYN_IRRIP_PREFETCH':str(int(aware))}
        env.update(parameters)
        signature=dict(binary_sha256=digest,trace=str(trace.relative_to(ROOT)),
            size=trace.stat().st_size,mtime_ns=trace.stat().st_mtime_ns,
            warmup=COUNT,measured=COUNT,parameters=parameters)
        cached=json.loads(record.read_text()) if record.exists() else {}
        seconds=cached.get('seconds',0)
        if cached.get('signature')!=signature or not log.exists():
            command=[str(binary),'-warmup_instructions',str(COUNT),'-simulation_instructions',str(COUNT),
                     '-traces',str(trace.relative_to(ROOT))]
            started=time.monotonic()
            with log.open('w') as f:
                subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
            seconds=time.monotonic()-started
        stats=metrics(log)
        text=log.read_text()
        assert 'SPP uniform_conf=2 pattern_conf=1 accuracy=1,2,4' in text
        assert f'prefetch_aware={int(aware)}' in text
        control=diagnostics(text,.1)
        summary=next(line for line in text.splitlines() if line.startswith('DYN_SUMMARY '))
        counts={k:int(v) for k,v in (part.split('=') for part in summary.split()[1:])}
        stats.update(**control,roi_prefetch_fills=counts['roi_prefetch_fills'],roi_prefetch_hits=counts['roi_prefetch_hits'])
        if aware: assert stats['roi_prefetch_fills']>0 and stats['roi_prefetch_hits']>0
        else: assert stats['roi_prefetch_fills']==stats['roi_prefetch_hits']==0
        record.write_text(json.dumps(dict(signature=signature,seconds=seconds,metrics=stats),indent=2)+'\n')
        print(f'{name} {scheme}: IPC {stats["ipc"]:.6f}, {seconds:.1f}s',flush=True)
        return (name,scheme),stats
    combined={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(run,t,a) for a in [False,True] for t in traces]
        for future in as_completed(futures):
            key,stats=future.result(); combined[key]=stats
    rows=[]
    for trace in traces:
        name=trace.name[:-3]
        refs={s:metrics(path) for s,path in [
            ('none',ROOT/'results/task2/full'/name/'lru.log'),
            ('spp',ROOT/'results/task1/sweep'/name/'u2-p1-a1-2-4.log'),
            ('dynamic',ROOT/'results/task2b/full'/name/'threshold-0.10.log')]}
        for scheme in ['none','spp','dynamic','combined-plain','combined-aware']:
            stats=refs[scheme] if scheme in refs else combined[name,scheme]
            rows.append(dict(trace=name,scheme=scheme,**stats,
                speedup=stats['ipc']/refs['none']['ipc'],
                vs_spp=stats['ipc']/refs['spp']['ipc'],
                vs_dynamic=stats['ipc']/refs['dynamic']['ipc'],
                coverage=1-stats['l1d_load_mpki']/refs['none']['l1d_load_mpki'],
                coverage_vs_dynamic=1-stats['l1d_load_mpki']/refs['dynamic']['l1d_load_mpki']))
    # Controller diagnostics are only present in newly run combined rows.
    fields=list(dict.fromkeys(k for r in rows for k in r))
    rows=[{k:r.get(k) for k in fields} for r in rows]
    write_csv(OUT/'results.csv',rows)
    aggregates=[]
    for scheme in ['none','spp','dynamic','combined-plain','combined-aware']:
        group=[r for r in rows if r['scheme']==scheme]
        gm=lambda k: math.exp(sum(math.log(r[k]) for r in group)/len(group))
        aggregates.append(dict(scheme=scheme,**{k:gm(k) for k in ['speedup','vs_spp','vs_dynamic',
            'l1d_load_mpki','l2c_load_mpki','l2_instruction_mpki','l2_data_mpki']},
            simulator_accuracy=gm('simulator_accuracy') if all(r['simulator_accuracy'] for r in group) else None))
    write_csv(OUT/'aggregates.csv',aggregates)
    (OUT/'summary.json').write_text(json.dumps(dict(rows=rows,aggregates=aggregates),indent=2)+'\n')
    lines=['Task 3: fixed SPP + dynamic I-RRIP','=================================','',
        'All runs: 25M warmup + 25M measured instructions. Native Apple Clang; GCC 7 validation remains outstanding. SPP uses uniform confidence 2, pattern confidence 1, accuracy boundaries 1/2/4 percent. Dynamic I-RRIP uses the original controller at threshold 0.10 (the best measured Task 2B variant). No joint tuning is performed.', '',
        'The plain combination is an ablation. The Task 3 prefetch-aware version inserts follower data prefetches at RRPV 3, and leaves RRPV unchanged on data-prefetch hits. Demand reuse promotes according to the existing I-RRIP/RRIP mode. RRIP leaders retain their ordinary insertion and promotion rules; only demand LOADs train the controller. DYN_IRRIP_PREFETCH=1 enables this rule; default 0 preserves Task 2 behavior.', '',
        '| Trace | Scheme | IPC | Gain vs baseline | Vs SPP | Vs dynamic | L1D MPKI | L2 MPKI | L2 instruction MPKI | L2 data MPKI | Coverage | Accuracy |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    pct=lambda x:'—' if x is None else f'{x*100:.2f}%'
    for r in rows:
        lines.append(f"| {r['trace']} | {r['scheme']} | {r['ipc']:.6f} | {(r['speedup']-1)*100:+.3f}% | {(r['vs_spp']-1)*100:+.3f}% | {(r['vs_dynamic']-1)*100:+.3f}% | {r['l1d_load_mpki']:.4f} | {r['l2c_load_mpki']:.4f} | {r['l2_instruction_mpki']:.4f} | {r['l2_data_mpki']:.4f} | {pct(r['coverage'])} | {pct(r['simulator_accuracy'])} |")
    lines+=['','Geometric means:', '', '| Scheme | Gain vs baseline | Vs SPP | Vs dynamic | L1D MPKI | L2 MPKI |', '|---|---:|---:|---:|---:|---:|']
    for r in aggregates:
        lines.append(f"| {r['scheme']} | {(r['speedup']-1)*100:+.3f}% | {(r['vs_spp']-1)*100:+.3f}% | {(r['vs_dynamic']-1)*100:+.3f}% | {r['l1d_load_mpki']:.4f} | {r['l2c_load_mpki']:.4f} |")
    lines+=['', 'Rationale: speculative data has not demonstrated demand reuse, so it receives little retention priority and repeated speculative hits cannot protect it. Demand reuse restores the usual priority. This can reduce competition with instructions and proven demand data, but may evict useful prefetches too early. This simple choice is evaluated once, without retuning either component.', '',
        'Accuracy = useful / prefetches sent to lower level, matching printed simulator accuracy; useful / all-issued is separately retained in results.csv. Coverage = net L1D demand miss reduction against no-prefetch LRU. coverage_vs_dynamic also measures incremental reduction against no-prefetch dynamic I-RRIP. Standalone references reuse their completed runs. Individual logs and JSON files record all controller windows and prefetch-awareness callback counts.']
    (OUT/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(aggregates,indent=2),flush=True)


if __name__=='__main__':
    main()
