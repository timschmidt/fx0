// SPDX-License-Identifier: GPL-2.0-only
static struct qcom_smd_rpm *watched;
static void assert_transport_irq_order(bool enable) {
 CHECK(watched&&watched->sleep_owner==&watched->system_token&&watched->system_token.cookie);
 CHECK(watched->receive_masked==enable);
 CHECK(!pthread_mutex_trylock(&watched->lock.native));CHECK(!pthread_mutex_unlock(&watched->lock.native));
}
