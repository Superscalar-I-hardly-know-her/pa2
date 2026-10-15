// Exercise the actual policy against small, deliberately constructed cache sets.
#include "../replacement/irrip.l2c_repl"
#include "../replacement/base_replacement.cc"

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
    CACHE cache("test", 1, L2C_WAY, L2C_WAY, 1, 1, 1, 1);
    cache.l2c_initialize_replacement();
    auto reset = [&]() {
        for (unsigned w = 0; w < L2C_WAY; ++w) {
            cache.block[0][w].valid = 1;
            cache.block[0][w].instruction = 1;
            rrpv[0][w] = 0;
        }
    };
    auto victim = [&]() { return cache.l2c_find_victim(0, 0, 0, cache.block[0], 0, 0, LOAD); };
    auto update = [&](unsigned way, unsigned type, bool hit, bool instruction) {
        cache.l2c_update_replacement_state(0, 0, way, 0, 0, 0, type, hit, instruction);
    };

    reset();
    cache.block[0][4].valid = 0;
    assert(victim() == 4);
    for (unsigned w = 0; w < L2C_WAY; ++w) assert(rrpv[0][w] == 0);

    for (int insert = 0; insert <= 2; ++insert) {
        instruction_insert = insert;
        update(0, LOAD, false, true);
        assert(rrpv[0][0] == insert);
        // Incoming data must not inherit the old instruction victim's type.
        update(0, LOAD, false, false);
        assert(rrpv[0][0] == 2);
        update(0, LOAD_TRANSLATION, false, true);
        assert(rrpv[0][0] == 2);
    }
    for (int promotion = 0; promotion <= 1; ++promotion) {
        data_hit = promotion;
        cache.block[0][0].instruction = 0;
        update(0, LOAD, true, false);
        assert(rrpv[0][0] == promotion);
        cache.block[0][0].instruction = 1;
        // A data hit on mixed-use code retains instruction-level protection.
        update(0, LOAD, true, false);
        assert(rrpv[0][0] == 0);
    }

    for (int bias = 0; bias <= 3; ++bias) {
        instruction_aware = 1;
        eviction_bias = bias;
        for (int data_rrpv = 0; data_rrpv <= 3; ++data_rrpv) {
            reset();
            rrpv[0][0] = 3;
            cache.block[0][1].instruction = 0;
            rrpv[0][1] = data_rrpv;
            assert(victim() == (data_rrpv >= 3-bias ? 1u : 0u));
            // An eligible distant instruction prevents further aging.
            assert(rrpv[0][1] == data_rrpv);
        }
    }
    reset();
    rrpv[0][0] = 3;
    cache.block[0][1].instruction = cache.block[0][2].instruction = 0;
    rrpv[0][1] = 2;
    rrpv[0][2] = 3;
    assert(victim() == 2); // Highest data RRPV wins, not first data way.
    rrpv[0][1] = 3;
    assert(victim() == 1); // Equal scores use way order.

    instruction_aware = 0;
    assert(victim() == 0);
    instruction_aware = 1;
    reset();
    assert(victim() == 0); // All-instruction sets always make progress.
    for (unsigned w = 0; w < L2C_WAY; ++w) assert(rrpv[0][w] == 3);
    reset();
    eviction_bias = 0;
    for (unsigned w = 0; w < L2C_WAY; ++w) cache.block[0][w].instruction = 0;
    rrpv[0][3] = 2;
    assert(victim() == 3);
    assert(rrpv[0][0] == 1 && rrpv[0][3] == 3);
    cout << "I-RRIP policy tests passed" << endl;
}
