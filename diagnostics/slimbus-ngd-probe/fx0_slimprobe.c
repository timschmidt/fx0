// SPDX-License-Identifier: GPL-2.0-only
/*
 * Fx0 diagnostic: vote MSM8226 SLIMbus power through the ADSP's QMI
 * SLIMbus service, read the controller version and the NGD status word at
 * both candidate NGD offsets, then vote power off again. The message
 * definitions follow drivers/slimbus/qcom-ngd-ctrl.c.
 */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/net.h>
#include <linux/soc/qcom/qmi.h>
#include <linux/workqueue.h>

#define SLIMBUS_QMI_SVC_ID			0x0301
#define SLIMBUS_QMI_SVC_V1			1
#define SLIMBUS_QMI_INS_ID			0
#define SLIMBUS_QMI_SELECT_INSTANCE_REQ_V01	0x0020
#define SLIMBUS_QMI_POWER_REQ_V01		0x0021
#define SLIMBUS_QMI_REQ_MAX_MSG_LEN		14
#define SLIMBUS_QMI_RESP_TOUT			1000

#define FX0_SLIM_BASE				0xfe12f000
#define FX0_SLIM_SIZE				0x35000

enum { SLIMBUS_MODE_MASTER_V01 = 2 };
enum { SLIMBUS_PM_INACTIVE_V01 = 1, SLIMBUS_PM_ACTIVE_V01 = 2 };

struct slimbus_select_inst_req_msg_v01 {
	u32 instance;
	u8 mode_valid;
	u32 mode;
};

struct slimbus_power_req_msg_v01 {
	u32 pm_req;
	u8 resp_type_valid;
	u32 resp_type;
};

struct slimbus_resp_msg_v01 {
	struct qmi_response_type_v01 resp;
};

static const struct qmi_elem_info select_req_ei[] = {
	{ .data_type = QMI_UNSIGNED_4_BYTE, .elem_len = 1, .elem_size = sizeof(u32),
	  .tlv_type = 0x01, .offset = offsetof(struct slimbus_select_inst_req_msg_v01, instance) },
	{ .data_type = QMI_OPT_FLAG, .elem_len = 1, .elem_size = sizeof(u8),
	  .tlv_type = 0x10, .offset = offsetof(struct slimbus_select_inst_req_msg_v01, mode_valid) },
	{ .data_type = QMI_UNSIGNED_4_BYTE, .elem_len = 1, .elem_size = sizeof(u32),
	  .tlv_type = 0x10, .offset = offsetof(struct slimbus_select_inst_req_msg_v01, mode) },
	{ .data_type = QMI_EOTI },
};

static const struct qmi_elem_info power_req_ei[] = {
	{ .data_type = QMI_UNSIGNED_4_BYTE, .elem_len = 1, .elem_size = sizeof(u32),
	  .tlv_type = 0x01, .offset = offsetof(struct slimbus_power_req_msg_v01, pm_req) },
	{ .data_type = QMI_OPT_FLAG, .elem_len = 1, .elem_size = sizeof(u8),
	  .tlv_type = 0x10, .offset = offsetof(struct slimbus_power_req_msg_v01, resp_type_valid) },
	{ .data_type = QMI_SIGNED_4_BYTE_ENUM, .elem_len = 1, .elem_size = sizeof(u32),
	  .tlv_type = 0x10, .offset = offsetof(struct slimbus_power_req_msg_v01, resp_type) },
	{ .data_type = QMI_EOTI },
};

static const struct qmi_elem_info resp_ei[] = {
	{ .data_type = QMI_STRUCT, .elem_len = 1, .elem_size = sizeof(struct qmi_response_type_v01),
	  .tlv_type = 0x02, .offset = offsetof(struct slimbus_resp_msg_v01, resp),
	  .ei_array = qmi_response_type_v01_ei },
	{ .data_type = QMI_EOTI },
};

static struct qmi_handle fx0_qmi;
static struct sockaddr_qrtr fx0_sq;
static struct work_struct fx0_work;

