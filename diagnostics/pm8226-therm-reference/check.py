#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fault-inject the actual diagnostic's masked reference write and rollback."""
from pathlib import Path
import subprocess
import tempfile

text = Path(__file__).with_name("fx0-btc-reference.c").read_text()
functions = text[text.index("static int set_reference("):text.index("static int fx0_btc_show(")]
stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#define BAT_THERM_REF 0x124a
#define BAT_THERM_REF_MASK 0xc0
struct regmap { unsigned int value; int calls, fail; bool after, permanent, ignored; } state;
static struct regmap *map=&state;
static unsigned int original;
static bool changed;
static int regmap_update_bits(struct regmap *m, unsigned int address, unsigned int mask, unsigned int value)
{
 assert(address==BAT_THERM_REF && mask==0xc0 && !(value&~mask));
 bool fail=(++m->calls==m->fail || m->permanent);
 if (fail&&!m->after) return -EIO;
 if (!m->ignored) m->value=(m->value&~mask)|value;
 return fail?-EIO:0;
}
static int regmap_read(struct regmap *m, unsigned int address, unsigned int *value)
{
 assert(address==BAT_THERM_REF);
 if (++m->calls==m->fail || m->permanent) return -EIO;
 *value=m->value;return 0;
}
static void setup(unsigned int value)
{ state=(struct regmap){.value=value};original=value;changed=false; }
'''
main = r'''
int main(void)
{
 unsigned count=0;
 for (unsigned mode=0;mode<=0xc0;mode+=0x40) for(unsigned low=0;low<64;low++) {
  setup(mode|low);changed=true;
  assert(set_reference(0xc0)==0 && state.value==(0xc0|low));count++;
  assert(restore_reference()==0 && state.value==original && !changed);count++;
 }
 setup(0x9b);assert(set_reference(1)==-EINVAL && state.calls==0);count++;
 setup(0x9b);assert(restore_reference()==0 && state.calls==0);count++;
 for(int call=1;call<=2;call++) for(int after=0;after<2;after++) {
  setup(0x9b);changed=true;state.fail=call;state.after=after;
  assert(set_reference(0xc0)==-EIO);
  assert(restore_reference()==0 && state.value==0x9b && !changed);count++;
 }
 for(int call=1;call<=2;call++) for(int after=0;after<2;after++) {
  setup(0x9b);state.value=0xdb;changed=true;state.fail=call;state.after=after;
  assert(restore_reference()==0 && state.value==0x9b && !changed);count++;
 }
 setup(0x9b);state.ignored=true;changed=true;
 assert(set_reference(0xc0)==-EIO && state.value==0x9b);
 assert(restore_reference()==0 && !changed);count++;
 setup(0x9b);state.value=0xdb;changed=true;state.permanent=true;
 assert(restore_reference()==-EIO && changed && state.value==0xdb && state.calls==2);count++;
 printf("PASS: %u actual masked-reference/rollback cases under ASan/UBSan\n",count);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="fx0-btc-reference-") as temporary:
    root = Path(temporary)
    (root / "check.c").write_text(stubs + functions + main)
    subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", str(root / "check.c"), "-o", str(root / "check")], check=True)
    subprocess.run([str(root / "check")], check=True)
