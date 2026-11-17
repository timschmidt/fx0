# SPDX-License-Identifier: GPL-2.0-only
"""Reject L2 sequence, context and abort regressions by named assertions."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('l2_model', B / 'check-model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = m.model(a.source)
controls = []


def change(name, func, before, after, assertion):
    body = m.function(code, func)
    assert body.count(before) == 1 and before != after, name
    controls.append((name, code.replace(body, body.replace(before, after)), assertion))


change('RPM-program-selects-no-RPM', 'spm_8226_l2_set_mode',
    'starts[] = { 0, 0, 4, 26, 54 }', 'starts[] = { 0, 0, 4, 26, 26 }',
    'bank.registers[0x30/4]==(mode ? starts[mode]<<4|1 : 0)')
change('GDHS-program-selects-retention', 'spm_8226_l2_set_mode',
    'starts[] = { 0, 0, 4, 26, 54 }', 'starts[] = { 0, 0, 0, 26, 54 }',
    'bank.registers[0x30/4]==(mode ? starts[mode]<<4|1 : 0)')
change('enabled-readback-ignored', 'spm_8226_l2_disarm',
    'if (!read_ret && !control)', 'if (!read_ret)', '!bank.registers[0x30/4]&&operations<=4')
change('persistent-disarm-error-not-fatal', 'spm_8226_l2_set_mode',
    'if (ret)\n\t\tpanic("MSM8226 L2 disarm failed: %d", ret);',
    'if (ret)\n\t\treturn ret;', 'unknown disable state must not return')
change('failed-arm-not-disarmed', 'spm_8226_l2_set_mode',
    'if (spm_8226_l2_disarm(map))', 'if (false && spm_8226_l2_disarm(map))',
    '!bank.registers[0x30/4]')
change('persistent-entry-recovery-error-not-fatal', 'spm_8226_l2_set_mode',
    'panic("MSM8226 L2 entry recovery failed\\n");', 'return ret;',
    'unknown entry recovery must not return')
change('mode-write-readback-not-checked', 'spm_8226_l2_set_mode',
    'if (!ret && value != control)', 'if (false && !ret && value != control)',
    'bank.registers[0x30/4]==(starts[mode]<<4|1)')
change('controller-state-not-validated', 'spm_8226_l2_set_mode',
    'if ((value & masks[i]) != expected[i])', 'if (false && (value & masks[i]) != expected[i])',
    '==-EOPNOTSUPP')
change('lost-sequence-not-checked-before-arm', 'spm_8226_l2_set_mode',
    'ret = spm_8226_l2_sequence_verify(map);', 'ret = 0;', '==-EIO')
change('sequence-init-omitted-before-publication', 'spm_8226_l2_register',
    'ret = spm_8226_l2_sequence_init(map);', 'ret = 0;',
    'bank.registers[(0x80+4*i)/4]==spm_8226_l2_sequence[i]')
change('initial-control-guard-omitted', 'spm_8226_l2_sequence_init',
    'if (control)\n\t\treturn -EBUSY;\n\tret = regmap_read(map, 0x20, &avs);\n\tif (ret)\n\t\treturn ret;\n\tif (avs & 1)',
    'if (false && control)\n\t\treturn -EBUSY;\n\tret = regmap_read(map, 0x20, &avs);\n\tif (ret)\n\t\treturn ret;\n\tif (avs & 1)',
    '!writes&&!sequence_writes&&!publication_calls')
change('initial-AVS-guard-omitted', 'spm_8226_l2_sequence_init',
    'if (avs & 1)\n\t\treturn -EBUSY;', 'if (false && (avs & 1))\n\t\treturn -EBUSY;',
    '!writes&&!sequence_writes&&!publication_calls')
change('CPU0-IRQ-ownership-check-omitted', 'spm_set_l2_low_power_mode',
    'if (raw_smp_processor_id() || !irqs_disabled())',
    'if (false && (raw_smp_processor_id() || !irqs_disabled()))', '!operations')
change('secondary-CPU-check-omitted', 'spm_set_l2_low_power_mode',
    'if (mode != SPM_L2_MODE_DISABLED && num_online_cpus() != 1)',
    'if (false && mode != SPM_L2_MODE_DISABLED && num_online_cpus() != 1)', '!operations')
records = []
for name, mutated, assertion in controls:
    out = a.output / name
    result = m.run_code(mutated, out)
    stderr = (out / 'run.stderr').read_text()
    assert result['failures'] > 0 and assertion in stderr, (name, result, assertion, stderr)
    records.append(dict(name=name, rejected=True, failures=result['failures'], named_assertion=assertion))
result = dict(passed=True, controls=records, normal_LSan_and_failfast_ASan_UBSan=True,
    crashes_or_compiler_or_sanitizer_faults_do_not_count=True,
    only_synthetic_services=True, no_phone_network_radio_audio_or_firmware_execution=True)
(a.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(dict(passed=True, controls_rejected=len(records))))
