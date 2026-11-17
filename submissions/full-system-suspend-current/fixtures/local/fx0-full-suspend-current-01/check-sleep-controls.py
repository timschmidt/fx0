# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,json,subprocess,sys,hashlib
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--groups',nargs='*');a=p.parse_args();a.output.mkdir(exist_ok=False)
B=Path(__file__).resolve().parent
M='drivers/irqchip/irq-qcom-mpm.c';T='drivers/soc/qcom/smd-rpm.c';S='drivers/rpmsg/qcom_smd.c';C='drivers/pmdomain/qcom/cpr.c';H='drivers/pmdomain/qcom/cpr-msm8926-suspend.h';V='drivers/pmdomain/qcom/cpr-voltage.h';P='drivers/soc/qcom/msm8226-pm.c';G='drivers/irqchip/irq-gic.c';L='drivers/clk/qcom/clk-pll.c';LH='drivers/clk/qcom/clk-pll-suspend.h'
groups={
 'mpm-probe':('check-mpm-probe.py',[M]),
 'smd-state':('check-smd-state.py',[S]),
 'clock-probe':('check-clock-probe.py',['drivers/clk/qcom/a53-pll.c','drivers/clk/qcom/apcs-msm8916.c','drivers/clk/qcom/gcc-msm8974.c']),
 'smd-edge':('check-smd-edge-lifetime.py',[S]),
 'lifetime':('check-coordinator-lifetime.py',[P]),
 'mpm':('check-mpm-sleep.py',[M]),
 'transport':('check-transport-sleep.py',[T,S,'include/linux/soc/qcom/smd-rpm.h']),
 'coordinator':('check-coordinator.py',[P,G,'arch/arm/mach-qcom/platsmp.c','kernel/power/suspend.c']),
 'cpr-api':('check-cpr-api.py',[C,H,V]),
 'cpr-transaction':('check-cpr-suspend.py',[H,V]),
 'pll':('check-pll-context.py',[L,LH,'drivers/clk/qcom/clk-pll.h','drivers/clk/qcom/common.h'])}
