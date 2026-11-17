// SPDX-License-Identifier: GPL-2.0-only
static void reset(void) {
 CHECK(!live_allocations&&!mailboxes&&!notifiers&&!irq_requests&&!chrdevs&&!edge_memory);edge_node=(struct device_node){"smd-edge",NULL,1};syscon_node=(struct device_node){"syscon",NULL,1};parent_node=(struct device_node){"remoteproc","qcom,msm8226-rpm-proc",1};parent=(struct device){.of_node=&parent_node};child=(struct device){0};full_pm=smem_available=true;legacy_syscon=false;fail_at=ops=irq_disables=irq_flags=removed_children=cancel_calls=0;cases++;
}
static void refs(void) {EXPECT(edge_node.refs==1&&syscon_node.refs==1&&parent_node.refs==1);CHECK(!live_allocations&&!mailboxes&&!notifiers&&!irq_requests&&!chrdevs&&!edge_memory);}
int main(void) {
 for(int syscon=0;syscon<2;syscon++)for(int pm=0;pm<2;pm++)for(int msm=0;msm<2;msm++) {
  reset();legacy_syscon=syscon;full_pm=pm;if(!msm)parent_node.compatible="qcom,msm8916-rpm-proc";
  struct qcom_smd_edge *e=qcom_smd_register_edge(&parent,&edge_node);CHECK(!IS_ERR(e));int max_ops=ops;CHECK(e->no_suspend==(bool)(pm&&msm));CHECK(!!(irq_flags&IRQF_NO_SUSPEND)==(bool)(pm&&msm));CHECK(chrdevs==!(pm&&msm));CHECK(notifiers==(pm&&msm));qcom_smd_unregister_edge(e);refs();
  for(int fault_at=1;fault_at<=max_ops;fault_at++) {reset();legacy_syscon=syscon;full_pm=pm;if(!msm)parent_node.compatible="qcom,msm8916-rpm-proc";fail_at=fault_at;e=qcom_smd_register_edge(&parent,&edge_node);CHECK(IS_ERR(e));refs();}
 }
 reset();smem_available=false;CHECK(PTR_ERR(qcom_smd_register_edge(&parent,&edge_node))==-EPROBE_DEFER);refs();
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);return failures?1:0;
}
