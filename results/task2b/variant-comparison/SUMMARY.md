# Dynamic controller experiments

All variants use 32 permanent RRIP leaders, 4096-observation windows, five thresholds, and the fixed Task 2A I-RRIP configuration. Every full run uses 25M warmup + 25M measured instructions.

1. **Start RRIP:** original controller; every window selects I-RRIP iff the score exceeds the threshold.
2. **Start I-RRIP:** only initialization changes; all later decisions are identical in definition to the original controller.
3. **Persistent evidence:** starts in I-RRIP, requires two consecutive below-threshold windows with misses to select RRIP, and returns to I-RRIP after one above-threshold window. No-miss or equality windows retain mode and break the low-score streak.

## Best threshold for each method

| Method | Best threshold | Speedup vs LRU | IPC change vs static I-RRIP |
| --- | ---: | ---: | ---: |
| Start RRIP | 0.10 | 1.018020 (+1.802%) | -0.0413% |
| Start I-RRIP | 0.10 | 1.017787 (+1.779%) | -0.0642% |
| Start I-RRIP + persistent evidence | 0.10, 0.25, 0.50 | 1.017711 (+1.771%) | -0.0716% |

Selected static I-RRIP speedup vs LRU: **1.018441 (+1.844%)**.

## Matched-threshold comparisons

These ratios isolate the two changes at the same threshold rather than comparing separately selected winners.

| Threshold | Start I-RRIP vs original | Persistence vs initial-only |
| --- | ---: | ---: |
| 0.10 | -0.0229% | -0.0075% |
| 0.25 | -0.0165% | +0.2336% |
| 0.50 | -0.0131% | +0.2318% |
| 0.75 | -0.0411% | +0.1968% |
| 0.90 | -0.0122% | -0.0036% |

## Conclusion

The best dynamic result is original at threshold 0.10, with -0.0413% IPC relative to selected static I-RRIP. None of these dynamic variants beats selected static I-RRIP on the geometric mean.

Comparison IPC is computed from exact retired-instruction and cycle counts, avoiding the simulator output’s six-digit IPC rounding. All decision windows were independently checked against their controller rules. Original results were retained; the two new sweeps ran sequentially. Different warmup behavior can affect ROI results even when ROI mode fractions match.
