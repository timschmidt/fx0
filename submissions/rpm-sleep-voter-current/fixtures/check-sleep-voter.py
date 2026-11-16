# SPDX-License-Identifier: GPL-2.0-only
"""Compose exact three-voter/CPR sleep bodies with synthetic kernel services."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('boot', B / 'check-boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


def model(source, transport, cpu):
    code, bindings = boot.model(source, transport, cpu)
    code = code[:code.index('int main(void)\n{')]
    code = '#include <setjmp.h>\n' + code
    code = code.replace('static bool boot_safety;', 'static bool boot_safety, sleep_safety;\nstatic unsigned fault_span;')
    code = code.replace('alloc_calls == fault_at ? fault_mode : FAST',
        '(fault_at && alloc_calls >= fault_at && alloc_calls < fault_at + (fault_span ? fault_span : 1)) ? fault_mode : FAST')
    marker = 'if (boot_safety && state == QCOM_SMD_RPM_ACTIVE_STATE)'
    assert code.count(marker) == 1
    code = code.replace(marker, '''if (sleep_safety && state == QCOM_SMD_RPM_SLEEP_STATE)
            EXPECT(proposed.enabled && proposed.uV >= apc_voltage);
        ''' + marker)
    code = code.replace('struct qcom_rpm_reg vreg[2];', 'struct qcom_rpm_reg vreg[3];')
    code = code.replace('struct regulator_dev rdev[2];', 'struct regulator_dev rdev[3];')
    code = code.replace('struct regulator normal, ao, apc;', 'struct regulator normal, ao, so, apc;')
    code = code.replace('bool boot_apc, boot_on, always_on;', 'bool boot_apc, boot_on, always_on, sleep_supply;')
    marker = '    CHECK(!strcmp(name, "qcom,boot-apc-supply")); return node->boot_apc;'
    assert code.count(marker) == 1
    code = code.replace(marker, '    if (!strcmp(name, "vdd-mx-sleep-supply")) return node->sleep_supply;\n' + marker)
    marker = 'static struct regulator *devm_regulator_get(struct device *dev, const char *id)'
    assert code.count(marker) == 1
    code = code.replace(marker, '''static struct regulator *devm_regulator_get(struct device *, const char *);
static struct regulator *boot_devm_regulator_get(struct device *dev, const char *id)''')
    old = boot.pair.legacy.function(code, 'regulator_enable')
    code = code.replace(old, old.replace('return rpm_reg_enable(reg->rdev);', '''int ret = rpm_reg_enable(reg->rdev);
    if (!ret && ((struct qcom_rpm_reg *)reg->rdev->data)->sleep_only) ++reg->enable_count;
    return ret;'''))
    code = code.replace('#define panic(...) CHECK(!"unexpected recovery panic")', '''static jmp_buf fatal_target;
static bool expect_fatal;
static unsigned fatal_calls;
#define panic(...) do { CHECK(expect_fatal); ++fatal_calls; longjmp(fatal_target, 1); } while (0)''')
    services = (B / 'sleep-voter-services.c').read_text()
    header = (cpu / 'drivers/pmdomain/qcom/cpr-sleep.h').read_text()
    core = (source / 'drivers/regulator/core.c').read_text()
    resume = boot.pair.legacy.function(core, 'regulator_resume')
    code = code.replace('struct regulator_ops {', 'struct regulator_ops {\n    int (*resume)(struct regulator_dev *);')
    code += resume
    bindings['regulator_resume'] = hashlib.sha256(resume.encode()).hexdigest()
    names = ['cpr_sleep_vote_disable', 'cpr_sleep_vote_init']
    bodies = ''.join(boot.pair.legacy.function(header, n) for n in names)
    code += services.replace('/* ACTUAL_SLEEP_CLIENT */', bodies)
    code += (B / 'sleep-voter-model.c').read_text()
    for name in names:
        body = boot.pair.legacy.function(header, name)
        assert body == boot.pair.legacy.function(code, name)
        bindings[name] = hashlib.sha256(body.encode()).hexdigest()
    return code, bindings


def run(source, transport, cpu, output):
    code, bindings = model(source, transport, cpu)
    report = boot.pair.run_code(code, output)
    report.update(actual_function_and_table_bindings=bindings,
        actual_callback_and_client_bodies_byte_exact=True,
        generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        normal_LSan_and_failfast_ASan_UBSan=True,
        synthetic_OF_devres_reference_counts_locks_RPMsg_and_firmware=True,
        firmware_KVP_atomicity_not_assumed_or_qualified=True,
        PM_callback_failure_does_not_require_resume=True,
        physical_sleep_or_global_collapse_qualified=False,
        no_phone_radio_audio_network_or_firmware_execution=True)
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['failures'] == 0, report
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--transport-source', required=True, type=Path)
    p.add_argument('--cpu-source', required=True, type=Path)
    a = p.parse_args()
    r = run(a.source, a.transport_source, a.cpu_source, a.output)
    print(json.dumps({k:r[k] for k in ['cases', 'checks', 'failures']}))
