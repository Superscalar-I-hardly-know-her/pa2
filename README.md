# ChampSim

ChampSim is a trace-based simulator for microarchitecture research.

Useful trace links:
- Traces (access requires an LDAP ID): https://drive.google.com/drive/folders/1zYchkn-M1auZp_l5wRkIzAcDYPkNtW3H?usp=sharing
- ChampSim wiki: https://champsim.github.io/ChampSim/master/index.html

## Clone the repository

```bash
git clone https://github.com/cs683-iitb-autumn-2026/pa2.git
```

## Compile

To compile ChampSim, specify three parameters: the L1D prefetcher, the L2C replacement policy, and the binary name.

For example, `./build_champsim.sh no lru baseline` builds a single-core processor with a hashed perceptron branch predictor, no L1D data prefetcher, and the LRU replacement policy for the L2C.

You can give the binary any name. Custom names help distinguish binaries that use the same configuration.

```bash
./build_champsim.sh ${L1D_PREFETCHER} ${L2C_REPLACEMENT} ${BINARY_NAME}

./build_champsim.sh no lru baseline
```

## Run simulation

```bash
./bin/[BINARY] -warmup_instructions [N_WARM] -simulation_instructions [N_SIM] -traces [TRACE_DIR]/[TRACE]
./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ../traces/trace1.champsimtrace.xz
```

Where:
- `${BINARY}`: ChampSim binary compiled by `build_champsim.sh` (for example, `hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline`)
- `${N_WARM}`: number of instructions for the warmup period (25 million)
- `${N_SIM}`: number of instructions for the detailed simulation (25 million)
- `${TRACE_DIR}`: directory containing the trace (for example, `../traces/`)
- `${TRACE}`: name of the trace (for example, `trace1.champsimtrace.xz`)

## Evaluate the simulation

ChampSim measures IPC (instructions per cycle) as its main performance metric. It also prints other useful metrics at the end of each simulation.

## Compiler selection

The setup below specifies GNU GCC/G++ 7. Native macOS experiments so far used
Apple Clang, including the Task 1 baseline, SPP, IP-stride and Task 2 runs;
they have not been validated against GCC 7. The currently selected compiler is
Apple Clang 21.0.0. `/usr/bin/g++` on this Mac is Clang.
Homebrew GCC 16.1.0 is installed, but is also a different version from GCC 7.

The build now prints its compiler and saves its version beside the binary in
`bin/*.compiler.txt`. To require the README's version on a GCC 7 installation:

```bash
CXX=g++-7 CHAMPSIM_REQUIRE_GCC7=1 ./build_champsim.sh spp lru task1-spp-gcc7
```

The check runs before source/configuration changes and rejects Clang and other
GCC major versions. Repeat for `no lru`, `ip_stride lru`, `no irrip`, and
`no dyn_irrip` as needed. Native development builds remain available without the
strict flag. Comparisons under GCC 7 must use GCC 7 for both baseline and policy;
existing Clang results should retain their compiler provenance.

## Install GCC 7 on Ubuntu

```bash
sudo apt update
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
vim /etc/apt/sources.list
```

Update the last line with:

```bash
deb [arch=amd64] http://archive.ubuntu.com/ubuntu focal main universe
```

Then run:

```bash
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
sudo apt-get install gcc-7
sudo apt-get install g++-7
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-7 0
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-7 0
```

If GCC and G++ are already present in `/usr/bin`, configure the alternatives using:

```bash
sudo update-alternatives --config g++
sudo update-alternatives --config gcc
```


## Task 2A: parameterized I-RRIP

Build with `./build_champsim.sh no irrip task2-irrip`. On macOS the Makefile
uses dynamic linking; Linux retains the original static-link default.

The selected Task 2A configuration is instruction insertion 2, data-hit RRPV 1,
and instruction-aware eviction with bias 2. It achieved 1.844% geometric-mean
speedup over LRU across the three traces, tied with bias 3 at the reported IPC
precision. Bias 2 retains less aggressive instruction protection. The completed
sweep remains in `results/task2/full/`; `results/task2/selected-config.json`
records the selection.

The policy uses those values by default and reads these optional environment
overrides once at initialization:

| Variable | Default | Values |
| --- | --- | --- |
| `IRRIP_INSERT` | 2 | Instruction insertion RRPV: 0, 1, or 2 |
| `IRRIP_DATA_HIT` | 1 | Data hit RRPV: 0 or 1 |
| `IRRIP_AWARE` | 1 | Instruction-aware eviction: 0 or 1 |
| `IRRIP_BIAS` | 2 | Eviction bias: 0 through 3; ignored when awareness is off |

Data fills enter at RRPV 2; instruction hits promote to 0. A resident line
becomes an instruction line on an instruction access and retains that status
until replacement. Translation requests do not mark lines as instructions.
Like the supplied SRRIP, the policy updates RRPV on every hit, including writebacks.

