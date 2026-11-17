/* SPDX-License-Identifier: GPL-2.0-only */
int main(void)
{
    const unsigned starts[]={0,0,4,26,54};
    /* The raw map exposes exactly the bounded L2 programs and control register. */
    for(unsigned address=0;address<4096;address++) {
        bool seq=address>=0x80&&address<=0xd0&&address%4==0;
        bool read=address==4||address==8||address==0x14||address==0x1c||address==0x20||address==0x30||address==0x34||address==0x40||address==0x44||address==0xfd0||seq;
        bool write=address==8||address==0x18||address==0x1c||address==0x30||address==0x34||address==0x40||address==0x44||seq;
        EXPECT(access_ok(address,false)==read&&access_ok(address,true)==write);
    }
    reset(); EXPECT(spm_8226_l2_register(&pdev,&driver)==0);
    EXPECT(published&&publication_calls==1&&driver.l2_map==&bank);
    EXPECT(sequence_writes==21&&writes==25&&!control_writes);
    unsigned init_ops=operations;
    preserved(); EXPECT(!bank.registers[0x30/4]); ++cases;
    for(unsigned scenario=0;scenario<2;scenario++) {
        reset(); bank.registers[scenario ? 0x20/4 : 0x30/4]=1;
        EXPECT(spm_8226_l2_sequence_init(&bank)==-EBUSY);
        EXPECT(!writes&&!sequence_writes&&!publication_calls); ++cases;
    }
    /* Every initialization access can fail, be dropped, or return corrupt data. */
    for(unsigned kind=FAIL;kind<=CORRUPT;kind++)
    for(unsigned at=1;at<=init_ops;at++)
    for(unsigned effect=0;effect<2;effect++) {
        reset(); fault_kind=kind; fault_at=at; applied=effect;
        int ret=spm_8226_l2_register(&pdev,&driver);
        EXPECT(!bank.registers[0x30/4]&&!control_writes);
        EXPECT(bank.registers[0x1c/4]==0x73&&bank.registers[0x14/4]==0x73);
        if(ret) EXPECT(!published&&!publication_calls&&!driver.l2_map);
        else EXPECT(published&&driver.l2_map==&bank);
        if(!published) {
            const unsigned regs[]={8,0x34,0x40,0x44};
            const unsigned wanted[]={0x14,0x3c102800,0x02030080,0x00030000};
            bool known=true,complete=true;
            for(unsigned i=0;i<4;i++) {
                known &= !bank.registers[regs[i]/4] || bank.registers[regs[i]/4]==wanted[i];
                complete &= bank.registers[regs[i]/4]==wanted[i];
            }
            bool retryable=known&&(!bank.registers[8/4]||complete);
            clear_io(); EXPECT(spm_8226_l2_register(&pdev,&driver)==(retryable ? 0 : -EOPNOTSUPP));
            if(!retryable) {
                EXPECT(!published&&!writes&&!bank.registers[0x30/4]);
                EXPECT(bank.registers[0x1c/4]==0x73&&bank.registers[0x14/4]==0x73);
                ++cases; continue;
            }
        }
        preserved(); ++cases;
    }
    /* No controller is published until all resource/lifetime and I/O gates pass. */
    for(unsigned scenario=0;scenario<10;scenario++) {
        reset();
        if(scenario==0) master_flag=false;
        if(scenario==1) is_module=true;
        if(scenario==2) missing_resource=true;
        if(scenario==3) resource.size=0x100;
        if(scenario==4) is_syscon=true;
        if(scenario==5) published=true;
        if(scenario==6) lookup_error=-EIO;
        if(scenario==7) map_error=-ENOMEM;
        if(scenario==8) registry_error=-ENOMEM;
        if(scenario==9) bank.registers[0x30/4]=1;
        const int errors[]={-ENODEV,-EOPNOTSUPP,-EINVAL,-EINVAL,-EINVAL,-EEXIST,-EIO,-ENOMEM,-ENOMEM,-EBUSY};
        EXPECT(spm_8226_l2_register(&pdev,&driver)==errors[scenario]);
        EXPECT(!driver.l2_map);
        if(scenario<8) EXPECT(!operations);
        EXPECT(bank.registers[0x1c/4]==0x73&&bank.registers[0x14/4]==0x73);
        ++cases;
    }
    /* Each complete vendor program arms only its own index and can be disarmed. */
    for(unsigned mode=0;mode<SPM_L2_MODE_NR;mode++) {
        ready(); EXPECT(spm_set_l2_low_power_mode(&driver,mode)==0);
        EXPECT(bank.registers[0x30/4]==(mode ? starts[mode]<<4|1 : 0));
        EXPECT(!sequence_writes); preserved();
        EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED)==0);
        EXPECT(!bank.registers[0x30/4]); ++cases;
    }
    ready(); EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_COLLAPSE_RPM)==0);
    unsigned arm_ops=operations;
    /* All mode-access faults return either a verified complete mode or disabled. */
    for(unsigned mode=SPM_L2_MODE_RETENTION;mode<SPM_L2_MODE_NR;mode++)
    for(unsigned kind=FAIL;kind<=CORRUPT;kind++)
    for(unsigned at=1;at<=arm_ops;at++)
    for(unsigned effect=0;effect<2;effect++) {
        ready(); fault_kind=kind; fault_at=at; applied=effect;
        int ret=spm_set_l2_low_power_mode(&driver,mode);
        if(ret) EXPECT(!bank.registers[0x30/4]);
        else EXPECT(bank.registers[0x30/4]==(starts[mode]<<4|1));
        EXPECT(!sequence_writes&&operations<80); preserved();
        clear_io(); EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED)==0);
        EXPECT(!bank.registers[0x30/4]); ++cases;
    }
    /* Lost or corrupted program/configuration must never authorize an arm. */
    for(unsigned i=0;i<21;i++) {
        ready(); bank.registers[(0x80+4*i)/4]^=1;
        EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_COLLAPSE_RPM)==-EIO);
        EXPECT(!bank.registers[0x30/4]&&control_writes==1); ++cases;
    }
    const unsigned addresses[]={0xfd0,4,8,0x34,0x40,0x44,0x20,0x14};
    const unsigned masks[]={1,4,1,1,1,1,1,0x10000};
    for(unsigned i=0;i<ARRAY_SIZE(addresses);i++) {
        ready(); bank.registers[addresses[i]/4]^=masks[i];
        EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_COLLAPSE_RPM)==-EOPNOTSUPP);
        EXPECT(!bank.registers[0x30/4]&&control_writes==1); ++cases;
    }
    /* Context rejection performs no MMIO; CPU0 with local IRQs off serializes APC IPIs. */
    for(unsigned scenario=0;scenario<6;scenario++) {
        ready();
        if(scenario==0) driver.l2_map=NULL;
        if(scenario==1) driver.reg_data=&ordinary;
        if(scenario==2) cpu=1;
        if(scenario==3) irq_off=false;
        if(scenario==4) online=4;
        int ret=spm_set_l2_low_power_mode(scenario==5 ? NULL : &driver,SPM_L2_MODE_COLLAPSE_RPM);
        EXPECT(ret==(scenario==2||scenario==3 ? -EPERM : scenario==4 ? -EBUSY : -ENODEV));
        EXPECT(!operations); ++cases;
    }
    ready(); online=4;
    EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED)==0); ++cases;
    ready(); bank.registers[0x30/4]=54<<4|1;
    EXPECT(spm_set_l2_low_power_mode(&driver,(enum spm_l2_sleep_mode)-1)==-EINVAL);
    EXPECT(!bank.registers[0x30/4]); ++cases;
    for(unsigned kind=FAIL;kind<=CORRUPT;kind++)
    for(unsigned at=1;at<=4;at++)
    for(unsigned effect=0;effect<2;effect++) {
        ready(); bank.registers[0x30/4]=54<<4|1;
        fault_at=at; fault_kind=kind; applied=effect;
        EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED)==0);
        EXPECT(!bank.registers[0x30/4]&&operations<=4); preserved(); ++cases;
    }
    /* Unknown disable state is fatal, including applied-but-unreadable outcomes. */
    for(unsigned effect=0;effect<2;effect++) {
        ready(); bank.registers[0x30/4]=54<<4|1;
        fault_at=1; fault_span=4; fault_kind=FAIL; applied=effect;
        expect_fatal=true;
        if(!setjmp(fatal_target)) {
            spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED);
            EXPECT(!"unknown disable state must not return");
        }
        expect_fatal=false;
        EXPECT(fatal_calls==1&&operations==4);
        clear_io(); EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED)==0);
        EXPECT(!bank.registers[0x30/4]); preserved(); ++cases;
    }
    /* An uncertain arm followed by two unreadable disarm attempts is also fatal. */
    for(unsigned effect=0;effect<2;effect++) {
        ready(); fault_at=arm_ops-1; fault_span=5; fault_kind=FAIL; applied=effect;
        expect_fatal=true;
        if(!setjmp(fatal_target)) {
            spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_COLLAPSE_RPM);
            EXPECT(!"unknown entry recovery must not return");
        }
        expect_fatal=false;
        EXPECT(fatal_calls==1&&operations==arm_ops+3);
        clear_io(); EXPECT(spm_set_l2_low_power_mode(&driver,SPM_L2_MODE_DISABLED)==0);
        EXPECT(!bank.registers[0x30/4]); preserved(); ++cases;
    }
    printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u,\"initialization_IO_points\":%u,\"arm_IO_points\":%u}\n",cases,checks,failures,init_ops,arm_ops);
    return 0;
}
