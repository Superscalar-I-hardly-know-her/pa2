#!/usr/bin/env python3
"""Plot the default SPP full-run speedups."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
data = json.loads((root/'results/task1/full/summary.json').read_text())
rows = data['rows']
labels = [r['trace'] for r in rows] + ['Geomean']
values = [(r['speedup']-1)*100 for r in rows] + [(data['geometric_mean_speedup']-1)*100]
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(labels, values, color=['#3478a8']*3+['#475569'], width=.6)
ax.axhline(0, color='#333333', linewidth=.8)
ax.set_ylabel('IPC change versus no-prefetch LRU (%)')
ax.set_title('Initial SPP: 25M warmup + 25M measured instructions')
ax.spines[['top', 'right']].set_visible(False)
ax.bar_label(bars, labels=[f'{v:+.2f}%' for v in values], padding=4)
ax.margins(y=.25)
fig.tight_layout()
output=root/'results/task1/plots'
output.mkdir(exist_ok=True)
for suffix in ['png','pdf']:
    fig.savefig(output/f'initial-speedup.{suffix}', dpi=180)
