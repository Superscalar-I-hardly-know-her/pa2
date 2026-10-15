Initial SPP evaluation
======================

All runs use 25M warmup + 25M measured instructions, LRU at L2, and the default SPP parameters (uniform confidence 4, pattern confidence 2, accuracy boundaries 25/50/75%). Three concurrent workers. Baselines reuse the completed no-prefetch LRU runs from results/task2/full. Speedups use exact retired instructions / cycles.

| Trace | Baseline IPC | SPP IPC | IPC change | L1D MPKI baseline → SPP | Useful / issued |
|---|---:|---:|---:|---:|---:|
| Trace1-003 | 0.231828 | 0.232519 | +0.298% | 10.6784 → 10.4034 | 8.73% |
| Trace2-001 | 0.251534 | 0.251884 | +0.139% | 13.5367 → 13.4056 | 4.49% |
| Trace3-002 | 0.381848 | 0.382557 | +0.186% | 3.4036 → 3.3480 | 1.93% |

Geometric mean speedup: 1.002076x (+0.208%).

All traces finish at degree one. Both uniform and pattern paths issue predictions. Useful/issued accuracy is low; issued includes redundant requests that later hit existing lines or merge, so this ratio is not simply the correctness of the address prediction. Coverage in results.csv is the relative reduction in demand L1D LOAD MPKI. No thresholds were tuned for these runs.

Per-trace JSON records include commands, binary hash, defaults, duration, and baseline source. Raw simulator output is retained alongside them.
