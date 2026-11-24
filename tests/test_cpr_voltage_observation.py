"""Execute CPR read-only diagnostics for unapplied, live and failed APC reads."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr-observe'))
spec = importlib.util.spec_from_file_location('functions',ROOT/'tests/test_cpr_runtime_clock.py')
EXTRACT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EXTRACT)

HARNESS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#define BIT(x) (1U<<(x))
#define GENMASK(h,l) ((~0U>>(31-(h)))&(~0U<<(l)))
#define guard(x) (void)
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
typedef uint32_t u32;
struct fuse_corner {u32 ring_osc_idx;};
struct corner {int uV,last_uV;struct fuse_corner *fuse_corner;};
struct cpr_msm8926_data {bool applied;};
struct cpr_drv {
 struct corner *corner;struct cpr_msm8926_data *msm8926;
 bool loop_disabled,suspended;int lock;struct {void *apc;} rails;
};
struct seq_file {void *private;char buffer[2048];size_t used;};
static int apc_target,apc_reads,register_reads;
static u32 control;
static int regulator_get_voltage(void *rail){CHECK(rail==(void *)1);apc_reads++;return apc_target;}
static u32 cpr_read(struct cpr_drv *drv,u32 offset){
 CHECK(drv);register_reads++;
 CHECK(offset==REG_RBCPR_GCNT_TARGET(2) || offset==REG_RBCPR_CTL ||
       offset==REG_RBIF_IRQ_STATUS || offset==REG_RBCPR_RESULT_0);
 return offset==REG_RBCPR_CTL?control:0;
}
static void seq_printf(struct seq_file *s,const char *format,...) {
 va_list args;va_start(args,format);int bytes=vsnprintf(s->buffer+s->used,sizeof(s->buffer)-s->used,format,args);va_end(args);
 CHECK(bytes>=0 && (size_t)bytes<sizeof(s->buffer)-s->used);s->used+=bytes;
}
static void seq_puts(struct seq_file *s,const char *value){seq_printf(s,"%s",value);}
'''
MAIN = r'''
int main(void) {
 struct fuse_corner fuse={.ring_osc_idx=2};struct corner corner={1080000,1080000,&fuse};
 struct cpr_msm8926_data data={0};struct cpr_drv drv={.msm8926=&data,.rails={.apc=(void *)1}};
 struct seq_file s={.private=&drv};apc_target=1150000;
 CHECK(!cpr_debug_info_show(&s,NULL));CHECK(strstr(s.buffer,"CPU domain is not attached"));
 CHECK(!apc_reads && !register_reads);
 drv.corner=&corner;
 for(int mode=0;mode<5;mode++) {
  data.applied=mode!=0;drv.suspended=mode==2;drv.loop_disabled=mode==3;
  corner.last_uV=mode?1040000:1080000;apc_target=mode==4?-5:mode?1040000:1150000;
  control=mode==1?1:0;s=(struct seq_file){.private=&drv};apc_reads=register_reads=0;
  struct cpr_drv before=drv;struct corner corner_before=corner;struct cpr_msm8926_data data_before=data;
  CHECK(!cpr_debug_info_show(&s,NULL));
  CHECK(!memcmp(&before,&drv,sizeof(drv)) && !memcmp(&corner_before,&corner,sizeof(corner)) && !memcmp(&data_before,&data,sizeof(data)));
  CHECK(apc_reads==1 && register_reads==4);
  CHECK(strstr(s.buffer,"planned_volt = 1080000 uV"));CHECK(!strstr(s.buffer,"current_volt"));
  if(!mode) {
   CHECK(strstr(s.buffer,"cached_volt = 1080000 uV"));
   CHECK(strstr(s.buffer,"corner_voltage_applied = 0"));CHECK(strstr(s.buffer,"apc_target = 1150000 uV"));
  } else {
   CHECK(strstr(s.buffer,"cached_volt = 1040000 uV"));CHECK(strstr(s.buffer,"corner_voltage_applied = 1"));
  }
  if(mode==1)CHECK(strstr(s.buffer,"feedback_allowed = 1"));
  if(mode==0 || mode==2 || mode==3)CHECK(strstr(s.buffer,"feedback_allowed = 0"));
  if(mode==4) {CHECK(strstr(s.buffer,"apc_target_read_error = -5"));CHECK(!strstr(s.buffer,"apc_target = -5 uV"));}
 }
 drv.msm8926=NULL;s=(struct seq_file){.private=&drv};apc_reads=0;
 CHECK(!cpr_debug_info_show(&s,NULL));CHECK(strstr(s.buffer,"corner, current_volt = 1040000 uV"));
 CHECK(!apc_reads && !strstr(s.buffer,"planned_volt") && !strstr(s.buffer,"apc_target"));
 puts("unattached, planned/cache/target distinction, applied/suspended/inhibited, exact read error and legacy output passed without state mutation");
 return 0;
}
'''


class VoltageObservationTests(unittest.TestCase):
    def test_actual_diagnostics_are_read_only_and_distinguish_targets(self):
        source=(KERNEL/'drivers/pmdomain/qcom/cpr.c').read_text()
        definitions=source[source.index('/* Register Offsets'):source.index('enum voltage_change_dir')]
        functions=''.join(EXTRACT.function(source,name) for name in ['cpr_is_allowed(', 'cpr_debug_info_show('])
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);cfile=base/'test.c';binary=base/'test'
            # The inherited seq_file callback's second argument is unused.
            # Other diagnostics in the actual function still compile with Werror.
            cfile.write_text('#include <stdint.h>\n'+definitions+HARNESS+functions+MAIN)
            result=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                                   str(cfile),'-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('without state mutation',result.stdout)


if __name__=='__main__':
    unittest.main()
