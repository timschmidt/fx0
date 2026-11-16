# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual driver descriptors plus current or legacy IIO scan/push code."""
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
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--legacy-core', type=Path)
p.add_argument('--mutation', choices=['legacy-reader'])
a = p.parse_args(); a.output.mkdir(mode=0o700)
actual, current, hashes = parts.scan_parts(a.source, a.legacy_core)
tail = r'''
static unsigned cases, checks, failures;
#define CHECK(c) do { checks++; if (!(c)) { failures++; if (failures < 10) printf("FAIL %d %s\n", __LINE__, #c); } } while (0)
int main(void)
{
 const unsigned expected_no_stamp[] = {6,8,6,8,12,14,16};
 const unsigned expected_stamp[] = {16,16,16,16,24,24,32};
 const unsigned current_offset[] = {8,8,8,8,16,16,16};
 CHECK(ARRAY_SIZE(inv_mpu6515_scan_masks) == 8);
 for (unsigned i = 0; i < 7; i++) for (unsigned stamp = 0; stamp < 2; stamp++) {
  cases++;
  struct iio_dev d = model_iio_device(NULL, inv_mpu6515_scan_masks[i], stamp);
  unsigned bytes = stamp ? expected_stamp[i] : expected_no_stamp[i];
  CHECK(d.scan_bytes == bytes); CHECK(d.scan_index_timestamp == 8 && d.masklength == 9);
  if (stamp) CHECK(d.scan_timestamp_offset == (MODEL_CURRENT ? current_offset[i] : bytes-8));
  if (MODEL_LEGACY_READER && stamp && i == 6) d.observer_offset = bytes-8;
  _Alignas(16) unsigned char sample[32] = {0};
  int64_t time = 1000000007;
  CHECK(iio_push_to_buffers_with_ts(&d, sample, sizeof(sample), time) == 0);
  CHECK(d.samples == 1);
  if (stamp) CHECK(d.timestamp == time);
  CHECK(iio_push_to_buffers_with_ts(&d, sample, bytes-1, time) == -ENOSPC);
  CHECK(d.samples == 1);
 }
 struct iio_dev q = model_iio_device(NULL, BIT(INV_MPU6515_SCAN_QUATERNION), true);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u,\"quaternion_scan_bytes\":%u,\"timestamp_offset\":%u}\n",
  cases, checks, failures, q.scan_bytes, q.scan_timestamp_offset);
 return failures != 0;
}
'''
program = (b/'scan-head.c').read_text()+'\ntypedef int64_t s64;\n'+actual
program += '\n#define MODEL_CURRENT '+str(int(current))+'\n#define MODEL_LEGACY_READER '+str(int(a.mutation is not None))+'\n'
program += (b/'scan-setup.c').read_text()+tail
(a.output/'actual-functions.c').write_text(actual); (a.output/'model.c').write_text(program)
c = subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(a.output/'model.c'), '-o', str(a.output/'model')], capture_output=True, text=True)
(a.output/'compile.stderr').write_text(c.stderr); assert c.returncode == 0, c.stderr
r = subprocess.run([str(a.output/'model')], capture_output=True, text=True)
(a.output/'run.stdout').write_text(r.stdout); (a.output/'run.stderr').write_text(r.stderr)
result = json.loads(r.stdout.splitlines()[-1])
result.update(returncode=r.returncode, source_files=hashes,
              actual_source_SHA256=hashlib.sha256(actual.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              current_core=current, mutation=a.mutation, sanitizer_diagnostics=bool(r.stderr),
              object_type_layout_resolver_and_sink_services_modeled=True,
              full_registration_IOCTLS_or_physical_acceptance=False)
(a.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result)); assert r.returncode in [0, 1] and not r.stderr
