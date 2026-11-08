"""Compile the actual fixed-range SAW transaction helper with faulted I/O."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
HEADER = Path(os.environ.get('FX0_SAW_FTS2_HEADER', KERNEL/'drivers/regulator/qcom-spmi-saw-fts2.h'))
HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "qcom-spmi-saw-fts2.h"
#define CHECK(x) do { if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);} } while(0)
static struct regmap pmic={0},saw={1};
static unsigned int p[0x1800],s[0x1000];
struct operation {int map,write;unsigned int address,value;};
static struct operation operations[1000];
static int n,fail_at,writes,polls,ack_after;
static int second_fail_at,commit_error,second_commit_error,expect_panic,panics,busy_cycles,persistent_fault;
static jmp_buf panic_jump;
void panic(const char *format, ...){(void)format;panics++;if(expect_panic)longjmp(panic_jump,1);fprintf(stderr,"unexpected unrecoverable CPU rail\n");exit(99);}
static int io_fault(void){return n==fail_at||n==second_fail_at||(persistent_fault&&n>=second_fail_at&&second_fail_at>0);}
static int committed_fault(void){return n==fail_at?commit_error:second_commit_error;}
static unsigned int target;
static unsigned long delay_total;
void udelay(unsigned long amount){delay_total+=amount;}
int regmap_read(struct regmap *map,unsigned int address,unsigned int *value){
 CHECK(n<1000);operations[n++]=(struct operation){map->id,0,address,0};
 if(io_fault()&&!committed_fault())return -EIO;
 if(map==&saw && address==0x14){
  polls++;
  if(busy_cycles&&polls<=busy_cycles){s[0x14]=target|0x10000;p[0x1741]=target;}
  else if(ack_after>=0 && polls>=ack_after){s[0x14]=target;p[0x1741]=target;}
 }
 if(io_fault())return -EIO;
 *value=map==&pmic?p[address]:s[address];return 0;
}
int regmap_write(struct regmap *map,unsigned int address,unsigned int value){
 CHECK(n<1000);operations[n++]=(struct operation){map->id,1,address,value};
 /* No range register, PMIC data-slot, AVS or unrelated writes allowed. */
 CHECK((map==&pmic && address==0x1745)||(map==&saw&&(address==0x18||address==0x1c)));
 if(io_fault()&&!committed_fault())return -EIO;
 writes++;
 if(map==&pmic)p[address]=value;else s[address]=value;
 if(map==&saw&&address==0x1c){target=value&255;polls=0;if(io_fault())p[0x1741]=target;}
 if(io_fault())return -EIO;
 return 0;
}
static void clear_trace(void){n=fail_at=writes=polls=0;second_fail_at=commit_error=second_commit_error=expect_panic=panics=busy_cycles=persistent_fault=0;delay_total=0;ack_after=1;}
static struct spmi_saw_fts2 reset(unsigned int range,unsigned int mode){
 memset(p,0,sizeof(p));memset(s,0,sizeof(s));clear_trace();
 p[0x1704]=0x1c;p[0x1705]=8;p[0x1740]=range;p[0x1741]=range?115:230;
 p[0x1745]=mode;p[0x1761]=0x81;
 s[0xfd0]=0x20010000;s[4]=4;s[8]=0x14;s[0x40]=0x02030080;s[0x44]=0x30000;s[0x1c]=0xa5000073;s[0x14]=p[0x1741];target=p[0x1741];
 return (struct spmi_saw_fts2){.pmic=&pmic,.saw=&saw,.base=0x1700};
}
static struct spmi_saw_fts2 ready(unsigned int range,unsigned int mode){
 struct spmi_saw_fts2 state=reset(range,mode);CHECK(!spmi_saw_fts2_init(&state));clear_trace();return state;
}
int main(void){
 struct spmi_saw_fts2 state;
 int init_reads,raise_ops;
 /* Both boot ranges are discovered without writes, including slew margin. */
 state=reset(1,0x80);CHECK(!spmi_saw_fts2_init(&state));CHECK(!writes&&state.range==1&&state.step_uV==10000&&state.step_rate==9600);init_reads=n;
 state=reset(0,0x40);CHECK(!spmi_saw_fts2_init(&state));CHECK(!writes&&state.range==0&&state.step_uV==5000&&state.step_rate==4800);
 for(int fault=1;fault<=init_reads;fault++){
  state=reset(1,0x80);fail_at=fault;CHECK(spmi_saw_fts2_init(&state)==-EIO);CHECK(!writes);
 }
 state=reset(1,0x80);s[0xfd0]=0x30000000;CHECK(spmi_saw_fts2_init(&state)==-ENODEV&&!writes);
 state=reset(1,0x80);s[4]=0;CHECK(spmi_saw_fts2_init(&state)==-ENODEV&&!writes);
 state=reset(1,0x80);s[8]=s[0x40]=s[0x44]=0;CHECK(spmi_saw_fts2_init(&state)==-EPROBE_DEFER&&!writes);
 state=reset(1,0x80);s[8]=0;CHECK(spmi_saw_fts2_init(&state)==-EOPNOTSUPP&&!writes);
 state=reset(1,0x80);p[0x1704]=0;CHECK(spmi_saw_fts2_init(&state)==-ENODEV&&!writes);
 state=reset(1,0x80);p[0x1705]=0;CHECK(spmi_saw_fts2_init(&state)==-ENODEV&&!writes);
 state=reset(2,0x80);CHECK(spmi_saw_fts2_init(&state)==-EINVAL&&!writes);
 state=reset(1,0);CHECK(spmi_saw_fts2_init(&state)==-EOPNOTSUPP&&!writes);
 state=reset(1,0x80);s[0x20]=1;CHECK(spmi_saw_fts2_init(&state)==-EOPNOTSUPP&&!writes);
 /* Range1 selector is literal uV/10000, never the range0 encoding. */
 state=ready(1,0x80);CHECK(!spmi_saw_fts2_set(&state,1,116));CHECK(p[0x1740]==1&&s[0x1c]==0xa5000074&&delay_total==2&&writes==2);
 state=ready(0,0x80);CHECK(!spmi_saw_fts2_set(&state,0,232));CHECK(p[0x1740]==0&&delay_total==3);
 /* AUTO rising: PWM first; acknowledged command and ramp before restore. */
 state=ready(1,0x42);CHECK(!spmi_saw_fts2_set(&state,1,116));raise_ops=n;
 CHECK(operations[5].map==0&&operations[5].address==0x1745&&operations[5].value==0x82);
 CHECK(operations[6].address==0x18&&operations[7].address==0x1c&&operations[8].address==0x14);
 CHECK(operations[raise_ops-1].map==0&&operations[raise_ops-1].address==0x1745&&operations[raise_ops-1].value==0x42);
 CHECK(delay_total==44&&p[0x1745]==0x42&&!state.mode_pending);
 /* Real transition errors propagate; mode-only post-set errors defer safely. */
 for(int fault=1;fault<=raise_ops;fault++){
  state=ready(1,0x40);fail_at=fault;CHECK(spmi_saw_fts2_set(&state,1,116)==(fault==raise_ops?0:-EIO));
  if(fault==raise_ops)CHECK(state.mode_restore_error==-EIO);
  if(fault<=5)CHECK(!writes);
  if(fault==7)CHECK(p[0x1745]==0x80&&state.mode_pending);
  if(fault>=8&&fault<raise_ops)CHECK(p[0x1741]==115);
 }
 state=ready(1,0x40);ack_after=-1;CHECK(spmi_saw_fts2_set(&state,1,116)==-ETIMEDOUT);
 CHECK(p[0x1741]==115&&p[0x1745]==0x40&&!state.mode_pending);
 /* Retry reconciles current PMIC state, then completes deferred mode restore. */
 clear_trace();CHECK(!spmi_saw_fts2_set(&state,1,115));CHECK(p[0x1745]==0x40&&!state.mode_pending);
 state=ready(1,0x80);ack_after=4;CHECK(!spmi_saw_fts2_set(&state,1,116));CHECK(polls==4);
 state=ready(1,0x40);CHECK(!spmi_saw_fts2_set(&state,1,110));CHECK(writes==2&&delay_total==0&&p[0x1745]==0x40);
 state=ready(1,0x80);CHECK(!spmi_saw_fts2_set(&state,1,110));CHECK(writes==2&&delay_total==0);
 state=ready(1,0x80);CHECK(!spmi_saw_fts2_set(&state,1,115));CHECK(delay_total==0);
 for(int range=0;range<2;range++){
  for(unsigned int selector=0;selector<=256;selector++){
   unsigned int uv=selector*(range?10000:5000);
   int supported=selector<=255&&uv>=(unsigned)(range?700000:350000)&&uv<=(unsigned)(range?2040000:1275000);
   state=ready(range,0x80);int ret=spmi_saw_fts2_set(&state,range,selector);
   CHECK(supported?ret==0:ret==-EINVAL);
   if(!supported)CHECK(!n&&!writes);
  }
 }
 state=ready(1,0x80);CHECK(spmi_saw_fts2_set(&state,0,230)==-EINVAL&&!n);
 state=ready(1,0x80);state.step_rate=0;CHECK(spmi_saw_fts2_set(&state,1,115)==-EINVAL&&!n);
 state=ready(1,0x80);p[0x1741]=0;CHECK(spmi_saw_fts2_set(&state,1,115)==-EIO&&!writes);
 state=ready(1,0x80);p[0x1740]=0;CHECK(spmi_saw_fts2_set(&state,1,115)==-EIO&&!writes);
 state=ready(1,0x80);p[0x1745]=0;CHECK(spmi_saw_fts2_set(&state,1,115)==-EOPNOTSUPP&&!writes);
 state=ready(1,0x80);s[0x20]=1;CHECK(spmi_saw_fts2_set(&state,1,115)==-EOPNOTSUPP&&!writes);
 puts("Fixed-range initialization, selector, slew, retry and I/O fault contracts passed");
 return 0;
}
'''


RECOVERY_MAIN = r"""
static struct spmi_saw_fts2 fatal_state;
static void fatal_case(int position,int committed) {
 fatal_state=ready(1,0x80);
 fail_at=7;commit_error=1; /* committed VCTL write from 1150 to 1100mV */
 second_fail_at=7+position;second_commit_error=committed;persistent_fault=1;
 expect_panic=1;
 if(!setjmp(panic_jump)) {
  (void)spmi_saw_fts2_set(&fatal_state,1,110);
  CHECK(0); /* No uncertain rail state may return to the clock caller. */
 }
 CHECK(panics==1);
}
int main(void) {
 struct spmi_saw_fts2 state;
 int cases=0,recovery_cases=0;
 for(unsigned int range=0;range<2;range++)
  for(unsigned int mode=0x40;mode<=0x80;mode+=0x40)
   for(int direction=-1;direction<=1;direction++) {
    unsigned int old=range?115:230,target_selector=old+direction*(range?5:10);
    state=ready(range,mode);CHECK(!spmi_saw_fts2_set(&state,range,target_selector));
    int total=n;
    int mode_restore=state.restore_mode && operations[total-1].write && operations[total-1].map==0?total:0;
    for(int fault=1;fault<=total;fault++)for(int committed=0;committed<2;committed++) {
     state=ready(range,mode);fail_at=fault;commit_error=committed;
     int ret=spmi_saw_fts2_set(&state,range,target_selector);
     CHECK(ret==(fault==mode_restore?0:-EIO));
     CHECK(p[0x1741]==(ret?old:target_selector));
     CHECK(p[0x1740]==range && !panics);
     if(ret && fault==mode_restore)CHECK(0);
     cases++;
    }
   }
 /* Every recovery I/O failure gets one bounded retry, even after mutation. */
 for(int position=1;position<=6;position++)for(int committed=0;committed<2;committed++) {
  state=ready(1,0x80);fail_at=7;commit_error=1;
  second_fail_at=7+position;second_commit_error=committed;
  CHECK(spmi_saw_fts2_set(&state,1,110)==-EIO);
  CHECK(p[0x1741]==115 && p[0x1740]==1 && !panics);
  recovery_cases++;
  fatal_case(position,committed);
 }
 /* A failed mode restore after a confirmed old voltage remains a safe error. */
 state=ready(1,0x40);fail_at=7;commit_error=1;second_fail_at=14;
 CHECK(spmi_saw_fts2_set(&state,1,110)==-EIO);
 CHECK(p[0x1741]==115 && p[0x1745]==0x80 && state.mode_pending && !panics);
 /* A matching byte with a busy controller is not an acknowledgement. */
 state=ready(1,0x80);busy_cycles=3;
 CHECK(!spmi_saw_fts2_set(&state,1,116));CHECK(polls==4);
 printf("%d before/after-effect I/O cases, %d recovery retry cases and 12 persistent fail-stop contracts passed\n",cases,recovery_cases);
 return 0;
}
"""


@unittest.skipUnless(HEADER.exists(), 'Candidate fixed-range SAW helper required')
class SawFts2Tests(unittest.TestCase):
    def run_harness(self, harness, extra_headers=None, header=None):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base/'linux').mkdir()
            (base/'linux/regmap.h').write_text('#pragma once\n#include <stdbool.h>\nstruct regmap {int id;};\nint regmap_read(struct regmap*,unsigned int,unsigned int*);\nint regmap_write(struct regmap*,unsigned int,unsigned int);\n')
            (base/'linux/errno.h').write_text('#define EPROBE_DEFER 517\n#define EIO 5\n#define ENODEV 19\n#define EINVAL 22\n#define EOPNOTSUPP 95\n#define ETIMEDOUT 110\n')
            (base/'linux/kernel.h').write_text('#define max(a,b) ((a)>(b)?(a):(b))\n#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))\n')
            (base/'linux/delay.h').write_text('void udelay(unsigned long);\n')
            (base/'linux/panic.h').write_text('void panic(const char *,...) __attribute__((noreturn));\n')
            (base/'linux/iopoll.h').write_text('#define read_poll_timeout_atomic(op,ret,condition,delay,timeout,sleep,args...) ({int poll_result=-ETIMEDOUT; for(int poll_index=0;poll_index<50;poll_index++){ret=op(args);if(condition){poll_result=0;break;}} poll_result;})\n')
            (base/'qcom-spmi-saw-fts2.h').write_bytes(HEADER.read_bytes() if header is None else header)
            for name, content in (extra_headers or {}).items():
                path = base/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            (base/'test.c').write_text(harness)
            result = subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I',str(base),str(base/'test.c'),'-o',str(base/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run([str(base/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('contracts passed',result.stdout)
            return result.stdout


    def test_actual_transaction_helper(self):
        self.run_harness(HARNESS)

    def test_recovery_after_effects_and_persistent_failure(self):
        report = self.run_harness(HARNESS.split('int main(void)')[0] + RECOVERY_MAIN)
        self.assertIn('248 before/after-effect I/O cases, 12 recovery retry cases', report)

    def test_actual_provider_mapping_and_smp_dispatch(self):
        source = (HEADER.parent/'qcom_spmi-regulator.c').read_text()
        def function(name, source=source):
            import re
            match=re.search(r'static (?:inline )?(?:int|void)\s+'+name+r'\s*\([^;{}]*\)\s*\{',source)
            self.assertIsNotNone(match,name)
            start=source.index('{',match.start());depth=1;end=start+1
            while depth:
                depth += (source[end]=='{')-(source[end]=='}');end+=1
            return source[match.start():end]
        prefix=HARNESS.split('static struct spmi_saw_fts2 ready(')[0]
        definitions=r"""
