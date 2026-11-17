#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Rebuild pinned experimental kernel artifacts without a private signing key.

Bubblewrap exposes only system build tools, the source export, public signing
inputs and a new output directory. It provides no workstation network or USB.
This qualifies artifact reproduction, not a phone installation or APK recipe.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--inputs', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--jobs', type=int, default=4)
parser.add_argument('--rust-toolchain', type=Path, required=True, help='Installed public Rust toolchain directory matching the saved config metadata')
args = parser.parse_args()
source, inputs, output = (p.resolve() for p in [args.source, args.inputs, args.output])
rust_toolchain = args.rust_toolchain.resolve()
assert (rust_toolchain / 'bin/rustc').is_file()
assert 1 <= args.jobs <= 8
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = json.loads((inputs / 'manifest.json').read_text())
expected = json.loads((inputs / 'expected-build.json').read_text())
assert manifest['files'] == {str(p.relative_to(inputs)): sha(p) for p in inputs.rglob('*')
                            if p.is_file() and p.name != 'manifest.json'}
assert not any(p.is_symlink() for p in inputs.rglob('*'))
assert not (source / '.git').exists()
assert expected['source_files'] == {p: sha(source / p) for p in expected['source_files']}
assert expected['source_head'] == manifest['source_head']
output.mkdir(exist_ok=False)
out = output / 'out'
out.mkdir()
(out / 'tmp').mkdir()
(out / '.config').write_bytes((inputs / 'kernel.config').read_bytes())
assert sha(out / '.config') == expected['config_SHA256']
controller = output / 'controller.json'
record = dict(started_UTC=datetime.now(timezone.utc).isoformat(), passed=False, state='prepared',
    source_head=expected['source_head'], source_tree=expected['source_tree'],
    input_manifest_SHA256=sha(inputs / 'manifest.json'), public_Rust_compiler_SHA256=sha(rust_toolchain / 'bin/rustc'), controller_script_SHA256=sha(Path(__file__)),
    clean_output_directory=True, source_export_without_Git=True,
    development_private_key_not_mounted=True, private_key_not_read_hashed_or_copied=True,
    network_namespace_isolated=True, hardware_device_access_excluded=True,
    environment_cleared=True, source_and_inputs_read_only=True, Git_denied=True,
    phone_access=False, published=False, input_publication_pending=True,
    maintained_LTS_acceptance=False, full_APK_install_update_recovery_or_physical_acceptance=False,
    installation_profile=expected['installation_profile'], stages=[])
child = None

def save():
    controller.write_text(json.dumps(record, indent=2) + '\n')

def interrupted(sig, frame):
    raise InterruptedError(str(sig))

signal.signal(signal.SIGTERM, interrupted)
sandbox = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL',
    '--ro-bind', '/usr', '/usr', '--ro-bind', '/etc', '/etc',
    '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/sbin', '/sbin',
    '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
    '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
    '--ro-bind', str(rust_toolchain), '/toolchains/rust',
    '--ro-bind', str(source), '/src/linux', '--ro-bind', str(inputs), '/inputs',
    '--bind', str(out), '/build/out', '--clearenv']
environment = dict(PATH='/toolchains/rust/bin:/inputs/bin:/usr/bin:/usr/sbin:/bin:/sbin', HOME='/homeless',
    USER='fx0-review', LANG='C.UTF-8', LC_ALL='C.UTF-8', TZ='UTC',
    TMPDIR='/build/out/tmp', PYTHONDONTWRITEBYTECODE='1', GIT_NO_LAZY_FETCH='1',
    KBUILD_BUILD_VERSION=expected['fixed_build_version'],
    KBUILD_BUILD_USER=expected['fixed_build_user'], KBUILD_BUILD_HOST=expected['fixed_build_host'],
    KBUILD_BUILD_TIMESTAMP=expected['fixed_build_timestamp'], SOURCE_DATE_EPOCH=expected['source_date_epoch'])
for key, value in environment.items():
    sandbox += ['--setenv', key, value]
sandbox += ['--chdir', '/src/linux', '--']
record['sandbox_environment'] = environment
record['sandbox_mounts'] = dict(read_only=['/usr', '/etc', '/toolchains/rust', '/src/linux', '/inputs'],
    writable=['/build/out', '/tmp'], synthetic=['/dev', '/proc'],
    home_root_run_sys_and_host_boot_not_mounted=True)
maps = '-fdebug-prefix-map=/src/linux=/usr/src/linux -fdebug-prefix-map=/build/out=/usr/src/linux-build'
make = ['make', 'O=/build/out', 'ARCH=arm', 'RUSTC=/toolchains/rust/bin/rustc', 'LLVM=-21', 'W=1',
    'KCFLAGS=-Werror=incompatible-function-pointer-types ' + maps, 'KAFLAGS=' + maps,
    'LOCALVERSION=-g' + expected['source_head'][:12],
    'CONFIG_MODULE_SIG_KEY=/inputs/module-verification.pem',
    '--jobserver-style=pipe', '-j' + str(args.jobs)]

