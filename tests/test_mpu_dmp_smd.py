"""Real native significant-motion lifecycle against fault-injected regmap/PM."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_mpu_dmp_native import SHIM, PACKET_SHIM, LIFECYCLE_SHIM

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/iio/imu/inv_mpu6050/inv_mpu_dmp.c'
PM_SHIM = r'''
struct device;
#define regmap_get_device(m) ((struct device *)(m))
#define BIT(n) (1U<<(n))
#define dev_dbg(...) ((void)0)
static int pm_refs, pm_error;
static int lock_held, irq_depth, wake_depth, wake_enable_error, wake_disable_error;
static int can_wake=1;
static void mutex_lock(void *p) { (void)p; assert(!lock_held);lock_held=1; }
static void mutex_unlock(void *p) { (void)p; assert(lock_held);lock_held=0; }
static void disable_irq(int irq) { (void)irq;assert(!lock_held);irq_depth++; }
static void enable_irq(int irq) { (void)irq;assert(!lock_held && irq_depth>0);irq_depth--; }
static int enable_irq_wake(int irq) { (void)irq;if(wake_enable_error)return wake_enable_error;wake_depth++;return 0; }
static int disable_irq_wake(int irq) { (void)irq;if(wake_disable_error)return wake_disable_error;assert(wake_depth>0);wake_depth--;return 0; }
static int device_may_wakeup(struct device *dev) { (void)dev;return can_wake; }
static void pm_wakeup_event(struct device *dev,int ms) { (void)dev;(void)ms; }
static int pm_runtime_resume_and_get(struct device *dev) { (void)dev; if(pm_error)return pm_error; pm_refs++; return 0; }
static void pm_runtime_put_autosuspend(struct device *dev) { (void)dev; assert(pm_refs>0); pm_refs--; }
static void model_guard(void *p) { (void)p; }
#define guard(x) model_guard
'''
MAIN = r'''
int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m,.irq=76};
 int calls,i; bool event;
 m.regs[0x39]=4;
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0 && pm_refs==1);
 calls=m.calls;
 assert(st.dmp_smd_armed && st.dmp_smd_mode && st.dmp_active);
 assert(m.regs[0x6a]==0x80 && m.regs[0x38]==2 && m.regs[0x23]==0);
 assert(m.ram[1983]==0xa3 && m.ram[1985]==0xff);
 assert(m.ram[1770]==0xf4 && m.ram[1701]==0xf4 && m.ram[288]==0 && m.ram[289]==1);
 assert(m.ram[344]==5 && m.ram[345]==0xdc && m.ram[342]==2 && m.ram[343]==0x58);
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0 && pm_refs==1 && m.calls==calls);
 assert(inv_mpu6515_dmp_smd_event(&st)==0 && st.dmp_smd_armed); /* stale status cleared */
 m.regs[0x39]=8;
 assert(inv_mpu6515_dmp_smd_event(&st)==0 && st.dmp_smd_armed && pm_refs==1);
 m.regs[0x39]=4;
 assert(inv_mpu6515_dmp_smd_event(&st)==1 && !st.dmp_active && !st.dmp_smd_armed && pm_refs==0);
 assert(inv_mpu6515_dmp_smd_event(&st)==0);
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0 && pm_refs==1);
 m.regs[0x39]=4; m.fail=m.calls+1;
 assert(inv_mpu6515_dmp_smd_event(&st)==-EREMOTEIO && st.dmp_smd_armed && pm_refs==1);
 assert(inv_mpu6515_dmp_smd_event(&st)==1 && pm_refs==0);
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0);
 inv_mpu6515_dmp_cleanup(&st);
 assert(pm_refs==0 && !st.dmp_active);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); memset(&st,0,sizeof(st)); st.chip_type=INV_MPU6515;st.reg=&r;st.map=&m;st.irq=76;
  m.fail=i;
  assert(inv_mpu6515_dmp_smd_set(&st,true)==-EREMOTEIO);
  assert(pm_refs==0 && !st.dmp_smd_pm && !st.dmp_smd_mode && !st.dmp_active);
 }
 pm_error=-EIO; m.calls=0;
 assert(inv_mpu6515_dmp_smd_set(&st,true)==-EIO && pm_refs==0 && m.calls==0);
 pm_error=0; st.chip_config.wom_en=true;
 assert(inv_mpu6515_dmp_smd_set(&st,true)==-EBUSY && pm_refs==0);
 st.chip_config.wom_en=false; m.fail=0;
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0);
 can_wake=0;
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==-EBUSY && irq_depth==0 && !event);
 can_wake=1;wake_enable_error=-EREMOTEIO;
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==-EREMOTEIO && irq_depth==0 && wake_depth==0);
 wake_enable_error=0;
 m.regs[0x39]=4;
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==-EBUSY && event && pm_refs==0 && irq_depth==0);
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0);
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==0 && !event);
 assert(st.dmp_smd_suspended && irq_depth==1 && wake_depth==1 && pm_refs==1);
 i=m.calls;
 assert(inv_mpu6515_dmp_smd_event(&st)==-EBUSY && m.calls==i);
 assert(inv_mpu6515_dmp_smd_set(&st,false)==-EBUSY && m.calls==i);
 assert(inv_mpu6515_dmp_smd_resume(&st,&event)==0 && !event);
 assert(!st.dmp_smd_suspended && irq_depth==0 && wake_depth==0 && pm_refs==1);
 assert(st.dmp_smd_armed); /* RTC/abort resume retains armed DMP */
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==0);
 m.regs[0x39]=4;
 assert(inv_mpu6515_dmp_smd_resume(&st,&event)==0 && event && st.dmp_smd_last_status==4);
 assert(!st.dmp_active && pm_refs==0 && irq_depth==0 && wake_depth==0);
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0);
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==0);
 wake_disable_error=-EREMOTEIO;
 assert(inv_mpu6515_dmp_smd_resume(&st,&event)==-EREMOTEIO && !event);
 assert(irq_depth==0 && wake_depth==1 && st.dmp_smd_irq_wake);
 wake_disable_error=0;
 assert(inv_mpu6515_dmp_smd_set(&st,false)==0 && pm_refs==0 && wake_depth==0);
 assert(inv_mpu6515_dmp_smd_set(&st,true)==0);
 assert(inv_mpu6515_dmp_smd_suspend(&st,&event)==0);
 m.regs[0x39]=4;m.fail=m.calls+1;
 assert(inv_mpu6515_dmp_smd_resume(&st,&event)==-EREMOTEIO && !event && irq_depth==0 && wake_depth==0);
 assert(st.dmp_smd_armed && pm_refs==1);
 assert(inv_mpu6515_dmp_smd_event(&st)==1 && pm_refs==0);
 printf("Passed real SMD configuration, PM balance, stale/pedometer controls, one-shot/rearm, suspend/IRQ balance and %d startup operation failures\n",calls);
 return 0;
}
'''


class SignificantMotion(unittest.TestCase):
    def test_native_event_lifecycle_and_status_causality(self):
        source = SOURCE.read_text()
        code = source.split('#define INV_MPU6515_DMP_FIRMWARE')[0]
        code += source[source.index('int inv_mpu6515_dmp_configure('):]
        code = '\n'.join(line for line in code.splitlines() if not line.startswith('#include'))
        shim = SHIM.replace('unsigned user_ctrl, int_enable, fifo_r_w;', 'unsigned user_ctrl, int_enable, fifo_r_w, int_status;')
        shim = shim.replace('bool dmp_active,dmp_saved_valid,dmp_overflow;',
                            'bool dmp_active,dmp_saved_valid,dmp_overflow,dmp_smd_mode,dmp_smd_armed,dmp_smd_pm,dmp_smd_suspended,dmp_smd_irq_wake; u8 dmp_smd_last_status; int irq;')
        shim = shim.replace('else { *v=m->regs[r]; }', 'else { *v=m->regs[r]; if(r==0x39)m->regs[r]=0; }')
        with tempfile.TemporaryDirectory(prefix='fx0-smd-') as directory:
            src = Path(directory) / 'smd.c'
            exe = Path(directory) / 'smd'
            src.write_text(shim + PACKET_SHIM + LIFECYCLE_SHIM + PM_SHIM + code + MAIN)
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
            result = subprocess.run([str(exe)],text=True,capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
