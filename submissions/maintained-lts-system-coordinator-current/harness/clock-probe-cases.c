// SPDX-License-Identifier: GPL-2.0-only
int main(void) {
 int cases=0;
 for(int cfg=0;cfg<2;cfg++)for(int msm=0;msm<2;msm++) {
  full_pm=cfg;reads=fail_read=registrations=0;map.words[1]=0xf0000028;map.words[2]=0xfff80000;map.words[3]=0xfff80001;map.words[5]=0xdeadbeef;
  struct device_node node={"/soc/clock@123",msm};struct device parent={.of_node=&node};struct platform_device pdev={.dev={.of_node=&node,.parent=&parent}};
  CHECK(!qcom_a53pll_probe(&pdev));struct clk_pll *pll=allocated;
  CHECK(pll->critical_rate==msm&&flags==(msm?CLK_GET_RATE_NOCACHE:0)&&ops==&clk_pll_sr2_ops);
  CHECK(pll->suspend_valid==(bool)(cfg&&msm));CHECK(reads==(cfg&&msm?4:0)&&registrations==1);
  if(cfg&&msm)CHECK(pll->suspend_config==0xdeadbeef&&pll->suspend_l==40&&!pll->suspend_m&&pll->suspend_n==1);
  free(allocated);allocated=NULL;
  CHECK(!qcom_apcs_msm8916_clk_probe(&pdev));struct clk_regmap_mux_div *md=pdev.data;CHECK(md==allocated&&md->critical_rate==msm);CHECK(flags==(CLK_IS_CRITICAL|CLK_SET_RATE_PARENT|(msm?CLK_GET_RATE_NOCACHE:0))&&ops==&clk_regmap_mux_div_ops);free(allocated);allocated=NULL;
  parent_deferred=true;CHECK(qcom_apcs_msm8916_clk_probe(&pdev)==-EPROBE_DEFER);free(allocated);allocated=NULL;parent_deferred=false;cases++;
 }
 for(int step=1;step<=4;step++) {
  full_pm=true;reads=registrations=0;fail_read=step;struct device_node node={"/soc/clock@123",true};struct platform_device pdev={.dev={.of_node=&node}};
  CHECK(qcom_a53pll_probe(&pdev)==-EIO);CHECK(reads==step&&!registrations&&!((struct clk_pll *)allocated)->suspend_valid);free(allocated);allocated=NULL;cases++;
 }
 CHECK(!gpll0_init.flags);msm8226_clock_override();CHECK(gpll0_init.flags==CLK_GET_RATE_NOCACHE);
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":0}\n",cases,checks);return 0;
}
