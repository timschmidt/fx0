"""Execute actual PLL/mux rate selection with the qualified board's PLL OPPs."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
KERNEL=Path(os.environ.get('FX0_KERNEL_SOURCE',ROOT/'worktrees/linux-fx0-cpr-observe'))
spec=importlib.util.spec_from_file_location('clock_functions',ROOT/'tests/test_cpr_runtime_clock.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
HARNESS=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EINVAL 22
#define BIT(x) (1U<<(x))
#define mult_frac(x,n,d) ((unsigned long)((uint64_t)(x)*(n)/(d)))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
typedef uint32_t u32;
struct clk_hw {unsigned long cached;};
struct clk_regmap {struct clk_hw hw;};
struct pll_freq_tbl {unsigned long freq;};
struct clk_pll {const struct pll_freq_tbl *freq_tbl;struct clk_regmap clkr;};
struct clk_regmap_mux_div {unsigned int hid_width,div,src;const u32 *parent_map;struct clk_regmap clkr;};
struct clk_rate_request {unsigned long rate,best_parent_rate;struct clk_hw *best_parent_hw;};
#define to_clk_pll(hw) container_of(container_of(hw,struct clk_regmap,hw),struct clk_pll,clkr)
#define to_clk_regmap_mux_div(hw) container_of(container_of(hw,struct clk_regmap,hw),struct clk_regmap_mux_div,clkr)
static struct clk_hw aux={600000000};
static struct clk_pll pll;
static struct clk_regmap_mux_div mux;
static const u32 parent_map[]={4,5};
static int writes;
static u32 written_src,written_div;
static unsigned long clk_pll_recalc_rate(struct clk_hw *hw,unsigned long parent) {(void)parent;return hw->cached;}
static unsigned int clk_hw_get_num_parents(struct clk_hw *hw) {CHECK(hw==&mux.clkr.hw);return 2;}
static struct clk_hw *clk_hw_get_parent_by_index(struct clk_hw *hw,unsigned int index) {CHECK(hw==&mux.clkr.hw && index<2);return index?&pll.clkr.hw:&aux;}
static unsigned long clk_hw_get_rate(struct clk_hw *hw) {return hw->cached;}
static long clk_hw_round_rate(struct clk_hw *,unsigned long);
static int mux_div_rate_error(struct clk_regmap_mux_div *md,int error) {CHECK(md==&mux);return error;}
static int mux_div_set_src_div(struct clk_regmap_mux_div *md,u32 src,u32 div) {CHECK(md==&mux);written_src=src;written_div=div;writes++;return 0;}
'''
ROUND=r'''
static long clk_hw_round_rate(struct clk_hw *hw,unsigned long rate) {
 if(hw==&aux)return aux.cached;
 CHECK(hw==&pll.clkr.hw);
 struct clk_rate_request request={.rate=rate,.best_parent_rate=19200000};
 CHECK(!clk_pll_determine_rate(hw,&request));return request.rate;
}
'''
MAIN=r'''
int main(int argc,char **argv) {
 CHECK(argc==2);pll=(struct clk_pll){.freq_tbl=frequencies,.clkr={.hw={800000000}}};
 mux=(struct clk_regmap_mux_div){.hid_width=5,.parent_map=parent_map};
 if(!strcmp(argv[1],"missing"))pll.freq_tbl=missing_787;
 if(!strcmp(argv[1],"wrong_aux"))aux.cached=480000000;
 if(strcmp(argv[1],"canonical")) {
  unsigned long requested=!strcmp(argv[1],"missing")?787200000:300000000;
  struct clk_rate_request req={.rate=requested};CHECK(!mux_div_determine_rate(&mux.clkr.hw,&req));
  CHECK(req.rate!=requested);writes=0;
  CHECK(__mux_div_set_rate_and_parent(&mux.clkr.hw,requested,0,0)==-EINVAL && !writes);
  puts("non-exact rate rejected before mux programming");return 0;
 }
 const unsigned long rates[]={300000000,384000000,600000000,787200000,998400000,1094400000,1190400000,1305600000,1344000000,1401600000,1497600000,1593600000,1689600000,1785600000};
 for(unsigned int round=0;round<3;round++)for(unsigned int i=0;i<sizeof(rates)/sizeof(rates[0]);i++) {
  unsigned long rate=rates[i];struct clk_rate_request req={.rate=rate};
  CHECK(!mux_div_determine_rate(&mux.clkr.hw,&req) && req.rate==rate);
  bool auxiliary=rate==300000000 || rate==600000000;
  unsigned long expected_parent=auxiliary?600000000:rate==384000000?768000000:rate;
  CHECK(req.best_parent_hw==(auxiliary?&aux:&pll.clkr.hw) && req.best_parent_rate==expected_parent);
  if(!auxiliary)pll.clkr.hw.cached=req.best_parent_rate;
  writes=0;CHECK(!__mux_div_set_rate_and_parent(&mux.clkr.hw,rate,req.best_parent_rate,auxiliary?4:5));
  CHECK(writes==1 && written_src==(auxiliary?4U:5U));
  CHECK(written_div==((rate==300000000 || rate==384000000)?3U:1U));
  CHECK(mux.src==written_src && mux.div==written_div);
 }
 puts("42 canonical selections/programming decisions pass; 787.2 MHz uses direct 787.2 MHz CPU PLL");return 0;
}
'''
class RateSelectionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();base=Path(cls.temp.name)
  dtsi=(KERNEL/'arch/arm/boot/dts/qcom/qcom-msm8226.dtsi').read_text();start=dtsi.index('a7pll_opp_table: opp-table {');at=dtsi.index('{',start);end=at+1;depth=1
  while depth:depth+=(dtsi[end]=='{')-(dtsi[end]=='}');end+=1
  rates=list(map(int,re.findall(r'opp-hz\s*=\s*/bits/\s*64\s*<(\d+)>',dtsi[at:end])))
  if not rates or rates!=sorted(set(rates)) or any(rate%19200000 for rate in rates):raise RuntimeError('Unexpected PLL OPP table')
  tables=''
  for name,values in [('frequencies',rates),('missing_787',[r for r in rates if r!=787200000])]:tables+='static const struct pll_freq_tbl '+name+'[]={'+','.join('{'+str(r)+'}' for r in values)+',{0}};\n'
  pll=(KERNEL/'drivers/clk/qcom/clk-pll.c').read_text();mux=(KERNEL/'drivers/clk/qcom/clk-regmap-mux-div.c').read_text()
  code=HARNESS+tables+F.function(pll,'find_freq(')+F.function(pll,'clk_pll_determine_rate(')+ROUND
  code+=''.join(F.function(mux,name) for name in ['is_better_rate(','mux_div_determine_rate(','__mux_div_set_rate_and_parent('])+MAIN
  source=base/'selection.c';source.write_text(code);cls.exe=base/'selection'
  result=subprocess.run(['cc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(source),'-o',str(cls.exe)],capture_output=True,text=True)
  if result.returncode:raise RuntimeError(result.stderr)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def run_model(self,mode):
  result=subprocess.run([str(self.exe),mode],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
 def test_canonical_rate_parent_and_divider_decisions(self):self.run_model('canonical')
 def test_missing_787_PLL_point_cannot_program_a_nonexact_rate(self):self.run_model('missing')
 def test_wrong_auxiliary_parent_cannot_program_300_MHz(self):self.run_model('wrong_aux')
if __name__=='__main__':unittest.main()
