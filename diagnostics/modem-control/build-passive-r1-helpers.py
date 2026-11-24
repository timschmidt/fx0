#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the exact passive-r1 helpers using authenticated userspace build roots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'diagnostics/modem-control/passive-r1-helpers'
LOCK = ROOT / 'manifests/passive-r1-helpers.json'
SOURCES = {'native-return.c', 'native-return-harness.c', 'qrtr-local-rmtfs.c', 'observer-test.c'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native-root', 'target-root', 'output-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    require(not sys.flags.optimize, 'Optimized Python is forbidden')
    native, target = args.native_root.resolve(), args.target_root.resolve()
    base = args.output_dir.absolute()
    lock = json.loads(LOCK.read_text())
    require(lock['format'] == 1 and set(lock['sources_SHA256']) == SOURCES, 'Unexpected helper lock')
    for kind, path in [('native', native), ('target', target)]:
        require(sha(path / 'lib/apk/db/installed') == lock[kind + '_database_SHA256'],
                'Root database differs from authenticated profile')
    for name, expected in lock['sources_SHA256'].items():
        require(sha(SOURCE / name) == expected, 'Public helper source differs')
    for name, expected in lock['target_link_inputs_SHA256'].items():
        path = (target / name.removeprefix('/target/')).resolve()
        require(path.is_relative_to(target) and sha(path) == expected, 'Target link input differs')
    # Each attempt owns a new directory. No previous attempt or toolchain is modified.
    base.mkdir(mode=0o700, exist_ok=False)
    for name in ('inputs', 'one', 'two', 'checks', 'tmp'):
        (base / name).mkdir(mode=0o700)
    for name in SOURCES:
        shutil.copyfile(SOURCE / name, base / 'inputs' / name)
    prefix = ['bwrap', '--unshare-all', '--die-with-parent', '--clearenv']
    for name in ('usr', 'lib', 'bin', 'sbin'):
        prefix += ['--ro-bind', str(native / name), '/' + name]
    prefix += ['--ro-bind', str(target), '/target', '--bind', str(base), '/work',
               '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp',
               '--setenv', 'PATH', '/usr/bin:/bin', '--chdir', '/work']
    compiler = ['/usr/bin/clang', '--target=armv7-alpine-linux-musleabihf',
                '--sysroot=/target', '--gcc-toolchain=/target/usr', '-fuse-ld=lld',
                '-static', '-Os', '-Wall', '-Wextra', '-Werror',
                '-fstack-protector-strong', '-I/work/inputs']
    report = {'builds': [], 'checks': [], 'phone_access': False, 'passed': False}
    env = os.environ | {'TMPDIR': str(base / 'tmp')}

    def save():
        (base / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n')

    save()
    for directory, name, source in [
        ('one', 'native-return', 'native-return.c'),
        ('one', 'qrtr-local-rmtfs', 'qrtr-local-rmtfs.c'),
        ('two', 'native-return', 'native-return.c'),
        ('two', 'qrtr-local-rmtfs', 'qrtr-local-rmtfs.c'),
        ('checks', 'native-return-harness', 'native-return-harness.c'),
        ('checks', 'observer-test', 'observer-test.c'),
    ]:
        command = prefix + compiler + ['-Wl,-t', '-Wl,-Map=/work/' + directory + '/' + name + '.map',
                                      '/work/inputs/' + source, '-o', '/work/' + directory + '/' + name]
        result = subprocess.run(command, capture_output=True, timeout=120, env=env)
        (base / directory / (name + '-build.log')).write_bytes(result.stdout + result.stderr)
        report['builds'].append({'directory': directory, 'name': name, 'returncode': result.returncode})
        save()
        require(result.returncode == 0, 'Helper compiler failed; retain attempt and inspect build log')
        linked = {}
        for line in result.stdout.decode().splitlines():
            item = line.split('(', 1)[0].strip()
            if item.startswith('/target/'):
                path = (target / item.removeprefix('/target/')).resolve()
                require(path.is_relative_to(target), 'Linker input escapes target root')
                linked['/target/' + str(path.relative_to(target))] = sha(path)
        require(linked == lock['target_link_inputs_SHA256'], 'Unexpected target link cohort')
        binary = base / directory / name
        if directory in ('one', 'two'):
            require(sha(binary) == lock['binaries'][name]['SHA256'] and
                    binary.stat().st_size == lock['binaries'][name]['bytes'], 'Helper binary differs')
        report['builds'][-1].update({'SHA256': sha(binary), 'target_link_inputs_SHA256': linked})
        save()
    runner = ['bwrap', '--unshare-all', '--die-with-parent', '--clearenv',
              '--ro-bind', '/usr/bin/qemu-arm-static', '/qemu', '--bind', str(base), '/work',
              '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp', '--chdir', '/work', '/qemu']
    for label, arguments, expected in [
        ('return-controls', ['/work/checks/native-return-harness'], 0),
        ('observer-classifier', ['/work/checks/observer-test'], 0),
        ('return-invalid-cli', ['/work/one/native-return', '--invalid'], 1),
        ('observer-invalid-cli', ['/work/one/qrtr-local-rmtfs', 'invalid'], 2),
    ]:
        result = subprocess.run(runner + arguments, capture_output=True, timeout=15, env=env)
        (base / (label + '.log')).write_bytes(result.stdout + result.stderr)
        report['checks'].append({'case': label, 'returncode': result.returncode, 'expected': expected})
        save()
        require(result.returncode == expected, 'QEMU helper control failed')
    for kind, path in [('native', native), ('target', target)]:
        require(sha(path / 'lib/apk/db/installed') == lock[kind + '_database_SHA256'],
                'Build root database changed')
    for name in lock['binaries']:
        require((base / 'one' / name).read_bytes() == (base / 'two' / name).read_bytes(),
                'Helper pair differs')
    report['passed'] = True
    save()
    print(json.dumps({'passed': True, 'compiler_jobs': len(report['builds']),
                      'QEMU_controls': len(report['checks']), 'phone_access': False}))


if __name__ == '__main__':
    main()
