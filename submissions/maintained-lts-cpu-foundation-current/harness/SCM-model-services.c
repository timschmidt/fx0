// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic firmware implements only the pinned two-word/three-word contract. */
static enum qcom_scm_convention __get_convention(void) { convention_checks++; return qcom_scm_convention; }
static int __scm_smc_call(struct device *d, const struct qcom_scm_desc *desc,
 enum qcom_scm_convention c, struct qcom_scm_res *r, bool atomic) {
 (void)d; (void)desc; (void)c; (void)r; (void)atomic;
 arm_calls++; return -EOPNOTSUPP;
}
static void arm_smccc_smc(unsigned long a0, unsigned long a1, unsigned long a2,
 unsigned long a3, unsigned long a4, unsigned long a5, unsigned long a6, unsigned long a7,
 struct arm_smccc_res *r) {
 CHECK(a0==1 && a1!=0 && a2==(uintptr_t)model_allocation);
 CHECK(a3==0 && a4==0 && a5==0 && a6==0 && a7==0 && model_lock==1);
 smc_calls++;
 struct scm_legacy_command *cmd=model_allocation;
 CHECK(le32_to_cpu(cmd->len)==48 && mapped_size==48);
 CHECK(le32_to_cpu(cmd->buf_offset)==16 && le32_to_cpu(cmd->resp_hdr_offset)==24);
 CHECK(le32_to_cpu(cmd->id)==((8U<<10)|7U));
 /* Inspect bytes independently of the actual transport's access helpers. */
 const uint8_t *bytes=model_allocation;
 for(unsigned i=0;i<4;i++) CHECK(bytes[16+i]==((expected_address>>(8*i))&255));
 for(unsigned i=20;i<24;i++) CHECK(bytes[i]==0);
 r->a0=smc_calls<=interruptions ? QCOM_SCM_INTERRUPTED : (unsigned long)smc_error;
 if(r->a0) return;
 struct scm_legacy_response *rsp=(void *)(bytes+24);
 rsp->len=cpu_to_le32(24); rsp->buf_offset=cpu_to_le32(12);
 for(unsigned i=0;i<3;i++) {
  uint32_t le=cpu_to_le32(model_words[i]); memcpy((uint8_t *)rsp+12+4*i,&le,4);
 }
}
static void dma_sync_single_for_cpu(struct device *d, dma_addr_t address, size_t n, int direction) {
 CHECK(d==&model_device && direction==DMA_FROM_DEVICE && n==12 && !model_lock);
 syncs++;
 if(address==(uintptr_t)model_allocation+24) {
  CHECK(syncs<=poll_delay);
  if(syncs==poll_delay) {
   struct scm_legacy_response *rsp=(void *)((uint8_t *)model_allocation+24);
   rsp->is_complete=cpu_to_le32(1);
  }
 } else CHECK(address==(uintptr_t)model_allocation+36 && syncs==poll_delay+1);
}
