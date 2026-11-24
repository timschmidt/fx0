#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only verification of the installed persistent kernel and core peripherals."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--boot-id', required=True, help='Expected new persistent boot ID')
args = parser.parse_args()
parent = Path('/var/lib/fx0-rollback/kernel-6.18.63-01')
plan = json.loads((parent / 'install-plan-confirmed-02.json').read_text())
status = json.loads((parent / 'kernel-update-status.json').read_text())
release = plan['candidate_release']
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot == args.boot_id
assert os.uname().release == release and boot != plan['boot_id']
assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def out(*args):
    return subprocess.check_output(args, text=True, timeout=20).strip()
kernel_notes_sha256 = sha('/sys/kernel/notes')
assert kernel_notes_sha256 == '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
assert status['stage'] == 'updated-and-verified' and status['all_owned_process_groups_terminal']
assert sha(parent / 'install_native_v2.py') == plan['controller_sha256']
assert sha(parent / 'update_transaction.py') == plan['transaction_helper_sha256']
assert sha(parent / 'commit_state.py') == plan['commit_state_helper_sha256']
assert sha(parent / 'backup.private.json') == plan['backup_metadata_sha256']
backup = json.loads((parent / 'backup.private.json').read_text())
assert sha(parent / 'before-files.private.tar.gz') == backup['archive_sha256']
assert sha(parent / 'boot-partition.private.img') == backup['raw_boot_sha256']
sys.path.insert(0, str(parent))
import install_native_v2 as verifier
needed = {'lib/apk/db/installed', 'etc/apk/world', 'boot/boot.img'}
original = {}
with tarfile.open(parent / 'before-files.private.tar.gz', 'r|gz') as archive:
    for member in archive:
        if member.name in needed:
            assert member.isfile()
            original[member.name] = archive.extractfile(member).read()
assert set(original) == needed
baseline = verifier.database(original['lib/apk/db/installed'])
current = verifier.database(Path('/lib/apk/db/installed').read_bytes())
kernel_package = 'linux-postmarketos-qcom-msm8226'
assert current.keys() == baseline.keys()
assert {k: v for k, v in current.items() if k != kernel_package} == {
    k: v for k, v in baseline.items() if k != kernel_package}
assert current[kernel_package] == dict(V=['6.18.63-r1'], C=[plan['candidate_control_checksum']])
old_world = original['etc/apk/world'].decode()
held = [line for line in old_world.splitlines(keepends=True) if line.startswith(kernel_package + '><Q1')]
assert len(held) == 1
expected_world = old_world.replace(held[0], kernel_package + '><' + plan['candidate_control_checksum'] + '\n').encode()
assert Path('/etc/apk/world').read_bytes() == expected_world
assert Path('/etc/kernel-cmdline.d/90-fx0-module-signatures.conf').read_bytes() == b'module.sig_enforce=1\n'
assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip() == 'Y'
cmdline = Path('/proc/cmdline').read_text().split()
assert [word for word in cmdline if word.startswith('module.sig_enforce=')] == ['module.sig_enforce=1']
assert not any(word.startswith('fx0.native_trial=') for word in cmdline)
assert not Path('/run/systemd/system/fx0-native-return.timer').exists()
modules = []
for name, expected in plan['candidate_payload_sha256'].items():
    assert sha('/' + name) == expected, name
    if name.endswith('.ko.zst'):
        modules.append(name)
