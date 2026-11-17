// SPDX-License-Identifier: GPL-2.0-only
static struct regulator apc_store,mx_store,so_store;
static struct clk cpu_store,aux_store,pll_store,gpll_store;
static struct regmap mux_store;
static struct cpr_voltage rails;
static struct cpr_msm8926_suspend sleep_ctx;
static unsigned long saved_rate;
static int saved_apc,saved_mx;
static void init(unsigned long rate,int voltage,int mx_voltage) {
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
static int prepare(void) {int ret;catching=true;if(setjmp(fatal))ret=-EOWNERDEAD;else ret=cpr_suspend_prepare(&sleep_ctx,saved_rate,750000,MAX_UV);catching=false;return ret;}
static int restore(void) {catching=true;if(setjmp(fatal)){catching=false;return -EOWNERDEAD;}cpr_suspend_restore(&sleep_ctx);catching=false;return 0;}
static void old_point(void) {CHECK(!sleep_ctx.active&&!sleep_ctx.exclusive&&!cpuclk->exclusive);CHECK(cpuclk->rate==saved_rate&&apc->voltage==saved_apc);CHECK(mx->voltage>=saved_mx&&rails.mx_min_uV>=saved_apc);CHECK(so->request==MAX_UV);}
static void prepared(void) {CHECK(sleep_ctx.active&&sleep_ctx.exclusive&&cpuclk->exclusive==1);CHECK(cpuclk->rate==300000000&&apc->voltage==MAX_UV&&mx->voltage==MAX_UV);CHECK(!pllclk->enabled&&!pllclk->prepared&&so->request==MAX_UV);}
static void warm(void) { /* Synthetic safe 300 MHz point to expose cached consumer requests. */
 apc->voltage=750000;apc->acks=0;mx->acks=0;
}
int main(void) {
 init(300000000,1000000,1050000);CHECK(!cpr_voltage_bootstrap(&rails,MAX_UV));CHECK(mx->voltage==MAX_UV&&mx->refs==1&&apc->voltage==1000000);cases++;
 const unsigned long rates[]={300000000,384000000,600000000,787200000,998400000,1094400000,1190400000,1305600000,1344000000,1401600000,1497600000,1593600000,1689600000,1785600000};
 for(unsigned i=0;i<sizeof(rates)/sizeof(rates[0]);i++)for(int v=750000;v<=MAX_UV;v+=12500) {
  init(rates[i],v,v<1050000?1050000:v);CHECK(!prepare());prepared();warm();CHECK(!restore());old_point();CHECK(cache_skips>0);CHECK(!restore());old_point();cases++;
 }
 /* Single API errors/applied errors/cached or dropped clock writes. */
 for(int type=1;type<=3;type++)for(int n=1;n<=140;n++) {
  init(787200000,1000000,1100000);fault_step=n;fault_kind=type;int ret=prepare();
  CHECK(ret==0||ret==-EIO||ret==-EBUSY||ret==-ERANGE);if(!ret){prepared();warm();CHECK(!restore());}
  old_point();cases++;
 }
 for(int type=1;type<=3;type++)for(int n=1;n<=100;n++) {
  init(1497600000,1125000,1200000);CHECK(!prepare());warm();ops=0;fault_step=n;fault_kind=type;
  CHECK(!restore());old_point();cases++;
 }
 init(787200000,1000000,1100000);extra_pll_ref=true;CHECK(prepare()==-EBUSY);old_point();cases++;
 init(787200000,1000000,1100000);gpll->rate=800000000;CHECK(prepare()==-EIO);old_point();cases++;
 init(787200000,1000000,1100000);corrupt_parent_on_mx=true;CHECK(prepare()==-EOWNERDEAD);CHECK(sleep_ctx.active&&cpuclk->exclusive==1&&apc->voltage==MAX_UV);CHECK(cpuclk->rate==saved_rate);cases++;
 init(787200000,1000000,1100000);so->request=750000;CHECK(prepare()==-ERANGE);CHECK(!cpuclk->exclusive&&!sleep_ctx.active);cases++;
 init(787200000,1000000,1100000);rails.mx_enabled=false;CHECK(prepare()==-EINVAL);CHECK(!ops&&!cpuclk->exclusive);cases++;
 init(787200000,1000000,1100000);sleep_ctx.clock=NULL;CHECK(prepare()==-EINVAL);CHECK(!ops);cases++;
 init(787200000,1000000,1100000);mux->cmd=BIT(0);CHECK(prepare()==-EIO);CHECK(!sleep_ctx.active&&!cpuclk->exclusive);cases++;
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d,\"caught_logical_fatals\":%d}\n",cases,checks,failures,panics);return failures?1:0;
}
