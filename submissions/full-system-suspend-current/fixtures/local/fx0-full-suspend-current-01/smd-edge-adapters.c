// SPDX-License-Identifier: GPL-2.0-only
#define to_smd_edge(p) container_of(p,struct qcom_smd_edge,dev)
void qcom_smd_unregister_edge(struct qcom_smd_edge *edge);
static void put_device(struct device *d) {
 if(d==&child){d->registered=false;chrdevs--;return;}
 struct qcom_smd_edge *e=to_smd_edge(d);CHECK(e==edge_memory);
 if(irq_requests){CHECK(irq_disables==1&&cancel_calls==2&&!e->scan_work.scheduled&&!e->state_work.scheduled);irq_requests--;}
 CHECK(!mailboxes&&!notifiers&&!child.registered);d->release(d);
}
static void device_unregister(struct device *d) {CHECK(d->registered);d->registered=false;put_device(d);}
static int devm_request_irq(struct device *d,int irq,int (*fn)(int,void *),unsigned long flags,const char *name,void *arg) {
 struct qcom_smd_edge *e=arg;CHECK(e==to_smd_edge(d)&&e->sleep_lock.initialized&&e->scan_work.initialized&&e->state_work.initialized&&fn==qcom_smd_edge_intr);
 if(fault())return -ENOMEM;irq_requests++;irq_flags=flags;
 /* An IRQ may queue both lifecycle workers before later registration fails. */
 e->scan_work.scheduled=e->state_work.scheduled=true;return 0;
}
