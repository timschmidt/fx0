#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the actual BMS snapshot helpers with a faulting register backend."""
import argparse
from pathlib import Path
import subprocess
import tempfile

PRELUDE = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef uint8_t u8;
typedef uint64_t u64;
typedef long long s64;
#define BIT(n) (1U << (n))
#define GENMASK_ULL(h, l) ((~0ULL >> (63-(h))) & (~0ULL << (l)))
#define BMS_CC_DATA_CTL 0x4042
#define BMS_HOLD_OUTPUT BIT(0)
struct bms_outputs { u8 cc[5], shadow[5], ocv[2], vbat[2], vsense[2]; };
struct regmap {
    unsigned int control;
    int calls, writes, fail_at, fail_after_write;
    int ignore_hold, torn, cc_reads, permanent_release_error;
};
static uint32_t get_unaligned_le32(const u8 *p)
{ return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static s64 sign_extend64(u64 value, int index)
{ unsigned int shift = 63-index; return (s64)(value << shift) >> shift; }
static int regmap_read(struct regmap *map, unsigned int reg, unsigned int *value)
{
    assert(reg == BMS_CC_DATA_CTL);
    if (++map->calls == map->fail_at) return -EIO;
    *value = map->control;
    return 0;
}
static int regmap_update_bits(struct regmap *map, unsigned int reg,
                              unsigned int mask, unsigned int value)
{
    assert(reg == BMS_CC_DATA_CTL && mask == BMS_HOLD_OUTPUT);
    map->writes++;
    int fail = ++map->calls == map->fail_at;
    if (map->permanent_release_error && !(value & BMS_HOLD_OUTPUT)) return -EIO;
    if (fail && !map->fail_after_write) return -EIO;
    if (!(map->ignore_hold && (value & BMS_HOLD_OUTPUT)))
        map->control = (map->control & ~mask) | (value & mask);
    return fail ? -EIO : 0;
}
static int regmap_bulk_read(struct regmap *map, unsigned int reg, void *buffer, size_t size)
{
    assert(map->control & BMS_HOLD_OUTPUT);
    assert((reg == 0x408a && size == 5) || (reg == 0x40a8 && size == 5) ||
           ((reg == 0x4090 || reg == 0x409e || reg == 0x4098) && size == 2));
    if (++map->calls == map->fail_at) return -EIO;
    u8 *p = buffer;
    for (size_t i = 0; i < size; i++) p[i] = (reg & 255) + i;
    if (reg == 0x408a && map->cc_reads++ && map->torn) p[0] ^= 1;
    return 0;
}
'''
MAIN = r'''
static struct regmap fresh(void) { struct regmap m = { .control = 0xa0 }; return m; }
int main(void)
{
    struct regmap map = fresh();
    struct bms_outputs out;
    unsigned int before = 0, after = 0;
    int result = bms_take_snapshot(&map, &out, &before, &after);
    assert(result == 0 && before == 0xa0 && after == 0xa0 && map.control == 0xa0);
    int normal_calls = map.calls;
    assert(normal_calls == 15);
    for (int op = 1; op <= normal_calls; op++) {
        for (int after_write = 0; after_write < 2; after_write++) {
            map = fresh(); map.fail_at = op; map.fail_after_write = after_write;
            result = bms_take_snapshot(&map, &out, &before, &after);
            assert(map.control == 0xa0); /* Includes unrelated control bits. */
            if (op < 14) assert(result < 0); /* Snapshot failure cannot become success. */
            else assert(result == 0); /* A single release I/O fault is retried. */
        }
    }
    map = fresh(); map.control |= BMS_HOLD_OUTPUT;
    assert(bms_take_snapshot(&map, &out, &before, &after) == -EBUSY);
    assert(map.control == 0xa1 && map.writes == 0 && map.calls == 1);
    map = fresh(); map.ignore_hold = 1;
    assert(bms_take_snapshot(&map, &out, &before, &after) == -EIO && map.control == 0xa0);
    map = fresh(); map.torn = 1;
    assert(bms_take_snapshot(&map, &out, &before, &after) == -EIO && map.control == 0xa0);
    map = fresh(); map.permanent_release_error = 1;
    assert(bms_take_snapshot(&map, &out, &before, &after) == -EIO);
    assert(map.control == 0xa1); /* Do not claim recovery from a permanently failed bus. */
    struct vector { u8 raw[5]; s64 expected; } vectors[] = {
        {{0,0,0,0,0}, 0}, {{1,0,0,0,0}, 1}, {{0x78,0x56,0x34,0x12,0}, 0x12345678LL},
        {{255,255,255,255,7}, 34359738367LL}, {{0,0,0,0,8}, -34359738368LL},
        {{255,255,255,255,15}, -1}, {{254,255,255,255,15}, -2},
        {{0,0,0,0,240}, 0}, {{255,255,255,255,255}, -1}
    };
    for (size_t i = 0; i < sizeof(vectors)/sizeof(vectors[0]); i++)
        assert(bms_decode_cc(vectors[i].raw) == vectors[i].expected);
    puts("Snapshot success, 30 single-operation faults, 4 ownership/consistency/permanent-fault cases and 9 decoder vectors pass");
    return 0;
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).with_name('fx0-pm8226-bms-snapshot.c'))
    parser.add_argument('--cc', default='clang')
    args = parser.parse_args()
    source = args.source.read_text().split('/* BEGIN TESTED SNAPSHOT HELPERS */', 1)[1].split('/* END TESTED SNAPSHOT HELPERS */', 1)[0]
    with tempfile.TemporaryDirectory(prefix='fx0-bms-check-') as temporary:
        root = Path(temporary)
        (root/'check.c').write_text(PRELUDE + source + MAIN)
        subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,address', '-fno-sanitize-recover=all',
                        str(root/'check.c'), '-o', str(root/'check')], check=True)
        subprocess.run([str(root/'check')], check=True)

if __name__ == '__main__':
    main()