assert Path('/usr/share/kernel/postmarketos-qcom-msm8226/kernel.release').read_text().strip() == release
assert out('findmnt', '-n', '-o', 'FSTYPE', '-T', '/usr/lib/modules') != 'tmpfs'
image = Path('/boot/boot.img').read_bytes()
assert hashlib.sha256(image).hexdigest() == status['candidate_boot_image_sha256']
kernel, dtb, ramdisk, image_cmdline = verifier.boot_parts(image, plan['kernel_bytes'])
assert hashlib.sha256(kernel).hexdigest() == plan['kernel_sha256']
assert hashlib.sha256(dtb).hexdigest() == plan['DTB_sha256']
assert ramdisk == Path('/boot/initramfs').read_bytes()
assert verifier.cpio_index(ramdisk) == plan['expected_initramfs_payloads']
assert image_cmdline.count('module.sig_enforce=1') == 1
raw = Path('/dev/mmcblk0p15').read_bytes()
assert hashlib.sha256(raw[:plan['boot_offset']]).hexdigest() == plan['bootloader_prefix_sha256']
assert raw[plan['boot_offset']:plan['boot_offset'] + len(image)] == image
assert out('systemctl', 'is-system-running') == 'running'
assert not out('systemctl', '--failed', '--no-legend')
assert not out('systemctl', 'list-jobs', '--no-legend')
assert out('systemctl', 'is-active', 'tinydm', 'upower', 'iio-sensor-proxy').splitlines() == ['active'] * 3
assert Path('/sys/devices/system/cpu/online').read_text().strip() == '0-3'
assert Path('/sys/class/graphics/fb0/name').read_text().strip() == 'msmdrmfb'
display = {}
for name in ['fd900000.display-subsystem', 'fd928000.iommu', 'fd922800.dsi', 'fd922a00.phy']:
    path = Path('/sys/bus/platform/devices') / name / 'power/control'
    assert path.read_text().strip() == 'auto'
    display[name] = 'auto'
sway = int(out('pgrep', '-x', 'sway'))
gestures = [int(value) for value in out('pgrep', '-x', 'lisgd').splitlines()]
assert len(gestures) == 1
touch = Path('/dev/input/by-path/first-touchscreen').resolve()
assert any(os.readlink(path) == str(touch) for path in Path('/proc', str(gestures[0]), 'fd').iterdir())
temperatures = {path.parent.name: int(path.read_text()) for path in Path('/sys/class/thermal').glob('thermal_zone*/temp')}
assert len(temperatures) == 2 and all(-40000 <= value < 60000 for value in temperatures.values())
with open('/sys/kernel/debug/regmap/0-01/registers', 'rb') as stream:
    pmic = {hex(address): os.pread(stream.fileno(), 9, address * 9).decode()
            for address in [0xc041, 0xc046, 0x1740, 0x1741]}
assert pmic == {'0xc041': 'c041: 00\n', '0xc046': 'c046: 00\n', '0x1740': '1740: 01\n', '0x1741': '1741: 73\n'}
serious = [line for line in out('dmesg').splitlines()
           if re.search(r'CFI failure|Kernel panic|Internal error: Oops|BUG:|WARNING: CPU:', line)]
assert not serious, serious
print(json.dumps(dict(
    recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    boot_id=boot, kernel=release, package_version='6.18.63-r1',
    taint=0, kernel_notes_sha256=kernel_notes_sha256,
    signature_enforcement='Y', persistent_signature_cmdline=True,
    native_trial_marker=False, return_timer=False, modules_on_persistent_storage=True,
    candidate_payload_files_verified=len(plan['candidate_payload_sha256']),
    candidate_module_files_verified=len(modules),
    initramfs_payload_entries_verified=len(plan['expected_initramfs_payloads']),
    other_package_identities_unchanged=len(current) - 1,
    installed_world_exact=True, boot_image_sha256=hashlib.sha256(image).hexdigest(),
    raw_boot_sha256=hashlib.sha256(raw).hexdigest(), bootloader_prefix_preserved=True,
    original_r50_backups_still_verified=True, systemd='running',
    Sway_PID=sway, gesture_PID=gestures[0], gesture_touchscreen_open=True,
    display_PM_auto=display, CPUs_online='0-3', temperatures_mC=temperatures,
    PMIC_registers=pmic, serious_kernel_warnings=serious,
    audio_testing=False, read_only=True)))