def run(label, command, timeout=900):
    global child
    log = output / (label + '.log')
    with log.open('xb') as stream:
        child = subprocess.Popen(sandbox + command, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        record.update(state='running ' + label, active_PID=child.pid)
        save()
        code = child.wait(timeout=timeout)
    record.pop('active_PID', None)
    lines = log.read_text(errors='replace').splitlines()
    record['stages'].append(dict(label=label, returncode=code, log_SHA256=sha(log),
        diagnostics=[s for s in lines if 'warning:' in s.lower() or 'error:' in s.lower()]))
    save()
    assert code == 0, (label, code, lines[-12:])

try:
    probe = ('from pathlib import Path; import json; '
        'assert not any(Path(p).exists() for p in ["/home","/root","/run","/sys","/boot","/dev/bus/usb"]); '
        'interfaces=[s.split(":",1)[0].strip() for s in Path("/proc/net/dev").read_text().splitlines()[2:]]; '
        'assert interfaces==["lo"],interfaces; '
        'print(json.dumps({"home_and_hardware_absent":True,"network_interfaces":interfaces}))')
    run('isolation-probe', ['python3', '-B', '-c', probe], 30)
    run('Rust-toolchain-probe', ['/toolchains/rust/bin/rustc', '-vV'], 30)
    run('config', make + ['olddefconfig'], 180)
    assert sha(out / '.config') == expected['config_SHA256'], 'Generated config differs from the pinned toolchain/config inputs'
    run('kernel-modules', make + ['zImage', 'modules'], 7200)
    artifacts = {p: sha(out / p) for p in expected['core_artifacts']}
    modules = {p: sha(out / p) for p in expected['module_artifacts']}
    record.update(core_artifacts=artifacts, raw_module_artifacts=modules,
        core_artifacts_match_controlled_build=artifacts == expected['core_artifacts'],
        all_459_raw_modules_match_controlled_build=modules == expected['module_artifacts'])
    assert artifacts == expected['core_artifacts'], 'Kernel output differs from controlled build'
    assert modules == expected['module_artifacts'], 'Raw modules differ from controlled build'
    assert sha(out / 'certs/signing_key.x509') == expected['public_certificate_SHA256']
    assert not (out / 'certs/signing_key.pem').exists(), 'Unexpected generated signing key'
    run('dtbs', make + ['dtbs'], 900)
    attach = ('cmd_sign=/usr/bin/python3 /inputs/attach-signature.py '
        '--manifest /inputs/module-signatures.json --sign-file /build/out/scripts/sign-file --module $@')
    run('modules-install', make + ['INSTALL_MOD_PATH=/build/out/stage', attach, 'modules_install'], 900)
    run('dtbs-install', make + ['INSTALL_DTBS_PATH=/build/out/stage/boot/dtbs', 'dtbs_install'], 300)
    release = expected['release']
    module_directory = '/build/out/stage/lib/modules/' + release
    run('module-signatures', ['python3', '-B', '/inputs/verify_kernel_modules.py',
        '--modules', module_directory, '--release', release,
        '--certificate', '/inputs/module-verification.der', '--expected-count', '459',
        '--report', '/build/out/module-signatures.json'], 600)
    run('module-dependencies', ['python3', '-B', '/inputs/verify_kernel_module_dependencies.py',
        '--modules', module_directory, '--expected-count', '459',
        '--report', '/build/out/module-dependencies.json'], 600)
    assert sha(out / '.config') == expected['config_SHA256']
    assert expected['source_files'] == {p: sha(source / p) for p in expected['source_files']}
    assert manifest['files'] == {str(p.relative_to(inputs)): sha(p) for p in inputs.rglob('*')
                                if p.is_file() and p.name != 'manifest.json'}
    assert not (out / 'certs/signing_key.pem').exists()
    staged = out / 'stage/lib/modules' / release
    record.update(passed=True, state='terminal success', release=release,
        modules_built=459, modules_staged_and_verified=459,
        installed_module_files={str(p.relative_to(staged)): sha(p) for p in sorted(staged.rglob('*'))
            if p.is_file() and not p.is_symlink()},
        installed_DTBS={str(p.relative_to(out / 'stage/boot/dtbs')): sha(p)
            for p in sorted((out / 'stage/boot/dtbs').rglob('*.dtb'))},
        config_SHA256=sha(out / '.config'), certificate_only_input=True,
        full_private_key_free_rebuild_passed=True, new_private_key_generated=False,
        signature_attachment_uses_actual_kernel_sign_file_s=True)
except BaseException as error:
    record.update(state='terminal failure', error_type=type(error).__name__, error=str(error))
    raise
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    record.pop('active_PID', None)
    record['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    record['finished_UTC'] = datetime.now(timezone.utc).isoformat()
    save()
print(json.dumps(dict(passed=record['passed'], release=record.get('release'),
    modules=record.get('modules_staged_and_verified'),
    private_key_free_rebuild=record.get('full_private_key_free_rebuild_passed'))))