Victim selection uses invalid ways first. Otherwise, age all RRPVs until at
least one reaches 3. With instruction-aware eviction, select the data line
with the largest RRPV if it reaches `3 - bias`; otherwise select the first
RRPV-3 line. Equal candidates use way order. Bias 0 only breaks distant-line
ties; bias 3 always chooses data when present and can retain stale instructions.
With awareness off, choose the first RRPV-3 line without considering type.
`INSERT=2`, `DATA_HIT=0`, and `AWARE=0` reproduce ordinary SRRIP.

Run the policy tests and the trace smoke tests:

```bash
c++ -std=c++11 -O2 -Iinc tests/test_irrip.cc -o /tmp/test_irrip
/tmp/test_irrip
python3 scripts/sweep_task2.py --smoke --build
```

Run the full sweep:

```bash
python3 scripts/sweep_task2.py --jobs 4
```

The runner creates `.gz`/`.xz` symlinks for extensionless compressed traces.
It runs with prefetching disabled and up to `--jobs` concurrent simulations
(default 1): 30 distinct I-RRIP
configurations plus LRU on each trace. Full runs use 25M warmup + 25M measured
instructions; smoke runs use 10K + 10K and also compare against standalone
SRRIP. Each simulation has its own log and process environment; the main thread
writes the summary tables. Builds remain sequential. Do not run two copies of
the runner simultaneously.

Results go to `results/task2/full/` or `results/task2/smoke/`: raw logs,
per-run configuration and binary hashes, `results.csv`, and `ranking.csv`.
Speedup is relative to LRU on the same trace; rankings use geometric-mean
speedup across every trace. Instruction/data MPKI refer to L2 **LOAD** misses,
excluding RFO, writeback, and translation requests. Smoke rankings are only
for checking the pipeline, not selecting the final policy.

Rerunning resumes successful runs with matching binary, trace, and instruction
counts. Failures are recorded and retried on the next invocation. Use `--build`
after changing C++ sources; use `--traces-dir` or `--output` for alternate paths.
Traces, compressed archives, and build outputs are ignored by Git.

