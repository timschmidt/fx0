#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile actual BMS math against independently calculated rational vectors."""
import argparse
import resource
from fractions import Fraction
from pathlib import Path
import subprocess
import tempfile

STUBS = r'''
#include <stdint.h>
#include <stdbool.h>
#include <limits.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int16_t s16;
typedef int64_t s64;
#define S64_MAX INT64_MAX
#define BMS_CC_MASK ((1ULL<<36)-1)
#define BMS_CURRENT_NUMERATOR (542535LL*3291*10)
#define BMS_CHARGE_NUMERATOR (542535ULL*3291*56*10/3600)
#define check_add_overflow(a,b,c) __builtin_add_overflow(a,b,c)
struct bms_counter { u64 previous; s64 charge_uah,remainder; bool initialized; };
static u32 get_unaligned_le32(const u8 *p)
{ return (u32)p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24; }
static s64 sign_extend64(u64 x, unsigned int bit) { return (s64)(x<<(63-bit))>>(63-bit); }
static s64 div64_s64(s64 a,s64 b) { return a/b; }
static u64 div64_u64_rem(u64 a,u64 b,u64 *r) { *r=a%b;return a/b; }
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver',type=Path)
    args=parser.parse_args()
    source=args.driver.read_text().split('/* BEGIN TESTED BMS MATH */',1)[1].split('/* END TESTED BMS MATH */',1)[0]
    lines=['int main(void) { int count=0,value,ret; struct bms_counter c={0};']
    for raw,gain,resistance in [(0,3291,10800),(1,3291,10800),(-1,3291,10800),
                                (400,3291,10800),(-400,3291,10800),(32767,3291,10800),
                                (-32768,3291,10800),(32767,1,1),(-32768,1,1),
                                (1,0,10800),(1,-1,10800),(1,3291,0)]:
        expected=int(Fraction(-raw*542535*3291*10,gain*resistance)) if gain>0 and resistance else 0
        status=-22 if gain<=0 or not resistance else -34 if not -(1<<31)<=expected<(1<<31) else 0
        lines.append(f'value=123;ret=bms_current_to_ua({raw},{gain},{resistance},&value);assert(ret=={status});')
        if not status:lines.append(f'assert(value=={expected});')
        lines.append('count++;')
    denominator=32764*3291*10800
    sequences=[
        [0,1000000,2000000,1000000,0],
        [(1<<36)-100000,100000,0,(1<<36)-100000],
        [(1<<35)-100000,(1<<35)+100000,(1<<35)-100000],
        [0,1<<35,0],
        [0,*range(1,10001)],
        [0,*[((1<<36)-n)&((1<<36)-1) for n in range(1,10001)]],
    ]
    for sequence in sequences:
        lines.append('c=(struct bms_counter){0};')
        previous=sequence[0];total=0
        for index,raw in enumerate(sequence):
            if index:
                delta=(raw-previous)&((1<<36)-1)
                if delta&(1<<35):delta-=1<<36
                total-=delta
            exact=Fraction(total*277741751,denominator);whole=int(exact)
            remainder=total*277741751-whole*denominator
            lines.append(f'assert(bms_counter_step(&c,{raw}ULL,{denominator}ULL)==0);assert(c.charge_uah=={whole}LL && c.remainder=={remainder}LL);count++;')
            previous=raw
    lines += [
        'c=(struct bms_counter){0};assert(bms_counter_step(&c,0,0)==-ERANGE && !c.initialized);count++;',
        'assert(bms_counter_step(&c,0,S64_MAX)==-ERANGE && !c.initialized);count++;',
        f'c=(struct bms_counter){{.initialized=true,.charge_uah=S64_MAX,.previous=1000000}};assert(bms_counter_step(&c,0,{denominator}ULL)==-ERANGE);assert(c.charge_uah==S64_MAX && c.previous==1000000);count++;',
        'const u8 bytes[5]={255,255,255,255,255};assert(bms_decode_counter(bytes)==BMS_CC_MASK);count++;',
        'printf("%d current/counter/rollover/fraction/overflow cases pass\\n",count);return 0;}',
    ]
    with tempfile.TemporaryDirectory(prefix='fx0-bms-math-') as temporary:
        root=Path(temporary);(root/'check.c').write_text(STUBS+source+'\n'.join(lines))
        subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined,address',
                        '-fno-sanitize-recover=all',str(root/'check.c'),'-o',str(root/'check')],check=True)
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        subprocess.run([str(root/'check')],check=True)

if __name__=='__main__':main()
