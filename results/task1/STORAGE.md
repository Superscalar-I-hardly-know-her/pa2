Prefetcher storage overhead
==========================

The counts below describe the implemented policies with 64-bit addresses and
64-byte cache lines. They separate compact logical hardware state from the
ordinary C++ integers/padding used by the simulator. Parameters selected by the
sweep change values, not table sizes. No cache replacement metadata is charged
to either standalone prefetcher: both comparisons retain the same LRU policy.

SPP IP table: 64 entries (16 sets × 4 ways)
-----------------------------------------

| Field | Bits per entry | Reason |
|---|---:|---|
| Valid | 1 | Allocated/unallocated |
| IP tag | 64 | Full, unmasked instruction pointer |
| Last cache-line address | 58 | 64-bit byte address shifted right by 6 |
| Last stride | 7 | Signed strides from −63 through +63; zero represents reset |
| Uniform confidence | 3 | Saturates at 7 |
| Stride-history signature | 28 | Four seven-bit signed stride encodings |
| History length | 3 | Values 0 through 4 |
| LRU rank | 2 | Four ways, persistent ranks 0 through 3 |
| **Total** | **166** | **64 × 166 = 10624 bits = 1328 bytes** |

The allocation code temporarily uses rank 4 before immediately updating ranks
and setting the new tracker to rank 0. The two-bit rank budget describes state
between demand accesses; rank 4 can be an allocation control signal. A literal
hardware translation that stores that intermediate sentinel needs three rank
bits instead, adding 64 bits to the table. No separate tag for the set is needed:
the set is selected by the existing IP hash. The full IP is retained as in code,
without assuming tag compression.

SPP pattern table: 256 direct-mapped entries
-------------------------------------------

| Field | Bits per entry | Reason |
|---|---:|---|
| Valid | 1 | Entry allocated |
| IP tag | 64 | Distinguishes different instructions |
| Signature tag | 28 | Distinguishes their four-stride contexts |
| Predicted next stride | 7 | Same signed stride range |
| Confidence | 2 | Values 0 through 3 |
| **Total** | **102** | **256 × 102 = 26112 bits = 3264 bytes** |

Direct mapping needs no replacement ranks. Index hashing does not remove the
stored tags in this accounting. Temporary lookahead copies use the same
signature representation and do not add persistent table entries.

SPP controller, configuration, and counters
------------------------------------------

| State | Bits | Reason |
|---|---:|---|
| Demand access interval counter | 12 | Persistent values 0..4095, then reset at the next update |
| Current prefetch degree | 4 | Literal values 1, 2, 4, 8 |
| Uniform threshold | 3 | Configurable 1..7 |
| Pattern threshold | 2 | Configurable 1..3 |
| Three accuracy boundaries | 21 | Three seven-bit percentages, each at most 100 |
| **Controller + configuration** | **42** | **16 + 26 bits** |

The counter's comparison with 4096 can use an increment carry; retaining the
intermediate value 4096 in a register would require 13 counter bits instead.
An encoded degree needs only two bits, but this budget retains the actual
numeric degree values. Fixed constants such as table dimensions and masks are
hardwired and need no configuration registers. The division/comparison logic,
ports and combinational address/hash arithmetic are logic cost, not table bits.

The implementation reuses the cache's two existing 64-bit counters, pf_issued
and pf_useful, for accuracy; it allocates no private copy. If a hardware design
does not already expose these counters, add **128 bits** for them. Their width
matches the code and accommodates cumulative feedback. Narrower or windowed
counters would be a different implementation. The two 64-bit uniform/pattern
prediction counters are diagnostic only and add another **128 bits** if retained.

| SPP budget | Bits | Bytes (rounded up only at the total) |
|---|---:|---:|
| Predictor tables only | 36736 | 4592 |
| Tables + controller + programmable configuration | 36778 | 4598 |
| Above + private accuracy counters, if required | 36906 | 4614 |
| Above + both diagnostic prediction counters | 37034 | 4630 |

Thus the implemented predictor needs approximately **4.49 KiB** of compact
operational storage with the existing accuracy counters. If parameters are
hardwired after selection, the 26 configuration bits can also be omitted.
Existing cache prefetch/useful bits, cache arrays, queues, MSHRs, and LRU state
are shared simulator infrastructure and are excluded consistently for both
prefetchers. This is a storage estimate, not a hardware area/timing estimate.

Supplied IP-stride
------------------

| Field | Logical bits per entry | Reason |
|---|---:|---|
| IP identifier | 8 | Code masks IP with 0xFF before storing/comparing |
| Last cache-line address | 58 | 64-bit address shifted right by 6 |
| Last stride | 59 | Signed difference of two 58-bit line addresses |
| LRU rank | 5 | Values 0..23 for 24 fully associative trackers |
| **Total** | **130** | **24 × 130 = 3120 bits = 390 bytes** |

No valid bit or confidence counter is implemented in the supplied IP-stride
tracker; initialization uses IP zero. Its degree 3 and IP mask are constants.
Keeping a literal 64-bit stride rather than its sufficient 59-bit representation
raises the compact count to 135 bits/entry, **3240 bits = 405 bytes**. The compact
SPP tables are about **11.77×** the size of the compact IP-stride table, reflecting
more IP trackers, full IP tags, and a separate context-to-stride table. This
comparison does not claim equal storage budgets or isolate each algorithm's
benefit at equal capacity.

Measured C++ host allocations on this Mac
----------------------------------------

Measured by compiling probes that include the actual prefetcher source:

| Allocation | SPP | IP-stride |
|---|---:|---:|
| sizeof(IP_TRACKER) | 48 bytes | 32 bytes |
| IP table | 3072 bytes | 768 bytes |
| Pattern entries | 32 bytes × 256 = 8192 bytes | None |
| Controller globals | 8 bytes | None |
| Configuration globals | 20 bytes | Constants |
| Diagnostic counters | 16 bytes | None |
| **Sum of prefetcher object sizes** | **11308 bytes** | **768 bytes** |

These sums exclude linker-section padding, stack temporaries and the shared
CACHE object. The simulator allocates full uint64_t/int/unsigned fields and ABI
padding; it does not pack the logical bit fields. Host sizes are separate from
the compact hardware budget. Raw measurements and arithmetic are saved in
storage-overhead.json.
