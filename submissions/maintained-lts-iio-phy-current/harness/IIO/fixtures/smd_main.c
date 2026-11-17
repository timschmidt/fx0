// SPDX-License-Identifier: GPL-2.0-only

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
