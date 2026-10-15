# I-RRIP event audit

The original 10K + 10K smoke runs completed successfully, but every configuration
had identical statistics within each trace. Those runs alone did not establish
that the eviction preferences were exercised.

A temporary instrumented build of the actual I-RRIP policy recorded every L2
replacement update and victim selection during 250K warmup + 250K measured
instructions. All 30 configurations were checked on all three traces.
Instrumentation was compiled into a separate binary; the running full sweep
and its binaries were unchanged.

An independent model reconstructed every resident line's valid bit, instruction
classification, and RRPV. It calculated aging directly as `3 - max(RRPV)` and
checked victim selection, way-order ties, insertion, promotion, and instruction
classification against the recorded events. It did not call the production
victim selector to generate expected answers.

**All 90 audits passed: 2,826,586 events, including 475,620 full-set evictions,
with zero mismatches.** See `summary.csv` for per-configuration counts,
`examples.json` for actual eviction snapshots, and `audit.json` for provenance.
The counts sum across configurations; the same input accesses are intentionally
repeated under different policies.

## Exact examples

For the default configuration (instruction insertion 1, data hits 1, bias 0),
Trace 2 event 7040 had these ways in order:

```
Before: I1 D2 D2 I1 I1 I1 D2 I1
Aged:   I2 D3 D3 I2 I2 I2 D3 I2
Victim: way 1 (first data line at RRPV 3)
```

At event 12270, old instructions correctly lost to younger data:

```
Before: I0 I1 I1 I0 I2 D1 I2 D1
Aged:   I1 I2 I2 I1 I3 D2 I3 D2
Victim: way 4 (instruction at RRPV 3; data is only at 2)
```

## Mixed instruction/data sequence

A constructed trace first executed at address 0x400000 and read 0x500000 as
data, later executed at 0x500000 while accessing 16 conflicting L1D lines,
and finally read 0x500000 as data again. The real cache handlers produced:

| Event | Access to L2 set 896, way 0 | Classification after access | RRPV |
| --- | --- | --- | --- |
| 6 | Data fill | Data | 2 |
| 7 | Instruction hit | Instruction | 0 |
| 256 | Subsequent data hit | Instruction | 0 |

This verifies the actual hit path sets the instruction bit when a data line
becomes code and does not clear it on a later data access. Raw events are in
`mixed-use-events.log`; U records contain set, way, request type, hit flag,
incoming instruction flag, resident instruction flag, and RRPV before/after.
On fills the logged resident flag still belongs to the victim, before fill_cache.

## Repeat the event audit

After building the simulator, run `python3 -B tests/audit_irrip.py` from the
repository. It links a temporary instrumented policy against the existing
simulator objects and checks all 90 configurations without changing production
sources or binaries. The mixed-use check above was run separately using the
constructed three-phase trace; it is not part of that script.
