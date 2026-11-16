// SPDX-License-Identifier: GPL-2.0-only

static void reset(void) {
 available=true;convention=SMC_CONVENTION_LEGACY;calls=availability_checks=convention_checks=transport_rc=0;
 reply=(struct qcom_scm_res){.result={0x76543210,0xfedcba98,0}};
}
int main(void) {
 const u32 address=0x12345678;const u64 sentinel=0x1122334455667788ULL;u64 value;
 reset();CHECK(qcom_scm_legacy_fuse_read(address,NULL)==-EINVAL);CHECK(!calls && !availability_checks && !convention_checks);
 reset();value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address+4,&value)==-EINVAL);CHECK(value==sentinel && !calls && !availability_checks);
 reset();available=false;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EPROBE_DEFER);CHECK(value==sentinel && !calls && !convention_checks);
 reset();convention=SMC_CONVENTION_ARM_32;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EOPNOTSUPP);CHECK(value==sentinel && !calls);
 reset();convention=SMC_CONVENTION_ARM_64;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EOPNOTSUPP);CHECK(value==sentinel && !calls);
 reset();convention=SMC_CONVENTION_UNKNOWN;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EOPNOTSUPP);CHECK(value==sentinel && !calls);
 reset();CHECK(!qcom_scm_legacy_fuse_read(address,&value));CHECK(calls==1 && value==0xfedcba9876543210ULL);CHECK(captured.svc==8 && captured.cmd==7 && captured.arginfo==2 && captured.owner==2);CHECK(captured.args[0]==address && captured.args[1]==0);
 reset();transport_rc=-ETIMEDOUT;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-ETIMEDOUT);CHECK(value==sentinel && calls==1);
 reset();transport_rc=3;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EIO);CHECK(value==sentinel && calls==1);
 reset();reply.result[2]=7;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EIO);CHECK(value==sentinel && calls==1);
 reset();reply.result[0]|=0xfeedface00000000ULL;reply.result[1]|=0xdeadbeef00000000ULL;CHECK(!qcom_scm_legacy_fuse_read(address,&value));CHECK(value==0xfedcba9876543210ULL);
 reset();reply.result[0]=reply.result[1]=0;CHECK(!qcom_scm_legacy_fuse_read(address,&value));CHECK(value==0);
 reset();CHECK(!qcom_scm_legacy_fuse_read(0xfffffff8,&value));CHECK(captured.args[0]==0xfffffff8ULL);
 puts("13 actual-API contracts passed");return 0;
}
