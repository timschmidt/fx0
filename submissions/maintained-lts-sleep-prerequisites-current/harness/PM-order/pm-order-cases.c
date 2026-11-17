// SPDX-License-Identifier: GPL-2.0-only
static int mem_prepare(void) { event(PREPARE);CHECK(device_irqs&&!irq_disabled);return failure(PREPARE); }
static int mem_late(void) { event(MEM_LATE);CHECK(!device_irqs&&!irq_disabled&&admission_closed);return failure(MEM_LATE); }
static int mem_enter(suspend_state_t s) { event(ENTER);CHECK(s==PM_SUSPEND_MEM&&irq_disabled&&!device_irqs&&admission_closed&&core_suspended);return failure(ENTER); }
static void mem_wake(void) { event(MEM_WAKE);CHECK(!device_irqs&&!irq_disabled&&admission_closed); }
static void mem_finish(void) { event(FINISH);CHECK(device_irqs&&!irq_disabled&&!admission_closed&&!late_done); }
static int idle_prepare(void) { event(IDLE_PREPARE);CHECK(device_irqs&&!irq_disabled);return failure(IDLE_PREPARE); }
static int idle_late(void) { event(IDLE_LATE);CHECK(!device_irqs&&!irq_disabled);return failure(IDLE_LATE); }
static void idle_wake(void) { event(IDLE_WAKE);CHECK(!device_irqs&&!irq_disabled); }
static void idle_restore(void) { event(IDLE_RESTORE);CHECK(device_irqs&&!irq_disabled); }
static int index_of(int code) { for (int i=0;i<num_events;i++)if (events[i]==code)return i;return -1; }
int main(void) {
 mem_ops=(struct platform_suspend_ops){.prepare=mem_prepare,.prepare_late=mem_late,.enter=mem_enter,.wake=mem_wake,.finish=mem_finish};
 idle_ops=(struct platform_s2idle_ops){.prepare=idle_prepare,.prepare_late=idle_late,.restore_early=idle_wake,.restore=idle_restore};
 for (int state=PM_SUSPEND_TO_IDLE;state<=PM_SUSPEND_MEM;state+=2)
 for (int step=0;step<=ENTER;step++)for (int test=0;test<=TEST_CORE;test++)for (int wake=0;wake<2;wake++) {
  irq_disabled=false;device_irqs=true;late_done=false;admission_closed=false;cpus_disabled=false;core_suspended=false;num_events=0;
  fail_step=step;test_level=test;pending=wake;system_state=SYSTEM_RUNNING;bool woke=false;
  (void)suspend_enter(state,&woke);
  CHECK(device_irqs&&!irq_disabled&&!admission_closed&&!late_done&&!cpus_disabled&&!core_suspended);
  if (state==PM_SUSPEND_MEM) {
   CHECK(index_of(IDLE_PREPARE)<0&&index_of(IDLE_LATE)<0&&index_of(IDLE_WAKE)<0&&index_of(IDLE_RESTORE)<0);
   if (index_of(MEM_LATE)>=0) CHECK(index_of(MEM_LATE)>index_of(DPM_NOIRQ));
   if (index_of(MEM_WAKE)>=0) CHECK(index_of(MEM_WAKE)<index_of(DPM_RESUME_NOIRQ));
   CHECK(index_of(FINISH)>=0);
   if (index_of(DPM_EARLY)>=0) CHECK(index_of(FINISH)>index_of(DPM_EARLY));
  } else {
   CHECK(index_of(PREPARE)<0&&index_of(MEM_LATE)<0&&index_of(MEM_WAKE)<0&&index_of(FINISH)<0&&index_of(ENTER)<0);
   if (index_of(IDLE_RESTORE)>=0) { CHECK(index_of(IDLE_RESTORE)>index_of(IDLE_PREPARE));CHECK(index_of(IDLE_RESTORE)<index_of(DPM_EARLY)); }
  }
  if (!step&&!test&&!wake) {
   const int mem_expected[]={PREPARE,DPM_LATE,DPM_NOIRQ,MEM_LATE,CPUS_OFF,IRQS_OFF,CORE_OFF,ENTER,CORE_ON,IRQS_ON,CPUS_ON,MEM_WAKE,DPM_RESUME_NOIRQ,DPM_EARLY,FINISH};
   const int idle_expected[]={DPM_LATE,IDLE_PREPARE,DPM_NOIRQ,IDLE_LATE,IDLE_LOOP,IDLE_WAKE,DPM_RESUME_NOIRQ,IDLE_RESTORE,DPM_EARLY};
   const int *expected=state==PM_SUSPEND_MEM?mem_expected:idle_expected;
   size_t count=state==PM_SUSPEND_MEM?sizeof(mem_expected)/sizeof(int):sizeof(idle_expected)/sizeof(int);
   CHECK(num_events==(int)count);CHECK(!memcmp(events,expected,count*sizeof(int)));
  }
  cases++;
 }
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":0}\n",cases,checks);return 0;
}
