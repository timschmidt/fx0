// SPDX-License-Identifier: GPL-2.0-only
static struct msm8226_pm pm;
static struct device dev;
static struct platform_device cpr_dev,mpm_dev;
static struct spm_driver_data spms[4],l2;
static struct qcom_smd_rpm rpm;
static void reset(void) {
 memset(&pm,0,sizeof(pm));dev.data=&pm;pm.dev=&dev;pm.cpr=&cpr_dev;pm.mpm=&mpm_dev;pm.rpm=&rpm;pm.l2=&l2;
 msm8226_pm=&pm;
 for(unsigned int c=0;c<4;c++) {spms[c].cpu=c;msm8226_cpu_spm[c]=&spms[c];pm.acc[c]=acc[c];atomic_store(&acc[c][2],0);atomic_store(&arrived[c],0);atomic_store(&msm8226_boot_requested[c],false);atomic_store(&cpu_modes[c],PM_SLEEP_MODE_STBY);CHECK(!started[c]);for(int i=0;i<1024;i++)atomic_store(&gic_regs[c][i],U32_MAX);}
 current_cpu=0;irq_off=false;pm_depth=cluster_depth=0;online_cpus=4;l2_mode=SPM_L2_MODE_DISABLED;cache_clean=outer_clean=scm_calls=genpd_requests=enter_calls=0;
 cpr_quiesced=cpr_safe=rpm_frozen=rx_masked=mpm_armed=core_suspended=late_done=false;device_irqs=true;
 gic_drop_clear=gic_boot_during_clear=lose_secondary_at_cluster=lose_secondary_at_cpu_arm=false;fail_step=test_level=0;pending=false;firmware_wake=true;gic_data[0].available=true;suspend_ops=&msm8226_suspend_ops;s2idle_ops=NULL;system_state=SYSTEM_RUNNING;pm_suspend_target_state=PM_SUSPEND_MEM;cases++;
}
static void verify_done(void) {
 CHECK(device_irqs&&!irq_off&&!cpr_quiesced&&!cpr_safe&&!rpm_frozen&&!rx_masked&&!mpm_armed&&!core_suspended&&!late_done);
 CHECK(!pm.voltage_prepared&&!pm.transport_prepared&&!pm.mpm_prepared);CHECK(num_online_cpus()==4&&!pm_depth&&!cluster_depth&&l2_mode==SPM_L2_MODE_DISABLED);
 for(unsigned int c=0;c<4;c++)CHECK(!started[c]&&cpu_modes[c]==PM_SLEEP_MODE_STBY&&!readl_relaxed(&acc[c][2]));
 CHECK(system_state==SYSTEM_RUNNING);
}
static void dispatcher_cases(void) {
 for(int failure=0;failure<=SECONDARY_NOT_READY;failure++)for(int test=0;test<=TEST_CORE;test++)for(int wake=0;wake<2;wake++) {
  reset();fail_step=failure;test_level=test;pending=wake;bool woke=false;int ret=suspend_enter(PM_SUSPEND_MEM,&woke);verify_done();
  if(!failure&&!test&&!wake){CHECK(!ret&&scm_calls==1&&cache_clean==1&&outer_clean==1&&genpd_requests==2);}
  if(failure==CPR_PREPARE||failure==DPM_LATE)CHECK(ret==-EIO&&!genpd_requests);
  CHECK(scm_calls<=1&&cache_clean==outer_clean);
 }
 reset();firmware_wake=false;bool woke=false;CHECK(suspend_enter(PM_SUSPEND_MEM,&woke)==-EAGAIN);verify_done();CHECK(scm_calls==1);
 reset();pm_suspend_target_state=PM_SUSPEND_TO_IDLE;CHECK(!suspend_enter(PM_SUSPEND_TO_IDLE,&woke));verify_done();CHECK(!scm_calls&&genpd_requests==2);
}
static void direct_guards(void) {
 for(int missing=0;missing<12;missing++) {
  reset();irq_off=true;online_cpus=1;cpr_quiesced=cpr_safe=rpm_frozen=rx_masked=mpm_armed=true;pm.voltage_prepared=pm.transport_prepared=pm.mpm_prepared=true;
  for(int c=1;c<4;c++)atomic_store(&acc[c][2],MSM8226_CPU_COLLAPSED);
  if(missing==0)msm8226_pm=NULL;
  if(missing==1)current_cpu=1;
  if(missing==2)irq_off=false;
  if(missing==3)online_cpus=2;
  if(missing==4)pm.voltage_prepared=false;
  if(missing==5)pm.transport_prepared=false;
  if(missing==6)pm.mpm_prepared=false;
  if(missing==7)cpr_safe=false;
  if(missing==8)rpm_frozen=false;
  if(missing==9)mpm_armed=false;
  if(missing==10)atomic_store(&acc[2][2],0);
  if(missing==11)atomic_store(&acc[3][2],0);
  CHECK(msm8226_suspend_enter(PM_SUSPEND_MEM)<0);CHECK(!scm_calls&&!pm_depth&&!cluster_depth&&l2_mode==SPM_L2_MODE_DISABLED);
 }
 reset();irq_off=true;CHECK(msm8226_suspend_enter(PM_SUSPEND_TO_IDLE)==-EINVAL);irq_off=false;
 CHECK(qcom_msm8226_cpu_collapse(0)==-EINVAL);CHECK(qcom_msm8226_cpu_collapse(4)==-EINVAL);current_cpu=1;CHECK(qcom_msm8226_cpu_collapse(1)==-EINVAL);irq_off=true;CHECK(qcom_msm8226_cpu_collapse(2)==-EINVAL);irq_off=false;current_cpu=0;
 CHECK(!qcom_msm8226_cpu_kill(0)&&!qcom_msm8226_cpu_kill(4)&&!qcom_msm8226_cpu_kill(1));msm8226_pm=NULL;CHECK(qcom_msm8226_cpu_kill(1));CHECK(!qcom_msm8226_pm_active());msm8226_pm=&pm;CHECK(qcom_msm8226_pm_active());CHECK(msm8226_cpu_disable(0)==-EPERM);
}
static void gic_cases(void) {
 reset();gic_drop_clear=true;irq_off=true;CHECK(gic_cpu_quiesce_ppis(0)==-EIO);irq_off=false;
 reset();gic_boot_during_clear=true;current_cpu=1;irq_off=true;CHECK(!msm8226_cpu_disable(1));msm8226_cpu_die(1);CHECK(!pm_depth&&!cluster_depth&&cpu_modes[1]==PM_SLEEP_MODE_STBY&&!arrived[1]);current_cpu=0;irq_off=false;
 reset();gic_drop_clear=true;bool woke=false;CHECK(suspend_enter(PM_SUSPEND_MEM,&woke)==-EIO);verify_done();CHECK(!scm_calls);
 for(int stage=0;stage<2;stage++){reset();lose_secondary_at_cluster=!stage;lose_secondary_at_cpu_arm=stage;CHECK(suspend_enter(PM_SUSPEND_MEM,&woke)==-EBUSY);verify_done();CHECK(!scm_calls&&!cache_clean&&!outer_clean);}

 reset();CHECK(gic_cpu_quiesce_ppis(0)==-EINVAL);irq_off=true;CHECK(gic_cpu_quiesce_ppis(1)==-EINVAL);gic_data[0].available=false;CHECK(gic_cpu_quiesce_ppis(0)==-ENODEV);gic_data[0].available=true;
 CHECK(!gic_cpu_quiesce_ppis(0));CHECK(readl_relaxed(&gic_regs[0][GIC_DIST_ENABLE_SET/4])==0xffff);for(int i=0;i<4;i++)CHECK(!readl_relaxed(&gic_regs[0][GIC_DIST_SGI_PENDING_CLEAR/4+i]));irq_off=false;
}
int main(void) {alarm(40);dispatcher_cases();direct_guards();gic_cases();printf("{\"cases\":%d,\"checks\":%d,\"failures\":0,\"dispatcher_scenarios\":136,\"scenarios_starting_secondary_threads\":%d}\n",cases,atomic_load(&checks),threaded_scenarios);return 0;}
