// SPDX-License-Identifier: GPL-2.0-only

int main(int argc,char **argv) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 u8 image[2943]; FILE *f; int calls,i;
 assert(argc==2); f=fopen(argv[1],"rb"); assert(f);
 assert(fread(image,1,sizeof(image),f)==sizeof(image)); fclose(f);
 fixture.data=image; fixture.size=sizeof(image);
 assert(inv_mpu6515_dmp_load(&st)==0); calls=m.calls;
 assert(requests==1 && releases==1 && m.regs[0x70]==4 && m.regs[0x71]==0);
 assert(!memcmp(m.ram+32,image,sizeof(image)) && m.regs[0x6a]==0);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); m.fail=i; requests=0; releases=0;
  assert(inv_mpu6515_dmp_load(&st)==-EREMOTEIO);
  assert(requests==releases && m.regs[0x6a]==0);
 }
 memset(&m,0,sizeof(m)); requests=0; releases=0; missing=1;
 assert(inv_mpu6515_dmp_load(&st)==-ENOENT && requests==1 && releases==0 && m.calls==2);
 missing=0; fixture.size--;
 assert(inv_mpu6515_dmp_load(&st)==-EINVAL && m.calls==4);
 fixture.size++; image[0]^=1;
 assert(inv_mpu6515_dmp_load(&st)==-EINVAL && m.calls==6);
 image[0]^=1; m.corrupt=1;
 assert(inv_mpu6515_dmp_load(&st)==-EIO);
 printf("Passed real loader image/CRC, missing/invalid firmware, corruption and %d operation failures\n",calls);
 return 0;
}
