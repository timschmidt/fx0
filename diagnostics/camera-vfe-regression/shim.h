/* SPDX-License-Identifier: GPL-2.0-only */
/* Host-only endpoints. State transitions and IRQ dispatch are extracted kernel C. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef u32 dma_addr_t;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define BIT(n) (1U << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define VB2_BUF_STATE_DONE 1
#define CHECK(c, code) do { if (!(c)) die(code); } while (0)
static void die(const char *code) { fprintf(stderr, "FAIL:%s\n", code); exit(2); }
struct list_head { struct list_head *next, *prev; };
#define INIT_LIST_HEAD(p) do { (p)->next = (p); (p)->prev = (p); } while (0)
static bool list_empty(const struct list_head *p) { return p->next == p; }
static void list_add_tail(struct list_head *n, struct list_head *h)
{ n->prev = h->prev; n->next = h; h->prev->next = n; h->prev = n; }
static void list_del(struct list_head *n)
{ n->next->prev = n->prev; n->prev->next = n->next; n->next = n->prev = NULL; }
#define list_first_entry(p, t, m) container_of((p)->next, t, m)
struct completion { unsigned int done; };
static void complete(struct completion *p) { p->done++; }
struct vb2_buffer { u64 timestamp; };
struct vb2_v4l2_buffer { struct vb2_buffer vb2_buf; unsigned int sequence; };
struct camss_buffer {
 struct vb2_v4l2_buffer vb;
 dma_addr_t addr[3];
 struct list_head queue;
 unsigned int id, done;
};
struct vfe_device;
#include "kernel-types.h"
struct vfe_line { enum vfe_line_id id; struct vfe_output output; };
struct fake_device { int unused; };
struct camss { struct fake_device *dev; };
struct vfe_hw_ops {
 void (*reg_update_clear)(struct vfe_device *, enum vfe_line_id);
 void (*reg_update)(struct vfe_device *, enum vfe_line_id);
 void (*isr_read)(struct vfe_device *, u32 *, u32 *);
 void (*violation_read)(struct vfe_device *);
};
struct vfe_subdev_resources { const struct vfe_hw_ops *hw_ops; unsigned int line_num; bool rdi_rearm_at_sof; };
struct vfe_hw_ops_gen1 {
 void (*wm_set_ping_addr)(struct vfe_device *, u8, u32);
 void (*wm_set_pong_addr)(struct vfe_device *, u8, u32);
 void (*bus_reload_wm)(struct vfe_device *, u8);
 void (*wm_set_framedrop_period)(struct vfe_device *, u8, u8);
 void (*wm_set_framedrop_pattern)(struct vfe_device *, u8, u32);
 int (*wm_get_ping_pong_status)(struct vfe_device *, u8);
 void (*halt_clear)(struct vfe_device *);
};
struct vfe_device {
 struct camss *camss;
 struct vfe_line line[VFE_LINE_NUM_MAX];
 enum vfe_line_id wm_output_map[MSM_VFE_IMAGE_MASTERS_NUM];
 const struct vfe_subdev_resources *res;
 const struct vfe_hw_ops_gen1 *ops_gen1;
 struct vfe_isr_ops isr_ops;
 int output_lock;
 struct completion halt_complete, reset_complete;
 u32 status0, status1, ping[7], pong[7], pattern[7];
 unsigned int active[7], ack[VFE_LINE_NUM_MAX], writes[VFE_LINE_NUM_MAX], reload[7];
 unsigned int reads, errors, returns;
 unsigned int earliest_ack[8], ack_line[8];
};
static struct vfe_device *current_vfe;
static struct camss_buffer buffers[8];
static unsigned int lock_depth;
static void (*unlock_hook)(void);
static void lock_enter(void) { CHECK(lock_depth == 0, "LOCK_NESTING"); lock_depth++; }
static void lock_exit(void)
{
 CHECK(lock_depth == 1, "LOCK_RELEASE"); lock_depth--;
 if (unlock_hook) { void (*hook)(void) = unlock_hook; unlock_hook = NULL; hook(); }
}
#define spin_lock_irqsave(p, f) do { (void)(p); (f) = 0; lock_enter(); } while (0)
#define spin_unlock_irqrestore(p, f) do { (void)(p); (void)(f); lock_exit(); } while (0)
static u64 ktime_get_ns(void) { current_vfe->reads++; return 1000 + current_vfe->reads; }
static void dev_err_ratelimited(struct fake_device *dev, const char *fmt, ...)
{ (void)dev; (void)fmt; current_vfe->errors++; }
#define dev_dbg(...) do {} while (0)
static void vb2_buffer_done(struct vb2_buffer *vb, int state)
{
 struct camss_buffer *b = container_of(vb, struct camss_buffer, vb.vb2_buf);
 CHECK(state == VB2_BUF_STATE_DONE, "RETURN_STATE");
 CHECK(current_vfe->ack[current_vfe->ack_line[b->id]] >= current_vfe->earliest_ack[b->id], "ACK_BEFORE_RETURN");
 CHECK(b->done == 0, "DOUBLE_RETURN");
 b->done++; current_vfe->returns++;
}
static void reg_clear(struct vfe_device *v, enum vfe_line_id id)
{ CHECK(lock_depth == 1, "ACK_LOCK"); v->ack[id]++; }
static void reg_write(struct vfe_device *v, enum vfe_line_id id)
{ CHECK(lock_depth == 1, "WRITE_LOCK"); v->writes[id]++; }
static void isr_read(struct vfe_device *v, u32 *s0, u32 *s1)
{ *s0 = v->status0; *s1 = v->status1; }
static void violation_read(struct vfe_device *v) { (void)v; }
static void ping_write(struct vfe_device *v, u8 wm, u32 addr) { v->ping[wm] = addr; }
static void pong_write(struct vfe_device *v, u8 wm, u32 addr) { v->pong[wm] = addr; }
static void reload_write(struct vfe_device *v, u8 wm) { v->reload[wm]++; }
static void period_write(struct vfe_device *v, u8 wm, u8 period) { (void)v; (void)wm; (void)period; }
static void pattern_write(struct vfe_device *v, u8 wm, u32 pattern) { v->pattern[wm] = pattern; }
static int active_read(struct vfe_device *v, u8 wm) { return v->active[wm]; }
static void halt_clear(struct vfe_device *v) { (void)v; }
static const struct vfe_hw_ops hw = { reg_clear, reg_write, isr_read, violation_read };
static const struct vfe_subdev_resources resources = { &hw, VFE_LINE_NUM_MAX, false };
static const struct vfe_subdev_resources sof_resources = { &hw, VFE_LINE_NUM_MAX, true };
static const struct vfe_hw_ops_gen1 gen1_hw = {
 ping_write, pong_write, reload_write, period_write, pattern_write, active_read, halt_clear
};
