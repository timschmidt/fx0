# SPDX-License-Identifier: GPL-2.0-only
"""Merge each system-sleep feature against its exact original-parent blobs."""
from pathlib import Path
import hashlib
import json
import subprocess

B = Path(__file__).resolve().parent
R = B.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
E = R / 'worktrees/linux-fx0-cpu-current-01'
plan = json.loads((B / 'prepared.json').read_text())
receipt = B / 'composition.json'
record = (json.loads(receipt.read_text()) if receipt.exists() else
          dict(base=plan['base'], completed=[], phone_access=False, published=False))


def save():
    receipt.write_text(json.dumps(record, indent=2) + '\n')


def blob(commit, path):
    q = subprocess.run(['git', 'show', commit + ':' + path], cwd=E, capture_output=True)
    return q.stdout if q.returncode == 0 else b''


assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C, text=True).strip() == plan['base']
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=C)
for item in plan['origin_commits']:
    origin = item['commit']
    if any(row['origin_commit'] == origin for row in record['completed']):
        continue
    outputs = {}
    details = []
    for path in item['paths']:
        target = C / path
        ours = target.read_bytes() if target.exists() else b''
        base, theirs = blob(origin + '^', path), blob(origin, path)
        folder = B / 'stages' / origin[:12] / path
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in [('ours', ours), ('base', base), ('theirs', theirs)]:
            (folder / name).write_bytes(data)
        if ours == base:
            merged = theirs
        elif ours == theirs or theirs == base:
            merged = ours
        elif path == 'arch/arm/boot/dts/qcom/Makefile' and origin.startswith('fc5120c4e0f2'):
            anchor = b'\tqcom-msm8926-lg-madai-cpr.dtb \\\n'
            assert ours.count(anchor) == 1
            assert b'qcom-msm8926-lg-madai-suspend.dtb' not in ours
            merged = ours.replace(anchor, anchor + b'\tqcom-msm8926-lg-madai-suspend.dtb \\\n')
        else:
            q = subprocess.run(['git', 'merge-file', '--diff3', '-p', str(folder / 'ours'),
                                str(folder / 'base'), str(folder / 'theirs')], capture_output=True)
            (folder / 'merge.stdout').write_bytes(q.stdout)
            (folder / 'merge.stderr').write_bytes(q.stderr)
            if q.returncode:
                record.update(state='needs reconciliation', origin=origin, path=path)
                save()
                print(json.dumps(dict(origin=origin, path=path, returncode=q.returncode)))
                raise SystemExit(2)
            merged = q.stdout
        if path == 'drivers/regulator/qcom_smd-regulator.c':
            merged = merged.replace(b'devm_kzalloc_obj(dev, *pair)', b'devm_kzalloc(dev, sizeof(*pair), GFP_KERNEL)')
        if path == 'drivers/soc/qcom/msm8226-pm.c':
            merged = merged.replace(b'#include <asm/cacheflush.h>', b'#include <linux/cacheflush.h>')
        assert b'<<<<<<<' not in merged and b'>>>>>>>' not in merged
        (folder / 'after').write_bytes(merged)
        outputs[path] = merged
        details.append(dict(path=path, before_SHA256=hashlib.sha256(ours).hexdigest(),
                            original_parent_SHA256=hashlib.sha256(base).hexdigest(),
                            original_after_SHA256=hashlib.sha256(theirs).hexdigest(),
                            after_SHA256=hashlib.sha256(merged).hexdigest(),
                            existing_LTS_context_preserved=True))
    for path, data in outputs.items():
        target = C / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    record['completed'].append(dict(origin_commit=origin, subject=item['subject'], files=details))
    record.update(state='composed ' + origin[:12])
    save()
    print(origin[:12], item['subject'])
record.update(passed=True, state='all source changes composed')
save()
