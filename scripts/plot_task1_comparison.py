#!/usr/bin/env python3
"""Plot baseline, supplied IP-stride, and initial SPP measurements."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parents[1]
data = json.loads((root/'results/task1/comparison/summary.json').read_text())
rows = data['rows']
traces = sorted({r['trace'] for r in rows})
lookup = {(r['trace'],r['scheme']):r for r in rows}
output = root/'results/task1/plots'
colors = {'none':'#8b949e', 'ip_stride':'#d68430', 'spp':'#3478a8'}
names = {'none':'No prefetch', 'ip_stride':'IP-stride', 'spp':'SPP'}


def save(fig, name):
    fig.tight_layout(rect=(0,0,1,.95))
    for suffix in ['png','pdf']:
        fig.savefig(output/f'{name}.{suffix}', dpi=180)
    plt.close(fig)


def grouped(ax, key, schemes, scale=1, title='', ylabel=''):
    x = np.arange(len(traces))
    width = .8/len(schemes)
    for i,scheme in enumerate(schemes):
        values = [lookup[t,scheme][key] for t in traces]
        values = [np.nan if v is None else v*scale for v in values]
        ax.bar(x+(i-(len(schemes)-1)/2)*width, values, width,
               label=names[scheme], color=colors[scheme])
    ax.set_xticks(x, [t.split('-')[0] for t in traces])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.spines[['top','right']].set_visible(False)
    ax.axhline(0,color='#444444',linewidth=.6)


fig, axes = plt.subplots(3,2,figsize=(11,11))
for row in rows: row['ipc_change']=(row['speedup']-1)*100
specs = [('ipc_change',['ip_stride','spp'],1,'IPC change','% versus no prefetch'),
         ('l1d_load_mpki',['none','ip_stride','spp'],1,'L1D demand LOAD MPKI','Misses / 1,000 instructions'),
         ('coverage',['ip_stride','spp'],100,'Net L1D miss coverage','% baseline misses removed'),
         ('simulator_accuracy',['ip_stride','spp'],100,'Simulator prefetch accuracy','Useful / sent to lower level (%)'),
         ('useful_per_issued',['ip_stride','spp'],100,'Useful / all issued requests','%'),
         ('prefetch_hit_fraction',['ip_stride','spp'],100,'L1D prefetch lookup hit rate','% processed prefetches already present')]
for ax,(key,schemes,scale,title,label) in zip(axes.flat,specs):
    grouped(ax,key,schemes,scale,title,label)
axes[0,0].legend()
axes[0,1].legend()
fig.suptitle('Task 1: supplied IP-stride versus initial SPP\n25M warmup + 25M measured; LRU replacement',fontsize=14)
save(fig,'prefetcher-comparison')

fig,axes=plt.subplots(1,3,figsize=(14,4.5))
for ax,level in zip(axes,['l1d','l2c','llc']):
    grouped(ax,level+'_load_mpki',['none','ip_stride','spp'],title=level.upper()+' demand LOAD MPKI',ylabel='Misses / 1,000 instructions')
axes[0].legend()
fig.suptitle('Demand LOAD misses across the cache hierarchy')
save(fig,'prefetcher-cache-mpki')

fig,axes=plt.subplots(2,3,figsize=(13,8))
for ax,key,title in zip(axes.flat,['issued','lower_level_prefetches','useful','useless','late','prefetch_hits'],
                       ['Issued requests','Sent to lower level','Useful prefetches','Evicted unused','Late prefetches','L1D prefetch lookup hits']):
    grouped(ax,key,['ip_stride','spp'],title=title,ylabel='Count')
axes[0,0].legend()
fig.suptitle('Prefetch activity: simulator counters')
save(fig,'prefetcher-activity')