+typedef unsigned char u8;
+struct spmi_voltage_range {int min_uV,max_uV,step_uV,set_point_min_uV,set_point_max_uV;unsigned int n_voltages;u8 range_sel;};
+struct spmi_voltage_set_points {const struct spmi_voltage_range *range;int count;unsigned int n_voltages;};
+struct regulator_dev;
+struct regulator_ops {int (*enable)(struct regulator_dev*),(*disable)(struct regulator_dev*),(*is_enabled)(struct regulator_dev*),(*get_status)(struct regulator_dev*);int (*set_voltage_sel)(struct regulator_dev*,unsigned int),(*get_voltage_sel)(struct regulator_dev*),(*map_voltage)(struct regulator_dev*,int,int);};
+struct regulator_desc {unsigned int n_voltages,off_on_delay,poll_enabled_time;const struct regulator_ops *ops;};
+struct spmi_regulator {struct regmap *regmap;unsigned int base;struct spmi_saw_fts2 saw_fts2;struct spmi_voltage_range saw_range;struct spmi_voltage_set_points saw_points,*set_points;struct regulator_desc desc;struct regulator_ops saw_ops;void *dev;};
+struct regulator_dev {struct spmi_regulator *data;const struct regulator_desc *desc;void *ena_pin;int ena_gpio_state;long last_off;};
+typedef long s64;
+typedef long ktime_t;
+#define ktime_add_us(a,b) ((a)+(b))
+#define ktime_us_delta(a,b) ((a)-(b))
+#define ktime_get_boottime() 0L
+#define fsleep(n) ((void)(n))
+#define rdev_warn(r,fmt,args...) ((void)(r))
+#define rdev_err(r,fmt,args...) ((void)(r))
+#define rdev_get_name(r) ((void)(r), "test-apc")
+#define trace_regulator_enable(n) ((void)(n))
+#define trace_regulator_enable_delay(n) ((void)(n))
+#define trace_regulator_enable_complete(n) ((void)(n))
+static int _regulator_get_enable_time(struct regulator_dev *r){(void)r;return 0;}
+static int _regulator_check_status_enabled(struct regulator_dev *r){(void)r;return 1;}
+static int regulator_ena_gpio_ctrl(struct regulator_dev *r,bool enable){(void)r;(void)enable;return -EIO;}
+static int gate_writes,gate_reads;
+static int generic_enable(struct regulator_dev *r){(void)r;gate_writes++;return 0;}
+static int generic_disable(struct regulator_dev *r){(void)r;gate_writes++;return 0;}
+static int generic_is_enabled(struct regulator_dev *r){(void)r;gate_reads++;return 1;}
+static const struct regulator_ops original_ops={.enable=generic_enable,.disable=generic_disable,.is_enabled=generic_is_enabled};
+#define rdev_get_drvdata(r) ((r)->data)
+#define dev_err(dev,fmt,args...) ((void)(dev))
+static int warning_count,cpu_error,legacy_count;
+#define dev_warn_ratelimited(dev,fmt,args...) do{(void)(dev);warning_count++;}while(0)
+static int smp_call_function_single(int cpu,void (*fn)(void*),void *arg,bool wait){CHECK(cpu==0&&wait);if(cpu_error)return cpu_error;fn(arg);return 0;}
+static void spmi_saw_set_vdd(void *data){(void)data;legacy_count++;}
+""".replace('\n+','\n')
        start=source.index('struct spmi_saw_request {');end=source.index('};',start)+2
        definitions+='\n'+source[start:end]+'\n'
        for name in ['spmi_regulator_select_voltage','spmi_sw_selector_to_hw','spmi_hw_selector_to_sw','spmi_regulator_single_map_voltage','spmi_saw_fts2_set_vdd','spmi_regulator_saw_set_voltage','spmi_regulator_saw_fixed_get_voltage','spmi_regulator_saw_fixed_init','spmi_regulator_common_list_voltage','spmi_regulator_saw_init_ops']:
            definitions+='\n'+function(name)+'\n'
        core=(KERNEL/'drivers/regulator/core.c').read_text()
        definitions+='\n'+function('_regulator_is_enabled',core)+'\n'+function('_regulator_do_enable',core)+'\n'
        tests=r"""
