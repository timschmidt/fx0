#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check runtime-only policy identity generation and complete FDT rollback."""
import argparse
import ast
from pathlib import Path
import re
import resource
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('lk2nd', type=Path)
args = parser.parse_args()
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
source = args.lk2nd.resolve()
root = Path(__file__).resolve().parents[2]
base = ast.parse((root/'diagnostics/lk2nd-battery-handoff/check.py').read_text())
strings = {node.targets[0].id: ast.literal_eval(node.value) for node in base.body
           if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
           and node.targets[0].id in ['stubs', 'main']}
stubs = strings['stubs'].replace('SOURCE_DEVICE_HEADER', str(source/'lk2nd/device/device.h'))
stubs = stubs.replace('SOURCE_IMPLEMENTATION', str(source/'lk2nd/device/2nd/gpl/lg-madai-battery.c'))
helpers = strings['main'].split('int main(', 1)[0]
tests = r'''
int main(void)
{
 unsigned int count=0;
 for(unsigned int bms=0;bms<2;bms++) {
  fixture(bms);assert(!fdt_setprop(tree,node("/pmic/charger@1000"),"qcom,software-charge-control",NULL,0));
  operation=0;assert(!madai_battery_update_dt(tree,"ignored",0));verify(bms);
  assert(!strcmp(fdt_getprop(tree,node("/pmic/charger@1000"),"lg,battery-charge-profile",NULL),"tocad-madai"));count++;
  int steps=operation;
  for(int at=1;at<=steps;at++) {
   fixture(bms);assert(!fdt_setprop(tree,node("/pmic/charger@1000"),"qcom,software-charge-control",NULL,0));
   memcpy(original,tree,sizeof(tree));operation=0;fail_at=at;
   assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
  }
  fixture(bms);assert(!madai_battery_update_dt(tree,"ignored",0));verify(bms);
  assert(!fdt_getprop(tree,node("/pmic/charger@1000"),"lg,battery-charge-profile",NULL));count++;
  fixture(bms);assert(!fdt_setprop(tree,node("/pmic/charger@1000"),"qcom,software-charge-control",NULL,0));
  lk2nd_dev.cmdline="lge.battid=unknown";assert(!madai_battery_detect(NULL,0));
  memcpy(original,tree,sizeof(tree));assert(!madai_battery_update_dt(tree,"ignored",0));unchanged();count++;
  fixture(bms);assert(!fdt_setprop(tree,node("/pmic/charger@1000"),"qcom,software-charge-control",NULL,0));
  assert(!fdt_setprop_string(tree,node("/pmic/charger@1000"),"lg,battery-charge-profile","tocad-madai"));
  memcpy(original,tree,sizeof(tree));assert(madai_battery_update_dt(tree,"ignored",0)==-FDT_ERR_EXISTS);unchanged();count++;
 }
 printf("PASS: %u actual runtime policy identity/data/FDT rollback cases ASan/UBSan\n",count);
}
'''
with tempfile.TemporaryDirectory(prefix='fx0-policy-profile-') as directory:
    directory = Path(directory)
    boot = re.search(r'enum boot_type \{.*?\n\};', (source/'app/aboot/boot.h').read_text(), re.S)[0]
    (directory/'boot.h').write_text(boot)
    (directory/'debug.h').write_text('')
    (directory/'check.c').write_text(stubs+helpers+tests)
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(directory),
                    str(directory/'check.c'), '-lfdt', '-Wl,--wrap=fdt_setprop',
                    '-Wl,--wrap=fdt_add_subnode', '-Wl,--wrap=fdt_open_into', '-o', str(directory/'check')], check=True)
    subprocess.run([str(directory/'check')], check=True, timeout=10)
