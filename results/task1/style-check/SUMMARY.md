SPP style rewrite verification
==============================

The prefetcher now follows the supplied IP-stride structure: named IP_TRACKER
and STRIDE_PATTERN classes, last_cl_addr/last_stride/lru fields, explicit indexed
tracker lookup and replacement, signed stride calculation, and a prefetch loop
using pf_address. Comments explain the extra pattern-training and throttling
steps. Parameters, table dimensions, signatures, confidence transitions, LRU
behavior, page checks, destination, request order, and printed statistics are
preserved. Test references were renamed to match the clearer field names.

Validation:

- Existing exact sequence tests pass, including AddressSanitizer and UBSan.
- A temporary before/after differential harness ran 200,000 mixed accesses per
  configuration across all 12 sweep configurations. Digests of request streams,
  final predictor tables, confidence/controller state, and counters match across
  all 2.4 million accesses. See differential.json for source hashes and digests.
- All three real traces were rerun with selected SPP parameters (uniform 2,
  pattern 1, accuracy 1/2/4 percent), LRU, 25M warmup + 25M measured instructions.
  Every parsed metric and cache access/hit/miss counter matches the prior sweep
  exactly. See full-trace-check.json and the three logs.

Validation uses GCC 7, consistent with the existing experiments.
