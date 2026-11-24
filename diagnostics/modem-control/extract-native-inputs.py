#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Select GPL r50 kernel/modules from the already-audited local backup, without a phone."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    with args.backup.open('rb') as stream:
        archive_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert archive_sha == 'abbaed40f197afa6fd49d0eead6f68b62479ae7e7422faffb500032ea18ac5cb'
    args.output.mkdir(mode=0o700, exist_ok=False)
    with tarfile.open(args.backup) as archive:
        prefix = 'usr/lib/modules/6.18.59-fx0-dmp/'
        dependencies = archive.extractfile(prefix + 'modules.dep').read().decode()
        graph = {row.split(':', 1)[0]: row.split(':', 1)[1].split() for row in dependencies.splitlines()}
        order, active = [], set()
        def visit(name):
            assert name not in active
            if name in order:
                return
            assert name.startswith('kernel/') and name.endswith('.ko.zst') and '..' not in Path(name).parts
            active.add(name)
            for child in graph[name]:
                visit(child)
            active.remove(name)
            order.append(name)
        visit('kernel/drivers/remoteproc/qcom_q6v5_mss.ko.zst')
        assert len(order) == 5
        selected = ['boot/vmlinuz', 'boot/System.map', 'boot/config', prefix + 'modules.dep',
                    *[prefix + name for name in order]]
        files = {}
        for name in selected:
            member = archive.getmember(name)
            assert member.isfile()
            data = archive.extractfile(member).read()
            path = args.output / 'retained-r50' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    assert files['boot/vmlinuz']['sha256'] == '7e896bb7c3fc80d7d8c8306a659fa57c1bcb3924ec2aaf37b77924e23c274417'
    result = {'archive_sha256': archive_sha, 'release': '6.18.59-fx0-dmp',
              'dependency_order': order, 'files': files,
              'extract_scope': 'Existing audited host backup: GPL kernel, public metadata and exactly dependency-closed signed modules; no firmware, calibration or key bytes'}
    (args.output / 'retained-inputs.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Selected native kernel, map/config and five dependency-closed modules; no device access.')


if __name__ == '__main__':
    main()
