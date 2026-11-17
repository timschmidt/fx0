// SPDX-License-Identifier: GPL-2.0-only
static struct qcom_mpm_priv p;
static struct device dev,owner,other;
static struct irq_domain mpm_domain,gic_domain,gpio_domain,spmi_domain,mdss_domain;
static struct irq_desc desc[128];
static struct irq_data parents[128];
static struct irqaction active,second;
static struct mpm_gic_map maps[4];
static u32 regs[170],image[128];
static struct mbox_chan channel;
static void cleanup(void) {
 while(action_count){--action_count;actions[action_count].f(actions[action_count].p);}
 while(allocation_count)free(allocations[--allocation_count]);
 for(int i=0;i<12;i++)CHECK(nodes[i].refs==1);
 CHECK(root.refs==1&&!lock_depth&&!rcu_depth);
}
static void reset(void) {
 memset(&p,0,sizeof(p));memset(regs,0,sizeof(regs));memset(image,0,sizeof(image));
 memset(descriptors,0,sizeof(descriptors));memset(pin_desc,0,sizeof(pin_desc));memset(desc,0,sizeof(desc));memset(parents,0,sizeof(parents));memset(replay_count,0,sizeof(replay_count));
 memset(nodes,0,sizeof(nodes));root=(struct device_node){.id=-1,.refs=1};
 for(int i=0;i<12;i++)nodes[i]=(struct device_node){.id=i,.refs=1,.irq_count=1,.args_count=2,.pin=2,.parent=&root,.controller=true};
 node_count=pass_number=0;add_second_pass=alloc_fail=false;action_fail=action_attempt=0;
 mbox_error=mbox_calls=txdone=replays=0;current_cpu=0;online_cpus=1;local_irqs_off=false;
 mpm_domain=(struct irq_domain){.fwnode=&root,.parent=&gic_domain};gic_domain=(struct irq_domain){0};gpio_domain=(struct irq_domain){.fwnode=&nodes[2]};spmi_domain=(struct irq_domain){.fwnode=&nodes[0]};mdss_domain=(struct irq_domain){.fwnode=&nodes[1]};
 maps[0]=(struct mpm_gic_map){2,184};maps[1]=(struct mpm_gic_map){47,140};maps[2]=(struct mpm_gic_map){53,72};maps[3]=(struct mpm_gic_map){62,190};
 p.base=regs;p.sleep_image=image;p.pin_count=64;p.reg_stride=2;p.maps=maps;p.map_cnt=4;p.domain=&mpm_domain;p.irq=5;p.mbox_chan=&channel;
 dev=(struct device){.data=&p,.of_node=&root};owner=(struct device){0};other=(struct device){0};
 active=(struct irqaction){.flags=IRQF_NO_SUSPEND};second=(struct irqaction){0};
 p.sleep_owner=&owner;
 cases++;
}
static struct irq_desc *add_irq(unsigned int irq,struct irq_domain *domain,unsigned int pin,bool armed,bool enabled) {
 desc[irq].irq_data=(struct irq_data){.domain=domain,.hwirq=pin,.irq=irq,.armed=armed,.disabled=!enabled};
 descriptors[irq]=&desc[irq];return &desc[irq];
}
static void pin_enable(unsigned int pin) {regs[2+pin/32]|=BIT(pin%32);}
static void map_irq(unsigned int pin,struct irq_desc *d) {pin_desc[pin]=d;pin_enable(pin);}
static void prepare(void) {int old_calls=mbox_calls,old_done=txdone;CHECK(!qcom_mpm_prepare_sleep(&dev,&owner));CHECK(p.sleep_prepared&&mbox_calls==old_calls+1&&txdone==old_done+1);}
static bool ready(void) {local_irqs_off=true;bool r=qcom_mpm_sleep_ready(&dev,&owner);local_irqs_off=false;return r;}
static void base(void) {reset();map_irq(2,add_irq(10,&mpm_domain,2,true,true));}
static void test_lifecycle(void) {
 reset();p.sleep_owner=NULL;CHECK(qcom_mpm_register_sleep(&dev,NULL)==-EPROBE_DEFER);dev.data=NULL;CHECK(qcom_mpm_register_sleep(&dev,&owner)==-EPROBE_DEFER);dev.data=&p;
 p.sleep_image=NULL;CHECK(qcom_mpm_register_sleep(&dev,&owner)==-EOPNOTSUPP);p.sleep_image=image;
 CHECK(!qcom_mpm_register_sleep(&dev,&owner));CHECK(qcom_mpm_register_sleep(&dev,&other)==-EBUSY);CHECK(qcom_mpm_unregister_sleep(&dev,&other)==-ESTALE);CHECK(!qcom_mpm_unregister_sleep(&dev,&owner));cleanup();
 base();CHECK(qcom_mpm_prepare_sleep(&dev,&other)==-EINVAL);local_irqs_off=true;CHECK(qcom_mpm_prepare_sleep(&dev,&owner)==-EPERM);local_irqs_off=false;CHECK(!mbox_calls);prepare();CHECK(qcom_mpm_prepare_sleep(&dev,&owner)==-EINVAL);CHECK(qcom_mpm_unregister_sleep(&dev,&owner)==-EBUSY);CHECK(ready());CHECK(qcom_mpm_finish_sleep(&dev,&other)==-ESTALE);CHECK(p.sleep_prepared);CHECK(!qcom_mpm_finish_sleep(&dev,&owner));CHECK(!p.sleep_prepared);CHECK(!qcom_mpm_finish_sleep(&dev,&owner));CHECK(!qcom_mpm_unregister_sleep(&dev,&owner));cleanup();
 reset();CHECK(qcom_mpm_prepare_sleep(&dev,&owner)==-EINVAL);CHECK(!mbox_calls&&!p.sleep_prepared);cleanup();
 reset();pin_enable(1);CHECK(qcom_mpm_prepare_sleep(&dev,&owner)==-EINVAL);CHECK(!mbox_calls);cleanup();
 reset();p.pin_count=63;pin_enable(63);pin_desc[63]=&desc[10];CHECK(qcom_mpm_prepare_sleep(&dev,&owner)==-EINVAL);CHECK(!mbox_calls);cleanup();
 base();regs[10]=~0U;regs[11]=~0U;mbox_error=-EIO;CHECK(qcom_mpm_prepare_sleep(&dev,&owner)==-EIO);CHECK(!p.sleep_prepared&&mbox_calls==1&&!txdone);CHECK(regs[0]==U32_MAX&&regs[1]==U32_MAX&&!regs[10]&&!regs[11]);mbox_error=0;prepare();cleanup();
 base();CHECK(mpm_pd_power_off(&p.genpd)==-EBUSY);CHECK(!mbox_calls);p.sleep_owner=NULL;CHECK(!mpm_pd_power_off(&p.genpd));CHECK(mbox_calls==1&&txdone==1);mbox_error=-EIO;CHECK(mpm_pd_power_off(&p.genpd)==-EIO);CHECK(txdone==1);cleanup();
}
static void test_coverage(void) {
 for(unsigned int pin=0;pin<64;pin++) {
  reset();struct irq_desc *d=add_irq(10,&mpm_domain,pin,true,true);map_irq(pin,d);prepare();bool direct=pin==2||pin==47||pin==53||pin==62;CHECK(ready()==direct);
  parents[10]=(struct irq_data){.domain=&mpm_domain,.hwirq=pin};d->irq_data.domain=&gpio_domain;d->irq_data.hwirq=100+pin;d->irq_data.parent_data=&parents[10];CHECK(ready());
  image[pin/32]&=~BIT(pin%32);CHECK(!ready());cleanup();
 }
 for(int kind=0;kind<8;kind++) {
  base();struct irq_desc *d=add_irq(11,&gic_domain,42,false,true);d->action=&active;
  if(kind==0)d->irq_data.disabled=true;
  if(kind==1)d->irq_data.hwirq=27;
  if(kind==2)d->irq_data.armed=true;
  if(kind==3){d->irq_data.hwirq=27;d->irq_data.armed=true;}
  if(kind==4){second.next=&active;d->action=&second;}
  if(kind==5){d->action=NULL;}
  if(kind==6){d->irq_data.domain=NULL;}
  if(kind==7){d->irq_data.irq=p.irq;descriptors[11]=NULL;descriptors[p.irq]=d;}
  prepare();CHECK(ready()==(kind==0||kind==1||kind==5||kind==7));cleanup();
 }
 for(int type=0;type<2;type++)for(int enabled=0;enabled<2;enabled++) {
  base();nodes[0].available=nodes[1].available=true;nodes[0].pin=62;nodes[1].pin=53;node_count=2;CHECK(!qcom_mpm_init_wake_domains(&dev,&p));CHECK(p.wake_domain_count==2);
  unsigned int pin=type?53:62;struct irq_desc *d=add_irq(11,type?&mdss_domain:&spmi_domain,123,true,true);
  if(enabled)map_irq(pin,add_irq(12,&mpm_domain,pin,false,true));
  prepare();CHECK(ready()==(bool)enabled);d->irq_data.domain=&gpio_domain;CHECK(!ready());cleanup();
 }
 base();prepare();CHECK(ready());local_irqs_off=false;CHECK(!qcom_mpm_sleep_ready(&dev,&owner));current_cpu=1;CHECK(!ready());current_cpu=0;online_cpus=2;CHECK(!ready());online_cpus=1;CHECK(ready());CHECK(!qcom_mpm_sleep_ready(&dev,&other));cleanup();
 for(int word=0;word<10;word++) {base();prepare();regs[word]^=BIT(0);CHECK(!ready());regs[word]^=BIT(0);CHECK(ready());cleanup();}
}
static void test_replay(void) {
 for(int level=0;level<2;level++)for(int mapped=0;mapped<2;mapped++) {
  base();struct irq_desc *d=add_irq(11,&mpm_domain,53,false,true);d->irq_data.level=level;map_irq(53,d);prepare();if(!mapped)pin_desc[53]=NULL;
  regs[10]|=BIT(2)|BIT(3);regs[11]|=BIT(21);CHECK(!qcom_mpm_finish_sleep(&dev,&owner));CHECK(!regs[10]&&!regs[11]);CHECK(replay_count[10]==1);CHECK(replay_count[11]==(unsigned)(mapped&&!level));CHECK(!p.sleep_prepared);
  CHECK(qcom_mpm_handler(0,&p)==IRQ_NONE);CHECK(replay_count[10]==1);cleanup();
 }
 base();p.sleep_owner=NULL;regs[10]=BIT(2);CHECK(qcom_mpm_handler(0,&p)==IRQ_HANDLED);CHECK(regs[10]==BIT(2));cleanup();
}
static void test_domains(void) {
 reset();CHECK(!qcom_mpm_init_wake_domains(&dev,&p));CHECK(!p.wake_domain_count&&!allocation_count);cleanup();
 for(int excluded=0;excluded<6;excluded++) {
  reset();node_count=1;nodes[0].available=true;
  if(excluded==0)nodes[0].available=false;
  if(excluded==1)nodes[0].irq_count=2;
  if(excluded==2)nodes[0].parse_fail=true;
  if(excluded==3)nodes[0].parent=&nodes[1];
  if(excluded==4)nodes[0].args_count=1;
  if(excluded==5)nodes[0].pin=64;
  CHECK(!qcom_mpm_init_wake_domains(&dev,&p));CHECK(!p.wake_domain_count);cleanup();
 }
 for(int fault=0;fault<6;fault++) {
  reset();node_count=2;nodes[0].available=nodes[1].available=true;nodes[1].pin=62;
  if(fault==1)alloc_fail=true;
  if(fault==2)action_fail=1;
  if(fault==3)action_fail=2;
  if(fault==4){add_second_pass=true;nodes[2].pin=53;}
  if(fault==5)nodes[1].pin=20;
  int ret=qcom_mpm_init_wake_domains(&dev,&p);
  CHECK(ret==(fault==1||fault==2||fault==3?-ENOMEM:fault==4?-EAGAIN:0));
  if(!fault)CHECK(p.wake_domain_count==2&&nodes[0].refs==2&&nodes[1].refs==2);
  if(fault==5)CHECK(p.wake_domain_count==1);
  cleanup();
 }
}
int main(void) {test_lifecycle();test_coverage();test_replay();test_domains();printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);return failures?1:0;}
