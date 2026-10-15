#!/usr/bin/env python3
"""Rank the SPP sweep and plot per-trace results and aggressiveness tradeoffs."""
import csv
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/task1/sweep'
rows=list(csv.DictReader((OUT/'results.csv').open()))
ranking=json.loads((OUT/'ranking.json').read_text())
reference=json.loads((ROOT/'results/task1/comparison/summary.json').read_text())
plot_dir=OUT/'plots'
plot_dir.mkdir(exist_ok=True)
traces=sorted({r['trace'] for r in rows})
lookup={(r['name'],r['trace']):r for r in rows}


def save(fig,name):
    fig.tight_layout()
    for suffix in ['png','pdf']:
        fig.savefig(plot_dir/f'{name}.{suffix}',dpi=180,bbox_inches='tight')
    plt.close(fig)


labels=[r['name'] for r in ranking]
values=[100*(r['speedup']-1) for r in ranking]
fig,ax=plt.subplots(figsize=(9,6))
y=np.arange(len(ranking))
colors=['#3478a8' if r['accuracy']==[25,50,75] else '#3a9179' if r['accuracy']==[3,6,12] else '#d68430' for r in ranking]
ax.barh(y,values,color=colors)
ax.set_yticks(y,labels)
ax.invert_yaxis()
ax.axvline(0,color='#333333',linewidth=.7)
for scheme,color in [('spp','#666666'),('ip_stride','#9d398a')]:
    gain=100*(reference['geomeans'][scheme]-1)
    ax.axvline(gain,color=color,linestyle='--',label=f'{scheme}: {gain:+.3f}%')
ax.set_xlabel('Geometric mean IPC change versus no prefetch (%)')
ax.set_title('SPP accuracy-boundary and confidence sweep')
ax.spines[['top','right']].set_visible(False)
ax.legend(loc='lower right')
save(fig,'ranking')

matrix=[]
for r in ranking:
    matrix.append([100*(float(lookup[r['name'],t]['speedup'])-1) for t in traces]+[100*(r['speedup']-1)])
matrix=np.array(matrix)
fig,ax=plt.subplots(figsize=(8,7))
limit=max(abs(matrix.min()),abs(matrix.max()))
im=ax.imshow(matrix,cmap='RdYlGn',vmin=-limit,vmax=limit,aspect='auto')
ax.set_yticks(np.arange(len(labels)),labels)
ax.set_xticks(np.arange(4),[t.split('-')[0] for t in traces]+['Geomean'])
for i in range(len(labels)):
    for j in range(4): ax.text(j,i,f'{matrix[i,j]:+.3f}%',ha='center',va='center',fontsize=9)
ax.set_title('IPC change versus no prefetch: 25M warmup + 25M measured')
fig.colorbar(im,ax=ax,label='IPC change (%)')
save(fig,'per-trace-speedup')

fig,axes=plt.subplots(1,3,figsize=(14,4.5))
for ax,key,title in zip(axes,['l1d_load_mpki','simulator_accuracy','issued'],
                       ['L1D load MPKI','Simulator accuracy (%)','Issued requests']):
    for r,color in zip(ranking,colors):
        x=r[key]*100 if key=='simulator_accuracy' else r[key]
        ax.scatter(x,100*(r['speedup']-1),color=color,marker='o' if r['uniform']==4 else '^',
                   s=45 if r['pattern']==1 else 85,edgecolor='#222222',linewidth=.4)
    for scheme,marker in [('spp','X'),('ip_stride','P')]:
        group=[r for r in reference['rows'] if r['scheme']==scheme]
        gm=math.exp(sum(math.log(r[key]) for r in group)/len(group))
        if key=='simulator_accuracy': gm*=100
        ax.scatter(gm,100*(reference['geomeans'][scheme]-1),marker=marker,color='#222222',s=100,label=scheme)
    ax.set_xlabel('Geometric mean '+title)
    ax.set_ylabel('Geometric mean IPC gain (%)')
    ax.spines[['top','right']].set_visible(False)
