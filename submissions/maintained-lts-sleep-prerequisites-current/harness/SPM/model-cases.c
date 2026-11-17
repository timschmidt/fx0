/* SPDX-License-Identifier: GPL-2.0-only */
int main(void)
{
    /* All declared SoCs retain their valid standby/SPC mode indices and bits. */
    for(const struct of_device_id *p=spm_match_table;p->compatible;p++) {
        const struct spm_reg_data *data=p->data;
        for(unsigned mode=0;mode<PM_SLEEP_MODE_NR;mode++) {
            reset(data);
            bool usable=!data->pmic_arbiter_master&&data->reg_offset&&data->reg_offset[SPM_REG_SPM_CTL];
            int ret=spm_set_low_power_mode(&direct,mode);
            if(!usable) EXPECT(ret==-EOPNOTSUPP&&!ctl_writes&&!ctl_reads);
            else {
                bool supported=mode==PM_SLEEP_MODE_STBY||data->start_index[mode];
                u32 initial=snapshot[control_offset()/4];
                EXPECT(ret==(supported ? 0 : -EOPNOTSUPP));
                if(supported) EXPECT(bank[control_offset()/4]==((initial&~(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT))|data->start_index[mode]<<SPM_CTL_INDEX_SHIFT|SPM_CTL_EN));
                else EXPECT(!(bank[control_offset()/4]&SPM_CTL_EN));
                preserved(initial);
            }
            ++cases;
        }
    }
    /* Invalid indices and unsupported modes disarm an owned CPU controller. */
    const int invalid[]={-1,PM_SLEEP_MODE_NR,999};
    for(unsigned i=0;i<ARRAY_SIZE(invalid);i++) {
        runtime_ready();
        EXPECT(spm_set_low_power_mode(&direct,invalid[i])==-EINVAL);
        EXPECT(!(bank[control_offset()/4]&SPM_CTL_EN)); preserved(0x8009); ++cases;
    }
    runtime_ready();
    EXPECT(spm_set_low_power_mode(NULL,PM_SLEEP_MODE_SPC)==-ENODEV);
    direct.reg_data=NULL;
    EXPECT(spm_set_low_power_mode(&direct,PM_SLEEP_MODE_SPC)==-ENODEV);
    EXPECT(!ctl_reads&&!ctl_writes); ++cases;
    /* A corrupt static catalogue cannot spill its start address into other bits. */
    runtime_ready(); struct spm_reg_data bad=spm_reg_8226_cpu;
    bad.start_index[PM_SLEEP_MODE_SPC]=128; direct.reg_data=&bad;
    EXPECT(spm_set_low_power_mode(&direct,PM_SLEEP_MODE_SPC)==-EINVAL);
    EXPECT(!(bank[control_offset()/4]&SPM_CTL_EN)); preserved(0x8009); ++cases;
    /* Posted writes can be dropped, corrupt or applied with stale readback. */
    for(unsigned kind=DROP;kind<=STALE;kind++)
    for(unsigned count=1;count<=100;count++)
    for(unsigned mode=0;mode<PM_SLEEP_MODE_NR;mode++) {
        if(mode==PM_SLEEP_MODE_RET) continue;
        runtime_ready(); bank[control_offset()/4]=0x8029;
        fault_kind=kind; fault_start=1; fault_count=count;
        int ret=spm_set_low_power_mode(&direct,mode);
        EXPECT(ret==(count<50 ? 0 : -ETIMEDOUT));
        if(ret) {
            EXPECT(!(bank[control_offset()/4]&SPM_CTL_EN));
            EXPECT(ctl_writes<=101);
        } else {
            EXPECT(ctl_writes==count+1&&delays==count);
            EXPECT(((bank[control_offset()/4]>>SPM_CTL_INDEX_SHIFT)&SPM_CTL_INDEX)==spm_reg_8226_cpu.start_index[mode]);
        }
        preserved(0x8009); ++cases;
    }
    /* Dropping an idempotent write is fine when readback proves the state. */
    runtime_ready(); fault_kind=DROP; fault_start=1; fault_count=100;
    EXPECT(spm_set_low_power_mode(&direct,PM_SLEEP_MODE_STBY)==0);
    EXPECT(ctl_writes==1&&!delays&&bank[control_offset()/4]==0x8009);
    preserved(0x8009); ++cases;
    /* END may reset INDEX during disable; EN and bypass still must match. */
    runtime_ready(); fault_kind=DROP; fault_start=2; fault_count=50;
    reset_disabled_index=true; expect_fatal=true;
    int reset_result=0;
    if(!setjmp(fatal_target)) reset_result=qcom_cpu_spc(&direct);
    expect_fatal=false;
    EXPECT(!fatal_calls&&reset_result==-ETIMEDOUT);
    EXPECT(bank[control_offset()/4]==0x8008);
    preserved(0x8009); ++cases;
    /* Low-level caller rejects failed SPC and always restores after suspend. */
    const int outcomes[]={0,-1,-EIO};
    for(unsigned kind=GOOD;kind<=STALE;kind++)
    for(unsigned stage=0;stage<3;stage++)
    for(unsigned result=0;result<ARRAY_SIZE(outcomes);result++) {
        runtime_ready(); suspend_result=outcomes[result];
        if(stage) { fault_kind=kind; fault_start=stage; fault_count=50; }
        int ret=qcom_cpu_spc(&direct);
        bool arm_failed=kind&&stage==1,restore_failed=kind&&stage==2;
        int expected=arm_failed ? -ETIMEDOUT : outcomes[result] ? outcomes[result] : restore_failed ? -ETIMEDOUT : 0;
        EXPECT(ret==expected);
        EXPECT(suspend_calls==(arm_failed ? 0U : 1U)&&scm_calls==suspend_calls);
        if(arm_failed||restore_failed) EXPECT(!(bank[control_offset()/4]&SPM_CTL_EN));
        else EXPECT((bank[control_offset()/4]&(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT|SPM_CTL_EN))==SPM_CTL_EN);
        preserved(0x8009); ++cases;
    }
    /* The actual CPU_PM macro balances notifications for success and every abort. */
    for(unsigned kind=GOOD;kind<=STALE;kind++)
    for(unsigned stage=0;stage<3;stage++)
    for(unsigned result=0;result<ARRAY_SIZE(outcomes);result++)
    for(unsigned admission=0;admission<2;admission++) {
        runtime_ready(); suspend_result=outcomes[result]; pm_error=admission ? -EBUSY : 0;
        if(stage) { fault_kind=kind; fault_start=stage; fault_count=50; }
        struct cpuidle_qcom_spm_data data={.spm=&direct};
        int ret=spm_enter_idle_state(NULL,&data.cpuidle_driver,1);
        bool failed=admission||outcomes[result]||(kind&&stage);
        EXPECT(ret==(failed ? -1 : 1));
        EXPECT(pm_enters==1&&pm_exits==(admission ? 0U : 1U));
        EXPECT(ct_enters==pm_exits&&ct_exits==pm_exits&&!in_pm);
        if(admission) EXPECT(!ctl_writes&&!suspend_calls&&!scm_calls);
        /* A subsequent generic WFI must not use a stale collapse entry. */
        clear_io(); EXPECT(spm_enter_idle_state(NULL,&data.cpuidle_driver,0)==0);
        EXPECT(wfi_calls==1&&!pm_enters&&!pm_exits&&!ctl_writes);
        preserved(0x8009); ++cases;
    }
    /* Persistent unknown enable after either programming stage cannot return. */
    for(unsigned kind=DROP;kind<=STALE;kind++)
    for(unsigned stage=1;stage<=2;stage++) {
        runtime_ready(); fault_kind=kind; fault_start=stage; fault_count=150;
        /* An unapplied arm timeout can still confirm a disabled old state;
         * stale/corrupt reads keep both recovery acknowledgments unverified. */
        expect_fatal=true;
        if(!setjmp(fatal_target)) {
            qcom_cpu_spc(&direct);
            EXPECT(!"persistent unknown CPU enable must not return");
        }
        expect_fatal=false;
        EXPECT(fatal_calls==1&&ctl_writes==150+stage-1);
        preserved(0x8009); ++cases;
    }
    /* Probe copies sequences first and publishes only after all setup succeeds. */
    for(const struct of_device_id *p=spm_match_table;p->compatible;p++)
    for(unsigned enabled=0;enabled<2;enabled++)
    for(unsigned error=0;error<2;error++) {
        reset(p->data); probe_phase=true; regulator_enabled=enabled;
        regulator_error=error ? -EIO : 0; node.compatible=p->compatible;
        int ret=spm_dev_probe(&pdev);
        bool master_node=((const struct spm_reg_data *)p->data)->pmic_arbiter_master;
        bool failed=enabled&&error&&!master_node;
        EXPECT(ret==(failed ? -EIO : 0));
        EXPECT(publication_calls==(failed ? 0U : 1U));
        EXPECT((pdev.data!=NULL)==!failed);
        if(master_node) EXPECT(l2_calls==1&&!regulator_calls);
        else EXPECT(regulator_calls==enabled);
        release_probe(); ++cases;
    }
    for(unsigned scenario=0;scenario<7;scenario++) {
        runtime_ready(); probe_phase=true; node.compatible="qcom,msm8226-saw2-v2.1-cpu";
        if(scenario==0) allocation_fail=true;
        if(scenario==1) mapping_error=-ENOMEM;
        if(scenario==2) node.compatible="qcom,not-a-saw";
        if(scenario>=3&&scenario<=5) { bank[control_offset()/4]=0x8029; fault_kind=scenario-2; fault_start=1; fault_count=50; }
        if(scenario==6) { node.compatible="qcom,msm8226-saw2-v2.1-l2"; l2_error=-EIO; }
        int ret=spm_dev_probe(&pdev);
        const int errors[]={-ENOMEM,-ENOMEM,-ENODEV,-ETIMEDOUT,-ETIMEDOUT,-ETIMEDOUT,-EIO};
        EXPECT(ret==errors[scenario]&&!publication_calls&&!pdev.data);
        EXPECT(!regulator_calls);
        if(scenario>=3&&scenario<=5) EXPECT(!(bank[control_offset()/4]&SPM_CTL_EN));
        release_probe(); ++cases;
    }
    /* All suppliers must be ready before firmware setup or first registration. */
    for(unsigned cpu=0;cpu<4;cpu++)
    for(unsigned unready=0;unready<2;unready++) {
        reset_admission();
        if(unready) providers[cpu].data=NULL; else provider_exists[cpu]=false;
        EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==-EPROBE_DEFER);
        EXPECT(!warm_calls&&!registration_calls&&!idle_allocation_count);
        admission_refs_balanced();
        providers[cpu].data=&provider_data[cpu]; provider_exists[cpu]=true;
        EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==0);
        EXPECT(warm_calls==1&&registration_calls==4&&idle_allocation_count==4);
        for(unsigned i=0;i<4;i++) EXPECT(registered[i]);
        release_admission(); ++cases;
    }
    /* Unsupported/disabled CPUs are skipped; their temporary references balance. */
    for(unsigned ready_mask=0;ready_mask<16;ready_mask++) {
        reset_admission();
        for(unsigned i=0;i<4;i++) if(!(ready_mask&(1U<<i))) providers[i].data=NULL;
        EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==(ready_mask==15 ? 0 : -EPROBE_DEFER));
        EXPECT(registration_calls==(ready_mask==15 ? 4U : 0U));
        EXPECT(warm_calls==(ready_mask==15 ? 1U : 0U));
        admission_refs_balanced(); release_admission(); ++cases;
    }
    for(unsigned cpu=0;cpu<4;cpu++)
    for(unsigned absent=0;absent<3;absent++) {
        reset_admission();
        if(absent==0) cpu_missing[cpu]=true;
        if(absent==1) saw_missing[cpu]=true;
        if(absent==2) saw_nodes[cpu].available=false;
        EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==0);
        EXPECT(warm_calls==1&&registration_calls==3&&idle_allocation_count==3);
        for(unsigned i=0;i<4;i++) EXPECT(registered[i]==(i!=cpu));
        release_admission(); ++cases;
    }
    for(unsigned count=1;count<=4;count++) {
        reset_admission(); present_cpus=count;
        EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==0);
        EXPECT(registration_calls==count&&idle_allocation_count==count);
        release_admission(); ++cases;
    }
    reset_admission(); scm_available=false;
    EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==-EPROBE_DEFER);
    EXPECT(!provider_gets&&!warm_calls&&!registration_calls&&!idle_allocation_count);
    release_admission(); ++cases;
    reset_admission(); warm_error=-EIO;
    EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==-EIO);
    EXPECT(warm_calls==1&&!registration_calls&&!idle_allocation_count);
    admission_refs_balanced(); warm_error=0;
    EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==0&&registration_calls==4);
    release_admission(); ++cases;
    /* Existing per-CPU allocation/DT/registration failure policy stays intact. */
    for(unsigned cpu=0;cpu<4;cpu++)
    for(unsigned stage=0;stage<4;stage++) {
        reset_admission();
        if(stage==0) idle_fail_allocation=cpu+1;
        if(stage==1||stage==2) { DT_error_cpu=cpu; DT_error=stage==1 ? 0 : -EIO; }
        if(stage==3) { registration_error_cpu=cpu; registration_error=-EIO; }
        EXPECT(spm_cpuidle_drv_probe(&idle_pdev)==0);
        EXPECT(registration_calls==(stage==3 ? 4U : 3U));
        for(unsigned i=0;i<4;i++) EXPECT(registered[i]==(i!=cpu));
        release_admission(); ++cases;
    }
    printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);
    return 0;
}
