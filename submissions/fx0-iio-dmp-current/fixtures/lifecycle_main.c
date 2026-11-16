// SPDX-License-Identifier: GPL-2.0-only

int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 struct iio_dev d=model_iio_device(&st, BIT(INV_MPU6515_SCAN_QUATERNION), true); int i,calls,stop_calls;
 u8 packet[16]={4,0};
 assert(inv_mpu6515_dmp_start(&st)==0 && st.dmp_active);
 calls=m.calls;
 assert(m.regs[0x6a]==0xc0 && m.regs[0x38]==0x12);
 assert(inv_mpu6515_dmp_stop(&st)==0 && !st.dmp_saved_valid && !st.dmp_active);
 stop_calls=m.calls-calls;
 assert(m.regs[0x19]==0 && m.regs[0x38]==0 && m.regs[0x6a]==0);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); st.dmp_saved_valid=false; st.dmp_active=false; m.fail=i;
  assert(inv_mpu6515_dmp_start(&st)==-EREMOTEIO);
  assert(!st.dmp_active && !(m.regs[0x6a]&0xc0));
 }
 for(i=1;i<=stop_calls;i++) {
  memset(&m,0,sizeof(m)); st.dmp_saved_valid=false; st.dmp_active=false;
  assert(inv_mpu6515_dmp_start(&st)==0);
  m.fail=m.calls+i;
  assert(inv_mpu6515_dmp_stop(&st)==-EREMOTEIO && st.dmp_saved_valid);
  assert(inv_mpu6515_dmp_stop(&st)==0 && !st.dmp_saved_valid);
 }
 memset(&m,0,sizeof(m)); st.dmp_saved_valid=false;
 assert(inv_mpu6515_dmp_start(&st)==0);
 m.fail=m.calls+1;
 assert(inv_mpu6515_dmp_stop(&st)==-EREMOTEIO && st.dmp_saved_valid);
 assert(inv_mpu6515_dmp_stop(&st)==0 && !st.dmp_saved_valid);
 assert(inv_mpu6515_dmp_start(&st)==0);
 memcpy(m.fifo,packet,7); m.fifo_len=7;
 assert(inv_mpu6515_dmp_read_fifo(&d,1000000000)==0 && d.samples==0 && st.dmp_tail_len==7);
 memcpy(m.fifo,packet+7,9); m.fifo_len=9;
 assert(inv_mpu6515_dmp_read_fifo(&d,1040000000)==0 && d.samples==1 && st.dmp_tail_len==0);
 assert(d.q[0]==(1<<30) && d.q[1]==0 && d.timestamp==1040000000);
 memcpy(m.fifo,packet,16); m.fifo[0]=0x7f; m.fifo_len=16;
 assert(inv_mpu6515_dmp_read_fifo(&d,1080000000)==-EPROTO && d.samples==1);
 assert(st.dmp_tail_len==0 && m.fifo_len==0);
 st.dmp_overflow=true;
 assert(inv_mpu6515_dmp_read_fifo(&d,1080000000)==-EOVERFLOW && !st.dmp_overflow);
 memcpy(m.fifo,packet,16); m.fifo[4]=0x7f; m.fifo_len=16;
 assert(inv_mpu6515_dmp_read_fifo(&d,1080000000)==-ERANGE && d.samples==1);
 memcpy(m.fifo,packet,16); memcpy(m.fifo+16,packet,16); m.fifo_len=32;
 assert(inv_mpu6515_dmp_read_fifo(&d,1200000000)==0 && d.samples==3);
 assert(d.timestamp==1200000000);
 /* A semantically invalid second packet invalidates the whole batch. */
 memcpy(m.fifo,packet,16); memcpy(m.fifo+16,packet,16); m.fifo[20]=0x7f; m.fifo_len=32;
 assert(inv_mpu6515_dmp_read_fifo(&d,1280000000)==-ERANGE && d.samples==3);
 m.fifo_len=992;
 assert(inv_mpu6515_dmp_read_fifo(&d,1320000000)==-EOVERFLOW && d.samples==3);
 printf("Passed native lifecycle (%d startup + %d stop failures), cleanup retry, FIFO fragments, quaternion, corruption and overflow controls\n",calls,stop_calls);
 return 0;
}
