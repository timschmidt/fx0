"""Execute PLL, mux and CPR functions with stale caches and ambiguous I/O."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT / 'worktrees/linux-fx0-runtime'))


def function(source, name):
    start = source.index(name)
    static = source.rfind('\nstatic ', 0, start)
    start = static + 1 if static > source.rfind('\n}', 0, start) else source.rfind('\n', 0, start) + 1
    brace = source.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


HARNESS = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <stdarg.h>
#define EINVAL 22
#define EIO 5
#define ERANGE 34
#define EBUSY 16
#define ETIMEDOUT 110
#define BIT(x) (1U << (x))
#define GENMASK(h,l) ((~0U >> (31-(h))) & (~0U << (l)))
#define ULONG_MAX 0xffffffffUL /* Target ARM32's limit on this host. */
#define do_div(n,d) ((n)/=(d))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define pr_err(...) log_error(__VA_ARGS__)
#define dev_err_ratelimited(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define WARN(condition,...) log_error(__VA_ARGS__)
#define PLL_OUTCTRL BIT(0)
#define PLL_BYPASSNL BIT(1)
#define PLL_RESET_N BIT(2)
#define PLL_VOTE_FSM_ENA BIT(20)
#define CMD_RCGR 0
#define CFG_RCGR 4
#define CMD_RCGR_UPDATE BIT(0)
#define CMD_RCGR_DIRTY_CFG BIT(4)
#define CMD_RCGR_ROOT_OFF BIT(31)
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint8_t u8;
struct regmap {u32 registers[32];int kind;};
struct clk_hw {unsigned long cached;int id;};
struct clk_regmap {struct clk_hw hw;struct regmap *regmap;};
struct pll_freq_tbl {unsigned long freq;unsigned short l,m,n;u32 ibits;};
struct clk_pll {
 u32 l_reg,m_reg,n_reg,config_reg,mode_reg,status_reg;
 u8 status_bit,post_div_width,post_div_shift;
 bool critical_rate;
 const struct pll_freq_tbl *freq_tbl;
 struct clk_regmap clkr;
};
struct clk_regmap_mux_div {
 u32 reg_offset,hid_width,hid_shift,src_width,src_shift,div,src;
 const u32 *parent_map;
 struct clk_regmap clkr;
 bool critical_rate;
};
#define to_clk_regmap(hw) container_of(hw,struct clk_regmap,hw)
#define to_clk_pll(hw) container_of(to_clk_regmap(hw),struct clk_pll,clkr)
#define to_clk_regmap_mux_div(hw) container_of(to_clk_regmap(hw),struct clk_regmap_mux_div,clkr)
static jmp_buf stop;
static int panics,io_calls,fail_at,fail_after,drop_write_at,lock_stuck,mux_stuck,late_cfg,late_busy;
static int pre_calls,post_calls,voltage_writes,voltage_target;
static char query_order[64];static int queries;
static struct regmap pll_map,aux_map,mux_map,apcs_view;
static int mx_enables,apc_enables,clock_calls;
static struct clk_pll cpu_pll,gpll0;
static struct clk_regmap_mux_div mux;
static struct clk_hw aux_vote;
static const u32 parents[]={4,5};
static const struct pll_freq_tbl frequencies[]={{768000000,40,0,1,0},{1190400000,62,0,1,0},{0}};
static void log_error(const char *fmt,...) {(void)fmt;}
static __attribute__((noreturn)) void panic(const char *fmt,...) {
 (void)fmt;panics++;longjmp(stop,1);
}
static const char *clk_hw_get_name(const struct clk_hw *hw) {(void)hw;return "test-clock";}
static void udelay(int delay) {(void)delay;}
static int regmap_read(struct regmap *map,unsigned int offset,u32 *out) {
 if(map==&apcs_view) {CHECK(offset==0x50 || offset==0x54);map=&mux_map;offset-=0x50;}
 io_calls++;CHECK(offset/4<32);
 if(io_calls==fail_at && !fail_after)return -EIO;
 *out=map->registers[offset/4];
 if(map==&mux_map && offset==CFG_RCGR && late_cfg && io_calls>=4)*out^=1;
 if(map==&mux_map && offset==CMD_RCGR && late_busy && io_calls>=3)*out|=CMD_RCGR_UPDATE;
 return io_calls==fail_at?-EIO:0;
}
static int regmap_update_bits(struct regmap *map,unsigned int offset,u32 mask,u32 value) {
 io_calls++;CHECK(offset/4<32);
 if(io_calls==fail_at && !fail_after)return -EIO;
 if(io_calls==drop_write_at)return 0;
 map->registers[offset/4]=(map->registers[offset/4]&~mask)|(value&mask);
 if(map==&pll_map && offset==cpu_pll.mode_reg) {
  map->registers[cpu_pll.status_reg/4]=!lock_stuck && (map->registers[offset/4]&6)==6?BIT(16):0;
 }
 if(map==&mux_map && offset==CFG_RCGR)map->registers[0]|=CMD_RCGR_DIRTY_CFG;
 if(map==&mux_map && offset==CMD_RCGR && value&CMD_RCGR_UPDATE && !mux_stuck)
  map->registers[0]&=~(CMD_RCGR_UPDATE|CMD_RCGR_DIRTY_CFG);
 return io_calls==fail_at?-EIO:0;
}
static unsigned int clk_hw_get_num_parents(const struct clk_hw *hw) {(void)hw;return 2;}
static struct clk_hw *clk_hw_get_parent_by_index(const struct clk_hw *hw,int index) {
 CHECK(hw==&mux.clkr.hw);return index?&cpu_pll.clkr.hw:&aux_vote;
}
static unsigned long clk_hw_get_rate(const struct clk_hw *hw) {return hw->cached;}
#define mult_frac(x,n,d) ((unsigned long)((u64)(x)*(n)/(d)))
struct clk {struct clk_hw *hw;};
static struct clk aux_clk,pll_clk,cpu_clk,gpll_clk;
static int missing_parent;
static bool ccf_parent_aux,cpu_nocache,parent_nocache;
static struct clk *clk_get_parent(struct clk *clk) {CHECK(clk==&aux_clk);return missing_parent?NULL:&gpll_clk;}
static unsigned long clk_get_rate(struct clk *clk);
static int clk_set_rate(struct clk *clk,unsigned long rate);
struct fuse_corner {int mx_min_uV,max_uV;};
struct corner {unsigned long freq;struct fuse_corner *fuse_corner;int uV;};
struct cpr_voltage {int mx_lower_error;void *apc;bool mx_enabled;};
struct cpr_msm8926_data {
 struct clk *aux_clk,*pll_clk;
 struct regmap *apcs;struct {int bootstrap_mx_uV;} plan;
 bool apc_enabled,applied;
};
struct cpr_drv {
 struct cpr_msm8926_data *msm8926;
 struct clk *cpu_clk;
 struct cpr_voltage rails;
 void *dev;
 struct corner *corners,*corner;
 unsigned int num_corners;
 bool initialized;
};
enum voltage_change_dir {NO_CHANGE,DOWN,UP};
static int cpr_pre_voltage(struct cpr_drv *drv,struct fuse_corner *f,enum voltage_change_dir dir) {
 (void)drv;(void)f;(void)dir;pre_calls++;return 0;
}
static int cpr_post_voltage(struct cpr_drv *drv,struct fuse_corner *f,enum voltage_change_dir dir) {
 (void)drv;(void)f;(void)dir;post_calls++;return 0;
}
static int cpr_voltage_set(struct cpr_voltage *rails,int apc,int mx) {
 (void)rails;CHECK(mx>=apc);voltage_writes++;voltage_target=apc;return 0;
}
static int regulator_get_voltage(void *reg) {CHECK(reg==(void *)3);return voltage_target;}
static int regulator_enable(void *reg) {CHECK(reg==(void *)3);apc_enables++;return 0;}
static int cpr_voltage_bootstrap(struct cpr_voltage *rails,int floor) {
 CHECK(floor==1287500);if(!rails->mx_enabled)mx_enables++;rails->mx_enabled=true;return 0;
}
'''

MODEL = r'''
static unsigned long clk_get_rate(struct clk *clk) {
 CHECK(queries<63);
 struct clk_hw *hw=clk->hw;
 if(clk==&gpll_clk) {
  query_order[queries++]='G';
  if(parent_nocache)hw->cached=clk_pll_recalc_rate(hw,19200000);
  aux_vote.cached=hw->cached;
  if(ccf_parent_aux)mux.clkr.hw.cached=mux_div_recalc_rate(&mux.clkr.hw,aux_vote.cached);
 } else if(clk==&pll_clk) {
  query_order[queries++]='P';
  if(parent_nocache)hw->cached=clk_pll_recalc_rate(hw,19200000);
  if(!ccf_parent_aux)mux.clkr.hw.cached=mux_div_recalc_rate(&mux.clkr.hw,hw->cached);
 } else if(clk==&aux_clk)query_order[queries++]='A';
 else {
  CHECK(clk==&cpu_clk);query_order[queries++]='C';
  if(cpu_nocache)hw->cached=mux_div_recalc_rate(hw,0);
 }
 return hw->cached;
}
static int clk_set_rate(struct clk *clk,unsigned long rate) {
 CHECK(clk==&cpu_clk && rate==300000000 && mx_enables==1 && apc_enables==1);clock_calls++;
 int ret=mux_div_set_src_div(&mux,4,3);
 if(!ret) {ccf_parent_aux=true;mux.clkr.hw.cached=mux_div_recalc_rate(&mux.clkr.hw,0);}
 return ret;
}
static void reset(void) {
 pll_map=(struct regmap){0};aux_map=(struct regmap){0};mux_map=(struct regmap){0};
 cpu_pll=(struct clk_pll){.l_reg=4,.m_reg=8,.n_reg=12,.config_reg=20,.mode_reg=0,.status_reg=28,
 .status_bit=16,.critical_rate=true,.freq_tbl=frequencies,.clkr={.hw={1190400000,2},.regmap=&pll_map}};
 gpll0=cpu_pll;gpll0.clkr.regmap=&aux_map;gpll0.clkr.hw.id=4;gpll0.clkr.hw.cached=600000000;gpll0.critical_rate=false;
 pll_map.registers[0]=7;pll_map.registers[1]=62;pll_map.registers[3]=1;pll_map.registers[7]=BIT(16);
 aux_map.registers[1]=31;aux_map.registers[2]=1;aux_map.registers[3]=4; /* 19.2 * 31.25 = 600. */
 mux=(struct clk_regmap_mux_div){.hid_width=5,.src_width=3,.src_shift=8,.parent_map=parents,
 .clkr={.hw={1190400000,3},.regmap=&mux_map},.critical_rate=true};
 mux_map.registers[1]=0x501;aux_vote=(struct clk_hw){600000000,1};
 aux_clk.hw=&aux_vote;pll_clk.hw=&cpu_pll.clkr.hw;cpu_clk.hw=&mux.clkr.hw;gpll_clk.hw=&gpll0.clkr.hw;
 panics=io_calls=fail_at=fail_after=drop_write_at=lock_stuck=mux_stuck=late_cfg=late_busy=0;
 pre_calls=post_calls=voltage_writes=queries=missing_parent=0;voltage_target=1140000;
 mx_enables=apc_enables=clock_calls=0;
 ccf_parent_aux=false;cpu_nocache=parent_nocache=true;memset(query_order,0,sizeof(query_order));
}
static void test_pll(void) {
 int total,controls=0;
 reset();CHECK(!clk_pll_sr2_set_rate(&cpu_pll.clkr.hw,768000000,19200000));total=io_calls;
 CHECK(clk_pll_recalc_rate(&cpu_pll.clkr.hw,19200000)==768000000);
 for(int critical=0;critical<2;critical++) {
  reset();cpu_pll.critical_rate=critical;
  CHECK(!clk_pll_sr2_set_rate(&cpu_pll.clkr.hw,768000000,19200000));total=io_calls;
  for(int after=0;after<2;after++)for(int fault=1;fault<=total;fault++) {
  reset();cpu_pll.critical_rate=critical;fail_at=fault;fail_after=after;
  int result=0;
  if(!setjmp(stop)) {result=clk_pll_sr2_set_rate(&cpu_pll.clkr.hw,768000000,19200000);CHECK(!critical);}
  CHECK(panics==critical && io_calls==fault && (critical || result==-EIO));controls++;
  }
 }
 /* Parent activation can also fail after CCF begins reparenting. */
 reset();pll_map.registers[0]=0;CHECK(!clk_pll_sr2_enable(&cpu_pll.clkr.hw));total=io_calls;
 for(int after=0;after<2;after++)for(int fault=1;fault<=total;fault++) {
  reset();pll_map.registers[0]=0;fail_at=fault;fail_after=after;
  if(!setjmp(stop)) {clk_pll_sr2_enable(&cpu_pll.clkr.hw);CHECK(0);}
  CHECK(panics==1 && io_calls==fault);controls++;
 }
 reset();lock_stuck=1;
 if(!setjmp(stop)) {clk_pll_sr2_set_rate(&cpu_pll.clkr.hw,768000000,19200000);CHECK(0);}
 CHECK(panics==1);
 reset();cpu_pll.critical_rate=false;lock_stuck=1;
 CHECK(clk_pll_sr2_set_rate(&cpu_pll.clkr.hw,768000000,19200000)==-ETIMEDOUT && !panics);
 for(int after=0;after<2;after++)for(int fault=1;fault<=2;fault++) {
  reset();fail_at=fault;fail_after=after;
  if(!setjmp(stop)) {clk_pll_disable(&cpu_pll.clkr.hw);CHECK(0);}
  CHECK(panics==1);controls++;
 }
 for(int fault=1;fault<=4;fault++) {
  reset();cpu_pll.post_div_width=1;fail_at=fault;
  CHECK(clk_pll_recalc_rate(&cpu_pll.clkr.hw,19200000)==0);controls++;
 }
 reset();pll_map.registers[1]=41;pll_map.registers[2]=2;pll_map.registers[3]=3;
 CHECK(clk_pll_recalc_rate(&cpu_pll.clkr.hw,19200000)==800000000);
 reset();pll_map.registers[1]=1023;
 CHECK(!clk_pll_recalc_rate(&cpu_pll.clkr.hw,19200000));
 reset();drop_write_at=4; /* Lost L write must not select the old high rate. */
 if(!setjmp(stop)) {clk_pll_sr2_set_rate(&cpu_pll.clkr.hw,768000000,19200000);CHECK(0);}
 CHECK(panics==1);
 reset();pll_map.registers[0]=0;drop_write_at=5;
 if(!setjmp(stop)) {clk_pll_sr2_enable(&cpu_pll.clkr.hw);CHECK(0);}
 CHECK(panics==1);
 printf("PLL: %d I/O fault controls; critical writes/activation never return, legacy errors propagate, reads and ARM32 overflow fail closed\n",controls);
}
static void test_mux(void) {
 int controls=0;
 for(int critical=0;critical<2;critical++)for(int after=0;after<2;after++)for(int fault=1;fault<=(critical?5:3);fault++) {
  reset();mux.critical_rate=critical;fail_at=fault;fail_after=after;int result=0;
  if(!setjmp(stop)) {result=mux_div_set_src_div(&mux,4,3);CHECK(!critical);}
  CHECK(panics==critical && (critical || result==-EIO));controls++;
 }
 reset();mux_stuck=1;
 if(!setjmp(stop)) {mux_div_set_src_div(&mux,4,3);CHECK(0);}
 CHECK(panics==1);
 for(int missing=1;missing<=2;missing++) {
  reset();drop_write_at=missing;
  if(!setjmp(stop)) {mux_div_set_src_div(&mux,4,3);CHECK(0);}
  CHECK(panics==1);
 }
 for(int fault=1;fault<=4;fault++) {
  reset();fail_at=fault;u32 src=99,div=99;
  CHECK(mux_div_get_src_div(&mux,&src,&div)==-EIO && src==99 && div==99);controls++;
 }
 for(int fault=0;fault<5;fault++) {
  reset();
  if(fault<3)mux_map.registers[0]=(u32[]){BIT(0),BIT(4),BIT(31)}[fault];
  if(fault==3)late_cfg=1;
  if(fault==4)late_busy=1;
  CHECK(!mux_div_recalc_rate(&mux.clkr.hw,0));controls++;
 }
 reset();CHECK(mux_div_recalc_rate(&mux.clkr.hw,0)==1190400000);
 CHECK(mux_div_get_parent(&mux.clkr.hw)==1);
 io_calls=0;fail_at=1;CHECK(mux_div_get_parent(&mux.clkr.hw)==2);fail_at=0;
 CHECK(!mux_div_set_src_div(&mux,4,3));CHECK(mux_div_recalc_rate(&mux.clkr.hw,0)==300000000);
 printf("MUX: %d I/O/unstable-state controls; critical programming never returns; actual source selection readback passed\n",controls);
}
static void test_cpr(void) {
 struct cpr_msm8926_data data={.aux_clk=&aux_clk,.pll_clk=&pll_clk};
 struct cpr_drv drv={.msm8926=&data,.cpu_clk=&cpu_clk};
 struct fuse_corner fuse={.mx_min_uV=1287500,.max_uV=1280000};
 struct corner low={.freq=300000000,.fuse_corner=&fuse},high={.freq=1190400000,.fuse_corner=&fuse};
 reset();CHECK(cpr_scale_voltage(&drv,&low,1080000,DOWN)==-ERANGE);
 CHECK(!voltage_writes && !pre_calls && !post_calls && voltage_target==1140000);
 /* CCF has already reparented to aux; hardware is still on the old PLL. */
 reset();ccf_parent_aux=true;cpu_pll.clkr.hw.cached=mux.clkr.hw.cached=300000000;
 CHECK(cpr_scale_voltage(&drv,&low,1080000,DOWN)==-ERANGE && !voltage_writes);
 CHECK(!memcmp(query_order,"GAPC",4));
 reset();CHECK(!mux_div_set_src_div(&mux,4,3));queries=0;
 CHECK(!cpr_scale_voltage(&drv,&low,1080000,DOWN));CHECK(voltage_writes==1 && voltage_target==1080000);
 reset();CHECK(!mux_div_set_src_div(&mux,4,3));queries=0;
 CHECK(!cpr_scale_voltage(&drv,&high,1140000,UP));CHECK(voltage_writes==1);
 reset();CHECK(!cpr_msm8926_check_cpu_rate(&drv,1190400000));int total=io_calls;
 for(int after=0;after<2;after++)for(int fault=1;fault<=total;fault++) {
  reset();fail_at=fault;fail_after=after;
  CHECK(cpr_scale_voltage(&drv,&low,1080000,DOWN)!=0 && !voltage_writes);
 }
 reset();missing_parent=1;CHECK(cpr_scale_voltage(&drv,&high,1140000,UP)==-EIO && !voltage_writes);
 reset();aux_map.registers[1]=41;aux_map.registers[2]=2;aux_map.registers[3]=3;
 CHECK(cpr_scale_voltage(&drv,&high,1140000,UP)==-EIO && !voltage_writes);
 reset();mux_map.registers[0]=CMD_RCGR_DIRTY_CFG;
 CHECK(cpr_scale_voltage(&drv,&high,1140000,UP)==-ERANGE && !voltage_writes);
 reset();drv.msm8926=NULL;CHECK(!cpr_scale_voltage(&drv,&low,1080000,DOWN));CHECK(!queries && voltage_writes==1);
 printf("CPR: stale PLL/topology, %d I/O controls, unknown/too-fast mux rejection; voltage ordering and legacy bypass passed\n",total*2);
}
static void test_startup(void) {
 struct cpr_msm8926_data data={.aux_clk=&aux_clk,.pll_clk=&pll_clk,.apcs=&apcs_view,.plan={1287500}};
 struct corner corners[]={{.freq=300000000,.uV=1080000},{.freq=384000000,.uV=1080000}};
 struct cpr_drv drv={.msm8926=&data,.cpu_clk=&cpu_clk,.corners=corners,.num_corners=2,.rails={.apc=(void *)3}};
 reset();pll_map.registers[1]=41;pll_map.registers[2]=2;pll_map.registers[3]=3;
 cpu_pll.clkr.hw.cached=mux.clkr.hw.cached=800000000;
 CHECK(!cpr_msm8926_bootstrap_clock(&drv));
 CHECK(clock_calls==1 && mx_enables==1 && apc_enables==1 && !voltage_writes);
 CHECK(data.apc_enabled && !data.applied && !drv.initialized && !drv.corner);
 CHECK(mux_map.registers[1]==0x403 && clk_get_rate(&cpu_clk)==300000000);
 CHECK(!cpr_msm8926_bootstrap_clock(&drv) && apc_enables==1 && mx_enables==1);
 reset();data.apc_enabled=false;drv.rails.mx_enabled=false;aux_map.registers[1]=40;
 CHECK(cpr_msm8926_bootstrap_clock(&drv)==-EIO && !clock_calls && !mx_enables && !apc_enables);
 puts("startup passed with real runtime parent refresh, actual PLL/mux readback, idempotent references and no APC voltage write");
}
int main(int argc,char **argv) {
 CHECK(argc==2);
 if(!strcmp(argv[1],"pll"))test_pll();
 else if(!strcmp(argv[1],"mux"))test_mux();
 else if(!strcmp(argv[1],"startup"))test_startup();
 else {CHECK(!strcmp(argv[1],"cpr"));test_cpr();}
 return 0;
}
'''


class RuntimeClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        pll = (KERNEL / 'drivers/clk/qcom/clk-pll.c').read_text()
        mux = (KERNEL / 'drivers/clk/qcom/clk-regmap-mux-div.c').read_text()
        cpr = (KERNEL / 'drivers/pmdomain/qcom/cpr.c').read_text()
        functions = ''.join(function(pll, name) for name in
                            ['clk_pll_rate_error(', 'clk_pll_disable_checked(', 'clk_pll_disable(',
                             'clk_pll_recalc_rate(', 'find_freq(', 'wait_for_pll(',
                             'clk_pll_sr2_enable(', 'clk_pll_sr2_set_rate('])
        functions += ''.join(function(mux, name) for name in
                             ['mux_div_rate_error(', 'mux_div_set_src_div(', 'mux_div_get_src_div(',
                              'mux_div_get_parent(', 'mux_div_recalc_rate('])
        functions += ''.join(function(cpr, name) for name in
                             ['cpr_msm8926_check_cpu_rate(', 'cpr_scale_voltage(', 'cpr_msm8926_bootstrap_clock('])
        (base / 'runtime.c').write_text(HARNESS + functions + MODEL)
        cls.exe = base / 'runtime'
        result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                                 str(base / 'runtime.c'), '-o', str(cls.exe)], capture_output=True, text=True)
        if result.returncode:
            cls.tmp.cleanup()
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_model(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('passed' if name != 'pll' else 'fail closed', result.stdout)

    def test_cpu_pll_programming_activation_and_read_errors(self):
        self.run_model('pll')

    def test_cpu_mux_programming_and_read_errors(self):
        self.run_model('mux')

    def test_actual_voltage_path_rejects_stale_cache_and_high_hardware_rate(self):
        self.run_model('cpr')

    def test_startup_with_real_runtime_clock_guard(self):
        self.run_model('startup')


if __name__ == '__main__':
    unittest.main()
