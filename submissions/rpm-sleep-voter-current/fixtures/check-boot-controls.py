# SPDX-License-Identifier: GPL-2.0-only
"""Reject premature, lost and unvalidated APC boot-floor handoffs."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('boot', B / 'check-boot.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path); p.add_argument('output', type=Path)
p.add_argument('--transport-source', required=True, type=Path)
p.add_argument('--cpu-source', required=True, type=Path)
a = p.parse_args(); assert not a.output.exists(); a.output.mkdir()
code, _ = m.model(a.source, a.transport_source, a.cpu_source)
controls = []


def change(name, before, after, assertion):
    assert before != after, name
    if code.count(before) == 1:
        mutated = code.replace(before, after)
    else:
        pair_body = m.pair.legacy.function(code, 'rpm_reg_write_pair')
        assert pair_body.count(before) == 1, name
        mutated = code.replace(pair_body, pair_body.replace(before, after))
    controls.append((name, mutated, assertion))


change('boot-voltage-hold-omitted', '\t\tactive.uV = max(active.uV, pair->boot_uV);',
    '\t\tactive.uV = active.uV;', 'fw[0].enabled && fw[0].uV == 1337500')
change('boot-enable-hold-omitted', '.enabled = normal->enabled || active_only->enabled || pair->boot_uV,',
    '.enabled = normal->enabled || active_only->enabled,', 'proposed.enabled && proposed.uV >= apc_voltage')
change('enabled-request-below-APC-releases-hold', '\tboot_handoff = active_only->enabled &&\n\t\t       active_only->uV >= pair->boot_min_uV;',
    '\tboot_handoff = active_only->enabled;', 'fw[0].enabled && fw[0].uV == 1337500')
change('handoff-keeps-permanent-maximum', '\tif (boot_handoff)\n\t\tpair->boot_uV = 0;',
    '\t(void)boot_handoff;', 'fw[0].uV == 1287500 && fw[0].enabled')
change('failed-handoff-loses-hold', 'restore:\n\t/* Callers restore their cache and can force a fresh acknowledged vote. */',
    'restore:\n\tpair->boot_uV = 0;\n\t/* Callers restore their cache and can force a fresh acknowledged vote. */',
    'fw[0].enabled && fw[0].uV == 1337500')
change('APC-read-failure-ignored', '\tif (boot_uV <= 0)\n\t\treturn boot_uV ?: -EINVAL;',
    '\tif (boot_uV <= 0)\n\t\tboot_uV = min_uV;', '!live_count && !factory_registers && !wire_calls')
change('APC-above-MX-ceiling-accepted', '\tif (boot_uV > max_uV)\n\t\treturn -ERANGE;',
    '\tif (boot_uV > max_uV)\n\t\tboot_uV = max_uV;', '!live_count && !factory_registers && !wire_calls')
change('APC-handoff-threshold-rounded-down', 'DIV_ROUND_UP(max_t(int, boot_uV, min_uV), 12500) * 12500',
    '(max_t(int, boot_uV, min_uV) / 12500) * 12500', 'proposed.enabled && proposed.uV >= apc_voltage')
change('disabled-cache-bypasses-boot-hold', '\t    !pair->boot_uV) {', '\t    true) {',
    'fw[0].enabled && fw[0].uV == 1337500')
change('core-boot-enable-can-release-hold', '\tif (of_property_read_bool(ao_node, "regulator-boot-on") ||\n\t    of_property_read_bool(ao_node, "regulator-always-on"))',
    '\tif (false && (of_property_read_bool(ao_node, "regulator-boot-on") ||\n\t    of_property_read_bool(ao_node, "regulator-always-on")))',
    '!live_count && !factory_registers && !wire_calls')
change('CPU-attach-skips-live-APC-recheck',
    '\tif (boot_uV < drv->corners[0].uV || boot_uV > data->plan.bootstrap_mx_uV)',
    '\tif (boot_uV < drv->corners[0].uV)', 'proposed.enabled && proposed.uV >= apc_voltage')
records = []
for name, mutated, assertion in controls:
    out = a.output / name
    report = m.pair.run_code(mutated, out)
    stderr = (out / 'run.stderr').read_text()
    assert report['failures'] > 0 and assertion in stderr, (name, report, assertion, stderr)
    records.append(dict(name=name, rejected=True, failures=report['failures'], named_assertion=assertion))
report = dict(passed=True, controls=records, normal_LSan_and_failfast_ASan_UBSan=True,
    no_hardware_phone_firmware_radio_audio_or_network_execution=True, deterministic_logical_services_only=True)
(a.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, controls_rejected=len(records))))
