// SPDX-License-Identifier: GPL-2.0-only
static struct qcom_smd_edge edge;
static struct qcom_smd_channel channel;
static struct qcom_smd_endpoint endpoint;
static struct qcom_smd_rpm rpm;
static struct device parent,client,other;
static void reset(void) {
 memset(&edge,0,sizeof(edge));CHECK(!pthread_mutex_init(&edge.sleep_lock.native,NULL));edge.no_suspend=true;edge.irq=91;
 channel=(struct qcom_smd_channel){.edge=&edge,.name="rpm_requests",.qsept=&endpoint,.state=SMD_CHANNEL_OPENED,.rx_state=SMD_CHANNEL_OPENED};endpoint=(struct qcom_smd_endpoint){.ept={.ops=&qcom_smd_endpoint_ops},.qsch=&channel};
 memset(&rpm,0,sizeof(rpm));CHECK(!pthread_mutex_init(&rpm.lock.native,NULL));rpm.rpm_channel=&endpoint.ept;rpm.dev=&parent;watched=&rpm;client.parent=other.parent=&parent;
 irq_off=false;irq_depth=disable_calls=enable_calls=0;scan_runs=state_runs=removed=0;worker_block=channel_closed=worker_entered=false;cases++;
}
static void fini(void) {CHECK(!rpm.sleep_owner&&!rpm.system_token.cookie&&!rpm.receive_masked&&!irq_depth);CHECK(!pthread_mutex_destroy(&rpm.lock.native));CHECK(!pthread_mutex_destroy(&edge.sleep_lock.native));}
static void register_client(void) {CHECK(!qcom_rpm_smd_register_sleep(&rpm,&client));CHECK(rpm.sleep_client==&client&&rpm.receive_irq==91);}
static void gate_cases(void) {
 reset();CHECK(qcom_rpm_smd_register_sleep(NULL,&client)==-EINVAL);CHECK(qcom_rpm_smd_register_sleep(&rpm,NULL)==-EINVAL);client.parent=&other;CHECK(qcom_rpm_smd_register_sleep(&rpm,&client)==-EINVAL);client.parent=&parent;
 endpoint.ept.ops=&other_ops;CHECK(qcom_rpm_smd_register_sleep(&rpm,&client)==-EOPNOTSUPP);endpoint.ept.ops=&qcom_smd_endpoint_ops;
 register_client();CHECK(qcom_rpm_smd_register_sleep(&rpm,&other)==-EBUSY);CHECK(qcom_rpm_smd_unregister_sleep(&rpm,&other)==-EINVAL);CHECK(qcom_rpm_smd_prepare_sleep(&rpm,&other)==-EINVAL);
 irq_off=true;CHECK(qcom_rpm_smd_prepare_sleep(&rpm,&client)==-EPERM);irq_off=false;CHECK(!disable_calls);
 for(int n=0;n<40;n++) {
  CHECK(!qcom_rpm_smd_prepare_sleep(&rpm,&client));CHECK(irq_depth==1&&rpm.receive_masked&&rpm.sleep_owner==&rpm.system_token);CHECK(!pthread_mutex_trylock(&rpm.lock.native));CHECK(!pthread_mutex_unlock(&rpm.lock.native));
  CHECK(qcom_rpm_smd_prepare_sleep(&rpm,&client)==-EINVAL);CHECK(qcom_rpm_smd_unregister_sleep(&rpm,&client)==-EBUSY);CHECK(qcom_rpm_smd_sleep_ready(&rpm,&client));
  CHECK(!qcom_rpm_smd_sleep_ready(&rpm,&other));channel.rx_state=SMD_CHANNEL_CLOSED;CHECK(!qcom_rpm_smd_sleep_ready(&rpm,&client));channel.rx_state=SMD_CHANNEL_OPENED;
  u64 saved=rpm.system_token.cookie;rpm.system_token.cookie++;CHECK(!qcom_rpm_smd_sleep_ready(&rpm,&client));rpm.system_token.cookie=saved;
  CHECK(qcom_rpm_smd_finish_sleep(&rpm,&other)==-EPERM);irq_off=true;CHECK(qcom_rpm_smd_finish_sleep(&rpm,&client)==-EPERM);irq_off=false;
  CHECK(!qcom_rpm_smd_finish_sleep(&rpm,&client));CHECK(!irq_depth&&!rpm.receive_masked&&!rpm.sleep_owner&&!rpm.system_token.cookie);CHECK(!qcom_rpm_smd_finish_sleep(&rpm,&client));
  CHECK(disable_calls==n+1&&enable_calls==n+1);cases++;
 }
 CHECK(!qcom_rpm_smd_unregister_sleep(&rpm,&client));fini();
 for(int fault=0;fault<3;fault++) {reset();register_client();if(fault==0)rpm.uncertain=true;if(fault==1)rpm.sleep_sequence=U64_MAX;if(fault==2)rpm.system_token.cookie=1;
  CHECK(qcom_rpm_smd_prepare_sleep(&rpm,&client)==(fault==0?-EIO:fault==1?-EOVERFLOW:-EINVAL));CHECK(!disable_calls&&!rpm.receive_masked);rpm.system_token.cookie=0;CHECK(!qcom_rpm_smd_unregister_sleep(&rpm,&client));fini();}
}
static void endpoint_cases(void) {
 for(int fault=0;fault<8;fault++){reset();int want=91;
  if(fault==0)endpoint.ept.ops=&other_ops;
  if(fault==1)edge.no_suspend=false;
  if(fault==2)channel.name="other_channel";
  if(fault==3)channel.qsept=NULL;
  if(fault==4)channel.state=SMD_CHANNEL_CLOSED;
  if(fault==5)channel.rx_state=SMD_CHANNEL_CLOSED;
  if(fault<3)want=-EOPNOTSUPP;if(fault==3)want=-EBUSY;if(fault==4||fault==5)want=-ENOTCONN;
  CHECK(qcom_smd_rpm_get_irq(&endpoint.ept)==want);CHECK(qcom_smd_rpm_get_irq(NULL)==-EOPNOTSUPP);fini();}
}
static void run_scheduled(void) {if(edge.scan_work.scheduled){edge.scan_work.scheduled=false;qcom_channel_scan_worker(&edge.scan_work);}if(edge.state_work.scheduled){edge.state_work.scheduled=false;qcom_channel_state_worker(&edge.state_work);}}
static void notifier_cases(void) {
 for(unsigned int prep=PM_SUSPEND_PREPARE;prep<=PM_RESTORE_PREPARE;prep++)for(int early_abort=0;early_abort<2;early_abort++) {
  reset();CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,0,NULL)==NOTIFY_DONE);CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,prep,NULL)==NOTIFY_OK);CHECK(edge.system_sleep);CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,prep,NULL)==NOTIFY_BAD);CHECK(edge.system_sleep);
  channel_closed=true;qcom_channel_scan_worker(&edge.scan_work);qcom_channel_state_worker(&edge.state_work);CHECK(!scan_runs&&!state_runs&&!removed);
  if(!early_abort){CHECK(qcom_smd_rpm_get_irq(&endpoint.ept)==91);}
  CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,prep+3,NULL)==NOTIFY_OK);CHECK(!edge.system_sleep&&edge.scan_work.scheduled&&edge.state_work.scheduled);run_scheduled();CHECK(scan_runs==1&&state_runs==1&&removed==1);
  fini();
 }
 reset();edge.no_suspend=false;edge.system_sleep=true;qcom_channel_scan_worker(&edge.scan_work);qcom_channel_state_worker(&edge.state_work);CHECK(scan_runs==1&&state_runs==1);edge.system_sleep=false;fini();
}
static void *worker(void *p) {qcom_channel_state_worker(p);return NULL;}
static void concurrent_cases(void) {
 for(int n=0;n<20;n++) {
  reset();worker_block=true;CHECK(!pthread_mutex_lock(&system_sleep_lock));pthread_t t;CHECK(!pthread_create(&t,NULL,worker,&edge.state_work));CHECK(!pthread_mutex_lock(&gate));while(!worker_entered)CHECK(!pthread_cond_wait(&cond,&gate));CHECK(!pthread_mutex_unlock(&gate));
  /* Worker holds edge lock and waits for the sleep mutex held by this thread. */
  CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,PM_SUSPEND_PREPARE,NULL)==NOTIFY_BAD);CHECK(!edge.system_sleep);
  CHECK(!pthread_mutex_unlock(&system_sleep_lock));CHECK(!pthread_join(t,NULL));CHECK(state_runs==1);worker_block=false;
  CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,PM_SUSPEND_PREPARE,NULL)==NOTIFY_OK);CHECK(qcom_smd_sleep_notify(&edge.sleep_nb,PM_POST_SUSPEND,NULL)==NOTIFY_OK);run_scheduled();fini();
 }
}
int main(void) {alarm(35);gate_cases();endpoint_cases();notifier_cases();concurrent_cases();printf("{\"cases\":%d,\"checks\":%d,\"failures\":0,\"threaded_busy_worker_cases\":20}\n",cases,atomic_load(&checks));return 0;}
