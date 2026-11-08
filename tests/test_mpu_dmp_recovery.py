"""Compile the recovery follow-up against the same modeled native bus."""
import os
import pathlib
import subprocess
import tempfile
import unittest
from test_mpu_dmp_native import STREAM_SHIM, PACKET_SHIM, LIFECYCLE_SHIM

KERNEL = pathlib.Path(os.environ.get('FX0_KERNEL_SOURCE', pathlib.Path(__file__).resolve().parents[1]/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/iio/imu/inv_mpu6050/inv_mpu_dmp.c'
MAIN = r'''
int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 int calls;
 assert(inv_mpu6515_dmp_recover(&st)==0 && m.calls==0);
 m.regs[0x1c]=0x10;
 assert(inv_mpu6515_dmp_start(&st)==0 && m.regs[0x1c]==0);
 calls=m.calls;
 assert(inv_mpu6515_dmp_recover(&st)==-EBUSY && m.calls==calls);
 assert(st.dmp_active && st.dmp_saved_valid);
 m.fail=m.calls+1;
 assert(inv_mpu6515_dmp_stop(&st)==-EREMOTEIO && st.dmp_saved_valid);
 m.fail=m.calls+1;
 assert(inv_mpu6515_dmp_recover(&st)==-EREMOTEIO && st.dmp_saved_valid);
 assert(!st.dmp_active);
 assert(inv_mpu6515_dmp_recover(&st)==0 && !st.dmp_saved_valid);
 assert(m.regs[0x1c]==0x10 && m.regs[0x6a]==0 && m.regs[0x38]==0);
 calls=m.calls;
 assert(inv_mpu6515_dmp_recover(&st)==0 && m.calls==calls);
 puts("Recovery gates active DMP, preserves pending state on failure and verifies raw restoration before access");
 return 0;
}
'''


class RecoveryGate(unittest.TestCase):
    def test_real_c_pending_restore_before_raw_access(self):
        self.assertTrue(SOURCE.exists(), 'recovery worktree is required')
        source = SOURCE.read_text()
        code = source.split('#define INV_MPU6515_DMP_FIRMWARE')[0]
        code += source[source.index('int inv_mpu6515_dmp_configure('):].split('\nint inv_mpu6515_dmp_smd_set(')[0]
        code = '\n'.join(line for line in code.splitlines() if not line.startswith('#include'))
        with tempfile.TemporaryDirectory(prefix='fx0-native-recovery-') as directory:
            src = pathlib.Path(directory) / 'recovery.c'
            exe = pathlib.Path(directory) / 'recovery'
            src.write_text(STREAM_SHIM + PACKET_SHIM + LIFECYCLE_SHIM + code + MAIN)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(src), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
