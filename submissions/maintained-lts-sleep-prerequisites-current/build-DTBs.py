# SPDX-License-Identifier: GPL-2.0-only
"""Compare all maintained MSM8226-family DTBs and validate the CPU contracts."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import signal
import subprocess

B = Path(__file__).resolve().parent
R = B.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
P = R / 'worktrees/linux-fx0-vfe-drain-02'
I = B.parent / 'cpu-stack-01'
D = B / 'DTBs-01'
D.mkdir(mode=0o700)
prefixes = ['qcom-msm8226', 'qcom-msm8926', 'qcom-msm8928', 'qcom-apq8026', 'qcom-apq8028']
names = sorted({p.with_suffix('.dtb').name for prefix in prefixes
                for p in (C / 'arch/arm/boot/dts/qcom').glob(prefix + '*.dts')})
new = 'qcom-msm8926-lg-madai-cpr.dtb'
assert len(names) == 17 and new in names
old_names = [n for n in names if n != new]
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C, text=True).strip() == '8d8cb579e4ba340a4bd943daca58dffa47aa2559'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
record = dict(passed=False, stages=[], names=names, baseline_names=old_names,
              baseline_is_pre_sleep_prerequisites_CPU_DTB_artifacts=True, baseline_source_head="8d8cb579e4ba340a4bd943daca58dffa47aa2559", phone_access=False,
              physical_acceptance=False, full_unfiltered_board_schema_acceptance=False)
child = None


def save():
    (D / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')


def run(label, source, out, arguments, timeout=300):
    global child
    env = os.environ | {'TMPDIR': str(out / 'tmp'), 'GIT_NO_LAZY_FETCH': '1'}
    with (D / (label + '.log')).open('xb') as log:
        child = subprocess.Popen(arguments, cwd=source, env=env, stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        record.update(state='running ' + label, active_PID=child.pid)
        save()
        code = child.wait(timeout=timeout)
    record.pop('active_PID', None)
    record['stages'].append(dict(label=label, returncode=code, log_SHA256=sha(D / (label + '.log'))))
    save()
    assert code == 0, label


try:
    prior = json.loads((I / 'DTBs-01/controller.json').read_text())
    assert prior['passed']
    baseline_out = I / 'DTBs-01/candidate-out'
    for name, digest in prior['DTBs']['candidate'].items():
        assert sha(baseline_out / 'arch/arm/boot/dts/qcom' / name) == digest
    builds = {'baseline': prior['DTBs']['candidate']}
    for label, source, selected in [('candidate', C, names)]:
        out = D / (label + '-out')
        out.mkdir()
        (out / 'tmp').mkdir()
        seed = (R / 'local/fx0-lts-production-current-01/native-02/arm-normal-out/.config'
                if label == 'baseline' else B / 'native-02/arm-normal-CPU-enabled-out/.config')
        (out / '.config').write_bytes(seed.read_bytes())
        make = ['make', 'O=' + str(out), 'ARCH=arm', 'LLVM=-21', 'W=1', '-j2']
        run(label + '-config', source, out, make + ['olddefconfig'])
        run(label + '-DTBs', source, out, make + ['qcom/' + n for n in selected])
        builds[label] = {n: sha(out / 'arch/arm/boot/dts/qcom' / n) for n in selected}
    unchanged = [n for n in names if n != new]
    assert len(unchanged) == 16 and all(builds['baseline'][n] == builds['candidate'][n] for n in unchanged)
    assert builds['baseline'][new] != builds['candidate'][new]
    warnings = {'baseline': prior['warnings']['candidate'], 'candidate': [l.replace(str(C), '<source>').replace(str(D / 'candidate-out'), '<out>') for l in (D / 'candidate-DTBs.log').read_text().splitlines() if 'warning' in l.lower() or 'error:' in l.lower()]}
    assert Counter(warnings['baseline']) == Counter(warnings['candidate']), 'DTC diagnostic multiset changed'
    schema = B / 'bindings-01-out/Documentation/devicetree/bindings/processed-schema.json'
    validator = R / 'local/power-managed-port-01/schema-venv/bin/dt-validate'
    filters = ['opp/opp-v2-kryo-cpu.yaml', 'opp/opp-v2-qcom-level.yaml', 'power/avs/qcom,cpr.yaml',
               'regulator/qcom,spmi-regulator.yaml', 'soc/qcom/qcom,saw2.yaml', 'nvmem/qcom,qfprom.yaml', 'regulator/qcom,smd-rpm-regulator.yaml']
    checks = []
    for name in names:
        for index, selected in enumerate(filters):
            log = D / (name + '.schema-' + str(index) + '.log')
            q = subprocess.run([str(validator), '-s', str(schema), '-l', selected,
                                str(D / 'candidate-out/arch/arm/boot/dts/qcom' / name)],
                               capture_output=True, timeout=60)
            log.write_bytes(q.stdout + q.stderr)
            checks.append(dict(board=name, schema=selected, returncode=q.returncode,
                               log_SHA256=sha(log), silent=not q.stdout and not q.stderr))
    record.update(DTBs=builds, byte_identical_other_boards=unchanged,
                  warnings=warnings, schema_checks=checks, processed_schema_SHA256=sha(schema),
                  processed_schema_entries=len(json.loads(schema.read_text())),
                  candidate_ordinary_and_CPU_targets_built=True)
    save()
    assert all(x['returncode'] == 0 and x['silent'] for x in checks), 'CPU schema diagnostics retained'
    record.update(passed=True, state='terminal success')
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
    save()
print(json.dumps(dict(passed=True, baseline_DTBS=len(names), candidate_DTBS=len(names),
                     unchanged_other_boards=len(unchanged), selected_schema_checks=len(checks))))