+int main(void){
+ struct spmi_regulator v;
+ struct regulator_dev r={.data=&v,.desc=&v.desc};
+ u8 range,selector;
+ for(unsigned int boot_range=0;boot_range<2;boot_range++){
+  (void)reset(boot_range,0x80);memset(&v,0,sizeof(v));
+  v.regmap=&pmic;v.base=0x1700;v.saw_fts2.saw=&saw;
+  /* Actual initializer reads vreg's per-instance SAW map. */
+  v.saw_regmap=&saw;
+  CHECK(!spmi_regulator_saw_fixed_init(&v));
+  CHECK(v.set_points->count==1&&v.saw_range.range_sel==boot_range);
+  for(unsigned int i=0;i<v.desc.n_voltages;i++){
+   CHECK(!spmi_sw_selector_to_hw(&v,i,&range,&selector));
+   CHECK(range==boot_range);
+   CHECK(spmi_hw_selector_to_sw(&v,selector,&v.saw_range)==(int)i);
+   CHECK(spmi_regulator_common_list_voltage(&r,i)==selector*(boot_range?10000:5000));
+  }
+  CHECK(spmi_sw_selector_to_hw(&v,v.desc.n_voltages,&range,&selector)==-EINVAL);
+  int mapped=spmi_regulator_single_map_voltage(&r,1075000,1280000);
+  CHECK(mapped>=0);CHECK(!spmi_sw_selector_to_hw(&v,mapped,&range,&selector));
+  CHECK(selector==((boot_range)?108:215));
+  if(boot_range)CHECK(spmi_regulator_single_map_voltage(&r,1075000,1075000)==-EINVAL);
+  clear_trace();CHECK(spmi_regulator_saw_fixed_get_voltage(&r)==(boot_range?45:160));
+  clear_trace();fail_at=1;CHECK(spmi_regulator_saw_fixed_get_voltage(&r)==-EIO);
+  clear_trace();fail_at=2;CHECK(spmi_regulator_saw_fixed_get_voltage(&r)==-EIO);
+  clear_trace();p[0x1741]=0;CHECK(spmi_regulator_saw_fixed_get_voltage(&r)==-EINVAL);
+ }
+ (void)reset(1,0x40);memset(&v,0,sizeof(v));v.regmap=&pmic;v.base=0x1700;v.saw_regmap=&saw;
+ CHECK(!spmi_regulator_saw_fixed_init(&v));clear_trace();
+ cpu_error=-7;CHECK(spmi_regulator_saw_set_voltage(&r,46)==-7&&!n);cpu_error=0;
+ fail_at=9;CHECK(spmi_regulator_saw_set_voltage(&r,46)==-EIO);
+ clear_trace();CHECK(!spmi_regulator_saw_set_voltage(&r,46));CHECK(p[0x1741]==116);
+ p[0x1745]=0x40;clear_trace();fail_at=12;CHECK(!spmi_regulator_saw_set_voltage(&r,47));
+ CHECK(warning_count==1&&v.saw_fts2.mode_restore_error==-EIO&&v.saw_fts2.mode_pending);
+ clear_trace();CHECK(!spmi_regulator_saw_set_voltage(&r,47));CHECK(!v.saw_fts2.mode_pending&&!v.saw_fts2.mode_restore_error);
+ /* Legacy range0 dispatch remains supported without fixed-range state. */
+ v.saw_fts2.pmic=NULL;v.saw_range.range_sel=0;CHECK(!spmi_regulator_saw_set_voltage(&r,1)&&legacy_count==1);
+ v.saw_range.range_sel=1;CHECK(spmi_regulator_saw_set_voltage(&r,1)==-EINVAL&&legacy_count==1);
+ /* Actual kernel enable dispatch must never invoke a PMIC gate for fixed S2. */
+ v.saw_fts2.pmic=&pmic;v.desc.ops=&original_ops;spmi_regulator_saw_init_ops(&v);
+ CHECK(!v.desc.ops->enable&&!v.desc.ops->disable&&!v.desc.ops->is_enabled);
+ CHECK(v.desc.ops->set_voltage_sel==spmi_regulator_saw_set_voltage);
+ CHECK(_regulator_is_enabled(&r)==1&&!gate_reads);
+ CHECK(_regulator_do_enable(&r)==-EINVAL&&!gate_writes);
+ /* Legacy rails keep their original enable/disable behavior. */
+ v.saw_fts2.pmic=NULL;v.desc.ops=&original_ops;spmi_regulator_saw_init_ops(&v);
+ CHECK(v.desc.ops->enable==generic_enable&&v.desc.ops->disable==generic_disable);
+ CHECK(_regulator_is_enabled(&r)==1&&gate_reads==1);
+ CHECK(!_regulator_do_enable(&r)&&gate_writes==1);
+ puts("Provider mapping, getter faults, SMP, no-gate enable and legacy contracts passed");return 0;
+}
+""".replace('\n+','\n')
        definitions=definitions.replace('struct spmi_regulator {','struct spmi_regulator {struct regmap *saw_regmap;')
        self.run_harness(prefix+definitions+tests)


if __name__ == '__main__':
    unittest.main()
