// SPDX-License-Identifier: GPL-2.0-only
static void reset(void) {
 CHECK(!allocation);memset(nodes,0,sizeof(nodes));for(int i=0;i<18;i++)nodes[i]=(struct device_node){.id=i,.refs=1,.available=true};
 nodes[1].compatible="qcom,msm8926-cpr";nodes[2].compatible="qcom,mpm";nodes[3].compatible="qcom,msm8226-saw2-v2.1-l2";
 for(int i=4;i<8;i++)nodes[i].compatible="qcom,msm8226-saw2-v2.1-cpu";for(int i=10;i<14;i++)nodes[i].compatible="arm,cortex-a7";
 nodes[8].compatible="qcom,rpm-msm8226";pdev=(struct platform_device){.dev={.of_node=&nodes[0],.parent=&rpm_dev,.refs=1}};rpm_dev=(struct device){.of_node=&nodes[8],.refs=1,.bound=true,.data=&rpm};
 for(int i=0;i<7;i++)providers[i]=(struct platform_device){.dev={.of_node=&nodes[i+1],.refs=1,.bound=true}};
 providers[0].dev.data=&cpr_owner;providers[1].dev.data=&mpm_owner;providers[2].dev.data=&l2;
 for(int i=0;i<4;i++){spms[i].cpu=i;providers[i+3].dev.data=&spms[i];msm8226_cpu_spm[i]=NULL;}
 msm8226_pm=NULL;memset(links,0,sizeof(links));fail_at=ops=link_count=mpm_owner=rpm_owner=cpr_owner=warm_calls=install_calls=uninstall_calls=cancel_calls=0;installed_ops=NULL;in_probe=hotplug_writer=offline_at_publish=system_sleep_mutex=false;scm_available=true;online_mask=present_mask=15;present_count=4;cases++;
}
static int probe(void) {in_probe=system_sleep_mutex=true;int ret=msm8226_pm_probe(&pdev);in_probe=system_sleep_mutex=false;return ret;}
static void core_cleanup(void) {for(int i=0;i<link_count;i++){if(links[i].flags==DL_FLAG_AUTOREMOVE_CONSUMER)links[i].live=false;CHECK(!links[i].live);}for(int i=0;i<18;i++)CHECK(nodes[i].refs==1);for(int i=0;i<7;i++)CHECK(providers[i].dev.refs==1);CHECK(!hotplug_writer&&!mpm_owner&&!rpm_owner&&!cpr_owner&&!msm8226_pm);free(allocation);allocation=NULL;pdev.dev.data=NULL;}
static void successful(bool install_first) {CHECK(msm8226_pm==pdev.dev.data&&mpm_owner&&rpm_owner&&cpr_owner&&warm_calls==1);struct msm8226_pm *pm=pdev.dev.data;CHECK(pm&&pm->install_work.scheduled);for(int c=0;c<4;c++)CHECK(msm8226_cpu_spm[c]==&spms[c]);if(install_first){pm->install_work.scheduled=false;pm->install_work.fn(&pm->install_work);CHECK(install_calls==1);}msm8226_pm_remove(&pdev);CHECK(cancel_calls==1&&!pm->install_work.scheduled);CHECK(install_calls==(install_first?1:0)&&uninstall_calls==1&&!installed_ops);for(int c=0;c<4;c++)CHECK(msm8226_cpu_spm[c]==&spms[c]);core_cleanup();}
int main(void) {
 reset();CHECK(!probe());int max_ops=ops;successful(true);
 for(int step=1;step<=max_ops;step++) {reset();fail_at=step;int ret=probe();CHECK(ret<0);CHECK(!pdev.dev.data&&!msm8226_pm);if(allocation)CHECK(!((struct msm8226_pm *)allocation)->install_work.scheduled);core_cleanup();}
 reset();CHECK(!probe());successful(false);
 for(int bad=0;bad<10;bad++) {reset();if(bad==0)scm_available=false;if(bad==1)rpm_dev.bound=false;if(bad==2)rpm_dev.data=NULL;if(bad==3)nodes[8].compatible="qcom,rpm-msm8916";if(bad==4)nodes[1].compatible="qcom,not-cpr";if(bad==5)nodes[2].available=false;if(bad==6)providers[0].dev.data=NULL;if(bad==7)present_count=3;if(bad==8)nodes[10].compatible="arm,cortex-a53";if(bad==9)offline_at_publish=true;CHECK(probe()<0);core_cleanup();}
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":0,\"fault_positions\":%d}\n",cases,checks,max_ops);return 0;
}