mutations=[
 ('mpm-probe','mailbox-error-bypasses-domain-cleanup',M,'goto remove_provider;','if (false) goto remove_provider; return ret;'),
 ('mpm-probe','retain-failed-genpd-provider',M,'of_genpd_del_provider(np);','(void)of_genpd_del_provider;'),
 ('mpm-probe','remove-domain-before-provider',M,'of_genpd_del_provider(np);\nremove_genpd:\n\tpm_genpd_remove(genpd);','pm_genpd_remove(genpd);\n\tof_genpd_del_provider(np);\n\treturn ret;\nremove_genpd:\n\tpm_genpd_remove(genpd);'),
 ('mpm-probe','free-unacquired-mailbox',M,'goto remove_provider;','if (false) goto remove_provider; goto free_mbox;'),

 ('smd-state','create-non-rpm-device-on-reserved-edge',S,'if (edge->no_suspend && strcmp(channel->name, "rpm_requests"))','if (false && edge->no_suspend && strcmp(channel->name, "rpm_requests"))'),
 ('smd-state','mark-failed-registration-successful',S,'if (!ret)\n\t\t\tchannel->registered = true;','if (ret <= 0)\n\t\t\tchannel->registered = true;'),
 ('smd-state','forget-successful-registration',S,'if (!ret)\n\t\t\tchannel->registered = true;','if (!ret)\n\t\t\tchannel->registered = false;'),
 ('smd-state','retain-closed-channel-registration',S,'channel->registered = false;','channel->registered = true;'),

 ('clock-probe','capture-context-on-other-socs','drivers/clk/qcom/a53-pll.c','pll->critical_rate && IS_ENABLED(CONFIG_QCOM_MSM8226_PM)','IS_ENABLED(CONFIG_QCOM_MSM8226_PM)'),
 ('clock-probe','capture-without-coordinator','drivers/clk/qcom/a53-pll.c','pll->critical_rate && IS_ENABLED(CONFIG_QCOM_MSM8226_PM)','pll->critical_rate'),
 ('clock-probe','ignore-context-read-failure','drivers/clk/qcom/a53-pll.c','if (ret)\n\t\t\treturn ret;','if (false && ret)\n\t\t\treturn ret;'),
 ('clock-probe','cache-wrong-l-value','drivers/clk/qcom/a53-pll.c','pll->suspend_l &= 0x3ff;','pll->suspend_l |= 0x3ff;'),

 ('smd-edge','leak-edge-node-reference',S,'of_node_put(edge->of_node);','(void)edge->of_node;'),
 ('smd-edge','allow-no-suspend-on-every-edge',S,'edge->no_suspend = IS_ENABLED(CONFIG_QCOM_MSM8226_PM) &&\n\t\tof_device_is_compatible(dev->parent->of_node,\n\t\t\t\t\t\"qcom,msm8226-rpm-proc\");','edge->no_suspend = true || (IS_ENABLED(CONFIG_QCOM_MSM8226_PM) &&\n\t\tof_device_is_compatible(dev->parent->of_node,\n\t\t\t\t\t\"qcom,msm8226-rpm-proc\"));'),
 ('smd-edge','omit-no-suspend-irq-flag',S,'(edge->no_suspend ? IRQF_NO_SUSPEND : 0)','(0 * (edge->no_suspend ? IRQF_NO_SUSPEND : 0))'),
 ('smd-edge','forget-pm-notifier-unregister',S,'if (edge->sleep_nb_registered)','if (false && edge->sleep_nb_registered)'),
 ('smd-edge','failed-notifier-skips-irq-work-cleanup',S,'if (ret)\n\t\t\tgoto unregister_edge;','if (ret)\n\t\t\tgoto unregister_dev;'),
 ('smd-edge','leave-state-worker-queued-on-release',S,'cancel_work_sync(&edge->state_work);','(void)&edge->state_work;'),

 ('lifetime','retain-cpr-supplier-reference',P,'put_device(&pm->cpr->dev);','(void)pm->cpr;'),
 ('lifetime','delete-driver-managed-link-manually',P,'device_link_del(pm->cpr_link);','if (pm->mpm_link) device_link_del(pm->mpm_link); device_link_del(pm->cpr_link);'),
 ('lifetime','install-suspend-ops-during-probe',P,'schedule_work(&pm->install_work);','(void)schedule_work; msm8226_pm_install(&pm->install_work);'),
 ('lifetime','retain-pending-install-work',P,'cancel_work_sync(&pm->install_work);','(void)cancel_work_sync;'),
 ('lifetime','accept-unbound-rpm-parent',P,'if (!device_is_bound(dev->parent))','if (false && !device_is_bound(dev->parent))'),
 ('lifetime','retain-cpr-owner-on-probe-failure',P,'qcom_cpr_msm8926_suspend_detach(&pm->cpr->dev, dev);','(void)qcom_cpr_msm8926_suspend_detach;'),
 ('lifetime','publish-with-offline-cpu',P,'!cpumask_equal(cpu_online_mask, cpu_present_mask)','(false && !cpumask_equal(cpu_online_mask, cpu_present_mask))'),

 ('mpm','unknown-wake-route',M,'!qcom_mpm_wake_covered(priv)','(false && !qcom_mpm_wake_covered(priv))'),
 ('mpm','ignore-second-shared-action',M,'action = action->next','action = NULL'),
 ('mpm','ignore-snapshot-pin-enable',M,'return pin < priv->pin_count && priv->sleep_image[pin / 32] & BIT(pin % 32);','return pin < priv->pin_count;'),
 ('mpm','ignore-mailbox-failure',M,'if (ret < 0)\n\t\treturn ret;','if (false)\n\t\treturn ret;'),
 ('mpm','retain-replayed-status',M,'if (priv->sleep_owner)\n\t\t\tqcom_mpm_write','if (false)\n\t\t\tqcom_mpm_write'),
 ('mpm','replay-level-as-edge',M,'if (!irqd_is_level_type(d))','if (!irqd_is_level_type(d) || true)'),
 ('mpm','skip-domain-node-release-action',M,'ret = devm_add_action_or_reset(dev, qcom_mpm_put_node, node);','(void)qcom_mpm_put_node; (void)devm_add_action_or_reset; ret = 0;'),
 ('mpm','allow-multiple-online-cpus',M,'num_online_cpus() != 1','(false && num_online_cpus() != 1)'),
 ('transport','ignore-remote-channel-close',S,'GET_RX_CHANNEL_INFO(channel, state) != SMD_CHANNEL_OPENED','false'),
 ('transport','run-lifecycle-work-during-sleep',S,'if (!edge->system_sleep)','if (true)'),
 ('transport','allow-duplicate-prepare',S,'if (edge->system_sleep) {','if (false) {'),
 ('transport','lose-deferred-state-work',S,'schedule_work(&edge->scan_work);\n\t\tschedule_work(&edge->state_work);','schedule_work(&edge->scan_work);\n\t\t(void)&edge->state_work;'),
 ('transport','mask-before-freeze',T,'ret = qcom_rpm_smd_freeze(rpm, &rpm->system_token);\n\tif (ret)\n\t\treturn ret;\n\tdisable_irq(rpm->receive_irq);','disable_irq(rpm->receive_irq);\n\tret = qcom_rpm_smd_freeze(rpm, &rpm->system_token);\n\tif (ret)\n\t\treturn ret;'),
 ('transport','thaw-before-unmask',T,'if (rpm->receive_masked) {','qcom_rpm_smd_thaw(rpm, &rpm->system_token);\n\tif (rpm->receive_masked) {'),
 ('cpr-api','resume-before-voltage-restore',C,'if (drv->msm8926->sleep.active || drv->msm8926->suspend_irq_disabled)','if (false)'),
 ('cpr-api','skip-loop-quiescence-check',C,'if (cpr_read(drv, REG_RBCPR_CTL) & RBCPR_CTL_LOOP_EN ||\n\t    cpr_read(drv, REG_RBIF_IRQ_EN(0))) {','if (false) {'),
 ('cpr-api','ignore-prepared-pll-reference',C,'!clk_hw_is_prepared(__clk_get_hw(data->sleep.pll))','true'),
 ('coordinator','skip-last-collapse-status-check',P,'if (!msm8226_secondaries_collapsed(pm))\n\t\treturn -EBUSY;','if (false && !msm8226_secondaries_collapsed(pm))\n\t\treturn -EBUSY;'),
 ('coordinator','skip-outer-cache-clean',P,'outer_flush_all();','(void)outer_flush_all;'),
 ('coordinator','skip-l2-disarm',P,'l2_restore = spm_set_l2_low_power_mode(pm->l2, SPM_L2_MODE_DISABLED);','l2_restore = 0;'),
 ('coordinator','close-admission-in-early-callback',P,'.prepare_late = msm8226_platform_prepare_late,','.prepare = msm8226_platform_prepare_late,'),
 ('coordinator','lose-secondary-cpu-pm-exit',P,'cpu_pm_exit();','(void)cpu_pm_exit;'),
 ('coordinator','ignore-ppi-disable-readback',G,'if (readl_relaxed(base + GIC_DIST_ENABLE_SET) & GENMASK(31, 16))','if (false)'),
 ('cpr-transaction','skip-forced-apc-sync',H,'return cpr_suspend_sync(rails->apc);','return 0;'),
 ('cpr-transaction','allow-live-pll-reference',H,'if (__clk_get_enable_count(sleep->pll) ||\n\t    clk_hw_is_prepared(__clk_get_hw(sleep->pll))) {','if (false && (__clk_get_enable_count(sleep->pll) ||\n\t    clk_hw_is_prepared(__clk_get_hw(sleep->pll)))) {'),
 ('cpr-transaction','retain-clock-exclusivity',H,'clk_rate_exclusive_put(sleep->clock);','(void)clk_rate_exclusive_put;'),
 ('cpr-transaction','allow-low-sleep-mx-vote',H,'regulator_get_voltage(sleep->sleep_mx) != rails->mx_max_uV','regulator_get_voltage(sleep->sleep_mx) < 0'),
 ('pll','skip-disable-readback',L,'if (!ret && val & mask)','if (false)'),
 ('pll','accept-fsm-on-initial-prepare',LH,'if (mode & PLL_VOTE_FSM_ENA)','if (false)'),
 ('pll','cache-wrong-programmed-rate',L,'pll->suspend_l = f->l;','pll->suspend_l = 0;'),
 ('pll','skip-config-restoration',LH,'masks[0] = U32_MAX;','masks[0] = 0;'),
]
records=[]
for group,name,path,before,after in mutations:
 if a.groups and group not in a.groups:continue
 script,files=groups[group];base=a.output/name;tree=base/'tree';text=(a.source/path).read_text();assert before in text,(name,before)
 for f in files:
  dst=tree/f;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((a.source/f).read_bytes())
 # Mutate only the first occurrence, leaving every extracted function intact.
 (tree/path).write_text(text.replace(before,after,1));out=base/'result'
 r=subprocess.run([sys.executable,'-B',str(B/script),str(tree),str(out)],capture_output=True,text=True,timeout=65)
 (base/'controller.stdout').write_text(r.stdout);(base/'controller.stderr').write_text(r.stderr)
 assert (out/'qualification.json').exists(),(name,'no executed model result',r.stderr)
 j=json.loads((out/'qualification.json').read_text());stderr=(out/'run.stderr').read_text()
 assert j['returncode']==1 and ': ' in stderr and not any(x in stderr for x in ['AddressSanitizer','UndefinedBehaviorSanitizer','runtime error:','LeakSanitizer','unexpected fatal']), (name,j,stderr)
 records.append(dict(group=group,name=name,returncode=1,rejected_by_model_assertion=True,diagnostic=stderr.strip(),mutated_source_SHA256=hashlib.sha256((tree/path).read_bytes()).hexdigest()))
 (a.output/'partial.json').write_text(json.dumps(records,indent=2)+'\n')
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=len(records),records=records,compiler_crash_timeout_or_sanitizer_failure_counted=False),indent=2)+'\n')
print(json.dumps(dict(passed=True,controls=len(records))))