### Plot Task 2A results

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-plot.txt
.venv/bin/python scripts/plot_task2.py
```

Rerun the last command while the sweep progresses or after it finishes. It reads
a snapshot of completed results and exports PNG and PDF figures to
`results/task2/plots/`:

- `policy_comparison`: IPC, speedup, and the three L2 load MPKI metrics for LRU,
  SRRIP, the selected I-RRIP, and the suite winner once the sweep is complete.
- `<trace>_bias`: eviction-bias sensitivity, with insertion value shown by color
  and data-hit promotion by line style. Missing points are pending runs.
- `<trace>_tradeoff`: instruction MPKI versus data MPKI, colored by IPC change
  relative to LRU. Lower values on both axes are better.
- `suite_ranking`: geometric-mean speedup for configurations completed on all
  three traces. It appears once at least one configuration qualifies.

Every figure states how many runs are complete. The script saves `snapshot.csv`
with the exact data used for that set of plots. Configuration IDs use
`i<insertion>-h<data hit>-a<aware eviction>-b<bias>`. Optional `--input` and
`--output` arguments select a different CSV and figure directory.

## Task 2B: Dynamic I-RRIP

`replacement/dyn_irrip.l2c_repl` switches followers between ordinary SRRIP and
our selected static I-RRIP (insertion 2, data hit 1, bias 2). Exactly 32 of
1024 sets permanently use SRRIP: set `33*k`, for `k = 0..31`. This gives one
leader per group of 32 sets with a different offset in each group. The other
992 sets follow one global mode bit, initially SRRIP.

Leader demand LOAD hits and completed miss fills train four counters:
instruction/data accesses and instruction/data misses. Translation, prefetch,
RFO, and writeback requests do not train the controller. Classification uses
the incoming request, rather than the resident line's sticky instruction bit.
Merged requests share a fill observation, consistent with the simulator's load
miss statistics. Leaders occupy 3.125% of sets and remain on SRRIP in both modes.

After every 4096 observations, compute `instruction_misses / total_load_misses`.
Use I-RRIP when this is strictly greater than `DYN_IRRIP_THRESHOLD` (default
0.25); otherwise use SRRIP. A window without misses selects SRRIP. Reset all
four counters after each decision. Learning starts during warmup and continues
across the ROI boundary; neither mode switches nor ROI entry flush resident
metadata or discard a partial observation window. The decision applies after
the observation completing its window.

`DYN_WINDOW` log entries record the window counts, score, mode, and phase.
`DYN_SUMMARY` records decision/switch counts across warmup and ROI, pending
window counts, and the number of follower ROI loads handled in each mode.
The simulator now also invokes L2 replacement final statistics for single-core
runs; previously that callback was only invoked for multicore runs.

```bash
c++ -std=c++11 -O2 -Iinc tests/test_dyn_irrip.cc -o /tmp/test_dyn_irrip
/tmp/test_dyn_irrip
python3 scripts/sweep_task2b.py --smoke --jobs 4
python3 scripts/sweep_task2b.py --jobs 4
.venv/bin/python scripts/plot_task2b.py
```

The sweep evaluates thresholds 0.10, 0.25, 0.50, 0.75, and 0.90: 15 full runs,
with 25M warmup + 25M measured instructions and no prefetching. It reuses the
completed Task 2A LRU, SRRIP, and selected static I-RRIP baselines; these did not
change. It saves logs/records and comparative CSVs under `results/task2b/full/`,
validates every window's arithmetic/mode selection, and resumes matching
successful runs. Use `--build` after C++ changes. The 1M + 1M smoke test adds
threshold 1 (forced SRRIP) and compares it against standalone SRRIP on every
trace. Such short runs need not accumulate a full decision window; deterministic
unit tests exercise threshold boundaries, resets, and switches in both directions.

Plots under `results/task2b/plots/` show threshold sensitivity, comparison with
static baselines, and actual controller decisions. The suite-wide threshold
ranking uses geometric-mean speedup versus LRU.

### I-RRIP-first controller experiments

The two follow-up variants keep the leader mapping, 4096-observation windows,
and thresholds unchanged. Their results are separate from the original sweep.

```bash
python3 scripts/sweep_task2b.py --variant start-irrip --smoke --jobs 4
python3 scripts/sweep_task2b.py --variant start-irrip --jobs 4
python3 scripts/sweep_task2b.py --variant persistent --smoke --jobs 4
python3 scripts/sweep_task2b.py --variant persistent --jobs 4
.venv/bin/python scripts/plot_task2b.py --variant start-irrip
.venv/bin/python scripts/plot_task2b.py --variant persistent
.venv/bin/python scripts/compare_task2b_variants.py
```

`start-irrip` changes initialization only (`DYN_IRRIP_START=1`). It keeps the
original per-window rule, including selecting RRIP on equality or no misses.
`persistent` also sets `DYN_IRRIP_PERSIST=1`: leave I-RRIP only after two
consecutive windows with misses and score strictly below the threshold. Return
to I-RRIP after one above-threshold window. Equality and no-miss windows retain
the current mode and reset the streak. The mode remains global to followers;
leaders always use RRIP. `rrip_streak` in window logs records the evidence count.
Both flags default to 0, preserving the original controller unless requested.

Original results stay in `results/task2b/full/`; follow-up results go under
`results/task2b/start-irrip/` and `results/task2b/persistent/`. The runner retains
the original binary and builds a separate binary for the variants. The combined
report/figures under `results/task2b/variant-comparison/` compare each method's
best threshold and provide matched-threshold comparisons to isolate the changes.

## Task 3: fixed SPP + dynamic I-RRIP

The combination fixes SPP to the Task 1 sweep winner (uniform confidence 2,
pattern confidence 1, accuracy boundaries 1/2/4 percent) and dynamic I-RRIP to
the best measured Task 2B variant (original controller, threshold 0.10).
Neither component is retuned jointly.

`DYN_IRRIP_PREFETCH=1` adds one prefetch-aware rule in follower sets: data
PREFETCH fills enter at RRPV 3; PREFETCH hits leave the resident RRPV unchanged.
A later demand hit uses the existing mode's promotion rule. This gives
speculative data little retention until demand establishes reuse and prevents
repeated speculative requests from protecting a resident line. RRIP leaders
retain their existing rules. Prefetches never train the demand-only controller.
The flag defaults to zero, preserving Task 2 behavior. ROI prefetch-aware fill
and hit counts appear in `DYN_SUMMARY`.

```bash
./build_champsim.sh spp dyn_irrip task3-combined
c++ -std=c++11 -O2 -Iinc tests/test_dyn_irrip.cc -o /tmp/test_dyn_irrip
/tmp/test_dyn_irrip
python3 scripts/evaluate_task3.py
MPLCONFIGDIR=.cache/matplotlib XDG_CACHE_HOME=.cache .venv/bin/python scripts/plot_task3.py
```

The evaluation runs six simulations with up to four workers: plain combination
and prefetch-aware combination on each trace, at 25M warmup + 25M measured
instructions. It sets every selected parameter explicitly, validates controller
windows, records compiler/binary/trace provenance, and resumes matching runs.
No-prefetch LRU, selected standalone SPP, and selected standalone dynamic I-RRIP
references reuse their completed runs. `results/task3/` contains comparative
IPC/speedup, prefetch accuracy, coverage, L1D/L2/L2-instruction/L2-data LOAD MPKI,
raw counters, logs, and PNG/PDF plots. Native results use Clang; GCC 7 validation
remains a separate outstanding check.
