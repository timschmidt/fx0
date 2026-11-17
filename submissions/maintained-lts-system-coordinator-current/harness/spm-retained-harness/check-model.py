# SPDX-License-Identifier: GPL-2.0-only
"""Compose actual CPU SPM, probe and CPU-idle bodies with logical services."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('support', B / 'model-support.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def macro(text, name):
    lines = text[text.index('#define ' + name + '('):].splitlines(keepends=True)
    result = ''
    for line in lines:
        result += line
        if not line.rstrip().endswith('\\'):
            return result
    raise AssertionError(name)


def model(source):
    driver = (source / 'drivers/soc/qcom/spm.c').read_text()
    idle = (source / 'drivers/cpuidle/cpuidle-qcom-spm.c').read_text()
    public = (source / 'include/soc/qcom/spm.h').read_text()
    cpuidle = (source / 'include/linux/cpuidle.h').read_text()
    header = (source / 'include/linux/firmware/qcom/qcom_scm.h').read_text()
    code = (B / 'model-services.c').read_text()
    defines = '\n'.join(line for line in driver.splitlines() if
        line.startswith(('#define SPM_CTL_', '#define MAX_PMIC_DATA', '#define MAX_SEQ_DATA')))
    code = code.replace('/* ACTUAL_DEFINES */', defines)
    types = m.block(public, r'^enum pm_sleep_mode \{')
    types += m.block(driver, r'^enum spm_reg \{')
    types += m.block(driver, r'^struct spm_reg_data \{')
    types += m.block(driver, r'^struct spm_driver_data \{')
    code = code.replace('/* ACTUAL_TYPES */', types)
    tables = driver[driver.index('static const u16 spm_reg_offset_v4_1'):
        driver.index('static inline void spm_register_write(')]
    code = code.replace('/* ACTUAL_CATALOGUES */', tables)
    names = ['spm_register_write', 'spm_register_write_sync', 'spm_register_read',
             'spm_force_disable', 'spm_set_low_power_mode', 'spm_msm8226_cpu_ready']
    code = code.replace('/* ACTUAL_CPU_FUNCTIONS */', ''.join(m.function(driver, n) for n in names))
    match = m.block(driver, r'^static const struct of_device_id spm_match_table\[\] = \{')
    code = code.replace('/* ACTUAL_MATCH_TABLE */', match)
    code = code.replace('/* ACTUAL_PROBE */', m.function(driver, 'spm_dev_probe'))
    macros = ''.join(macro(cpuidle, n) for n in ['__CPU_PM_CPU_IDLE_ENTER', 'CPU_PM_CPU_IDLE_ENTER_PARAM'])
    code = code.replace('/* ACTUAL_IDLE_MACROS */', macros)
    code = code.replace('/* ACTUAL_IDLE_DATA */', m.block(idle, r'^struct cpuidle_qcom_spm_data \{'))
    idle_names = ['qcom_pm_collapse', 'qcom_cpu_spc', 'spm_enter_idle_state',
                  'spm_cpuidle_get_spm', 'spm_cpuidle_register', 'spm_cpuidle_drv_probe']
    code = code.replace('/* ACTUAL_GET_CPU */', m.function(driver, 'spm_get_cpu'))
    code = code.replace('/* ACTUAL_IDLE_FUNCTIONS */', ''.join(m.function(idle, n) for n in idle_names))
    idle_setup = ''.join(m.block(idle, pat) for pat in [r'^static struct cpuidle_driver qcom_spm_idle_driver = \{',
        r'^static const struct of_device_id qcom_idle_state_match\[\] = \{'])
    code = code.replace('/* ACTUAL_IDLE_SETUP */', idle_setup)
    constant = re.search(r'^#define QCOM_SCM_CPU_PWR_DOWN_L2_ON[^\n]*', header, re.M).group(0)
    code = code.replace('/* ACTUAL_SCM_FLAG */', constant)
    code += (B / 'model-cases.c').read_text()
    bindings = {}
    for text, group in [(driver, names + ['spm_dev_probe','spm_get_cpu']), (idle, idle_names)]:
        for n in group:
            body = m.function(text, n)
            assert m.function(code, n) == body, n
            bindings[n] = hashlib.sha256(body.encode()).hexdigest()
    for n in ['__CPU_PM_CPU_IDLE_ENTER', 'CPU_PM_CPU_IDLE_ENTER_PARAM']:
        assert macro(code, n) == macro(cpuidle, n)
        bindings[n] = hashlib.sha256(macro(cpuidle, n).encode()).hexdigest()
    bindings['all_SPM_catalogues_and_offsets'] = hashlib.sha256(tables.encode()).hexdigest()
    bindings['spm_match_table'] = hashlib.sha256(match.encode()).hexdigest()
    bindings['idle_template_and_DT_match'] = hashlib.sha256(idle_setup.encode()).hexdigest()
    return code, bindings


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    code, bindings = model(a.source)
    report = m.run_code(code, a.output)
    report.update(actual_functions_macros_and_catalogues=bindings,
        all_actual_bodies_byte_exact=True, normal_LSan_and_failfast_ASan_UBSan=True,
        source_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        MMIO_CPU_suspend_SCM_CPU_PM_context_probe_regulator_and_devres_services_synthetic=True,
        successful_warm_resume_and_abort_are_synthetic_outcomes=True,
        MMIO_bus_fault_or_real_hardware_concurrency_not_qualified=True,
        full_CPU_APC_cache_L2_SCM_RPM_MPM_system_entry_not_qualified=True,
        no_phone_network_firmware_radio_or_audio_execution=True)
    (a.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['failures'] == 0, report
    print(json.dumps({k:report[k] for k in ['cases', 'checks', 'failures']}))