static int fx0_request(int msg_id, const struct qmi_elem_info *ei, const void *req)
{
	struct slimbus_resp_msg_v01 resp = {};
	struct qmi_txn txn;
	int ret;

	ret = qmi_txn_init(&fx0_qmi, &txn, resp_ei, &resp);
	if (ret < 0)
		return ret;
	ret = qmi_send_request(&fx0_qmi, &fx0_sq, &txn, msg_id,
			       SLIMBUS_QMI_REQ_MAX_MSG_LEN, ei, req);
	if (ret < 0) {
		qmi_txn_cancel(&txn);
		return ret;
	}
	ret = qmi_txn_wait(&txn, msecs_to_jiffies(SLIMBUS_QMI_RESP_TOUT));
	if (ret < 0)
		return ret;
	pr_info("fx0_slimprobe: msg 0x%02x result %u error %u\n", msg_id,
		resp.resp.result, resp.resp.error);
	return resp.resp.result == QMI_RESULT_SUCCESS_V01 ? 0 : -EREMOTEIO;
}

static void fx0_work_fn(struct work_struct *work)
{
	struct slimbus_select_inst_req_msg_v01 sel = {
		.instance = 0, .mode_valid = 1, .mode = SLIMBUS_MODE_MASTER_V01,
	};
	struct slimbus_power_req_msg_v01 pwr = { .pm_req = SLIMBUS_PM_ACTIVE_V01 };
	void __iomem *base;
	u32 ver;

	if (fx0_request(SLIMBUS_QMI_SELECT_INSTANCE_REQ_V01, select_req_ei, &sel))
		return;
	if (fx0_request(SLIMBUS_QMI_POWER_REQ_V01, power_req_ei, &pwr))
		return;

	base = ioremap(FX0_SLIM_BASE, FX0_SLIM_SIZE);
	if (base) {
		ver = readl(base);
		pr_info("fx0_slimprobe: ctrl word 0x%08x (version 0x%04x)\n", ver, ver >> 16);
		pr_info("fx0_slimprobe: status @0x804 0x%08x @0x1004 0x%08x\n",
			readl(base + 0x804), readl(base + 0x1004));
		iounmap(base);
	}

	pwr.pm_req = SLIMBUS_PM_INACTIVE_V01;
	fx0_request(SLIMBUS_QMI_POWER_REQ_V01, power_req_ei, &pwr);
}

static int fx0_new_server(struct qmi_handle *qmi, struct qmi_service *svc)
{
	fx0_sq.sq_family = AF_QIPCRTR;
	fx0_sq.sq_node = svc->node;
	fx0_sq.sq_port = svc->port;
	pr_info("fx0_slimprobe: service at node %u port %u\n", svc->node, svc->port);
	schedule_work(&fx0_work);
	return 0;
}

static const struct qmi_ops fx0_ops = {
	.new_server = fx0_new_server,
};

static int __init fx0_slimprobe_init(void)
{
	int ret;

	INIT_WORK(&fx0_work, fx0_work_fn);
	ret = qmi_handle_init(&fx0_qmi, SLIMBUS_QMI_REQ_MAX_MSG_LEN, &fx0_ops, NULL);
	if (ret < 0)
		return ret;
	ret = qmi_add_lookup(&fx0_qmi, SLIMBUS_QMI_SVC_ID, SLIMBUS_QMI_SVC_V1,
			     SLIMBUS_QMI_INS_ID);
	if (ret < 0)
		qmi_handle_release(&fx0_qmi);
	return ret;
}

static void __exit fx0_slimprobe_exit(void)
{
	qmi_handle_release(&fx0_qmi);
	cancel_work_sync(&fx0_work);
}

module_init(fx0_slimprobe_init);
module_exit(fx0_slimprobe_exit);
MODULE_DESCRIPTION("Fx0 SLIMbus NGD version probe");
MODULE_LICENSE("GPL");
