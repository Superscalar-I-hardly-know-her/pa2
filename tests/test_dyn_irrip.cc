#include "../replacement/dyn_irrip.l2c_repl"
#include "../replacement/base_replacement.cc"
uint8_t warmup_complete[NUM_CPUS] = {};

// The memory hierarchy is not exercised by this policy-only test.
int CACHE::add_rq(PACKET *) { std::abort(); }
int CACHE::add_wq(PACKET *) { std::abort(); }
int CACHE::add_pq(PACKET *) { std::abort(); }
void CACHE::return_data(PACKET *) { std::abort(); }
void CACHE::operate() { std::abort(); }
void CACHE::increment_WQ_FULL(uint64_t) { std::abort(); }
uint32_t CACHE::get_occupancy(uint8_t, uint64_t) { std::abort(); }
uint32_t CACHE::get_size(uint8_t, uint64_t) { std::abort(); }

int main()
{
    CACHE cache("test", L2C_SET, L2C_WAY, L2C_SET*L2C_WAY, 1, 1, 1, 1);
    unsetenv("DYN_IRRIP_PREFETCH");
    unsetenv("DYN_IRRIP_START");
    unsetenv("DYN_IRRIP_PERSIST");
    cache.l2c_initialize_replacement();
    unsigned count = 0;
    for (unsigned group = 0; group < 32; ++group) {
        unsigned per_group = 0;
        for (unsigned set = group*32; set < (group+1)*32; ++set)
            per_group += leader(set);
        assert(per_group == 1);
        count += per_group;
    }
    assert(count == 32 && !prioritize_instructions);
    auto update = [&](unsigned set, unsigned type, bool hit, bool instruction) {
        cache.l2c_update_replacement_state(0, set, 0, 0, 0, 0, type, hit, instruction);
    };
    auto fill_window = [&](unsigned i_miss, unsigned d_miss) {
        for (unsigned i = 0; i < i_miss; ++i) observe(0, true, false);
        for (unsigned i = 0; i < d_miss; ++i) observe(0, false, false);
        for (unsigned i = i_miss+d_miss; i < window_size; ++i) observe(0, false, true);
        assert(instruction_accesses == 0 && data_accesses == 0);
        assert(instruction_misses == 0 && data_misses == 0);
    };
    threshold = 0.25;
    // Exactly at the threshold remains RRIP; exceeding it enables I-RRIP.
    fill_window(1, 3);
    assert(!prioritize_instructions && windows == 1 && switches == 0);
    fill_window(2, 2);
    assert(prioritize_instructions && windows == 2 && switches == 1);

    update(0, LOAD, true, false); // Leaders always promote data to 0.
    update(1, LOAD, true, false);
    assert(rrpv[0][0] == 0 && rrpv[1][0] == 1);
    assert(data_accesses == 1); // Only the leader trained the controller.
    instruction_accesses = data_accesses = instruction_misses = data_misses = 0;
    for (unsigned type : {RFO, PREFETCH, WRITEBACK, LOAD_TRANSLATION, PREFETCH_TRANSLATION, TRANSLATION_FROM_L1D})
        update(0, type, false, true);
    assert(instruction_accesses + data_accesses == 0);
    // Incoming access classification, not a mixed-use resident's sticky bit, trains the counters.
    cache.block[0][0].instruction = 1;
    update(0, LOAD, true, false);
    assert(data_accesses == 1 && instruction_accesses == 0 && rrpv[0][0] == 0);
    instruction_accesses = data_accesses = 0;

    auto prepare_set = [&](unsigned set) {
        for (unsigned w = 0; w < L2C_WAY; ++w) {
            cache.block[set][w].valid = 1;
            cache.block[set][w].instruction = 1;
            rrpv[set][w] = 0;
        }
        rrpv[set][0] = 3;
        cache.block[set][1].instruction = 0;
        rrpv[set][1] = 1;
    };
    auto victim = [&](unsigned set) { return cache.l2c_find_victim(0, 0, set, cache.block[set], 0, 0, LOAD); };
    prepare_set(0); prepare_set(1);
    assert(victim(0) == 0 && victim(1) == 1); // Permanent RRIP leaders, bias-2 followers.
    // A data-only window switches back; it does not reset resident RRPVs.
    fill_window(0, 100);
    assert(!prioritize_instructions && switches == 2);
    assert(rrpv[1][0] == 3 && rrpv[1][1] == 1 && victim(1) == 0);
    warmup_complete[0] = 1;
    cache.block[1][0].instruction = 0;
    update(1, LOAD, true, false);
    assert(rrpv[1][0] == 0 && roi_rrip_loads == 1);
    fill_window(100, 0);
    update(1, LOAD, true, false);
    assert(rrpv[1][0] == 1 && roi_irrip_loads == 1);
    fill_window(0, 0); // No misses means RRIP; division by zero is avoided.
    assert(!prioritize_instructions);
    cache.block[1][2].valid = 0;
    assert(victim(1) == 2);

    threshold = 1;
    fill_window(4096, 0);
    assert(!prioritize_instructions);
    threshold = 0;
    fill_window(1, 0);
    assert(prioritize_instructions);
    // Differential checks use direct max-distance aging rather than the policy loop.
    uint32_t random = 12345;
    auto next = [&]() { random = random*1664525u + 1013904223u; return random; };
    for (bool mode : {false, true}) {
        prioritize_instructions = mode;
        for (unsigned set : {0u, 1u}) {
            for (unsigned trial = 0; trial < 1000; ++trial) {
                unsigned expected_rrpv[L2C_WAY];
                int expected = -1;
                unsigned maximum = 0;
                for (unsigned w = 0; w < L2C_WAY; ++w) {
                    unsigned bits = next();
                    cache.block[set][w].valid = !(trial % 7 == 0 && w == trial % L2C_WAY);
                    cache.block[set][w].instruction = (bits >> 8) & 1;
                    expected_rrpv[w] = rrpv[set][w] = (bits >> 16) & 3;
                    maximum = std::max(maximum, expected_rrpv[w]);
                    if (!cache.block[set][w].valid && expected < 0) expected = w;
                }
                if (expected < 0) {
                    int best_data = -1;
                    for (unsigned w = 0; w < L2C_WAY; ++w) {
                        expected_rrpv[w] += 3-maximum;
                        if (expected < 0 && expected_rrpv[w] == 3) expected = w;
                        if (!cache.block[set][w].instruction &&
                            (best_data < 0 || expected_rrpv[w] > expected_rrpv[best_data])) best_data = w;
                    }
                    if (mode && !leader(set) && best_data >= 0 && expected_rrpv[best_data] >= 1)
                        expected = best_data;
                }
                assert(victim(set) == static_cast<unsigned>(expected));
                for (unsigned w = 0; w < L2C_WAY; ++w) assert(rrpv[set][w] == expected_rrpv[w]);
            }
        }
    }
    // Experiment 1 changes initialization only: the old decision rule still applies.
    setenv("DYN_IRRIP_START", "1", 1);
    setenv("DYN_IRRIP_PERSIST", "0", 1);
    cache.l2c_initialize_replacement();
    assert(prioritize_instructions && !persistent_switching);
    cache.block[1][0].instruction = 0;
    update(1, LOAD, true, false);
    update(0, LOAD, true, false);
    assert(rrpv[1][0] == 1 && rrpv[0][0] == 0);
    instruction_accesses = data_accesses = instruction_misses = data_misses = 0;
    fill_window(0, 0);
    assert(!prioritize_instructions); // Unchanged zero-miss rule in the initial-only ablation.

    // Experiment 2 needs two consecutive low-share windows, and retains mode
    // without evidence (no misses or exact equality). Recovery needs only one window.
    setenv("DYN_IRRIP_PERSIST", "1", 1);
    cache.l2c_initialize_replacement();
    threshold = 0.25;
    assert(prioritize_instructions && persistent_switching && rrip_streak == 0);
    fill_window(1, 3);
    assert(prioritize_instructions && rrip_streak == 0);
    fill_window(0, 1);
    assert(prioritize_instructions && rrip_streak == 1);
    fill_window(0, 0);
    assert(prioritize_instructions && rrip_streak == 0);
    fill_window(0, 1);
    fill_window(1, 3);
    assert(prioritize_instructions && rrip_streak == 0);
    fill_window(0, 1);
    assert(prioritize_instructions && rrip_streak == 1);
    fill_window(0, 1);
    assert(!prioritize_instructions && rrip_streak == 2);
    fill_window(0, 0);
    assert(!prioritize_instructions && rrip_streak == 0);
    fill_window(0, 1);
    fill_window(1, 0);
    assert(prioritize_instructions && rrip_streak == 0);
    fill_window(0, 1);
    fill_window(1, 0);
    assert(prioritize_instructions && rrip_streak == 0);
    fill_window(0, 1);
    fill_window(0, 1);
    assert(!prioritize_instructions);
    for (unsigned set : {0u, 1u})
        for (unsigned w = 0; w < L2C_WAY; ++w) assert(rrpv[set][w] == 3);
    // Task 3 awareness is optional; demand behavior and RRIP leaders are retained.
    setenv("DYN_IRRIP_PREFETCH", "1", 1);
    cache.l2c_initialize_replacement();
    warmup_complete[0] = 1;
    for (bool mode : {false, true}) {
        prioritize_instructions = mode;
        cache.block[1][0].instruction = 0;
        update(1, PREFETCH, false, false);
        assert(rrpv[1][0] == 3);
        update(1, PREFETCH, true, false);
        assert(rrpv[1][0] == 3);
        update(1, LOAD, true, false);
        assert(rrpv[1][0] == (mode ? 1 : 0));
        update(1, PREFETCH, true, false);
        assert(rrpv[1][0] == (mode ? 1 : 0));
        update(0, PREFETCH, false, false);
        assert(rrpv[0][0] == 2);
        update(0, PREFETCH, true, false);
        assert(rrpv[0][0] == 0);
        update(1, PREFETCH, false, true); // Does not demote instruction prefetches.
        assert(rrpv[1][0] == 2);
        cache.block[1][0].instruction = 1;
        update(1, LOAD, true, true);
        assert(rrpv[1][0] == 0);
    }
    assert(roi_prefetch_fills == 2 && roi_prefetch_hits == 4);
    assert(instruction_accesses + data_accesses == 0);
    unsetenv("DYN_IRRIP_PREFETCH");
    cache.l2c_initialize_replacement();
    update(1, PREFETCH, false, false);
    assert(rrpv[1][0] == 2); // Task 2 remains the default.
    cout << "Dynamic I-RRIP tests passed" << endl;
}
