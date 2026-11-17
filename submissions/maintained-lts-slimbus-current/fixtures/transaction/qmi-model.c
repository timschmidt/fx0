/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical IDR/completion/socket services; actual extracted QMI/NGD bodies. */
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
typedef uint16_t u16;
#define U16_MAX UINT16_MAX
#define GFP_KERNEL 0
#define QMI_RESULT_SUCCESS_V01 0
#define dev_err(...) ((void)0)
#define pr_err(...) ((void)0)
struct mutex { bool held; };
struct completion { bool done; };
struct qmi_elem_info { int unused; };
struct sockaddr_qrtr { int unused; };
struct qmi_txn;
struct idr { struct qmi_txn *entries[UINT16_MAX + 1]; };
struct qmi_handle { struct idr txns; struct mutex txn_lock; };
struct qcom_slim_ngd_ctrl {
	struct { struct qmi_handle *handle; } qmi;
	void *dev;
};
/* ACTUAL_TYPES */
/* ACTUAL_DEFINES */
static const struct qmi_elem_info slimbus_power_req_msg_v01_ei[1];
static const struct qmi_elem_info slimbus_power_resp_msg_v01_ei[1];
static unsigned cases, checks, failures;
static unsigned init_calls, send_calls, wait_calls, remove_calls, invalid_sends;
static int alloc_result, send_result, wait_result;
static unsigned response_result;
static bool should_complete, active_request;
static unsigned failed_init_cases, successful_id_zero_cases, successful_positive_id_cases;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; \
	if (failures <= 12) fprintf(stderr, "check failed line %d: %s\n", __LINE__, #x); \
	} } while (0)
static void mutex_init(struct mutex *m) { m->held = false; }
static void mutex_lock(struct mutex *m) { assert(!m->held); m->held = true; }
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held = false; }
static void init_completion(struct completion *c) { c->done = false; }
static void complete(struct completion *c) { c->done = true; }
static unsigned long wait_for_completion_timeout(struct completion *c, unsigned long timeout)
{
	assert(timeout == SLIMBUS_QMI_RESP_TOUT);
	++wait_calls;
	return c->done;
}
static int idr_alloc_cyclic(struct idr *idr, struct qmi_txn *txn,
			  int start, int end, int flags)
{
	assert(start == 0 && end == U16_MAX && flags == GFP_KERNEL);
	++init_calls;
	if (alloc_result >= 0) {
		assert(alloc_result < end && !idr->entries[alloc_result]);
		idr->entries[alloc_result] = txn;
	}
	return alloc_result;
}
static void *idr_remove(struct idr *idr, int id)
{
	assert(id >= 0 && id <= U16_MAX);
	++remove_calls;
	void *old = idr->entries[id];
	idr->entries[id] = NULL;
	return old;
}
/* ACTUAL_CORE */
/* ACTUAL_RESPONSE */
static ssize_t qmi_send_request(struct qmi_handle *qmi, struct sockaddr_qrtr *sq,
			       struct qmi_txn *txn, int msg_id, size_t len,
			       const struct qmi_elem_info *ei, const void *data)
{
	const struct slimbus_power_req_msg_v01 *req = data;
	++send_calls;
	/* Never execute a real send or dereference an unowned IDR record. */
	if (qmi->txns.entries[txn->id] != txn)
		++invalid_sends;
	CHECK(sq == NULL && msg_id == SLIMBUS_QMI_POWER_REQ_V01);
	CHECK(len == SLIMBUS_QMI_POWER_REQ_MAX_MSG_LEN);
	CHECK(ei == slimbus_power_req_msg_v01_ei);
	CHECK(req->resp_type_valid == 0);
	CHECK(req->pm_req == (active_request ? SLIMBUS_PM_ACTIVE_V01 : SLIMBUS_PM_INACTIVE_V01));
	CHECK(txn->ei == slimbus_power_resp_msg_v01_ei);
	if (send_result >= 0) {
		struct slimbus_power_resp_msg_v01 *resp = txn->dest;
		resp->resp.result = response_result;
		txn->result = wait_result;
		if (should_complete)
			qcom_slim_qmi_power_resp_cb(qmi, sq, txn, resp);
	}
	return send_result;
}
/* ACTUAL_DRIVER */
int main(void)
{
	static struct qmi_handle qmi;
	struct qcom_slim_ngd_ctrl ctrl = { .qmi.handle = &qmi };
	const int allocations[] = {-ENOMEM, -ENOSPC, 0, 1, 7, U16_MAX - 1};
	const int sends[] = {-ENOMEM, -EPIPE, 0};
	const int waits[] = {0, 0, -EPROTO, -EREMOTEIO};
	for (unsigned a = 0; a < sizeof(allocations) / sizeof(allocations[0]); ++a)
	for (unsigned s = 0; s < sizeof(sends) / sizeof(sends[0]); ++s)
	for (unsigned w = 0; w < sizeof(waits) / sizeof(waits[0]); ++w)
	for (unsigned r = 0; r < 2; ++r)
	for (unsigned active = 0; active < 2; ++active)
	for (unsigned foreign = 0; foreign < 2; ++foreign) {
		struct qmi_txn sentinel;
		memset(&qmi, 0, sizeof(qmi));
		alloc_result = allocations[a]; send_result = sends[s]; wait_result = waits[w];
		response_result = r; active_request = active; should_complete = w != 0;
		init_calls = send_calls = wait_calls = remove_calls = invalid_sends = 0;
		/* A failed negative allocation truncates into this valid u16 ID. */
		unsigned foreign_id = alloc_result < 0 ? (u16)alloc_result : 19;
		if (foreign) qmi.txns.entries[foreign_id] = &sentinel;
		int ret = qcom_slim_qmi_power_request(&ctrl, active);
		int expected = alloc_result < 0 ? alloc_result : send_result < 0 ? send_result :
			!should_complete ? -ETIMEDOUT : wait_result < 0 ? wait_result : r ? -EREMOTEIO : 0;
		++cases;
		CHECK(ret == expected);
		CHECK(init_calls == 1);
		CHECK(send_calls == (unsigned)(alloc_result >= 0));
		CHECK(wait_calls == (unsigned)(alloc_result >= 0 && send_result >= 0));
		CHECK(remove_calls == (unsigned)(alloc_result >= 0));
		CHECK(invalid_sends == 0);
		CHECK(!qmi.txn_lock.held);
		if (foreign) CHECK(qmi.txns.entries[foreign_id] == &sentinel);
		if (alloc_result >= 0) CHECK(qmi.txns.entries[alloc_result] == NULL);
		if (alloc_result < 0) ++failed_init_cases;
		else if (alloc_result == 0) ++successful_id_zero_cases;
		else ++successful_positive_id_cases;
	}
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u,"
	       "\"failed_initialization_cases\":%u,\"ID_zero_cases\":%u,\"positive_ID_cases\":%u}\n",
	       cases, checks, failures, failed_init_cases, successful_id_zero_cases, successful_positive_id_cases);
	return 0;
}
