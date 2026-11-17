// SPDX-License-Identifier: GPL-2.0-only

int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 struct inv_mpu6515_dmp_packet packet, before;
 u8 accel[]={0x40,0x0b,0x80,0,0x7f,0xff,0xff,0xff};
 u8 quat[]={0x04,0x03,0,0,0x80,0,0,0,0x7f,0xff,0xff,0xff,0xff,0xff,0xff,0xff};
 int i,calls;
 assert(inv_mpu6515_dmp_configure(&st)==0); calls=m.calls;
 assert(m.ram[1127]==0x4c && m.ram[1770]==0xa3 && m.ram[1701]==0xa3);
 assert(m.ram[744]==0 && m.ram[745]==7 && m.ram[731]==7);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); m.fail=i;
  assert(inv_mpu6515_dmp_configure(&st)==-EREMOTEIO && m.calls==i);
 }
 memset(&packet,0x5a,sizeof(packet)); before=packet;
 for(i=0;i<8;i++) {
  assert(inv_mpu6515_dmp_decode(accel,i,&packet)==-EAGAIN);
  assert(!memcmp(&packet,&before,sizeof(packet)));
 }
 assert(inv_mpu6515_dmp_decode(accel,8,&packet)==8);
 assert(packet.type==INV_MPU6515_DMP_ACCEL && packet.step_flags==11);
 assert(packet.xyz[0]==-32768 && packet.xyz[1]==32767 && packet.xyz[2]==-1);
 before=packet;
 for(i=0;i<16;i++) {
  assert(inv_mpu6515_dmp_decode(quat,i,&packet)==-EAGAIN);
  assert(!memcmp(&packet,&before,sizeof(packet)));
 }
 assert(inv_mpu6515_dmp_decode(quat,16,&packet)==16);
 assert(packet.type==INV_MPU6515_DMP_QUATERNION && packet.step_flags==3);
 assert(packet.xyz[0]==INT32_MIN && packet.xyz[1]==INT32_MAX && packet.xyz[2]==-1);
 before=packet; quat[0]=0x7f;
 assert(inv_mpu6515_dmp_decode(quat,16,&packet)==-EPROTO);
 assert(!memcmp(&packet,&before,sizeof(packet)));
 printf("Passed native packet fragments, signed extremes, no stale output and %d configuration-operation failures\n",calls);
 return 0;
}
