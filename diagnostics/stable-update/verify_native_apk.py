"""Pair exact native ARM verify rejections with an accepted signed archive."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

phase = Path('/runtime')
closure = json.loads((phase / 'dependency-closure.json').read_text())
manifest = json.loads((phase / 'runtime-manifest.json').read_text())
root = Path('/work/root')
(root / 'usr/lib').mkdir(parents=True)
(root / 'usr/sbin').mkdir()
(root / 'lib').symlink_to('usr/lib')
(root / 'sbin').symlink_to('usr/sbin')
assert hashlib.sha256((phase / 'runtime-libraries.tar.gz').read_bytes()).hexdigest() == closure['runtime_archive_sha256']
with tarfile.open(phase / 'runtime-libraries.tar.gz', 'r:gz') as archive:
    for name, row in manifest['paths'].items():
        path = root / name.lstrip('/')
        assert path.parent in {root / 'usr/lib', root / 'usr/sbin'}
        if row['kind'] == 'file':
            data = archive.extractfile(name.lstrip('/')).read()
            assert hashlib.sha256(data).hexdigest() == row['sha256']
            path.write_bytes(data)
            path.chmod(row['mode'])
        else:
            path.symlink_to(row['target'])
assert hashlib.sha256(Path('/qemu-arm-static').read_bytes()).hexdigest() == closure['emulator_sha256']
shutil.copyfile('/qemu-arm-static', root / '.qemu')
(root / '.qemu').chmod(0o700)
(root / 'etc/apk/keys').mkdir(parents=True)
for source in (phase / 'native-public-keys').iterdir():
    assert source.name.endswith('.pub') and source.is_file()
    shutil.copyfile(source, root / 'etc/apk/keys' / source.name)
(root / 'etc/apk/arch').write_text('armv7\n')
(root / 'archives').mkdir()
sources = dict(good=phase / 'runtime-packages/musl-1.2.6-r3.apk',
               altered_control=phase / 'runtime-package-verification/altered-control.apk',
               altered_payload=phase / 'runtime-package-verification/altered-payload.apk')
program = ['chroot', str(root), '/.qemu', '/usr/sbin/apk']
version = subprocess.run(program + ['--version'], capture_output=True, text=True, check=True)
assert version.stdout.strip() == 'apk-tools 3.0.8-r0, compiled for armv7.'
results = []
for label, source in sources.items():
    shutil.copyfile(source, root / 'archives' / (label + '.apk'))
    child = subprocess.run(program + ['--no-network', '--keys-dir', '/etc/apk/keys',
                                      'verify', '/archives/' + label + '.apk'],
                           capture_output=True, text=True, timeout=30)
    text = child.stdout + child.stderr
    Path('/receipts/' + label + '.log').write_text(text)
    if label == 'good':
        assert child.returncode == 0, text
    elif label == 'altered_control':
        assert child.returncode != 0 and 'BAD signature' in text, text
    else:
        assert child.returncode != 0 and 'v2 package integrity error' in text, text
    results.append(dict(case=label, returncode=child.returncode, input_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
record = dict(scope='Exact signed native ARM APK3.0.8 verify under explicit QEMU, isolated filesystem and no network',
              version=version.stdout.strip(), results=results,
              signed_archive_accepted=True, valid_gzip_altered_control_signature_rejected=True,
              valid_tar_gzip_altered_payload_integrity_rejected=True,
              runtime_archive_sha256=closure['runtime_archive_sha256'],
              emulator_sha256=closure['emulator_sha256'], private_keys_read=False,
              native_changes=False, package_hooks_executed=False)
Path('/receipts/result.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
