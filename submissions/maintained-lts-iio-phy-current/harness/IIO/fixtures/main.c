// SPDX-License-Identifier: GPL-2.0-only

int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 u8 input[2943], output[2943]; int n, calls;
 for(n=0;n<2943;n++) input[n]=(n*37+11)&255;
 memset(m.ram,0x5a,sizeof(m.ram));
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,sizeof(input))==0);
 calls=m.calls;
 assert(!memcmp(m.ram+32,input,sizeof(input)));
 for(n=0;n<32;n++) assert(m.ram[n]==0x5a);
 for(n=2975;n<3072;n++) assert(m.ram[n]==0x5a);
 assert(inv_mpu6515_dmp_mem_read(&st,32,output,sizeof(output))==0);
 assert(!memcmp(input,output,sizeof(input)));
 /* Fail each operation of an entire successful write/readback sequence. */
 for(n=1;n<=calls;n++) {
  memset(&m,0,sizeof(m)); m.fail=n;
  assert(inv_mpu6515_dmp_mem_write(&st,32,input,sizeof(input))==-EREMOTEIO);
  assert(m.calls==n && !(m.regs[0x6a]&0xc0));
 }
 memset(&m,0,sizeof(m)); m.corrupt=1;
 assert(inv_mpu6515_dmp_mem_write(&st,255,input,20)==-EIO);
 memset(&m,0,sizeof(m));
 assert(inv_mpu6515_dmp_mem_write(&st,31,input,1)==-EINVAL);
 assert(inv_mpu6515_dmp_mem_write(&st,3071,input,2)==-EINVAL);
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,0)==-EINVAL);
 assert(inv_mpu6515_dmp_mem_write(&st,~0u,input,1)==-EINVAL);
 assert(m.calls==0);
 m.regs[0x6a]=0x80;
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,1)==-EBUSY);
 m.regs[0x6a]=0x40;
 assert(inv_mpu6515_dmp_mem_read(&st,32,output,1)==-EBUSY);
 st.chip_type=0; m.calls=0;
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,1)==-EOPNOTSUPP);
 assert(m.calls==0);
 printf("Passed bounds, bank splits, cursor loss, corrupt readback and %d injected operation failures\n",calls);
 return 0;
}
