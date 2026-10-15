SPP checks and configuration
============================

Run the actual prefetcher with a stubbed request sink:

    c++ -std=c++11 -O2 -Iinc tests/test_spp.cc -o /tmp/test_spp
    /tmp/test_spp

Build the simulator:

    ./build_champsim.sh spp lru task1-spp

Parameters (environment variables, read at initialization):

| Variable | Default | Allowed |
|---|---:|---|
| SPP_UNIFORM_CONF | 4 | 1–7 |
| SPP_PATTERN_CONF | 2 | 1–3 |
| SPP_ACCURACY_LOW | 25 | 1–99 |
| SPP_ACCURACY_MID | 50 | 1–99 |
| SPP_ACCURACY_HIGH | 75 | 1–100 |

Accuracy boundaries must strictly increase. Confidence counts observations,
including the first occurrence. Pattern confidence saturates at three; a wrong
successor decrements confidence, and a subsequent observation replaces the
successor once confidence is zero. Uniform confidence counts consecutive equal
nonzero strides and saturates at seven. A mismatch immediately disables the old
uniform prediction. Nonuniform training continues in uniform mode.

The 64-entry IP table is 16 sets × 4 ways, with LRU replacement and full IP tags.
The 256-entry pattern table is direct mapped, with full (IP, history) tags.
Four signed seven-bit strides form a 28-bit history. Strides outside [-63,63]
reset history and uniform confidence. Zero strides leave predictor history alone.
Prediction uses only demand LOADs, targets L1, and stops at the current virtual
page boundary, an unknown context, or a rejected request. Speculative history
never modifies learned demand history.

Degree starts at two and is recomputed every 4096 demand accesses after at least
128 simulator-issued prefetches. The cumulative simulator ratio pf_useful / pf_issued
selects degrees 1, 2, 4, 8 at the three configured boundaries. Simulator counters
reset at ROI entry; predictor state and degree carry across warmup. This initial
controller intentionally uses cumulative feedback rather than short windows with
unmatched delayed hits. It can adapt slowly after a workload phase change.
Simulator pf_issued counts accepted calls to prefetch_line, including requests
that may later merge; these are the same accounting semantics as reported stats.

Logical table storage per core, assuming 64-bit addresses and 64-byte lines:

| Entry | Fields (bits) | Count | Total bits |
|---|---|---:|---:|
| IP | valid 1 + IP 64 + last line 58 + stride 7 + uniform confidence 3 + history length 3 + LRU rank 2 + history 28 | 64 | 10624 |
| Pattern | valid 1 + IP 64 + history 28 + stride 7 + confidence 2 | 256 | 26112 |

Tables total 36736 bits = 4592 bytes. Controller state adds a 12-bit access
counter and four-bit degree; configuration adds 26 bits (3 + 2 + 3×7).
Two 64-bit diagnostic prediction counters add 128 bits. Existing cache accuracy
counters are reused, not duplicated. C++ structs use ordinary integer fields and
padding rather than packed hardware fields; their host allocation is larger than
this logical storage estimate.

Tests check exact constant/negative/repeating-sequence predictions, same-line
accesses, immediate uniform break, page boundaries, prefetch-training exclusion,
IP separation, large-stride reset, and all accuracy bands. Trace smoke runs are
integration checks, not substitutes for the required 25M + 25M evaluation.

Full three-policy comparison
----------------------------

    ./build_champsim.sh ip_stride lru task1-ip-stride
    python3 scripts/compare_task1.py
    MPLCONFIGDIR=.cache/matplotlib XDG_CACHE_HOME=.cache .venv/bin/python scripts/plot_task1_comparison.py

The comparison reuses completed SPP and no-prefetch runs and runs/resumes the
three IP-stride traces with three workers. Output: results/task1/comparison.
It reports both the simulator's accuracy (useful / sent to lower level) and the
initial SPP controller's ratio (useful / all issued requests). These are different
metrics; the earlier full/results.csv column prefetch_accuracy is the latter.

Aggressiveness sweep
--------------------

    python3 scripts/sweep_task1.py --jobs 4
    MPLCONFIGDIR=.cache/matplotlib XDG_CACHE_HOME=.cache .venv/bin/python scripts/plot_task1_sweep.py

This runs 12 configurations (36 full simulations): uniform confidence 2/4,
pattern confidence 1/2, and accuracy boundaries 25/50/75, 3/6/12, 1/2/4 percent.
Only these existing environment parameters change. The degree schedule remains
1/2/4/8, and boundaries apply to useful/all-issued rather than printed simulator
accuracy. Source defaults are retained. Four workers run independent processes;
results and completed rankings are checkpointed after each run. Matching binary,
trace metadata, parameter and instruction-count signatures permit resuming.

The sweep uses the explicitly recorded GCC 7 SPP binary; compiler
identity is in results/task1/sweep/experiment.json. Existing default-SPP, IP-stride,
and no-prefetch runs serve as references.

Comparison sanity and storage accounting
-----------------------------------------

    python3 scripts/check_task1.py

The standalone evaluation, IP-stride comparison, and SPP sweep now reject logs
unless BTB, ITLB, DTLB, STLB, L1I, L1D, L2C and LLC all report LRU. Task 3 remains
an explicitly separate mixed-policy experiment. The audit covers all completed
Task 1 logs and their no-prefetch reference logs, validates run counts, and checks
that Task 3 logs are rejected by the same guard. Results: results/task1/sanity-check.json.

See results/task1/STORAGE.md for the full per-field logical bit budget, separate
controller/configuration/counter costs, IP-stride comparison, assumptions about
persistent state versus temporary sentinels, and measured C++ allocation sizes.
