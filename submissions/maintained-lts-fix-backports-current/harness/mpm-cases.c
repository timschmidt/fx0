// SPDX-License-Identifier: GPL-2.0-only
static void reset(void) {
 CHECK(!allocation_count);ops=fail_at=0;failure_error=-EPROBE_DEFER;pin_count=64;full_pm=false;
 genpd_live=provider_live=mailbox_live=domain_live=irq_live=false;
 mpm_node=(struct device_node){.id=1,.refs=1};parent_node=(struct device_node){.id=2,.refs=1};
 sram_node=(struct device_node){.id=3,.refs=1};parent=(struct device){.of_node=&parent_node};
 pdev=(struct platform_device){.dev={.of_node=&mpm_node,.parent=&parent}};cases++;
}
static void release(void) {EXPECT(sram_node.refs==1);while(allocation_count)free(allocations[--allocation_count]);}
static void success_cleanup(void) {
 CHECK(genpd_live&&provider_live&&mailbox_live&&domain_live&&irq_live&&allocation_count);
 struct qcom_mpm_priv *priv=allocations[0];irq_live=false;irq_domain_remove(&domain);
 mbox_free_channel(&mailbox);of_genpd_del_provider(&mpm_node);CHECK(!pm_genpd_remove(&priv->genpd));release();
}
int main(void) {
 reset();CHECK(!qcom_mpm_probe(&pdev,&parent_node));int max=ops;success_cleanup();
 for(int error=0;error<3;error++)for(int step=1;step<=max;step++) {
  reset();const int errors[]={-ENOMEM,-EIO,-EPROBE_DEFER};failure_error=errors[error];fail_at=step;
  int ret=qcom_mpm_probe(&pdev,&parent_node);CHECK(ret<0);
  EXPECT(!genpd_live&&!provider_live&&!mailbox_live&&!domain_live&&!irq_live);release();
 }
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);return failures?1:0;
}
