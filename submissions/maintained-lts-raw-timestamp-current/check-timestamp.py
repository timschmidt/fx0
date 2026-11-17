# SPDX-License-Identifier: GPL-2.0-only
"""Compile the complete pure timestamp module and inline API with synthetic times."""
from pathlib import Path
import argparse, hashlib, json, os, re, resource, subprocess
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--mutation', choices=['watermark', 'long-window', 'estimate-cap',
    'first-transition', 'odr-transition', 'reset-history', 'pending-odr'])
a = ap.parse_args()
N = Path(__file__).resolve().parent
O = a.output.resolve()
O.mkdir(mode=0o700)
(O / 'tmp').mkdir()
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
paths = ['drivers/iio/common/inv_sensors/inv_sensors_timestamp.c',
         'include/linux/iio/common/inv_sensors_timestamp.h']
c, h = [(a.source / f).read_text() for f in paths]
original = c + '\n' + h
def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)
if a.mutation == 'watermark':
    c = replace_once(c, 'return clamp(new_period, period_min, period_max);',
        '(void)period_min; (void)period_max; (void)new_period;\n\treturn ts->mult * ts->chip_period.val;')
elif a.mutation == 'long-window':
    c = replace_once(c, '(20 * NSEC_PER_MSEC)', '(200000 * NSEC_PER_MSEC)')
elif a.mutation == 'estimate-cap':
    c = replace_once(c, 'min(ts->mult * ts->chip_period.val, period)', 'ts->mult * ts->chip_period.val')
elif a.mutation == 'first-transition':
    c = replace_once(c, 'if ((delta + ts->period) > ts->timestamp)', 'if (true)')
elif a.mutation == 'odr-transition':
    c = replace_once(c, 'if ((timestamp + ts->period) > ts->timestamp)', 'if (true)')
elif a.mutation == 'reset-history':
    h = replace_once(h, '\tts->init = false;', '\tts->timestamp = 0;\n\tts->init = false;')
elif a.mutation == 'pending-odr':
    c = replace_once(c, '\tif (ts->new_mult) {\n\t\tit->lo = 0;\n\t\tit->up = 0;\n\t\tts->delta_counter = 0;\n\t}', '')
    c = replace_once(c, 'if (it->lo != 0 && !ts->new_mult)', 'if (it->lo != 0)')
program = (N / 'model-head.c').read_text()
program += '\n#define MODEL_HAS_INIT ' + str(int('bool init;' in h))
program += '\n#define MODEL_HAS_DELTA ' + str(int('delta_counter;' in h)) + '\n'
program += re.sub(r'^#include[^\n]*\n', '', h, flags=re.M)
program += '\n' + re.sub(r'^#include[^\n]*\n', '', c, flags=re.M)
program += '\n' + (N / 'model-tail.c').read_text()
(O / 'model.c').write_text(program)
env = os.environ | {'TMPDIR':str(O / 'tmp'), 'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1',
    'UBSAN_OPTIONS':'halt_on_error=1'}
cmd = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
    '-fno-omit-frame-pointer',
    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', str(O / 'model.c'), '-o', str(O / 'model')]
compile = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
(O / 'compile.log').write_text(compile.stdout + compile.stderr)
assert compile.returncode == 0 and not compile.stderr, compile.stderr
run = subprocess.run([str(O / 'model')], capture_output=True, text=True, env=env, timeout=60)
(O / 'stdout').write_text(run.stdout)
(O / 'stderr').write_text(run.stderr)
assert run.returncode in [0, 1] and not run.stderr, run.stderr
j = json.loads(run.stdout)
j.update(returncode=run.returncode, passed=run.returncode == 0, mutation=a.mutation,
    source_files={f:hashlib.sha256((a.source / f).read_bytes()).hexdigest() for f in paths},
    original_source_SHA256=hashlib.sha256(original.encode()).hexdigest(),
    program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
    complete_timestamp_module_and_inline_API=True, arithmetic_helpers_modeled=True,
    normal_LSan_and_failfast_ASan_UBSan=True, physical_acceptance=False,
    full_MPU_or_ICM_FIFO_callback_executed=False, phone_access=False)
(O / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
print(json.dumps(j))
