#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise actual camera discovery against renumbered and inconsistent sysfs fixtures."""
import importlib.util
import json
from pathlib import Path
import tempfile

source = Path(__file__).with_name('current-test.py')
spec = importlib.util.spec_from_file_location('camera_current', source)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def fixture(root, bus):
    nodes = {}
    for index, (model, address) in enumerate([('imx132', 0x36), ('imx179', 0x10)]):
        node = root / 'class/video4linux' / ('v4l-subdev' + str(9 + index))
        node.mkdir(parents=True)
        (node / 'name').write_text(f'{model} {bus}-{address:04x}\n')
        device = node / 'device'
        device.mkdir()
        driver = root / 'drivers' / model
        driver.mkdir(parents=True)
        (device / 'driver').symlink_to(driver)
        of = root / 'firmware' / ('camera@' + f'{address:x}')
        of.mkdir(parents=True)
        (of / 'compatible').write_bytes(('sony,' + model + '\0').encode())
        (of / 'reg').write_bytes(address.to_bytes(4, 'big'))
        (device / 'of_node').symlink_to(of)
        nodes[model] = node
    return nodes


cases = []
for bus in (2, 3, 17):
    with tempfile.TemporaryDirectory(prefix='fx0-camera-discovery-') as tmp:
        root = Path(tmp)
        nodes = fixture(root, bus)
        worker.SYS = root
        worker.command = lambda *args: "1: 'Internal front camera' (/soc/cci/i2c-bus@0/camera@36)\n2: 'Internal back camera' (/soc/cci/i2c-bus@0/camera@10)"
        actual = worker.find_cameras()
        assert actual['front'][0:2] == ('1', '/dev/v4l-subdev9')
        assert actual['back'][0:2] == ('2', '/dev/v4l-subdev10')
        cases.append(f'bus-{bus}-accepted')

for mutation in ('address', 'driver', 'compatible', 'firmware-address', 'duplicate', 'missing', 'listing'):
    with tempfile.TemporaryDirectory(prefix='fx0-camera-discovery-') as tmp:
        root = Path(tmp)
        nodes = fixture(root, 2)
        worker.SYS = root
        node = nodes['imx132']
        if mutation == 'address':
            (node / 'name').write_text('imx132 2-0037\n')
        elif mutation == 'driver':
            (node / 'device/driver').unlink()
            (node / 'device/driver').symlink_to(root / 'drivers/imx179')
        elif mutation == 'compatible':
            (node / 'device/of_node/compatible').write_bytes(b'sony,imx179\0')
        elif mutation == 'firmware-address':
            (node / 'device/of_node/reg').write_bytes((0x10).to_bytes(4, 'big'))
        elif mutation == 'duplicate':
            (root / 'class/video4linux/v4l-subdev11').symlink_to(node, target_is_directory=True)
        elif mutation == 'missing':
            (node / 'name').write_text('other 2-0036\n')
        elif mutation == 'listing':
            worker.command = lambda *args: "1: 'Internal front camera' (/wrong/camera@10)\n2: 'Internal back camera' (/wrong/camera@10)"
        try:
            worker.find_cameras()
        except ValueError:
            cases.append(mutation + '-rejected')
        else:
            raise AssertionError('unsafe inventory accepted: ' + mutation)
print(json.dumps({'actual_discovery_cases': len(cases), 'cases': cases,
                  'camera_devices_accessed': False, 'control_writes': False}, indent=2))
