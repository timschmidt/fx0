// SPDX-License-Identifier: GPL-2.0-only
static int qcom_mpm_init_wake_domains(struct device *d,struct qcom_mpm_priv *p) {CHECK(p->sleep_image&&full_pm);return fault()?failure_error:0;}
static void qcom_mpm_write(struct qcom_mpm_priv *p,unsigned int reg,unsigned int index,u32 value) {CHECK(p->base==mmio&&reg<5&&index<2&&!value);mmio[2+reg*2+index]=value;}
