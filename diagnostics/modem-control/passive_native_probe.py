# SPDX-License-Identifier: MIT
from pathlib import Path
import hashlib, json, subprocess

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def output(*command):
    return subprocess.run(command, capture_output=True, text=True, timeout=15).stdout.strip()
def main():
    source = Path('/usr/lib/modules/6.18.63-fx0-vibrator-alpine')
    module_rows = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    if len(module_rows) != 478:raise RuntimeError('Unexpected accepted-r1 module membership')
    print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        kernel=Path('/proc/sys/kernel/osrelease').read_text().strip(),
        kernel_notes_SHA256=sha('/sys/kernel/notes'), taint=int(Path('/proc/sys/kernel/tainted').read_text()),
        trial=any(word.startswith('fx0.native_trial=') for word in Path('/proc/cmdline').read_text().split()),
        boot_partition_sha256=sha('/dev/mmcblk0p15'),
        files_sha256={p:sha(p) for p in ['/lib/apk/db/installed','/etc/apk/world','/etc/apk/repositories','/boot/boot.img','/boot/initramfs']},
        installed_DB_sha256=sha('/lib/apk/db/installed'), world_sha256=sha('/etc/apk/world'),
        module_tree_digest=hashlib.sha256(json.dumps(module_rows,sort_keys=True).encode()).hexdigest(),
        modules_FSType=output('findmnt','-n','-o','FSTYPE','-T','/usr/lib/modules'),
        systemd=output('systemctl','is-system-running'), Sway=output('pgrep','-x','sway'), gesture=output('pgrep','-x','lisgd'),
        uptime=float(Path('/proc/uptime').read_text().split()[0]))))

if __name__ == '__main__':
    main()
