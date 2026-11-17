// SPDX-License-Identifier: GPL-2.0-only
static const uint64_t sentinel=0x1122334455667788ULL;
static void reset(void) {
 CHECK(!model_allocation && !model_lock);
 allocations=frees=maps=unmaps=syncs=smc_calls=availability_checks=convention_checks=arm_calls=slept=0;
 allocation_fail=map_fail=smc_error=interruptions=0; poll_delay=1;
 __scm=&model_scm; qcom_scm_convention=SMC_CONVENTION_LEGACY;
 model_words[0]=0x76543210; model_words[1]=0xfedcba98; model_words[2]=0;
 expected_address=0x1000;
}
static void invoke(int expected, uint64_t value) {
 uint64_t output=sentinel; cases++;
 int rc=qcom_scm_legacy_fuse_read(expected_address,&output);
 CHECK(rc==expected); CHECK(output==(expected?sentinel:value));
 CHECK(!model_allocation && !model_lock && arm_calls==0);
}
int main(void) {
 const unsigned addresses[]={0,8,0x1000,0x12345678,0xfffffff8};
 const uint32_t words[][2]={{0,0},{1,0},{0,1},{UINT32_MAX,0},{0,UINT32_MAX},
                          {UINT32_MAX,UINT32_MAX},{0x76543210,0xfedcba98},{0x80000000,0x7fffffff}};
 for(unsigned a=0;a<5;a++) for(unsigned w=0;w<8;w++) for(int delay=1;delay<=4;delay++) for(int irq=0;irq<4;irq++) {
  reset();expected_address=addresses[a];model_words[0]=words[w][0];model_words[1]=words[w][1];poll_delay=delay;interruptions=irq;
  invoke(0,(uint64_t)words[w][0]|((uint64_t)words[w][1]<<32));
  CHECK(allocations==1 && frees==1 && maps==1 && unmaps==1 && syncs==delay+1);
  CHECK(smc_calls==irq+1 && availability_checks==1 && convention_checks==2 && slept==1);
 }
 for(unsigned a=1;a<8;a++) {
  reset();expected_address+=a;invoke(-EINVAL,0);CHECK(!allocations && !availability_checks && !convention_checks);
 }
 reset();cases++;CHECK(qcom_scm_legacy_fuse_read(0x1000,NULL)==-EINVAL);CHECK(!allocations && !availability_checks);
 reset();__scm=NULL;invoke(-EPROBE_DEFER,0);CHECK(availability_checks==1 && !convention_checks && !allocations);
 for(unsigned c=0;c<4;c++) if(c!=SMC_CONVENTION_LEGACY) {
  reset();qcom_scm_convention=c;invoke(-EOPNOTSUPP,0);CHECK(!allocations && !slept && convention_checks==1);
 }
 reset();allocation_fail=1;invoke(-ENOMEM,0);CHECK(allocations==1 && !frees && !maps && !smc_calls);
 reset();map_fail=1;invoke(-ENOMEM,0);CHECK(allocations==1 && frees==1 && maps==1 && !unmaps && !smc_calls);
 const uint32_t statuses[]={1,2,7,UINT32_MAX,0x80000000};
 for(unsigned i=0;i<5;i++) { reset();model_words[2]=statuses[i];invoke(-EIO,0);CHECK(frees==1 && unmaps==1); }
 const int codes[]={-1,-2,-3,-4,-5,-12,-127,3};
 const int expected[]={-EIO,-EINVAL,-EINVAL,-EOPNOTSUPP,-ENOMEM,-EBUSY,-EINVAL,-EINVAL};
 for(unsigned i=0;i<8;i++) { reset();smc_error=codes[i];invoke(expected[i],0);CHECK(frees==1 && unmaps==1 && syncs==0); }
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);
 return failures!=0;
}
