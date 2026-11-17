// SPDX-License-Identifier: GPL-2.0-only
static struct regulator apc_store,mx_store,so_store;
static struct clk cpu_store,aux_store,pll_store,gpll_store;
static struct regmap mux_store;
static struct cpr_voltage rails;
static struct cpr_msm8926_suspend sleep_ctx;
static unsigned long saved_rate;
static int saved_apc,saved_mx;
static void init_rails(unsigned long rate,int voltage,int mx_voltage) {
 ops=fault_step=fault_kind=cache_skips=0;corrupt_parent_on_mx=extra_pll_ref=false;
 apc_store=(struct regulator){.kind=0,.request=voltage,.voltage=voltage,.refs=1};
 mx_store=(struct regulator){.kind=1,.request=mx_voltage,.voltage=mx_voltage,.refs=1};
 so_store=(struct regulator){.kind=2,.request=MAX_UV,.voltage=MAX_UV,.refs=1};
 apc=&apc_store;mx=&mx_store;so=&so_store;
 cpu_store=(struct clk){.rate=rate};aux_store=(struct clk){.rate=600000000};pll_store=(struct clk){.rate=rate>600000000?rate:768000000,.enabled=rate>600000000,.prepared=rate>600000000};gpll_store=(struct clk){.rate=600000000};
 cpuclk=&cpu_store;auxclk=&aux_store;pllclk=&pll_store;gpll=&gpll_store;auxclk->parent=gpll;
 cpuclk->hw.clock=cpuclk;pllclk->hw.clock=pllclk;
 mux=&mux_store;mux->cmd=0;mux->cfg=rate==300000000?(4<<8|3):(rate==600000000?(4<<8|1):(5<<8|1));
 rails=(struct cpr_voltage){.apc=apc,.mx=mx,.mx_max_uV=MAX_UV,.mx_min_uV=mx_voltage,.mx_enabled=true};
 sleep_ctx=(struct cpr_msm8926_suspend){.rails=&rails,.sleep_mx=so,.clock=cpuclk,.aux=auxclk,.pll=pllclk,.apcs=mux};
 saved_rate=rate;saved_apc=voltage;saved_mx=mx_voltage;
}
static struct cpr_drv drv;
static struct cpr_msm8926_data data;
static struct corner corner;
static struct device dev,owner,other;
static void reset(void) {
 init_rails(787200000,1000000,1100000);quiescent=true;local_irqs=true;
 data=(struct cpr_msm8926_data){.mx_sleep=so,.aux_clk=auxclk,.pll_clk=pllclk,.apcs=mux,.applied=true};corner=(struct corner){.freq=saved_rate,.min_uV=750000,.max_uV=MAX_UV};
 drv=(struct cpr_drv){.msm8926=&data,.initialized=true,.corner=&corner,.rails=rails,.cpu_clk=cpuclk,.base=cpr_regs,.irq=79};observed=&drv;
 dev=(struct device){.data=&drv,.driver=&cpr_driver.driver};owner=(struct device){0};other=(struct device){0};
 disable_calls=enable_calls=irq_depth=config_calls=corner_saves=config_error=rate_error=polls=0;cpr_regs[0]=RBCPR_CTL_LOOP_EN;cpr_regs[1]=7;cpr_regs[2]=0;pm_suspend_target_state=PM_SUSPEND_MEM;cases++;
}
static void attach(void) {CHECK(!qcom_cpr_msm8926_suspend_attach(&dev,&owner));CHECK(data.sleep.rails==&drv.rails&&data.sleep.sleep_mx==so&&data.sleep.clock==cpuclk&&data.sleep.aux==auxclk&&data.sleep.pll==pllclk&&data.sleep.apcs==mux);}
static void suspend(void) {CHECK(!cpr_pm_suspend(&dev));CHECK(drv.suspended&&!data.applied&&data.suspend_was_applied&&corner_saves==1);CHECK(!(cpr_regs[0]&RBCPR_CTL_LOOP_EN)&&!cpr_regs[1]);}
static void finish(void) {CHECK(!qcom_cpr_msm8926_suspend_restore(&dev,&owner));CHECK(!data.sleep.active&&!data.sleep.exclusive&&!irq_depth&&!data.suspend_irq_disabled);CHECK(!drv.lock.held);CHECK(!cpr_pm_resume(&dev));CHECK(!drv.suspended&&!data.applied);CHECK(!qcom_cpr_msm8926_suspend_detach(&dev,&owner));CHECK(cpuclk->rate==saved_rate&&apc->voltage==saved_apc&&mx->voltage>=saved_mx);}
static void attach_cases(void) {
 for(int fault=0;fault<9;fault++) {reset();
  if(fault==0)dev.driver=NULL;if(fault==1)dev.data=NULL;if(fault==2)drv.msm8926=NULL;if(fault==3)drv.initialized=false;if(fault==4)drv.corner=NULL;if(fault==5)data.mx_sleep=NULL;if(fault==6)data.suspend_owner=&other;if(fault==7)drv.suspended=true;
  int want=fault<2?-ENODEV:fault<6?-EPROBE_DEFER:fault<8?-EBUSY:0;CHECK(qcom_cpr_msm8926_suspend_attach(&dev,&owner)==want);CHECK(!drv.lock.held);
 }
 reset();CHECK(qcom_cpr_msm8926_suspend_attach(&dev,NULL)==-ENODEV);attach();CHECK(qcom_cpr_msm8926_suspend_attach(&dev,&other)==-EBUSY);CHECK(qcom_cpr_msm8926_suspend_detach(&dev,&other)==-ESTALE);
 CHECK(!cpr_pm_prepare(&dev));CHECK(!qcom_cpr_msm8926_suspend_detach(&dev,&owner));CHECK(cpr_pm_prepare(&dev)==-EOPNOTSUPP);pm_suspend_target_state=PM_SUSPEND_TO_IDLE;CHECK(!cpr_pm_prepare(&dev));pm_suspend_target_state=2;CHECK(cpr_pm_prepare(&dev)==-EOPNOTSUPP);drv.msm8926=NULL;CHECK(!cpr_pm_prepare(&dev)&&!cpr_pm_suspend(&dev)&&!cpr_pm_resume(&dev));
}
static void prepare_cases(void) {
 for(int fault=0;fault<12;fault++) {reset();attach();suspend();
  if(fault==0)data.suspend_owner=&other;if(fault==1)drv.suspended=false;if(fault==2)data.suspend_was_applied=false;if(fault==3)drv.corner=NULL;if(fault==4){data.suspend_irq_disabled=true;irq_depth=1;}
  if(fault==5)cpr_regs[0]|=RBCPR_CTL_LOOP_EN;if(fault==6)cpr_regs[1]=1;if(fault==7)cpr_regs[2]=RBCPR_RESULT0_BUSY_MASK;if(fault==8)rate_error=-ERANGE;if(fault==9)fault_step=ops+1;if(fault==9)fault_kind=1;if(fault==10)so->request=750000;
  int ret=qcom_cpr_msm8926_suspend_prepare(&dev,&owner);CHECK((ret==0)==(fault==11));CHECK(!drv.lock.held&&disable_calls==1);
  if(fault==11){CHECK(data.sleep.active&&data.suspend_irq_disabled&&irq_depth==1);CHECK(!qcom_cpr_msm8926_suspend_restore(&dev,&owner));}
  else CHECK(enable_calls==1&&!data.sleep.active&&irq_depth==(fault==4?1:0));
  if(fault==7)CHECK(polls==1001);
 }
 for(int n=1;n<=90;n++) {reset();attach();suspend();fault_step=ops+n;fault_kind=1;int ret=qcom_cpr_msm8926_suspend_prepare(&dev,&owner);if(!ret){CHECK(qcom_cpr_msm8926_suspend_ready(&dev,&owner));}else {CHECK(!data.sleep.active&&!irq_depth&&!data.suspend_irq_disabled);}finish();}
}
static void readiness_cases(void) {
 for(int bad=0;bad<8;bad++) {reset();attach();suspend();CHECK(!qcom_cpr_msm8926_suspend_prepare(&dev,&owner));CHECK(qcom_cpr_msm8926_suspend_ready(&dev,&owner));
  if(bad==0)data.suspend_owner=&other;if(bad==1)data.suspend_irq_disabled=false;if(bad==2)data.sleep.active=false;if(bad==3)pllclk->enabled=1;if(bad==4)pllclk->prepared=1;if(bad==5)drv.suspended=false;if(bad==6)cpr_regs[0]=RBCPR_CTL_LOOP_EN;if(bad==7)cpr_regs[1]=1;CHECK(!qcom_cpr_msm8926_suspend_ready(&dev,&owner));
 }
 reset();attach();suspend();CHECK(!qcom_cpr_msm8926_suspend_prepare(&dev,&owner));CHECK(qcom_cpr_msm8926_suspend_restore(&dev,&other)==-ESTALE);CHECK(data.sleep.active&&irq_depth==1);CHECK(qcom_cpr_msm8926_suspend_detach(&dev,&owner)==-EBUSY);finish();CHECK(enable_calls==1);CHECK(!qcom_cpr_msm8926_suspend_restore(&dev,NULL));CHECK(enable_calls==1);
}
static void resume_guard_cases(void) {
 reset();attach();suspend();CHECK(!qcom_cpr_msm8926_suspend_prepare(&dev,&owner));CHECK(cpr_pm_resume(&dev)==-EBUSY);CHECK(drv.suspended&&data.sleep.active&&data.suspend_irq_disabled&&config_calls==0);finish();
 reset();attach();suspend();config_error=-EIO;CHECK(cpr_pm_resume(&dev)==-EIO);CHECK(drv.suspended&&!drv.lock.held);config_error=0;CHECK(!cpr_pm_resume(&dev));CHECK(!drv.suspended&&!data.applied);
}
int main(void) {reset();CHECK(!cpr_voltage_bootstrap(&rails,MAX_UV));attach_cases();prepare_cases();readiness_cases();resume_guard_cases();printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);return failures?1:0;}
