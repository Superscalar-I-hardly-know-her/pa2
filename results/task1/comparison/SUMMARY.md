Task 1 comparison
=================

25M warmup + 25M measured instructions per trace. LRU at all cache levels; only the L1D prefetcher changes. IP-stride is the supplied implementation unchanged (24 trackers, 8-bit IP identifier, fixed degree 3, L1/L2 destination based on MSHR occupancy). SPP uses its initial defaults. No-prefetch and SPP runs are reused.

| Trace | Scheme | IPC | IPC change | L1D LOAD MPKI | Coverage | Simulator accuracy | Useful / issued |
|---|---|---:|---:|---:|---:|---:|---:|
| Trace1-003 | none | 0.231828 | +0.000% | 10.6784 | 0.00% | — | — |
| Trace1-003 | ip_stride | 0.232842 | +0.437% | 10.1182 | 5.25% | 52.94% | 5.48% |
| Trace1-003 | spp | 0.232519 | +0.298% | 10.4034 | 2.58% | 63.91% | 8.73% |
| Trace2-001 | none | 0.251534 | +0.000% | 13.5367 | 0.00% | — | — |
| Trace2-001 | ip_stride | 0.251263 | -0.108% | 13.4385 | 0.73% | 37.88% | 2.86% |
| Trace2-001 | spp | 0.251884 | +0.139% | 13.4056 | 0.97% | 77.53% | 4.49% |
| Trace3-002 | none | 0.381848 | +0.000% | 3.4036 | 0.00% | — | — |
| Trace3-002 | ip_stride | 0.382742 | +0.234% | 3.3179 | 2.52% | 16.06% | 1.37% |
| Trace3-002 | spp | 0.382557 | +0.186% | 3.3480 | 1.63% | 34.43% | 1.93% |

Geometric mean speedup: none 1.000000x (+0.000%), ip_stride 1.001876x (+0.188%), spp 1.002076x (+0.208%).

Coverage = 1 − prefetcher demand L1D LOAD MPKI / baseline demand L1D LOAD MPKI (net miss reduction, including pollution effects). Simulator accuracy = useful / prefetches issued to lower level, matching the printed ChampSim ACCURACY statistic. Useful / issued uses all accepted prefetch requests, including redundant requests; this is the initial SPP throttling signal and the quantity previously labeled accuracy in full/results.csv. The two denominators must not be mixed. Baseline prefetch accuracy is undefined.

results.csv includes exact instruction/cycle IPC, L1D/L1I/L2/LLC load MPKI, coverage, both accuracy definitions, requested/issued/useful/unused/lower-level prefetch counts, timely/late/dropped counters, and L1D prefetch hit/miss counters. cache-statistics.csv includes every printed cache access type. all-printed-statistics.json preserves the remaining simulator output, including queues, DRAM, and printed latency counters. Raw logs remain at the referenced paths. Some printed diagnostics span warmup as well as ROI; they are preserved without treating them as ROI-normalized metrics.
