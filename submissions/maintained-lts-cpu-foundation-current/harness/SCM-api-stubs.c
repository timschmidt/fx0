// SPDX-License-Identifier: GPL-2.0-only

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t u32;typedef uint64_t u64;
#define EINVAL 22
#define EPROBE_DEFER 517
#define EOPNOTSUPP 95
#define EIO 5
#define ETIMEDOUT 110
#define QCOM_SCM_ARGS(n) (n)
#define ARM_SMCCC_OWNER_SIP 2
#define CHECK(x) do { if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
struct device {int dummy;};
struct qcom_scm_desc {u32 svc,cmd,arginfo;u64 args[2];u32 owner;};
struct qcom_scm_res {u64 result[3];};
static struct device device;
static struct {struct device *dev;} scm={&device};
static __typeof__(scm) *__scm=&scm;
static bool available;
static enum qcom_scm_convention convention;
static int calls,availability_checks,convention_checks,transport_rc;
static struct qcom_scm_desc captured;
static struct qcom_scm_res reply;
static bool qcom_scm_is_available(void) {availability_checks++;return available;}
static enum qcom_scm_convention __get_convention(void) {convention_checks++;return convention;}
static int qcom_scm_call(struct device *dev,const struct qcom_scm_desc *desc,struct qcom_scm_res *res) {
 CHECK(dev==&device);calls++;captured=*desc;*res=reply;return transport_rc;
}
