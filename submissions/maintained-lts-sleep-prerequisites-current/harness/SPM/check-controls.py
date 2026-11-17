# SPDX-License-Identifier: GPL-2.0-only
"""Reject CPU-SPM timeout, recovery, caller and admission regressions."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cpu_model', B / 'check-model.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = q.model(a.source)
controls = []


def change(name, func, before, after, assertion, count=1):
    body = q.m.function(code, func)
    assert body.count(before) == count and before != after, name
    controls.append((name, code.replace(body, body.replace(before, after)), assertion))


change('retry-bound-expanded-past-contract', 'spm_register_write_sync',
    'attempt < SPM_CTL_WRITE_RETRIES', 'attempt < SPM_CTL_WRITE_RETRIES * 4',
    'ret==(count<50 ? 0 : -ETIMEDOUT)')
change('mode-readback-discarded', 'spm_register_write_sync',
    'if ((value & mask) == (val & mask))', 'if (true || (value & mask) == (val & mask))',
    'ret==(count<50 ? 0 : -ETIMEDOUT)')
change('mode-error-skips-disable', 'spm_set_low_power_mode',
    'spm_force_disable(drv, saved_ctl);', '(void)saved_ctl;',
    '!(bank[control_offset()/4]&SPM_CTL_EN)')
change('disable-clears-inherited-bypass', 'spm_force_disable',
    'saved_ctl & ~SPM_CTL_EN, mask', 'saved_ctl & ~(SPM_CTL_EN | BIT(3)), mask',
    'initial&~(SPM_CTL_INDEX', count=2)
change('disable-keeps-enable-set', 'spm_force_disable',
    'saved_ctl & ~SPM_CTL_EN, mask', 'saved_ctl | SPM_CTL_EN, mask',
    '!(bank[control_offset()/4]&SPM_CTL_EN)', count=2)
change('disable-requires-stale-index', 'spm_force_disable',
    'u32 mask = ~(SPM_CTL_INDEX << SPM_CTL_INDEX_SHIFT);', 'u32 mask = ~0U;',
    '!fatal_calls&&reset_result==-ETIMEDOUT')
change('unsupported-zero-index-accepted', 'spm_set_low_power_mode',
    'if (mode != PM_SLEEP_MODE_STBY && !start_index)',
    'if (false && mode != PM_SLEEP_MODE_STBY && !start_index)',
    'ret==(supported ? 0 : -EOPNOTSUPP)')
change('out-of-field-index-accepted', 'spm_set_low_power_mode',
    'if (start_index > SPM_CTL_INDEX)', 'if (false && start_index > SPM_CTL_INDEX)',
    'spm_set_low_power_mode(&direct,PM_SLEEP_MODE_SPC)==-EINVAL')
table = q.m.block(code, r'^static const struct spm_reg_data spm_reg_8226_cpu  = \{')
assert table.count('.start_index[PM_SLEEP_MODE_PC] = 5,') == 1
pc_case = code[:code.index('int main(void)\n{')] + '''int main(void)
{
    cases=1; runtime_ready();
    int ret=spm_set_low_power_mode(&direct,PM_SLEEP_MODE_PC);
    EXPECT(ret==0);
    EXPECT((bank[control_offset()/4]&(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT|SPM_CTL_EN))==(5U<<4|1));
    preserved(0x8009);
    printf("{\\"cases\\":1,\\"checks\\":%u,\\"failures\\":%u}\\n",checks,failures);
    return 0;
}
'''
positive = q.m.run_code(pc_case, a.output / 'PC-alias-positive')
assert positive['failures'] == 0
controls.append(('MSM8226-PC-alias-omitted', pc_case.replace(table, table.replace(
    '.start_index[PM_SLEEP_MODE_PC] = 5,', '.start_index[PM_SLEEP_MODE_PC] = 0,')),
    'ret==0'))
change('CPU-suspend-after-failed-SPC', 'qcom_cpu_spc',
    'if (ret)\n\t\treturn ret;', 'if (false && ret)\n\t\treturn ret;',
    'suspend_calls==(arm_failed ? 0U : 1U)')
change('standby-restore-omitted', 'qcom_cpu_spc',
    'restore_ret = spm_set_low_power_mode(drv, PM_SLEEP_MODE_STBY);', 'restore_ret = 0;',
    '(ctl>>SPM_CTL_INDEX_SHIFT)&SPM_CTL_INDEX')
change('standby-error-discarded', 'qcom_cpu_spc',
    'return ret ?: restore_ret;', '(void)restore_ret;\n\treturn ret;', 'ret==expected')
change('CPU-abort-error-discarded', 'qcom_cpu_spc',
    'return ret ?: restore_ret;', 'return restore_ret;', 'ret==expected')
change('probe-standby-error-discarded', 'spm_dev_probe',
    'if (ret)\n\t\t\treturn dev_err_probe(&pdev->dev, ret, "could not set standby\\n");',
    'if (false && ret)\n\t\t\treturn dev_err_probe(&pdev->dev, ret, "could not set standby\\n");',
    'ret==errors[scenario]&&!publication_calls&&!pdev.data')
body = q.m.function(code, 'spm_dev_probe')
assert body.count('platform_set_drvdata(pdev, drv);') == 2
early = body.replace('platform_set_drvdata(pdev, drv);', '')
early = early.replace('drv->dev = &pdev->dev;', 'drv->dev = &pdev->dev;\n\tplatform_set_drvdata(pdev, drv);')
controls.append(('probe-publishes-before-readiness', code.replace(body, early), '!publication_calls'))
change('probe-regulator-error-discarded', 'spm_dev_probe',
    'ret = spm_register_regulator(&pdev->dev, drv);\n\t\tif (ret)\n\t\t\treturn ret;',
    'ret = spm_register_regulator(&pdev->dev, drv);\n\t\t(void)ret;', 'ret==(failed ? -EIO : 0)')
macro = q.macro(code, '__CPU_PM_CPU_IDLE_ENTER')
assert macro.count('cpu_pm_exit();') == 1
controls.append(('CPU-PM-exit-unbalanced', code.replace(macro, macro.replace('cpu_pm_exit();', '(void)0;')),
    'ct_enters==pm_exits&&ct_exits==pm_exits&&!in_pm'))
preflight = '''for_each_present_cpu(cpu) {
		spm = spm_cpuidle_get_spm(cpu);
		if (IS_ERR(spm) && PTR_ERR(spm) != -ENODEV)
			return PTR_ERR(spm);
	}'''
change('supplier-preflight-omitted', 'spm_cpuidle_drv_probe', preflight, 'spm = NULL;\n\t(void)spm;',
    '!warm_calls&&!registration_calls&&!idle_allocation_count')
change('unready-provider-treated-as-unsupported', 'spm_cpuidle_get_spm',
    'return spm ?: ERR_PTR(-EPROBE_DEFER);', 'return spm ?: ERR_PTR(-ENODEV);',
    '!warm_calls&&!registration_calls&&!idle_allocation_count')
change('missing-provider-device-treated-as-unsupported', 'spm_cpuidle_get_spm',
    'if (!pdev)\n\t\treturn ERR_PTR(-EPROBE_DEFER);',
    'if (!pdev)\n\t\treturn ERR_PTR(-ENODEV);',
    '!warm_calls&&!registration_calls&&!idle_allocation_count')
change('provider-device-reference-leaked', 'spm_cpuidle_get_spm',
    'put_device(&pdev->dev);', '(void)pdev;',
    '!cpu_nodes[i].refs&&!saw_nodes[i].refs&&!providers[i].dev.refs')
change('CPU-node-reference-leaked', 'spm_cpuidle_get_spm',
    'of_node_put(cpu_node);', '(void)cpu_node;',
    '!cpu_nodes[i].refs&&!saw_nodes[i].refs&&!providers[i].dev.refs')
# A separately passing case catches premature fatal recovery cleanly.
mini = code[:code.index('int main(void)\n{')] + '''int main(void)
{
    cases=1;
    runtime_ready(); fault_kind=STALE; fault_start=1; fault_count=100;
    expect_fatal=true; int result=0;
    if(!setjmp(fatal_target)) result=spm_set_low_power_mode(&direct,PM_SLEEP_MODE_SPC);
    expect_fatal=false;
    EXPECT(!fatal_calls&&result==-ETIMEDOUT&&ctl_writes==101);
    preserved(0x8009);
    printf("{\\"cases\\":1,\\"checks\\":%u,\\"failures\\":%u}\\n",checks,failures);
    return 0;
}
'''
positive = q.m.run_code(mini, a.output / 'retry-positive')
assert positive['failures'] == 0
body = q.m.function(mini, 'spm_force_disable')
before = 'if (ret)\n\t\tret = spm_register_write_sync'
assert body.count(before) == 1
controls.append(('disable-second-attempt-omitted', mini.replace(body, body.replace(before,
    'if (false && ret)\n\t\tret = spm_register_write_sync')),
    '!fatal_calls&&result==-ETIMEDOUT&&ctl_writes==101'))
records = []
for name, mutated, assertion in controls:
    out = a.output / name
    result = q.m.run_code(mutated, out)
    stderr = (out / 'run.stderr').read_text()
    assert result['failures'] > 0 and assertion in stderr, (name,result,assertion,stderr)
    records.append(dict(name=name,rejected=True,failures=result['failures'],named_assertion=assertion))
report = dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,
    crashes_compiler_errors_and_sanitizer_faults_do_not_count=True,
    only_synthetic_services=True,no_phone_network_radio_audio_or_firmware_execution=True)
(a.output / 'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,controls_rejected=len(records))))
