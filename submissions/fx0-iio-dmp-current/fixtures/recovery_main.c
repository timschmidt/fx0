// SPDX-License-Identifier: GPL-2.0-only

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
