/* Host kernel-service model for test_nxp_nci_open_teardown.py. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%d: %s\n", __LINE__, #x); exit(1); } } while (0)
#define pr_debug(...) ((void)0)
#define nfc_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define WARN_ON_ONCE(x) CHECK(!(x))
#define NFC_FIRMWARE_NAME_MAXSIZE 32
#define GFP_KERNEL 0
#define NCI_CTRL_HDR_SIZE 3
#define NCI_RESET_TYPE_RESET_CONFIG 1
#define NCI_OP_CORE_RESET_CMD 0
#define NCI_RESET_TIMEOUT 5000
#define NCI_STATUS_OK 0
#define NCI_UP 0
#define NCI_INIT 1
#define NCI_UNREG 2
#define NCI_DATA_EXCHANGE 3
#define BIT(n) (1UL << (n))
#define IRQ_HANDLED 1
#define IRQ_NONE 0
#define I2C_FUNC_I2C 1
#define GPIOD_OUT_LOW 0
#define IRQF_TRIGGER_RISING 1
#define IRQF_ONESHOT 0x2000
#define NXP_NCI_I2C_MAX_PAYLOAD 32
#define NXP_NCI_I2C_DRIVER_NAME "nxp-nci_i2c"
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ACPI_COMPANION(dev) false
typedef unsigned char u8;
typedef int irqreturn_t;
struct work_struct { int dummy; };
struct completion { int dummy; };
struct mutex { bool held; };
struct firmware;
struct device { int dummy; };
struct clk { int votes; };
struct gpio_desc { int value; };
struct nci_dev;
struct sk_buff { u8 storage[16]; u8 *data; unsigned len; };
struct i2c_client { struct device dev; void *adapter, *data; int irq; };
struct nci_ctrl_hdr { u8 first, second, plen; };
struct nci_core_reset_cmd { u8 reset_type; };
struct nci_core_reset_rsp { u8 status, nci_ver, config_status; };
/* ACTUAL_TYPES */
struct list_head { struct list_head *next, *prev; };
struct nci_conn_info { struct list_head list; };
#define entry(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define list_for_each_entry_safe(pos, n, head, member) \
 for (pos = entry((head)->next, __typeof__(*pos), member), \
      n = entry(pos->member.next, __typeof__(*pos), member); \
      &pos->member != (head); \
      pos = n, n = entry(n->member.next, __typeof__(*n), member))
