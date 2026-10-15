#include <vector>
#include "../prefetcher/spp.l1d_pref"
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


std::vector<uint64_t> requests;
int CACHE::prefetch_line(uint64_t, uint64_t base, uint64_t target, int, uint32_t) {
    assert((base >> LOG2_PAGE_SIZE) == (target >> LOG2_PAGE_SIZE));
    requests.push_back(target >> LOG2_BLOCK_SIZE);
    ++pf_issued;
    return 1;
}
int main() {
    CACHE cache("test", 1, 8, 8, 1, 1, 1, 1);
    cache.cpu = 0;
    auto reset = [&]() { cache.l1d_prefetcher_initialize(); requests.clear();
        cache.pf_issued = cache.pf_useful = 0; };
    auto access = [&](uint64_t line, uint64_t ip = 0x1234) {
        requests.clear(); cache.l1d_prefetcher_operate(line << LOG2_BLOCK_SIZE, ip, 0, LOAD, 0);
    };
    reset();
    for (unsigned i=10; i<=13; ++i) { access(i); assert(requests.empty()); }
    access(14); assert((requests == std::vector<uint64_t>{15,16}));
    access(14); assert(requests.empty());
    access(20); assert(requests.empty()); // immediate loss of uniform eligibility
    reset();
    for (unsigned i=30; i>=26; --i) access(i);
    assert((requests == std::vector<uint64_t>{25,24}));
    reset();
    for (unsigned i=59; i<=63; ++i) access(i);
    assert(requests.empty()); // cannot cross page
    reset();
    const int cycle[] = {1,2,2,2,3};
    uint64_t line=1024;
    access(line);
    unsigned checked=0;
    for (unsigned i=0; i<150; ++i) {
        line += cycle[i%5]; access(line);
        if (!requests.empty()) {
            uint64_t expected=line;
            for (unsigned n=0; n<requests.size(); ++n) {
                expected += cycle[(i+1+n)%5]; assert(requests[n] == expected);
            }
            ++checked;
        }
    }
    assert(checked > 80);
    assert(pattern_predictions[0] > 100 && uniform_predictions[0] == 0);
    auto saved=trackers[0][(0x1234 ^ (0x1234 >> 4))%IP_TRACKER_SETS][0].signature;
    cache.l1d_prefetcher_operate(0, 0x1234, 0, PREFETCH, 0);
    assert(trackers[0][(0x1234 ^ (0x1234 >> 4))%IP_TRACKER_SETS][0].signature == saved);
    reset();
    cache.pf_issued=1000;
    for (unsigned band=0; band<4; ++band) {
        cache.pf_useful=band*250;
        for (unsigned i=0; i<4096; ++i) access(10);
        assert(prefetch_degree[0] == (1u << band));
    }
    // Two IPs with identical low eight bits remain separate.
    reset(); access(10,0x1234); access(30,0x2234);
    access(11,0x1234); assert(requests.empty());
    access(200,0x1234); assert(requests.empty()); // unsupported stride resets history
    std::cout << "SPP sequence tests passed" << std::endl;
}
