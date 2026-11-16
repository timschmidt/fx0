# SPDX-License-Identifier: GPL-2.0-only
"""Actual offset accessors and calibbias read case under synthetic PM/regmap."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess

b = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('iio_parts', b/'iio-model-parts.py')
parts = importlib.util.module_from_spec(spec); spec.loader.exec_module(parts)
p = argparse.ArgumentParser()
p.add_argument('source', type=Path); p.add_argument('output', type=Path)
p.add_argument('--baseline', type=Path)
p.add_argument('--part', choices=['offset', 'pm'])
p.add_argument('--mutation', choices=['gyro-stride', 'missing-put'])
a = p.parse_args(); a.output.mkdir(mode=0o700)
now = (a.source/'drivers/iio/imu/inv_mpu6050/inv_mpu_core.c').read_text()
old = a.baseline.read_text() if a.baseline else now
offset_source = old if a.part == 'offset' else now
pm_source = old if a.part == 'pm' else now
code = ''
if 'static unsigned int inv_mpu6050_offset_reg' in offset_source:
    code += parts.function(offset_source, 'inv_mpu6050_offset_reg')
for name in ['inv_mpu6050_sensor_set', 'inv_mpu6050_sensor_show']:
    code += parts.function(offset_source, name)
fn = parts.function(pm_source, 'inv_mpu6050_read_raw')
case = fn[fn.index('\tcase IIO_CHAN_INFO_CALIBBIAS'):fn.rindex('\tdefault:')]
code += '''static int model_calibbias(struct inv_mpu6050_state *st,
 const struct iio_chan_spec *chan, int *val) {
 int ret; switch (IIO_CHAN_INFO_CALIBBIAS) {
'''+case+''' default: return -EINVAL; } }
'''
if a.mutation == 'gyro-stride':
    needle = 'reg == INV_MPU6500_REG_ACCEL_OFFSET ? 3 : 2'
    assert needle in code; code = code.replace(needle, '3')
if a.mutation == 'missing-put':
    needle = 'pm_runtime_put_autosuspend(pdev);'
    assert needle in code; code = code.replace(needle, '(void)pdev;')
(a.output/'actual-functions.c').write_text(code)
head = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <endian.h>
typedef uint16_t __be16;
#define cpu_to_be16(x) htobe16((uint16_t)(x))
#define be16_to_cpup(p) be16toh(*(p))
#define INV_MPU6500_REG_ACCEL_OFFSET 0x77
enum { IIO_MOD_X = 1, IIO_MOD_Y, IIO_MOD_Z };
enum { IIO_ANGL_VEL, IIO_ACCEL, IIO_TEMP, IIO_CHAN_INFO_CALIBBIAS, IIO_VAL_INT };
static unsigned cases, checks, failures;
#define CHECK(c) do { checks++; if (!(c)) { failures++; if(failures < 9) printf("FAIL %d %s\n", __LINE__, #c); } } while (0)
struct device { int unused; };
struct regmap { uint8_t bytes[256]; unsigned calls, last; int error; };
struct regs { unsigned gyro_offset, accl_offset; };
struct inv_mpu6050_state { struct regmap *map; struct regs *reg; int lock; };
struct iio_chan_spec { int type, channel2; };
static int refs, gets, pm_put_calls, pm_error, recover_error, recover_calls, lock;
static bool enforce_power;
#define regmap_get_device(m) ((struct device *)(m))
static int __attribute__((unused)) pm_runtime_resume_and_get(struct device *d) { (void)d; gets++; if(pm_error) return pm_error; refs++; return 0; }
static void __attribute__((unused)) pm_runtime_put_autosuspend(struct device *d) { (void)d; CHECK(refs > 0 && !lock); refs--; pm_put_calls++; }
static void mutex_lock(int *p) { (void)p; CHECK(!lock); lock++; }
static void mutex_unlock(int *p) { (void)p; CHECK(lock == 1); lock--; }
static int __attribute__((unused)) inv_mpu6515_dmp_recover(struct inv_mpu6050_state *st) { (void)st; recover_calls++; CHECK(refs == 1 && lock == 1); return recover_error; }
static int bus(struct regmap *m, unsigned reg, void *data, size_t n, bool write) {
 m->calls++; m->last=reg; CHECK(n == 2 && reg+2 <= sizeof(m->bytes));
 if(enforce_power && refs != 1) return -EHOSTDOWN;
 if(m->error) return m->error;
 if(write) memcpy(m->bytes+reg,data,n); else memcpy(data,m->bytes+reg,n);
 return 0;
}
static int regmap_bulk_write(struct regmap *m, unsigned reg, const void *p, size_t n) { return bus(m,reg,(void*)p,n,true); }
static int regmap_bulk_read(struct regmap *m, unsigned reg, void *p, size_t n) { return bus(m,reg,p,n,false); }
'''
tail = r'''
static void reset(void) { refs=gets=pm_put_calls=pm_error=recover_error=recover_calls=lock=0; }
int main(void) {
 struct regmap m={0}; struct regs reg={.gyro_offset=0x13,.accl_offset=0x77};
 struct inv_mpu6050_state st={.map=&m,.reg=&reg};
 const int bases[]={0x06,0x13,0x77}, values[]={-32768,-16385,-2,-1,0,1,2,16384,32767};
 for(unsigned b=0;b<3;b++) for(unsigned axis=0;axis<3;axis++) for(unsigned v=0;v<9;v++) {
  cases++; unsigned addr=bases[b]+axis*(bases[b]==0x77?3:2); int out=123456;
  memset(m.bytes,0x5a,sizeof(m.bytes)); m.error=0;
  CHECK(inv_mpu6050_sensor_set(&st,bases[b],axis+IIO_MOD_X,values[v])==0);
  CHECK(m.last==addr && m.bytes[addr]==((uint16_t)values[v]>>8) && m.bytes[addr+1]==((uint16_t)values[v]&255));
  for(unsigned k=0;k<sizeof(m.bytes);k++) if(k!=addr && k!=addr+1) CHECK(m.bytes[k]==0x5a);
  m.bytes[addr]=(uint16_t)values[v]>>8; m.bytes[addr+1]=(uint16_t)values[v]&255;
  CHECK(inv_mpu6050_sensor_show(&st,bases[b],axis+IIO_MOD_X,&out)==IIO_VAL_INT && out==values[v]);
  m.error=-EREMOTEIO; out=123456;
  CHECK(inv_mpu6050_sensor_show(&st,bases[b],axis+IIO_MOD_X,&out)==-EREMOTEIO && out==123456);
  CHECK(inv_mpu6050_sensor_set(&st,bases[b],axis+IIO_MOD_X,values[v])==-EREMOTEIO);
 }
 enforce_power=true;
 for(unsigned type=0;type<2;type++) for(unsigned axis=0;axis<3;axis++) for(unsigned mode=0;mode<4;mode++) {
  cases++; reset(); memset(&m,0,sizeof(m)); int out=123456;
  struct iio_chan_spec ch={.type=type,.channel2=axis+IIO_MOD_X};
  unsigned addr=(type==IIO_ACCEL?0x77:0x13)+axis*(type==IIO_ACCEL?3:2);
  m.bytes[addr]=0x80; m.bytes[addr+1]=0x01;
  if(mode==1) pm_error=-EAGAIN;
  if(mode==2) m.error=-EREMOTEIO;
  if(mode==3) recover_error=-EBUSY;
  int expected= mode==1?-EAGAIN:mode==2?-EREMOTEIO:mode==3?-EBUSY:IIO_VAL_INT;
  int rc=model_calibbias(&st,&ch,&out);
  CHECK(rc==expected); CHECK(out==(mode?123456:-32767));
  CHECK(refs==0 && lock==0 && gets==1 && pm_put_calls==(mode!=1));
  CHECK(m.calls==(unsigned)(mode==0 || mode==2));
 }
 cases++; reset(); memset(&m,0,sizeof(m)); int out=123456;
 struct iio_chan_spec invalid={.type=IIO_TEMP,.channel2=IIO_MOD_X};
 CHECK(model_calibbias(&st,&invalid,&out)==-EINVAL);
 CHECK(refs==0 && gets==0 && pm_put_calls==0 && lock==0 && m.calls==0 && out==123456);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);
 return failures!=0;
}
'''
program=head+code+tail; (a.output/'model.c').write_text(program)
c = subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(a.output/'model.c'), '-o', str(a.output/'model')], capture_output=True, text=True, timeout=60)
(a.output/'compile.stderr').write_text(c.stderr); assert c.returncode == 0, c.stderr
r = subprocess.run([str(a.output/'model')], capture_output=True, text=True, timeout=60)
(a.output/'run.stdout').write_text(r.stdout); (a.output/'run.stderr').write_text(r.stderr)
result=json.loads(r.stdout.splitlines()[-1]); result.update(part=a.part,mutation=a.mutation,
 actual_source_SHA256=hashlib.sha256(code.encode()).hexdigest(),program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
 returncode=r.returncode,sanitizer_diagnostics=bool(r.stderr),all_calibration_bytes_synthetic=True,physical_calibration_acceptance=False)
(a.output/'qualification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
assert r.returncode in [0,1] and not r.stderr
