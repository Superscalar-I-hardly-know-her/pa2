Task 3: fixed SPP + dynamic I-RRIP
=================================

All runs: 25M warmup + 25M measured instructions. Native Apple Clang; GCC 7 validation remains outstanding. SPP uses uniform confidence 2, pattern confidence 1, accuracy boundaries 1/2/4 percent. Dynamic I-RRIP uses the original controller at threshold 0.10 (the best measured Task 2B variant). No joint tuning is performed.

The plain combination is an ablation. The Task 3 prefetch-aware version inserts follower data prefetches at RRPV 3, and leaves RRPV unchanged on data-prefetch hits. Demand reuse promotes according to the existing I-RRIP/RRIP mode. RRIP leaders retain their ordinary insertion and promotion rules; only demand LOADs train the controller. DYN_IRRIP_PREFETCH=1 enables this rule; default 0 preserves Task 2 behavior.

| Trace | Scheme | IPC | Gain vs baseline | Vs SPP | Vs dynamic | L1D MPKI | L2 MPKI | L2 instruction MPKI | L2 data MPKI | Coverage | Accuracy |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Trace1-003 | none | 0.231828 | +0.000% | -0.628% | -0.349% | 10.6784 | 17.7239 | 10.3634 | 7.3605 | 0.00% | — |
| Trace1-003 | spp | 0.233293 | +0.632% | +0.000% | +0.281% | 9.7858 | 17.0066 | 10.4292 | 6.5774 | 8.36% | 56.20% |
| Trace1-003 | dynamic | 0.232639 | +0.350% | -0.280% | +0.000% | 10.6795 | 18.8551 | 8.9298 | 9.9253 | -0.01% | — |
| Trace1-003 | combined-plain | 0.234663 | +1.223% | +0.587% | +0.870% | 9.7962 | 17.9409 | 8.9396 | 9.0014 | 8.26% | 55.98% |
| Trace1-003 | combined-aware | 0.234726 | +1.250% | +0.614% | +0.897% | 9.7967 | 17.9175 | 8.9158 | 9.0017 | 8.26% | 55.93% |
| Trace2-001 | none | 0.251534 | +0.000% | -0.515% | -4.229% | 13.5367 | 27.3732 | 18.8087 | 8.5645 | 0.00% | — |
| Trace2-001 | spp | 0.252836 | +0.517% | +0.000% | -3.734% | 13.1580 | 27.3677 | 19.1646 | 8.2032 | 2.80% | 49.78% |
| Trace2-001 | dynamic | 0.262642 | +4.416% | +3.879% | +0.000% | 13.5513 | 20.1137 | 8.0010 | 12.1126 | -0.11% | — |
| Trace2-001 | combined-plain | 0.264147 | +5.014% | +4.474% | +0.573% | 13.1775 | 19.9976 | 8.2581 | 11.7395 | 2.65% | 49.71% |
| Trace2-001 | combined-aware | 0.264207 | +5.038% | +4.498% | +0.596% | 13.1780 | 19.9921 | 8.2554 | 11.7366 | 2.65% | 49.65% |
| Trace3-002 | none | 0.381848 | +0.000% | -0.660% | -0.685% | 3.4036 | 3.9545 | 1.1189 | 2.8356 | 0.00% | — |
| Trace3-002 | spp | 0.384384 | +0.664% | +0.000% | -0.025% | 3.2080 | 3.6612 | 1.1321 | 2.5291 | 5.75% | 31.51% |
| Trace3-002 | dynamic | 0.384481 | +0.690% | +0.025% | +0.000% | 3.4042 | 3.9032 | 0.6374 | 3.2658 | -0.02% | — |
| Trace3-002 | combined-plain | 0.387203 | +1.403% | +0.733% | +0.708% | 3.2150 | 3.5920 | 0.6362 | 2.9558 | 5.54% | 30.96% |
| Trace3-002 | combined-aware | 0.387198 | +1.401% | +0.732% | +0.707% | 3.2148 | 3.5936 | 0.6390 | 2.9546 | 5.55% | 31.04% |

Geometric means:

| Scheme | Gain vs baseline | Vs SPP | Vs dynamic | L1D MPKI | L2 MPKI |
|---|---:|---:|---:|---:|---:|
| none | +0.000% | -0.601% | -1.770% | 7.8944 | 12.4258 |
| spp | +0.604% | +0.000% | -1.176% | 7.4474 | 11.9443 |
| dynamic | +1.802% | +1.190% | +0.000% | 7.8979 | 11.3967 |
| combined-plain | +2.532% | +1.916% | +0.717% | 7.4592 | 10.8822 |
| combined-aware | +2.548% | +1.932% | +0.733% | 7.4592 | 10.8782 |

Rationale: speculative data has not demonstrated demand reuse, so it receives little retention priority and repeated speculative hits cannot protect it. Demand reuse restores the usual priority. This can reduce competition with instructions and proven demand data, but may evict useful prefetches too early. This simple choice is evaluated once, without retuning either component.

Accuracy = useful / prefetches sent to lower level, matching printed simulator accuracy; useful / all-issued is separately retained in results.csv. Coverage = net L1D demand miss reduction against no-prefetch LRU. coverage_vs_dynamic also measures incremental reduction against no-prefetch dynamic I-RRIP. Standalone references reuse their completed runs. Individual logs and JSON files record all controller windows and prefetch-awareness callback counts.
