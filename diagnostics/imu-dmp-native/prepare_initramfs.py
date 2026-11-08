#!/usr/bin/env python3
"""Generate a native-DMP trial initramfs in a private mount namespace, without invoking the real boot-deploy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_file', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('--module-tree', type=Path, help='private candidate release directory to mount over the module search path')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('run on the phone as root')
    release_file = args.release_file.resolve(strict=True)
    release = release_file.read_text().strip()
    if not re.fullmatch(r'6\.18\.59-fx0-dmp(?:-candidate[-a-zA-Z0-9.]*)?', release):
        parser.error('expected the Fx0 DMP candidate kernel release')
    output = args.output_directory.resolve()
    if not output.is_relative_to('/var/lib/fx0-diagnostics') or output == Path('/var/lib/fx0-diagnostics'):
        parser.error('output must be a new directory below /var/lib/fx0-diagnostics')
    metadata = list(Path('/usr/share/kernel').glob('*/kernel.release'))
    if len(metadata) != 1:
        parser.error('expected one installed kernel flavor')
    metadata = metadata[0].resolve(strict=True)
    original = metadata.read_bytes()
    installed_modules = Path('/lib/modules').resolve(strict=True)
    installed_entries = sorted(p.name for p in installed_modules.iterdir())
    modules = installed_modules / release
    if args.module_tree is not None:
        modules = args.module_tree.resolve(strict=True)
        if modules.name != release or not modules.is_relative_to('/var/lib/fx0-diagnostics'):
            parser.error('--module-tree must be a matching release directory below /var/lib/fx0-diagnostics')
    for name in ('modules.dep', 'modules.builtin'):
        if not (modules / name).is_file():
            parser.error(f'candidate modules are not staged: {modules / name}')
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    boot_deploy = Path(shutil.which('boot-deploy') or '/missing-boot-deploy').resolve(strict=True)
    capture = output / 'capture-boot-deploy'
    capture.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nimport shutil, sys\nargs = sys.argv[1:]\nsource = Path(args[args.index('-d') + 1])\noutput = Path(args[args.index('-o') + 1])\nfor name in ('initramfs', 'initramfs-extra'):\n    if (source / name).is_file():\n        shutil.copyfile(source / name, output / name)\n(output / 'boot-deploy-intercepted').write_text('archive capture only\\n')\n")
    capture.chmod(0o700)
    # mkinitfs deletes its work directory even with -no-bootdeploy. Intercept
    # its deployment call inside the private namespace to retain the archive.
    command = ['unshare', '--mount', '--propagation', 'private', 'sh', '-eu', '-c',
               'mount --bind "$1" "$2"; mount --bind "$4" "$5"; '
               'if [ -n "$6" ]; then mount --bind "$6" "$7"; fi; exec mkinitfs -d "$3"',
               'fx0-native-initramfs', str(release_file), str(metadata), str(output),
               str(capture), str(boot_deploy),
               str(modules.parent) if args.module_tree is not None else '', str(installed_modules)]
    try:
        with (output / 'mkinitfs.log').open('xb') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    finally:
        if metadata.read_bytes() != original:
            raise RuntimeError('installed kernel metadata changed outside namespace')
        if sorted(p.name for p in installed_modules.iterdir()) != installed_entries:
            raise RuntimeError('installed module directory entries changed outside namespace')
    if result.returncode:
        raise RuntimeError(f'mkinitfs failed ({result.returncode}); see {output / "mkinitfs.log"}')
    if not (output / 'boot-deploy-intercepted').is_file():
        raise RuntimeError('archive capture shim was not invoked')
    archive = output / 'initramfs'
    if not archive.is_file() or archive.stat().st_size == 0:
        raise RuntimeError('mkinitfs did not produce a nonempty initramfs')
    manifest = {'kernel_release': release, 'installed_metadata_unchanged': True,
                'installed_metadata_sha256': hashlib.sha256(original).hexdigest(),
                'initramfs_bytes': archive.stat().st_size,
                'initramfs_sha256': sha256(archive),
                'modules_dep_sha256': sha256(modules / 'modules.dep'),
                'real_boot_deploy_invoked': False, 'boot_deploy_intercepted': True,
                'private_module_tree': args.module_tree is not None,
                'installed_module_entries_unchanged': True}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
