# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual IADC conversion code against independent integer vectors."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['unsigned-difference', 'missing-units', 'missing-range'])
a = p.parse_args()
a.output.mkdir(mode=0o700)
source = a.source.read_text()
m = re.search(r'^static int iadc_read_raw\(.*?^}', source, re.M | re.S)
assert m
function = m[0]
if a.mutation == 'unsigned-difference':
    function = function.replace('s32 vsense_uv, vsense_raw;', 's32 vsense_uv;\n\tu16 vsense_raw;')
elif a.mutation == 'missing-units':
    function = function.replace('(s64)vsense_uv * 1000000', '(s64)vsense_uv')
elif a.mutation == 'missing-range':
    function = function.replace('\t\tif (isense_ua < INT_MIN || isense_ua > INT_MAX)\n\t\t\treturn -ERANGE;\n', '')


def divide(n, d):
    return (abs(n) // abs(d)) * (-1 if (n < 0) != (d < 0) else 1)


vectors = []
for offset, gain in [(30000, 47857), (48000, 51200), (65534, 65535),
                     (0, 1), (10000, 9000), (32768, 65535)]:
    samples = set(range(0, 65536, 257)) | {offset, max(0, offset-1), min(65535, offset+1)}
    for rsense in [1, 7800, 9000, 10000, 10800, 4294967295]:
        for adc in sorted(samples):
            voltage = divide((adc-offset)*17857, gain-offset)
            current = divide(voltage*1000000, rsense)
            ok = -2147483648 <= current <= 2147483647
            vectors.append((adc, offset, gain, rsense, current if ok else 0, 1 if ok else -34))
head = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <errno.h>
#include <stdio.h>
typedef int32_t s32;
typedef long long s64;
typedef uint16_t u16;
typedef uint32_t u32;
#define IADC_REF_GAIN_MICRO_VOLTS 17857
#define IIO_CHAN_INFO_RAW 0
#define IIO_CHAN_INFO_SCALE 1
#define IIO_VAL_INT 1
#define IIO_VAL_INT_PLUS_MICRO 2
struct mutex { bool held; unsigned locks, unlocks; };
struct iadc_chip { void *dev; u32 rsense[2]; u16 offset[2], gain; struct mutex lock; };
struct iio_dev { struct iadc_chip *chip; };
struct iio_chan_spec { unsigned channel; };
#define iio_priv(d) ((d)->chip)
#define dev_dbg(dev, ...) do { (void)(dev); if (0) printf(__VA_ARGS__); } while (0)
static u16 injected_sample;
static int injected_error;
static unsigned conversions;
static void mutex_lock(struct mutex *m) { assert(!m->held); m->held = true; m->locks++; }
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held = false; m->unlocks++; }
static int iadc_do_conversion(struct iadc_chip *c, unsigned channel, u16 *sample)
{ assert(channel < 2 && c->lock.held); conversions++; *sample = injected_sample; return injected_error; }
static __attribute__((unused)) s64 div64_s64(s64 n, s64 d) { assert(d); return n/d; }
'''
data = 'static const struct vector { u16 adc, offset, gain; u32 rsense; int current, status; } vectors[] = {\n'
data += ',\n'.join('{%d,%d,%d,%dU,%d,%d}' % row for row in vectors)+'\n};\n'
tail = r'''
static unsigned cases, checks, failures;
#define CHECK(c) do { checks++; if (!(c)) { failures++; if (failures < 10) printf("FAIL %d: %s\n", __LINE__, #c); } } while (0)
int main(void)
{
 struct iadc_chip chip = {0}; struct iio_dev dev = {&chip};
 struct iio_chan_spec channel; int value, value2, ret;
 for (channel.channel = 0; channel.channel < 2; channel.channel++) {
  for (unsigned i = 0; i < sizeof(vectors)/sizeof(vectors[0]); i++) {
   const struct vector *v = &vectors[i]; cases++;
   chip.offset[channel.channel] = v->offset; chip.gain = v->gain;
   chip.rsense[channel.channel] = v->rsense; injected_sample = v->adc;
   value = 123; value2 = 456;
   ret = iadc_read_raw(&dev, &channel, &value, &value2, IIO_CHAN_INFO_RAW);
   CHECK(ret == v->status);
   CHECK(value == (v->status == IIO_VAL_INT ? v->current : 123));
   CHECK(value2 == 456);
   CHECK(!chip.lock.held && chip.lock.locks == chip.lock.unlocks);
  }
  unsigned before = conversions; value = value2 = 123; cases++;
  ret = iadc_read_raw(&dev, &channel, &value, &value2, IIO_CHAN_INFO_SCALE);
  CHECK(ret == IIO_VAL_INT_PLUS_MICRO && value == 0 && value2 == 1000);
  CHECK(conversions == before);
  cases++; CHECK(iadc_read_raw(&dev, &channel, &value, &value2, 999) == -EINVAL);
  CHECK(conversions == before);
  injected_error = -ETIMEDOUT; value = 123; cases++;
  CHECK(iadc_read_raw(&dev, &channel, &value, &value2, IIO_CHAN_INFO_RAW) == -ETIMEDOUT);
  CHECK(value == 123); CHECK(!chip.lock.held && chip.lock.locks == chip.lock.unlocks);
  injected_error = 0;
 }
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
 return failures != 0;
}
'''
program = head+'\n'+function+'\n'+data+tail
(a.output/'actual-function.c').write_text(function+'\n')
(a.output/'model.c').write_text(program)
c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(a.output/'model.c'), '-o', str(a.output/'model')], capture_output=True, text=True)
(a.output/'compile.stderr').write_text(c.stderr); assert c.returncode == 0, c.stderr
r = subprocess.run([str(a.output/'model')], capture_output=True, text=True)
(a.output/'run.stdout').write_text(r.stdout); (a.output/'run.stderr').write_text(r.stderr)
result = json.loads(r.stdout.splitlines()[-1])
result.update(returncode=r.returncode, mutation=a.mutation,
              source_SHA256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
              function_SHA256=hashlib.sha256(function.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              vector_count=len(vectors), all_calibration_vectors_synthetic=True,
              conversion_bus_and_mutex_services_modeled=True,
              physical_current_accuracy_direction_or_charging_acceptance=False,
              sanitizer_diagnostics=bool(r.stderr))
(a.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result)); assert r.returncode in [0, 1] and not r.stderr
