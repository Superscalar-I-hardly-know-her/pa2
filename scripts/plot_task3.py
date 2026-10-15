#!/usr/bin/env python3
"""Plot the fixed Task 3 combination and standalone references."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/task3'
data=json.loads((OUT/'summary.json').read_text())
rows=data['rows']
traces=sorted({r['trace'] for r in rows})
schemes=['none','spp','dynamic','combined-plain','combined-aware']
labels=['No PF / LRU','SPP / LRU','No PF / dynamic','SPP / dynamic','SPP / aware dynamic']
colors=['#8b949e','#3478a8','#9062a8','#d68430','#328668']
lookup={(r['trace'],r['scheme']):r for r in rows}
plots=OUT/'plots'
plots.mkdir(exist_ok=True)
for r in rows: r['ipc_change']=100*(r['speedup']-1)
specs=[('ipc_change',1,'IPC gain versus no-prefetch LRU','%'),
       ('l1d_load_mpki',1,'L1D demand LOAD MPKI','Misses / 1,000 instructions'),
       ('l2c_load_mpki',1,'L2 demand LOAD MPKI','Misses / 1,000 instructions'),
       ('l2_instruction_mpki',1,'L2 instruction LOAD MPKI','Misses / 1,000 instructions'),
       ('l2_data_mpki',1,'L2 data LOAD MPKI','Misses / 1,000 instructions'),
       ('coverage',100,'Net L1D miss coverage','% baseline misses removed'),
       ('simulator_accuracy',100,'Simulator prefetch accuracy','Useful / sent to lower level (%)'),
       ('useful_per_issued',100,'Useful / all issued requests','%')]
fig,axes=plt.subplots(4,2,figsize=(12,15))
x=np.arange(len(traces)); width=.15
for ax,(key,scale,title,ylabel) in zip(axes.flat,specs):
    for i,(scheme,label,color) in enumerate(zip(schemes,labels,colors)):
        values=[lookup[t,scheme][key] for t in traces]
        values=[v*scale if v is not None else np.nan for v in values]
        ax.bar(x+(i-2)*width,values,width,label=label,color=color)
    ax.set_xticks(x,[t.split('-')[0] for t in traces])
    ax.set_title(title); ax.set_ylabel(ylabel)
    ax.spines[['top','right']].set_visible(False)
    ax.axhline(0,color='#444444',linewidth=.7)
handles,legend_labels=axes[0,0].get_legend_handles_labels()
fig.legend(handles,legend_labels,ncol=3,loc='upper center',bbox_to_anchor=(.5,.972))
fig.suptitle('Task 3: fixed SPP + dynamic I-RRIP\n25M warmup + 25M measured; no joint tuning',fontsize=15,y=.998)
fig.tight_layout(rect=(0,0,1,.935))
for suffix in ['png','pdf']: fig.savefig(plots/f'comparison.{suffix}',dpi=180,bbox_inches='tight')
plt.close(fig)

fig,ax=plt.subplots(figsize=(9,4.5))
gains=[100*(r['speedup']-1) for r in data['aggregates']]
bars=ax.bar(np.arange(5),gains,color=colors,width=.65)
ax.set_xticks(np.arange(5),labels,rotation=12,ha='right')
ax.bar_label(bars,labels=[f'{v:+.3f}%' for v in gains],padding=4)
ax.set_ylabel('Geometric mean IPC gain versus no-prefetch LRU (%)')
ax.set_title('Task 3: standalone and combined policies')
ax.spines[['top','right']].set_visible(False); ax.axhline(0,color='#444444',linewidth=.7)
ax.margins(y=.15); fig.tight_layout()
for suffix in ['png','pdf']: fig.savefig(plots/f'geomean-speedup.{suffix}',dpi=180,bbox_inches='tight')
plt.close(fig)
