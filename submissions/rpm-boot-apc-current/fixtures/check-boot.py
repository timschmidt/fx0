# SPDX-License-Identifier: GPL-2.0-only
"""Compose the actual boot guard, provider factory, voltage constraints and CPR."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pair', B / 'check-pair.py')
pair = importlib.util.module_from_spec(spec); spec.loader.exec_module(pair)


def model(source, transport, cpu):
    code, bindings = pair.model(source, transport, cpu)
    core = (source / 'drivers/regulator/core.c').read_text()
    constraint = pair.legacy.function(core, 'machine_constraints_voltage')
    code = code.replace('    int type;\n};', '    int type;\n    int n_voltages;\n    bool continuous_voltage_range;\n};')
    code = code.replace('struct regulation_constraints {', '''struct regulation_constraints {
    int min_uV, max_uV;
    bool apply_uV;''')
    services = (B / 'boot-services.c').read_text().replace('/* ACTUAL_MACHINE_CONSTRAINTS */', constraint)
    marker = '/* Logical OF/devres/registration services for the exact provider factory. */'
    assert code.count(marker) == 1
    code = code.replace(marker, services + '\n' + marker)
    marker = '    registered[live_count++] = rdev;'
    assert code.count(marker) == 1
    code = code.replace(marker, '''    if (machine_registration) {
        unsigned slot = live_count;
        CHECK(slot < 8);
        machine_constraints[slot] = (struct regulation_constraints){
            .min_uV = config->of_node->min_uV,
            .max_uV = config->of_node->max_uV,
            .apply_uV = true,
        };
        rdev->constraints = &machine_constraints[slot];
        rdev->desc->n_voltages = 64;
        expected_pair = ((struct qcom_rpm_reg *)rdev->data)->pair;
        int ret = machine_constraints_voltage(rdev, rdev->constraints);
        if (ret) return ERR_PTR(ret);
    }
''' + marker)
    # Check the firmware-state abstract machine after every applied ACTIVE write.
    marker = 'if (current_fault == FAST || (uncertain && apply_uncertain)) fw[state] = proposed;'
    assert code.count(marker) == 1
    code = code.replace(marker, '''if (current_fault == FAST || (uncertain && apply_uncertain)) {
        if (boot_safety && state == QCOM_SMD_RPM_ACTIVE_STATE)
            EXPECT(proposed.enabled && proposed.uV >= apc_voltage);
        fw[state] = proposed;
    }''')
    code = code.replace('static unsigned cases, checks, failures, alloc_calls, wire_calls;',
                        'static bool boot_safety;\nstatic unsigned cases, checks, failures, alloc_calls, wire_calls;')
    cpr = (cpu / 'drivers/pmdomain/qcom/cpr.c').read_text()
    controller = pair.legacy.function(cpr, 'cpr_msm8926_bootstrap_clock')
    clock = (B / 'boot-clock-services.c').read_text().replace('/* ACTUAL_BOOTSTRAP_CLOCK */', controller)
    code = code[:code.index('int main(void)\n{')] + clock + (B / 'boot-model.c').read_text()
    assert pair.legacy.function(code, 'machine_constraints_voltage') == constraint
    bindings['machine_constraints_voltage'] = hashlib.sha256(constraint.encode()).hexdigest()
    assert pair.legacy.function(code, 'cpr_msm8926_bootstrap_clock') == controller
    bindings['cpr_msm8926_bootstrap_clock'] = hashlib.sha256(controller.encode()).hexdigest()
    return code, bindings


def run(source, transport, cpu, output, baseline=False):
    code, bindings = model(source, transport, cpu)
    report = pair.run_code(code, output)
    report.update(actual_function_and_table_bindings=bindings, callback_and_catalogue_bodies_byte_exact=True,
        generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        baseline=baseline, normal_LSan_and_failfast_ASan_UBSan=True,
        only_synthetic_OF_devres_regulator_RPMsg_firmware_state_and_locks=True,
        firmware_kernel_concurrency_and_hardware_qualified=False,
        full_deep_PM_handoff_qualified=False, no_device_audio_radio_or_network_execution=True)
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['failures'] > 0 if baseline else report['failures'] == 0, report
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--transport-source', required=True, type=Path)
    p.add_argument('--cpu-source', required=True, type=Path)
    p.add_argument('--baseline', action='store_true')
    a = p.parse_args()
    r = run(a.source, a.transport_source, a.cpu_source, a.output, a.baseline)
    print(json.dumps({k:r[k] for k in ['cases', 'checks', 'failures']}))
