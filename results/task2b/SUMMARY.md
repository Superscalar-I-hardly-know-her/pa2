# Task 2B results

All 15 runs completed with 25M warmup and 25M measured instructions, prefetching disabled.

The controller uses 32 permanent SRRIP leader sets and resets its four counters after every 4096 leader demand-load observations. Followers select the fixed Task 2A I-RRIP when the instruction share of load misses exceeds the threshold.

| Threshold | Geometric-mean speedup vs LRU | Change vs LRU |
| --- | ---: | ---: |
| 0.10 | 1.018020 | +1.802% |
| 0.25 | 1.015506 | +1.551% |
| 0.50 | 1.015490 | +1.549% |
| 0.75 | 1.008898 | +0.890% |
| 0.90 | 1.001100 | +0.110% |

Best tested threshold: **0.10**. Its geometric-mean speedup is 1.018020, compared with 1.018440 for selected static I-RRIP. Dynamic I-RRIP is approximately 0.041% slower than the selected static policy on this suite.

| Trace | IPC | Speedup vs LRU | L2 load MPKI | Instruction MPKI | Data MPKI | Follower ROI I-RRIP use |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Trace1-003 | 0.232639 | 1.003498 | 18.85510 | 8.92980 | 9.92532 | 100.0% |
| Trace2-001 | 0.262642 | 1.044161 | 20.11370 | 8.00104 | 12.11260 | 100.0% |
| Trace3-002 | 0.384481 | 1.006895 | 3.90320 | 0.63744 | 3.26576 | 100.0% |

## What the sensitivity study shows

Thresholds 0.10, 0.25, and 0.50 make identical decisions on Trace 1; 0.75 and 0.90 remain in SRRIP and exactly match its cycles. On Trace 2, lower thresholds retain instruction protection for more of the measured region and improve IPC. Identical points in portions of the curves reflect identical decisions, rather than unused parameters.

At threshold 0.10, followers use I-RRIP throughout the ROI on all three traces. The remaining differences from static I-RRIP are its learning history during warmup and the 32 sets permanently reserved for SRRIP. This simple heuristic did not beat the tuned static policy; we retain that result rather than tuning additional parameters.

The default threshold remains 0.25; reproduce the best tested configuration with `DYN_IRRIP_THRESHOLD=0.10`.

## Validation

- Deterministic tests cover leader placement, permanent leader behavior, threshold equality, counter resets, zero misses, ignored request types, and switches in both directions.
- 4000 independent randomized victim/aging checks cover leaders and followers in both modes.
- 1M + 1M forced-SRRIP runs match standalone SRRIP exactly on all three traces.
- Every full-run decision window was checked for counts, computed miss share, threshold decision, and switch accounting.
- Logs, machine-readable results, rankings, and PNG/PDF plots are retained under this directory.
