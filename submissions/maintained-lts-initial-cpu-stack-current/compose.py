# SPDX-License-Identifier: GPL-2.0-only
"""Reconcile the initial CPU stack against its exact original-parent sources."""
from pathlib import Path
import hashlib
import json
import subprocess

B = Path(__file__).resolve().parent
R = B.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
E = R / 'worktrees/linux-fx0-cpu-current-01'
plan = json.loads((B / 'prepared.json').read_text())
record_path = B / 'composition.json'
record = (json.loads(record_path.read_text()) if record_path.exists()
          else dict(base=plan['base'], completed=[], state='prepared', phone_access=False,
                    published=False, source_commits_not_yet_created=True))


def save():
    record_path.write_text(json.dumps(record, indent=2) + '\n')


def blob(commit, path):
    q = subprocess.run(['git', 'show', commit + ':' + path], cwd=E, capture_output=True)
    return q.stdout if q.returncode == 0 else b''


assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C, text=True).strip() == plan['base']
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=C)
for item in plan['origin_commits']:
    origin = item['commit']
    if origin.startswith('70db7a1d8440'):
        continue
    if any(row['origin_commit'] == origin for row in record['completed']):
        continue
    stage = B / 'stages' / origin[:12]
    stage.mkdir(parents=True, exist_ok=True)
    outputs = {}
    details = []
    for path in item['paths']:
        source = C / path
        ours = source.read_bytes() if source.exists() else b''
        base = blob(origin + '^', path)
        theirs = blob(origin, path)
        folder = stage / path
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in [('ours', ours), ('base', base), ('theirs', theirs)]:
            (folder / name).write_bytes(data)
        adjustments = []
        if ours == base:
            merged = theirs
        elif theirs == base or ours == theirs:
            merged = ours
        elif origin.startswith('57b4bd9ec2db') and path == 'arch/arm/boot/dts/qcom/Makefile':
            anchor = b'\tqcom-msm8926-lg-madai.dtb \\\n'
            assert ours.count(anchor) == 1 and b'qcom-msm8926-lg-madai-cpr.dtb' not in ours
            merged = ours.replace(anchor, anchor + b'\tqcom-msm8926-lg-madai-cpr.dtb \\\n')
            adjustments.append('Register the additional CPU target next to the ordinary board in the existing complete LTS list')
        elif origin.startswith('b920df1379ab') and path == 'drivers/soc/qcom/Kconfig':
            start = ours.index(b'config QCOM_SPM\n')
            end = ours.index(b'\nconfig ', start + 1)
            block = ours[start:end]
            assert block.count(b'\tselect QCOM_SCM\n') == 1 and b'MFD_SYSCON' not in block
            block = block.replace(b'\tselect QCOM_SCM\n', b'\tselect QCOM_SCM\n\tselect MFD_SYSCON\n')
            merged = ours[:start] + block + ours[end:]
            adjustments.append('Add MFD_SYSCON while retaining the LTS ARCH_QCOM/COMPILE_TEST dependency and QCOM_SCM select')
        elif origin.startswith('965b16234067') and path == 'drivers/cpufreq/cpufreq-dt-platdev.c':
            name = b'static bool __init cpu0_uses_msm8926_cpr(void)'
            start = theirs.index(name)
            helper = theirs[start:theirs.index(b'\n}', start) + 3]
            anchor = b'static int __init cpufreq_dt_platdev_init(void)'
            assert ours.count(anchor) == 1 and name not in ours
            merged = ours.replace(anchor, helper + b'\n' + anchor)
            anchor = b'\tmatch = of_match_node(allowlist, np);'
            assert merged.count(anchor) == 1
            guard = (b'\t/* Calibrated CPU/domain filtering must precede generic registration. */\n'
                     b'\tif (cpu0_uses_msm8926_cpr())\n\t\treturn -ENODEV;\n\n')
            merged = merged.replace(anchor, guard + anchor)
            adjustments.append('Insert the calibrated-OPP route guard while retaining LTS root-node lookup and allowlist/blocklist APIs')
        elif path == 'drivers/pmdomain/qcom/cpr-voltage.h':
            assert origin.startswith('68cc2620dd9e') and not base
            assert b'struct cpr_voltage {' in ours and b'cpr_voltage_set(' in theirs
            merged = theirs
            adjustments.append('Replace the older fork helper with the incoming retained/reconciled MX helper; complete consumer is included in this batch')
        elif path == 'drivers/pmdomain/qcom/cpr.c':
            assert origin.startswith('4569dae3b158')
            # Before this port the only differences from the exact parent are
            # the fork rails wrapper and pointer-vs-flexible-array allocation.
            # The incoming implementation retains rails and uses a checked flexible-array allocation.
            assert b'struct cpr_voltage\trails;' in ours
            assert b'struct cpr_voltage\trails;' in theirs
            assert b'cpr_voltage_set(' in theirs and b'cpr_voltage_bootstrap(' in theirs
            assert b'devm_kcalloc' in theirs and b'cpr_msm8926_read_calibration' in theirs
            assert b'struct fuse_corner\tfuse_corners[];' in theirs
            assert b'struct_size(drv, fuse_corners, data->cpr_desc->num_fuse_corners)' in theirs
            merged = theirs
            allocation = (b'drv = devm_kzalloc(dev,\n'
                          b'\t\t\tstruct_size(drv, fuse_corners, data->cpr_desc->num_fuse_corners),\n'
                          b'\t\t\tGFP_KERNEL);')
            assert allocation in merged
            merged = merged.replace(allocation, allocation.replace(b'\n\t\t\t', b'\n\t\t\t   '))
            adjustments.append('Incoming complete domain retains the fork rails wrapper and reconciles separate fuse allocation into the checked flexible-array allocation; original-parent comparison retained')
        else:
            q = subprocess.run(['git', 'merge-file', '--diff3', '-p', str(folder / 'ours'),
                                str(folder / 'base'), str(folder / 'theirs')], capture_output=True)
            (folder / 'merge.stdout').write_bytes(q.stdout)
            (folder / 'merge.stderr').write_bytes(q.stderr)
            if q.returncode:
                record.update(state='needs reconciliation', blocked_origin=origin,
                              blocked_path=path, merge_returncode=q.returncode)
                save()
                print(json.dumps(dict(origin=origin, path=path, returncode=q.returncode)))
                raise SystemExit(2)
            merged = q.stdout
            adjustments.append('Clean three-way merge against the exact original parent; preserve LTS context')
        if origin.startswith('76068f3c6a4e') and path.endswith('qcom_spmi-regulator.c'):
            for old, new in [
                    (b'devm_kzalloc_obj(dev, *vreg_list)', b'devm_kzalloc(dev, sizeof(*vreg_list), GFP_KERNEL)'),
                    (b'devm_kzalloc_obj(dev, *vreg)', b'devm_kzalloc(dev, sizeof(*vreg), GFP_KERNEL)')]:
                assert merged.count(old) == 1
                merged = merged.replace(old, new)
            adjustments.append('Keep the two LTS devm_kzalloc calls; typed allocation refactor is unavailable in 6.18')
        assert b'<<<<<<<' not in merged and b'>>>>>>>' not in merged
        outputs[path] = merged
        (folder / 'after').write_bytes(merged)
        details.append(dict(path=path, before_SHA256=hashlib.sha256(ours).hexdigest(),
                            original_parent_SHA256=hashlib.sha256(base).hexdigest(),
                            original_after_SHA256=hashlib.sha256(theirs).hexdigest(),
                            after_SHA256=hashlib.sha256(merged).hexdigest(), adjustments=adjustments))
    for path, data in outputs.items():
        target = C / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    record['completed'].append(dict(origin_commit=origin, subject=item['subject'], files=details))
    record.update(state='composed ' + origin[:12])
    record.pop('blocked_origin', None)
    record.pop('blocked_path', None)
    save()
    print(origin[:12], item['subject'])
record.pop('deferred_board_target_commit', None)
record.update(state='all selected source changes composed', passed=True,
              board_target_included=True, newer_typed_allocation_refactor_not_applied=True)
save()
