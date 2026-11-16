# SPDX-License-Identifier: GPL-2.0-only
"""Actual DMP code under synthetic bus/PM and actual current IIO layout helpers."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess

b = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('iio_parts', b/'iio-model-parts.py')
parts = importlib.util.module_from_spec(spec); spec.loader.exec_module(parts)
p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('kind', choices=['transport', 'packet', 'lifecycle', 'recovery', 'smd', 'loader'])
p.add_argument('--firmware', type=Path)
p.add_argument('--mutation', choices=['cursor', 'packet-error', 'restore-flag', 'status-bit', 'suspended-bus'])
a = p.parse_args(); a.output.mkdir(mode=0o700)

def fixture(name):
    return (b/'fixtures'/(name+'.c')).read_text()

source = (a.source/'drivers/iio/imu/inv_mpu6050/inv_mpu_dmp.c').read_text()
prefix = source.split('#define INV_MPU6515_DMP_FIRMWARE')[0]
suffix = source[source.index('int inv_mpu6515_dmp_configure('):]
if a.kind == 'transport':
    shim, code, main = fixture('shim'), prefix, fixture('main')
elif a.kind == 'packet':
    shim = fixture('shim')+fixture('packet_shim')
    code, main = prefix+suffix.split('/* Manufacturer SMD defaults;')[0], fixture('packet_main')
elif a.kind == 'loader':
    assert a.firmware and hashlib.sha256(a.firmware.read_bytes()).hexdigest() == 'eabe2b79d93565358cca83864fece47d7dca5d5826bfbdab2d79ed75996076aa'
    shim = fixture('shim')+fixture('loader_shim')
    code, main = source[:source.index('int inv_mpu6515_dmp_configure(')], fixture('loader_main')
else:
    shim = fixture('stream_shim')
    if a.kind == 'smd':
        shim = shim.replace('dmp_smd_mode;', 'dmp_smd_mode,dmp_smd_armed,dmp_smd_pm,dmp_smd_suspended,dmp_smd_irq_wake; u8 dmp_smd_last_status; int irq;')
        shim = shim.replace('else { *v=m->regs[r]; }', 'else { *v=m->regs[r]; if(r==0x39)m->regs[r]=0; }')
    shim += fixture('packet_shim')+fixture('lifecycle_shim')
    scan, current, hashes = parts.scan_parts(a.source)
    assert current
    shim += (b/'scan-head.c').read_text()+scan+'\n#define MODEL_CURRENT 1\n'+(b/'scan-setup.c').read_text()
    if a.kind == 'smd':
        shim += fixture('pm_shim')
    code = prefix+(suffix if a.kind == 'smd' else suffix.split('\nint inv_mpu6515_dmp_smd_set(')[0])
    main = fixture(a.kind+'_main')

mutations = {
    'cursor': ('ret = regmap_write(st->map, INV_DMP_MEM_START, address & 0xff);', 'ret = 0;'),
    'packet-error': ('return -EPROTO;', 'return -EAGAIN;'),
    'restore-flag': ('if (!first)\n\t\tst->dmp_saved_valid = false;', 'st->dmp_saved_valid = false;'),
    'status-bit': ('status & BIT(2)', 'status & BIT(3)'),
    'suspended-bus': ('if (st->dmp_smd_suspended)\n\t\treturn -EBUSY;', 'if (false)\n\t\treturn -EBUSY;'),
}
if a.mutation:
    old, new = mutations[a.mutation]
    assert old in code, (a.mutation, old)
    code = code.replace(old, new)
code = '\n'.join(line for line in code.splitlines() if not line.startswith('#include'))
(a.output/'actual-functions.c').write_text(code)
# Instrument fixture assertions; the actual driver function text stays unchanged.
counter = r'''
#include <stdlib.h>
static unsigned long model_checks;
#undef assert
#define assert(c) do { model_checks++; if (!(c)) { printf("MODEL_ASSERT %d %s\n", __LINE__, #c); exit(1); } } while (0)
'''
shim = '#include <stdio.h>\n'+counter+shim.replace('#include <assert.h>', '')
main = main.replace('int main(', 'int fixture_main(', 1)
wrapper = '\nint main(int argc, char **argv) { '
if a.kind in ['lifecycle', 'recovery', 'smd']:
    wrapper += 'struct iio_dev d = model_iio_device(NULL, inv_mpu6515_scan_masks[6], true); (void)d; '
wrapper += ('int rc = fixture_main(argc, argv);' if a.kind == 'loader' else '(void)argc; (void)argv; int rc = fixture_main();')
wrapper += ' printf("{\\\"checks\\\":%lu,\\\"passed\\\":true}\\n", model_checks); return rc; }\n'
# Keep the generated C string literal readable and valid.
wrapper = wrapper.replace('\\\"', '\\"').replace('\\\\n', '\\n')
program = shim+code+main+wrapper
(a.output/'model.c').write_text(program)
c = subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(a.output/'model.c'), '-o', str(a.output/'model')], capture_output=True, text=True, timeout=60)
(a.output/'compile.stderr').write_text(c.stderr); assert c.returncode == 0, c.stderr
cmd = [str(a.output/'model')]+([str(a.firmware)] if a.kind == 'loader' else [])
r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
(a.output/'run.stdout').write_text(r.stdout); (a.output/'run.stderr').write_text(r.stderr)
result = dict(kind=a.kind, mutation=a.mutation, returncode=r.returncode,
              passed=r.returncode == 0, sanitizer_diagnostics=any(t in r.stderr for t in ['AddressSanitizer', 'UndefinedBehaviorSanitizer', 'LeakSanitizer', 'runtime error:']),
              actual_source_SHA256=hashlib.sha256(code.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              firmware_bytes_published=False, physical_acceptance=False,
              regmap_PM_IRQ_services_modeled=True, integer_sqrt_modeled=True,
              actual_IIO_layout_and_push_helpers=a.kind in ['lifecycle', 'recovery', 'smd'])
if r.returncode == 0:
    result.update(json.loads(r.stdout.splitlines()[-1]))
(a.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert r.returncode == (1 if a.mutation else 0) and not r.stderr, r.stdout+r.stderr