static void list_del(struct list_head *node)
{
 node->prev->next = node->next; node->next->prev = node->prev;
}
struct queue { struct sk_buff *skb; };
struct workqueue { bool alive; };
struct nci_ops { int (*close)(struct nci_dev *); };
struct nci_dev {
 struct nxp_nci_info *info;
 unsigned long flags;
 struct mutex req_lock;
 const struct nci_ops *ops;
 struct queue rx_q, tx_q, cmd_q;
 struct workqueue *cmd_wq, *rx_wq, *tx_wq;
 struct work_struct rx_work;
 int cmd_timer, data_timer, cmd_cnt, cur_conn_id, nci_ver;
 struct list_head conn_info_list;
 void *nfc_dev;
};
static struct clk clock_model;
static struct gpio_desc en, fw;
static struct nxp_nci_i2c_phy phy;
static struct nxp_nci_info info;
static struct nci_dev ndev;
static struct workqueue queues[3];
static bool irq_registered, freed, pending_irq, no_response, probe_failure;
static int reset_sent, reset_acked, reset_timeouts, drained, destroyed;
static int fw_completed, work_drained, class_removed, rfkill_removed, data_completed;
static int read_offset;
static char events[128];
static void event(char c)
{
 size_t n = strlen(events); CHECK(n + 1 < sizeof(events)); events[n] = c;
}
static void mutex_lock(struct mutex *m) { CHECK(!m->held); m->held = true; }
static void mutex_unlock(struct mutex *m) { CHECK(m->held); m->held = false; }
static bool test_bit(int bit, const unsigned long *flags) { return !!(*flags & BIT(bit)); }
static void set_bit(int bit, unsigned long *flags) { *flags |= BIT(bit); }
static void clear_bit(int bit, unsigned long *flags) { *flags &= ~BIT(bit); }
static bool test_and_clear_bit(int bit, unsigned long *flags)
{ bool was = test_bit(bit, flags); clear_bit(bit, flags); return was; }
static void atomic_set(int *value, int next) { *value = next; }
static int msecs_to_jiffies(int msec) { return msec; }
static struct nxp_nci_info *nci_get_drvdata(struct nci_dev *d)
{ CHECK(d == &ndev && !freed); return d->info; }
static int clk_prepare_enable(struct clk *clock)
{ if (clock) { CHECK(!clock->votes); clock->votes++; } return 0; }
static void clk_disable_unprepare(struct clk *clock)
{ if (clock) { CHECK(clock->votes == 1); clock->votes--; } }
static void gpiod_set_value_cansleep(struct gpio_desc *gpio, int value)
{ if (gpio) gpio->value = value; }
static void usleep_range(int low, int high) { CHECK(low == 10000 && high == 15000); }
static void msleep(int ms) { CHECK(ms == 110); }
static struct sk_buff *alloc_skb(size_t size, int flags)
{ CHECK(size <= 16); struct sk_buff *skb = calloc(1, sizeof(*skb)); CHECK(skb); skb->data = skb->storage; return skb; }
static void *skb_put(struct sk_buff *skb, size_t size)
{ CHECK(skb->len + size <= 16); void *p = skb->data + skb->len; skb->len += size; return p; }
static void skb_put_data(struct sk_buff *skb, const void *data, size_t size)
{ memcpy(skb_put(skb, size), data, size); }
static void kfree_skb(struct sk_buff *skb) { free(skb); }
static void consume_skb(struct sk_buff *skb) { free(skb); }
static void skb_queue_purge(struct queue *q) { free(q->skb); q->skb = NULL; }
static void skb_queue_tail(struct queue *q, struct sk_buff *skb)
{ CHECK(q == &ndev.rx_q && !q->skb); q->skb = skb; }
static int nci_recv_frame(struct nci_dev *d, struct sk_buff *skb);
static void nci_core_reset_rsp_packet(struct nci_dev *d, const struct sk_buff *skb);
static void queue_work(struct workqueue *wq, struct work_struct *work)
{
 CHECK(wq == ndev.rx_wq && wq->alive && work == &ndev.rx_work);
 struct sk_buff *skb = ndev.rx_q.skb; CHECK(skb && skb->len == 6);
 CHECK(skb->data[0] == 0x40 && skb->data[1] == 0 && skb->data[2] == 3);
 /* Modeled RX dispatch strips the header before the actual reset parser. */
 skb->data += 3; skb->len -= 3; nci_core_reset_rsp_packet(&ndev, skb);
 free(skb); ndev.rx_q.skb = NULL;
}
static void flush_workqueue(struct workqueue *wq) { CHECK(wq->alive); }
static void destroy_workqueue(struct workqueue *wq)
{ CHECK(wq->alive && !info.info_lock.held); wq->alive = false; destroyed++; event('Q'); }
static void timer_delete_sync(int *timer) { (void)timer; }
static void nci_data_exchange_complete(struct nci_dev *d, void *data, int id, int error)
{ CHECK(d == &ndev && !data && id == 7 && error == -ENODEV); data_completed++; }
static void nci_req_cancel(struct nci_dev *d, int error) { CHECK(d == &ndev && error == ENODEV); }
static void nci_req_complete(struct nci_dev *d, int status)
{ CHECK(d == &ndev && status == NCI_STATUS_OK && reset_sent == 1); reset_acked++; event('A'); }
static void nfc_unregister_rfkill(void *dev)
{ CHECK(dev == &ndev && !info.info_lock.held); rfkill_removed++; }
static void nfc_remove_device(void *dev)
{ CHECK(dev == &ndev && destroyed == 3); class_removed++; event('U'); }
static int i2c_master_send(struct i2c_client *client, const u8 *data, unsigned len)
{
 CHECK(client == phy.i2c_dev && len == 4 && !freed);
 CHECK(data[0] == 0x20 && data[1] == 0 && data[2] == 1 && data[3] == 1);
 CHECK(info.mode == NXP_NCI_MODE_NCI && en.value && !fw.value);
 reset_sent++; event('T'); return len;
}
static int i2c_master_recv(struct i2c_client *client, u8 *data, unsigned len)
{
 static const u8 response[] = {0x40, 0, 3, 0, 0x10, 0};
 CHECK(client == phy.i2c_dev && irq_registered && !freed && len == 3);
 CHECK(read_offset == 0 || read_offset == 3);
 memcpy(data, response + read_offset, len); read_offset += len; return len;
}
static int nxp_nci_i2c_fw_read(struct nxp_nci_i2c_phy *p, struct sk_buff **skb)
{ CHECK(0); return -EIO; }
static void nxp_nci_fw_recv_frame(struct nci_dev *d, struct sk_buff *skb) { CHECK(0); }
static void free_irq(int irq, void *data);
/* ACTUAL_TRANSPORT */
static int nci_send_cmd(struct nci_dev *d, int opcode, int len, const void *payload)
{
 CHECK(d == &ndev && opcode == NCI_OP_CORE_RESET_CMD && len == 1);
 struct sk_buff *skb = alloc_skb(4, 0);
 const u8 header[] = {0x20, 0, 1};
 skb_put_data(skb, header, sizeof(header)); skb_put_data(skb, payload, len);
 return nxp_nci_send(d, skb);
}
static int __nci_request(struct nci_dev *d, void (*request)(struct nci_dev *, const void *), const void *opt, int timeout)
{
 CHECK(d == &ndev && timeout == 5000 && d->req_lock.held);
 CHECK(test_bit(NCI_INIT, &d->flags) && !test_bit(NCI_UP, &d->flags));
 CHECK(test_bit(NCI_UNREG, &d->flags)); request(d, opt);
 /* Model the completion wait and threaded IRQ, with no real five-second sleep. */
 if (irq_registered && !no_response)
  CHECK(nxp_nci_i2c_irq_thread_fn(42, &phy) == IRQ_HANDLED);
 if (reset_acked) return 0;
 reset_timeouts++; event('X'); return -ETIMEDOUT;
}
/* ACTUAL_NETWORK */
static void nxp_nci_fw_work_complete(struct nxp_nci_info *i, int error)
{
 CHECK(i == &info && error == -ESHUTDOWN); fw_completed++;
 CHECK(!i->phy_ops->set_mode(i->phy_id, NXP_NCI_MODE_COLD));
 i->mode = NXP_NCI_MODE_COLD;
}
static void cancel_work_sync(struct work_struct *work)
{ CHECK(work == &info.fw_info.work && !freed); work_drained++; }
static void free_irq(int irq, void *data)
{
 CHECK(irq == 42 && data == &phy && irq_registered && !freed);
 CHECK(!info.info_lock.held);
 if (pending_irq) {
  /* A queued thread must finish while NCI/driver data remains allocated. */
  CHECK(nxp_nci_i2c_irq_thread_fn(irq, data) == IRQ_HANDLED);
  pending_irq = false;
 }
 irq_registered = false; drained++; event('I');
}
static void nci_free_device(struct nci_dev *d)
{
 CHECK(d == &ndev && !freed && !irq_registered && !info.info_lock.held);
 CHECK(!d->req_lock.held && destroyed == 3 && class_removed == 1);
 CHECK(info.mode == NXP_NCI_MODE_COLD && !en.value && !fw.value);
 freed = true; event('D');
}
static bool i2c_check_functionality(void *adapter, int flags)
{ CHECK(flags == I2C_FUNC_I2C); return adapter != NULL; }
static void *devm_kzalloc(struct device *dev, size_t size, int flags)
{ CHECK(size == sizeof(phy)); memset(&phy, 0, sizeof(phy)); return &phy; }
static void i2c_set_clientdata(struct i2c_client *client, void *data) { client->data = data; }
static void *i2c_get_clientdata(struct i2c_client *client) { return client->data; }
static struct clk *devm_clk_get_optional(struct device *dev, const char *name)
{ CHECK(!strcmp(name, "ref")); return &clock_model; }
static int dev_err_probe(struct device *dev, int error, const char *message) { return error; }
static int acpi_nxp_nci_gpios[1];
static int devm_acpi_dev_add_driver_gpios(struct device *dev, int *mapping) { return 0; }
static struct gpio_desc *devm_gpiod_get(struct device *dev, const char *name, int flags)
{ CHECK(!strcmp(name, "enable") && flags == GPIOD_OUT_LOW); return &en; }
static struct gpio_desc *devm_gpiod_get_optional(struct device *dev, const char *name, int flags)
{ CHECK(!strcmp(name, "firmware") && flags == GPIOD_OUT_LOW); return &fw; }
static int nxp_nci_probe(void *id, struct device *dev, const struct nxp_nci_phy_ops *ops, unsigned payload, struct nci_dev **out)
{
 CHECK(id == &phy && ops == &i2c_phy_ops && payload == 32);
 info.phy_id = id; info.phy_ops = ops; info.mode = NXP_NCI_MODE_COLD;
 CHECK(!ops->set_mode(id, NXP_NCI_MODE_COLD)); *out = &ndev; return 0;
}
static unsigned long irq_get_trigger_type(int irq) { CHECK(irq == 42); return 1; }
static int request_threaded_irq(int irq, void *handler, irqreturn_t (*thread)(int, void *), unsigned long flags, const char *name, void *data)
{
 CHECK(irq == 42 && !handler && thread == nxp_nci_i2c_irq_thread_fn && data == &phy);
 CHECK(flags == (IRQF_TRIGGER_RISING | IRQF_ONESHOT) && !strcmp(name, NXP_NCI_I2C_DRIVER_NAME));
 if (probe_failure) return -EBUSY;
 CHECK(!irq_registered); irq_registered = true; return 0;
}
/* ACTUAL_REMOVAL */
int main(int argc, char **argv)
{
 CHECK(argc == 2);
 const struct nci_ops ops = {.close = nxp_nci_close};
 ndev.info = &info; ndev.ops = &ops; ndev.nfc_dev = &ndev;
 ndev.cmd_wq = &queues[0]; ndev.rx_wq = &queues[1]; ndev.tx_wq = &queues[2];
 for (int i = 0; i < 3; i++) queues[i].alive = true;
 struct nci_conn_info connection;
 connection.list.next = connection.list.prev = &ndev.conn_info_list;
 ndev.conn_info_list.next = ndev.conn_info_list.prev = &connection.list;
 struct i2c_client client = {.irq = 42, .adapter = &ndev};
 probe_failure = !strcmp(argv[1], "probe_irq_failure");
 bool legacy = !strcmp(argv[1], "core_legacy");
 bool open = !strncmp(argv[1], "open", 4);
 bool firmware_mode = !strncmp(argv[1], "firmware", 8);
 pending_irq = strstr(argv[1], "pending_irq") != NULL;
 no_response = strstr(argv[1], "timeout") != NULL;
 if (legacy) {
  static const struct nxp_nci_phy_ops no_callbacks;
  info.phy_ops = &no_callbacks;
  nxp_nci_remove(&ndev);
 } else {
  int rc = nxp_nci_i2c_probe(&client);
  if (probe_failure) CHECK(rc == -EBUSY);
  else {
   CHECK(!rc && irq_registered);
   if (strstr(argv[1], "no_clock")) phy.ref_clk = NULL;
   if (open) CHECK(!nxp_nci_open(&ndev));
   if (firmware_mode) {
    CHECK(!i2c_phy_ops.set_mode(&phy, NXP_NCI_MODE_FW));
    info.mode = NXP_NCI_MODE_FW;
   }
   if (open) set_bit(NCI_UP, &ndev.flags);
   if (strstr(argv[1], "data_exchange")) {
    set_bit(NCI_DATA_EXCHANGE, &ndev.flags); ndev.cur_conn_id = 7;
   }
   nxp_nci_i2c_remove(&client);
  }
 }
 printf("%s: events=%s reset_tx=%d reset_ack=%d reset_timeout=%d IRQ_drain=%d\n",
        argv[1], events, reset_sent, reset_acked, reset_timeouts, drained);
 CHECK(freed && !irq_registered && !pending_irq && destroyed == 3);
 CHECK(work_drained == 1 && class_removed == 1 && rfkill_removed == 1);
 CHECK(ndev.conn_info_list.next == &ndev.conn_info_list);
 CHECK(!clock_model.votes && !phy.ref_clk_enabled && !en.value && !fw.value);
 CHECK(!phy.hard_fault && !info.info_lock.held && !ndev.req_lock.held);
 CHECK(fw_completed == (int)firmware_mode);
 CHECK(data_completed == (strstr(argv[1], "data_exchange") != NULL));
 CHECK(drained == (!legacy && !probe_failure));
 CHECK(reset_sent == (int)open);
 CHECK(reset_acked == (open && !no_response));
 CHECK(reset_timeouts == (open && no_response));
 CHECK(events[strlen(events) - 1] == 'D');
 return 0;
}
