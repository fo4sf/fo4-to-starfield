// g++ -std=c++20 -Wall -Wextra -Werror -I sfse/FO4SFBorder tests/sfse_border_scan_test.cpp (tests/test_sfse_border.py)
#include "scan.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

using namespace fo4sfborder;

int main() {
    // a read-only "rdata" with the name twice (one decoy without the NUL) and a writable "data" with a Setting-like
    // object {vtable, value, name pointer} plus an unaligned copy of the pointer that must not count
    std::vector<std::uint8_t> rdata(256, 0xCC), data(128, 0);
    const char* name = kSettingName;
    std::memcpy(rdata.data() + 40, name, std::strlen(name) + 1);
    std::memcpy(rdata.data() + 120, name, std::strlen(name));          // no NUL after it: a longer name
    rdata[120 + std::strlen(name)] = 'X';
    const std::uintptr_t rbase = 0x140001000, dbase = 0x140100000;
    const std::uint64_t str = rbase + 40, vtbl = rbase + 8;
    std::memcpy(data.data() + 32, &vtbl, 8);
    data[40] = 1;                                                       // the bool value
    std::memcpy(data.data() + 48, &str, 8);                             // the name pointer
    std::memcpy(data.data() + 89, &str, 8);                             // unaligned: ignored
    std::vector<Region> regions = {{rbase, rdata.data(), rdata.size(), false}, {dbase, data.data(), data.size(), true}};

    auto strings = find_strings(regions, kSettingName);
    assert(strings.size() == 1 && strings[0] == rbase + 40);
    auto c = find_setting_candidates(regions);
    assert(c.size() == 1 && c[0].pointer_addr == dbase + 48 && c[0].string_addr == rbase + 40);
    // a pointer in a read-only region does not count
    std::memcpy(rdata.data() + 200, &str, 8);
    assert(find_setting_candidates(regions).size() == 1);

    assert(parse_signal("") == -1);
    assert(parse_signal("x border=off y") == 0);
    assert(parse_signal("border=off\nborder=on\n") == 1);
    assert(parse_signal("border=on\nborder=off\n") == 0);
    std::puts("sfse_border_scan_test: all passed");
    return 0;
}
