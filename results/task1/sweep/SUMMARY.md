SPP aggressiveness sweep
========================

12 configurations: accuracy boundaries 25/50/75, 3/6/12, 1/2/4 percent; uniform confidence 2 or 4; pattern confidence 1 or 2. Accuracy boundaries act on useful / all issued requests. All other predictor behavior is fixed. Each run uses 25M warmup + 25M measured instructions, LRU throughout, four concurrent workers, and Apple Clang (version recorded in experiment.json). These are native Mac experiments, not GCC 7 validation.

| Configuration | Geomean IPC gain vs baseline | Versus default SPP | Versus IP-stride | Geomean L1D MPKI | Simulator accuracy |
|---|---:|---:|---:|---:|---:|
| u2-p1-a1-2-4 | +0.604% | +0.396% | +0.416% | 7.4474 | 44.51% |
| u2-p2-a1-2-4 | +0.558% | +0.350% | +0.370% | 7.4707 | 43.58% |
| u2-p1-a3-6-12 | +0.477% | +0.269% | +0.289% | 7.5692 | 49.86% |
| u2-p2-a3-6-12 | +0.405% | +0.197% | +0.217% | 7.5960 | 48.37% |
| u2-p1-a25-50-75 | +0.397% | +0.189% | +0.209% | 7.6441 | 49.66% |
| u2-p2-a25-50-75 | +0.368% | +0.160% | +0.180% | 7.6635 | 48.58% |
| u4-p1-a1-2-4 | +0.340% | +0.132% | +0.152% | 7.6258 | 53.35% |
| u4-p1-a3-6-12 | +0.286% | +0.078% | +0.098% | 7.6929 | 57.19% |
| u4-p2-a1-2-4 | +0.270% | +0.063% | +0.083% | 7.6675 | 53.30% |
| u4-p1-a25-50-75 | +0.254% | +0.046% | +0.066% | 7.7283 | 56.03% |
| u4-p2-a3-6-12 | +0.235% | +0.028% | +0.048% | 7.7234 | 57.00% |
| u4-p2-a25-50-75 | +0.208% | +0.000% | +0.020% | 7.7580 | 55.46% |

Best by geometric mean IPC: **u2-p1-a1-2-4**. This is the best among tested configurations on these three traces, not a claim about other workloads. Source defaults have not been changed.

| Trace | IPC | Gain vs baseline | Versus default SPP | Versus IP-stride | L1D MPKI | Coverage | Simulator accuracy | Useful / issued | Final degree |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Trace1-003 | 0.233293 | +0.632% | +0.333% | +0.194% | 9.7858 | 8.36% | 56.20% | 4.27% | 8 |
| Trace2-001 | 0.252836 | +0.517% | +0.378% | +0.626% | 13.1580 | 2.80% | 49.78% | 2.53% | 4 |
| Trace3-002 | 0.384384 | +0.664% | +0.478% | +0.429% | 3.2080 | 5.75% | 31.51% | 2.06% | 4 |

Simulator accuracy = useful / sent to lower level. Coverage = net reduction in demand L1D load MPKI versus baseline. Degree is its final value, not a time average. Results include exact instruction/cycle ratios and raw prefetch counters. Per-run logs and JSON records preserve parameters, binary hash, trace metadata, and duration.

Plots: plots/ranking.png, plots/per-trace-speedup.png, plots/tradeoffs.png (PDF copies also available).

Geometric means across traces:

| Scheme | IPC gain | L1D MPKI | Coverage | Simulator accuracy | Issued requests |
|---|---:|---:|---:|---:|---:|
| IP-stride | +0.188% | 7.6696 | 2.12% | 31.82% | 208941 |
| Default SPP | +0.208% | 7.7580 | 1.60% | 55.46% | 81446 |
| Tuned SPP | +0.604% | 7.4474 | 5.12% | 44.51% | 449457 |
