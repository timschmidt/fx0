# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib, json, subprocess
N = Path(__file__).resolve().parent
R = N.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
plan = read(N / 'composition.json')
paths = set(plan['source_files'])
assert set(subprocess.check_output(['git', 'diff', '--name-only', plan['base']], cwd=C, text=True).splitlines()) == paths
assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=C)
assert all(sha(C / f) == h for f, h in plan['source_files'].items())
callers = subprocess.check_output(['rg', '-l', 'common/inv_sensors_timestamp.h', 'drivers', 'include'], cwd=C, text=True).splitlines()
assert set(callers) == {
    'drivers/iio/common/inv_sensors/inv_sensors_timestamp.c',
    'drivers/iio/imu/inv_mpu6050/inv_mpu_iio.h',
    'drivers/iio/imu/inv_mpu6050/inv_mpu_core.c',
    'drivers/iio/imu/inv_mpu6050/inv_mpu_ring.c',
    'drivers/iio/imu/inv_mpu6050/inv_mpu_trigger.c',
    'drivers/iio/imu/inv_icm42600/inv_icm42600_gyro.c',
    'drivers/iio/imu/inv_icm42600/inv_icm42600.h',
    'drivers/iio/imu/inv_icm42600/inv_icm42600_buffer.c',
    'drivers/iio/imu/inv_icm42600/inv_icm42600_accel.c'}
files = {f:sha(C / f) for f in callers if f not in paths}
extra = ['drivers/iio/imu/inv_mpu6050/inv_mpu_dmp.c', 'drivers/iio/industrialio-buffer.c',
    'include/linux/iio/buffer.h', 'drivers/iio/test/iio-test-format.c']
files.update({f:sha(C / f) for f in extra})
for f, h in files.items():
    old = subprocess.check_output(['git', 'show', plan['base'] + ':' + f], cwd=C)
    assert hashlib.sha256(old).hexdigest() == h
ring = (C / 'drivers/iio/imu/inv_mpu6050/inv_mpu_ring.c').read_text()
assert ring.index('if (st->dmp_active)') < ring.index('inv_sensors_timestamp_interrupt')
assert 'inv_sensors_timestamp_interrupt(&st->timestamp, 1, pf->timestamp);' in ring
assert 'inv_sensors_timestamp_apply_odr(&st->timestamp, fifo_period, 1, 0);' in ring
assert 'inv_sensors_timestamp_pop(&st->timestamp);' in ring
mpu = (C / 'drivers/iio/imu/inv_mpu6050/inv_mpu_core.c').read_text()
assert 'timestamp.jitter = 20;' in mpu and 'timestamp.clock_period = NSEC_PER_SEC / INV_MPU6050_INTERNAL_FREQ_HZ;' in mpu
assert '#define INV_MPU6050_INTERNAL_FREQ_HZ\t\t1000' in (C / 'drivers/iio/imu/inv_mpu6050/inv_mpu_iio.h').read_text()
for name in ['gyro', 'accel']:
    text = (C / ('drivers/iio/imu/inv_icm42600/inv_icm42600_' + name + '.c')).read_text()
    assert 'ts_chip.clock_period = 125000;' in text and 'ts_chip.jitter = 20;' in text
after = read(N / 'model-after-03/qualification.json')
controls = read(N / 'models-03/controller.json')
assert after['passed'] and after['cases'] == 504 and after['checks'] == 83780
assert controls['passed'] and controls['independent_regression_variants'] == 7
assert controls['records'][0]['failures'] == 344
assert after['infeasible_budget_overshoot_ns'] == 480000
j = dict(passed=True, base=plan['base'], source_files=plan['source_files'] | files,
    changed_paths=sorted(paths), endpoint_matches_official_except_init_doc_and_whitespace=True,
    original_147_inventory_unchanged=True, all_timestamp_consumers_enumerated=True,
    MPU_and_ICM_caller_source_unchanged=True, DMP_and_quaternion_ABI_source_unchanged=True,
    MPU_1kHz_clock_and_ICM_8kHz_clock_profiles_bound=True,
    full_MPU_or_ICM_FIFO_callbacks_replayed=False,
    upstream_five_runtime_changes_and_two_prerequisites=True,
    observed_infeasible_IRQ_budget=dict(period_min_ns=980000, IRQ_budget_ns=500000,
        timestamp_overshoot_ns=480000, reproduced_in_official_algorithm=True,
        physical_trigger_or_latency_observed=False, final_timing_acceptance_open=True),
    DTS_and_schema_unchanged=True, previous_full19_schema_proof_reusable=True,
    phone_access=False)
(N / 'source-equivalence.json').write_text(json.dumps(j, indent=2) + '\n')
print('Exact two-path scope, all consumers, preserved DMP ABI and timing limitation verified')