axes[0].legend()
fig.suptitle('Aggressiveness tradeoffs: blue 25/50/75, green 3/6/12, orange 1/2/4')
save(fig,'tradeoffs')

best=ranking[0]
best_rows=[lookup[best['name'],t] for t in traces]
aggregates=[]
for scheme,group in [('IP-stride',[r for r in reference['rows'] if r['scheme']=='ip_stride']),
                     ('Default SPP',[r for r in reference['rows'] if r['scheme']=='spp']),
                     ('Tuned SPP',best_rows)]:
    gm=lambda key: math.exp(sum(math.log(float(r[key])) for r in group)/len(group))
    aggregates.append(dict(scheme=scheme,**{key:gm(key) for key in
        ['speedup','l1d_load_mpki','l2c_load_mpki','llc_load_mpki','coverage',
         'simulator_accuracy','useful_per_issued','issued','useful','useless','late']}))
with (OUT/'aggregate-comparison.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(aggregates[0]))
    writer.writeheader(); writer.writerows(aggregates)
lines=['SPP aggressiveness sweep','========================','',
    '12 configurations: accuracy boundaries 25/50/75, 3/6/12, 1/2/4 percent; uniform confidence 2 or 4; pattern confidence 1 or 2. Accuracy boundaries act on useful / all issued requests. All other predictor behavior is fixed. Each run uses 25M warmup + 25M measured instructions, LRU throughout, four concurrent workers, and Apple Clang (version recorded in experiment.json). These are native Mac experiments, not GCC 7 validation.', '',
    '| Configuration | Geomean IPC gain vs baseline | Versus default SPP | Versus IP-stride | Geomean L1D MPKI | Simulator accuracy |',
    '|---|---:|---:|---:|---:|---:|']
for r in ranking:
    lines.append(f"| {r['name']} | {(r['speedup']-1)*100:+.3f}% | {(r['vs_default']-1)*100:+.3f}% | {(r['vs_ip_stride']-1)*100:+.3f}% | {r['l1d_load_mpki']:.4f} | {r['simulator_accuracy']*100:.2f}% |")
lines += ['',f"Best by geometric mean IPC: **{best['name']}**. This is the best among tested configurations on these three traces, not a claim about other workloads. Source defaults have not been changed.",'',
    '| Trace | IPC | Gain vs baseline | Versus default SPP | Versus IP-stride | L1D MPKI | Coverage | Simulator accuracy | Useful / issued | Final degree |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in best_rows:
    f=lambda key:float(r[key])
    lines.append(f"| {r['trace']} | {f('ipc'):.6f} | {(f('speedup')-1)*100:+.3f}% | {(f('vs_default')-1)*100:+.3f}% | {(f('vs_ip_stride')-1)*100:+.3f}% | {f('l1d_load_mpki'):.4f} | {f('coverage')*100:.2f}% | {f('simulator_accuracy')*100:.2f}% | {f('useful_per_issued')*100:.2f}% | {r['final_degree']} |")
lines += ['', 'Simulator accuracy = useful / sent to lower level. Coverage = net reduction in demand L1D load MPKI versus baseline. Degree is its final value, not a time average. Results include exact instruction/cycle ratios and raw prefetch counters. Per-run logs and JSON records preserve parameters, binary hash, trace metadata, and duration.', '', 'Plots: plots/ranking.png, plots/per-trace-speedup.png, plots/tradeoffs.png (PDF copies also available).']
lines += ['', 'Geometric means across traces:', '',
    '| Scheme | IPC gain | L1D MPKI | Coverage | Simulator accuracy | Issued requests |',
    '|---|---:|---:|---:|---:|---:|']
for r in aggregates:
    lines.append(f"| {r['scheme']} | {(r['speedup']-1)*100:+.3f}% | {r['l1d_load_mpki']:.4f} | {r['coverage']*100:.2f}% | {r['simulator_accuracy']*100:.2f}% | {r['issued']:.0f} |")
(OUT/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
(OUT/'best-config.json').write_text(json.dumps(best,indent=2)+'\n')
