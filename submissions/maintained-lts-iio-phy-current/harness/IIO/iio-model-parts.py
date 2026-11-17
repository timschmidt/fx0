# SPDX-License-Identifier: GPL-2.0-only
"""Extract actual driver metadata and core layout/push functions for host models."""
from pathlib import Path
import hashlib
import re


def function(text, name):
    m = re.search(r'^(?=[A-Za-z_*])[^\n]*?\b'+name+r'\(', text, re.M)
    assert m, name
    start = m.start()
    if text[start:].startswith(name) or text[start:].startswith('*'+name):
        previous = text[:start].rstrip('\n').rsplit('\n', 1)[-1]
        assert previous.startswith(('static ', 'const ', 'struct ', 'int ', 'void ')), (name, previous)
        start -= len(previous) + 1
    return text[start:text.index('\n}', m.start())+2]+'\n'


def macro(text, name):
    m = re.search(r'^#define '+name+r'\b', text, re.M)
    assert m, name
    lines = text[m.start():].splitlines(keepends=True)
    selected = []
    for line in lines:
        selected.append(line)
        if not line.rstrip().endswith('\\'):
            break
    return ''.join(selected)


def scan_parts(source, core_source=None):
    source = Path(source)
    core_source = Path(core_source or source)
    hashes = {}

    def read(root, name):
        p = root/name
        hashes[('driver/' if root == source else 'core/')+name] = hashlib.sha256(p.read_bytes()).hexdigest()
        return p.read_text()

    driver = read(source, 'drivers/iio/imu/inv_mpu6050/inv_mpu_core.c')
    header = read(source, 'drivers/iio/imu/inv_mpu6050/inv_mpu_iio.h')
    generic = read(core_source, 'include/linux/iio/iio.h') if (core_source/'include/linux/iio/iio.h').exists() else read(source, 'include/linux/iio/iio.h')
    core = read(core_source, 'drivers/iio/industrialio-buffer.c')
    push = read(core_source, 'include/linux/iio/buffer.h')
    lookup = read(source, 'drivers/iio/industrialio-core.c')
    enum = re.search(r'enum inv_mpu6050_scan \{.*?^};', header, re.M | re.S)[0]
    pieces = [enum+'\n']
    pieces += [line+'\n' for line in header.splitlines() if line.startswith('#define INV_MPU6515_SCAN_')]
    for name in ['IIO_CHAN_SOFT_TIMESTAMP']:
        pieces.append(macro(generic, name))
    for name in ['INV_MPU6050_CHAN', 'INV_MPU6050_TEMP_CHAN', 'INV_MPU6050_EVENT_CHAN',
                 'INV_MPU6050_SCAN_MASK_3AXIS_ACCEL', 'INV_MPU6050_SCAN_MASK_3AXIS_GYRO',
                 'INV_MPU6050_SCAN_MASK_TEMP']:
        pieces.append(macro(driver, name))
    for name in ['inv_mpu6515_channels', 'inv_mpu6515_scan_masks']:
        pieces.append(re.search(r'^static const [^\n]*\b'+name+r'\[\] = \{.*?^};', driver, re.M | re.S)[0]+'\n')
    pieces.append(function(lookup, 'iio_find_channel_from_si'))
    for name in ['iio_storage_bytes_for_si', 'iio_storage_bytes_for_timestamp', 'iio_compute_scan_bytes']:
        pieces.append(function(core, name))
    for name in ['iio_push_to_buffers_with_timestamp', 'iio_push_to_buffers_with_ts']:
        pieces.append(function(push, name))
    config = re.search(r'struct iio_device_config \{.*?\n\};', core, re.S).group()
    pieces.append(config)
    verify = function(core, 'iio_verify_update')
    start = verify.index('\tconfig->scan_bytes = iio_compute_scan_bytes(')
    end = verify.index('\n\treturn 0;', start)
    pieces.append('static void model_cache_config(struct iio_dev *indio_dev, struct iio_device_config *config, const unsigned long *scan_mask, bool scan_timestamp)\n{\n' + verify[start:end] + '\n}\n')
    enable = function(core, 'iio_enable_buffers')
    start = enable.index('\tindio_dev->active_scan_mask = config->scan_mask;')
    end = enable.index('\tiio_dev_opaque->currentmode', start)
    pieces.append('static void model_cache_enable(struct iio_dev *indio_dev, struct iio_device_config *config)\n{\n' + enable[start:end] + '\n}\n')
    actual = '\n'.join(pieces)
    current = 'timestamp_offset' in function(core, 'iio_compute_scan_bytes')
    return actual, current, hashes
