// SPDX-License-Identifier: GPL-2.0-only
static void *secondary(void *p) {
 current_cpu=(uintptr_t)p;irq_off=true;msm8226_cpu_die(current_cpu);CHECK(!pm_depth&&!cluster_depth&&cpu_modes[current_cpu]==PM_SLEEP_MODE_STBY);return NULL;
}
static int pm_sleep_disable_secondary_cpus(void) {
 threaded_scenarios++;CHECK(!irq_off&&!device_irqs&&cpr_safe&&mpm_armed&&rpm_frozen);unsigned int count=fail_step==CPUS_OFF?2:4;
 for(unsigned int c=1;c<count;c++) {
  CHECK(!msm8226_cpu_disable(c));atomic_fetch_sub(&online_cpus,1);CHECK(!pthread_create(&cpu_threads[c],NULL,secondary,(void *)(uintptr_t)c));started[c]=true;
  CHECK(!pthread_mutex_lock(&wake_lock));while(!atomic_load(&arrived[c]))CHECK(!pthread_cond_wait(&wake_cond,&wake_lock));CHECK(!pthread_mutex_unlock(&wake_lock));
  if(!qcom_msm8226_cpu_kill(c))return -EIO;
 }
 return fail_step==CPUS_OFF?-EIO:0;
}
static void pm_sleep_enable_secondary_cpus(void) {
 CHECK(!irq_off&&!device_irqs);
 for(unsigned int c=1;c<4;c++)if(started[c]) {CHECK(!msm8226_boot_secondary(c,NULL));CHECK(!pthread_join(cpu_threads[c],NULL));started[c]=false;atomic_fetch_add(&online_cpus,1);}
 CHECK(num_online_cpus()==4);
}
static void genpd_request(void) {CHECK(!irq_off&&!rpm_frozen&&!rx_masked);genpd_requests++;}
static int dpm_suspend_late(int msg) {
 CHECK(device_irqs&&!irq_off&&!cpr_quiesced);cpr_quiesced=true;late_done=true;
 int ret=fail_step==DPM_LATE?-EIO:msm8226_pm_suspend_late(msm8226_pm->dev);
 if(ret) {cpr_quiesced=false;late_done=false;CHECK(!msm8226_pm->voltage_prepared);}
 return ret;
}
static int dpm_suspend_noirq(int msg) {
 CHECK(device_irqs&&!irq_off&&late_done);device_irqs=false;genpd_request();
 if(fail_step==DPM_NOIRQ) {genpd_request();device_irqs=true;return -EIO;}return 0;
}
static void dpm_resume_noirq(int msg) {CHECK(!device_irqs&&!irq_off&&!mpm_armed);genpd_request();device_irqs=true;}
static void dpm_resume_early(int msg) {
 CHECK(device_irqs&&!irq_off&&late_done);CHECK(!msm8226_pm_resume_early(msm8226_pm->dev));CHECK(!cpr_safe);cpr_quiesced=false;late_done=false;
}
static void arch_suspend_disable_irqs(void) {CHECK(!irq_off&&num_online_cpus()==1);irq_off=true;}
static void arch_suspend_enable_irqs(void) {CHECK(irq_off&&!core_suspended&&!pm_depth&&!cluster_depth);CHECK(l2_mode==SPM_L2_MODE_DISABLED&&cpu_modes[0]==PM_SLEEP_MODE_STBY);irq_off=false;}
static int syscore_suspend(void) {CHECK(irq_off&&!core_suspended);if(fail_step==SYSCORE_OFF)return -EIO;core_suspended=true;return 0;}
static void syscore_resume(void) {CHECK(irq_off&&core_suspended);CHECK(l2_mode==SPM_L2_MODE_DISABLED&&cpu_modes[0]==PM_SLEEP_MODE_STBY);core_suspended=false;}
static bool pm_wakeup_pending(void) {return pending;}
static int suspend_test(int level) {return test_level==level;}
static void s2idle_loop(void) {CHECK(!irq_off&&!device_irqs&&!cpr_safe&&!rpm_frozen&&!mpm_armed);}
