#include "shim.h"
#define VFE_FRAME_DROP_UPDATES 2

#define VFE_0_IRQ_MASK_0_IMAGE_MASTER_n_PING_PONG(n)	BIT((n) + 8)
#define VFE_0_IRQ_STATUS_0		0x06c
#define VFE_0_IRQ_STATUS_0_CAMIF_SOF			BIT(0)
#define VFE_0_IRQ_STATUS_0_RDIn_REG_UPDATE(n)		BIT((n) + 5)
#define VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(n)		\
	((n) == VFE_LINE_PIX ? BIT(4) : VFE_0_IRQ_STATUS_0_RDIn_REG_UPDATE(n))
#define VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(n)	BIT((n) + 8)
#define VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(n)	BIT((n) + 25)
#define VFE_0_IRQ_STATUS_0_RESET_ACK			BIT(31)
#define VFE_0_IRQ_STATUS_1		0x070
#define VFE_0_IRQ_STATUS_1_VIOLATION			BIT(7)
#define VFE_0_IRQ_STATUS_1_BUS_BDG_HALT_ACK		BIT(8)
#define VFE_0_IRQ_STATUS_1_RDIn_SOF(n)			BIT((n) + 29)

struct camss_buffer *vfe_buf_get_pending(struct vfe_output *output)
{
	struct camss_buffer *buffer = NULL;

	if (!list_empty(&output->pending_bufs)) {
		buffer = list_first_entry(&output->pending_bufs,
					  struct camss_buffer,
					  queue);
		list_del(&buffer->queue);
	}

	return buffer;
}

void vfe_buf_add_pending(struct vfe_output *output,
			 struct camss_buffer *buffer)
{
	INIT_LIST_HEAD(&buffer->queue);
	list_add_tail(&buffer->queue, &output->pending_bufs);
}

void vfe_isr_comp_done(struct vfe_device *vfe, u8 comp)
{
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(vfe->wm_output_map); i++)
		if (vfe->wm_output_map[i] == VFE_LINE_PIX) {
			vfe->isr_ops.wm_done(vfe, i);
			break;
		}
}

void vfe_isr_reset_ack(struct vfe_device *vfe)
{
	complete(&vfe->reset_complete);
}

static void vfe_output_init_addrs(struct vfe_device *vfe,
				  struct vfe_output *output, u8 sync,
				  struct vfe_line *line)
{
	u32 ping_addr;
	u32 pong_addr;
	unsigned int i;

	output->gen1.active_buf = 0;

	for (i = 0; i < output->wm_num; i++) {
		if (output->buf[0])
			ping_addr = output->buf[0]->addr[i];
		else
			ping_addr = 0;

		if (output->buf[1])
			pong_addr = output->buf[1]->addr[i];
		else
			pong_addr = ping_addr;

		vfe->ops_gen1->wm_set_ping_addr(vfe, output->wm_idx[i], ping_addr);
		vfe->ops_gen1->wm_set_pong_addr(vfe, output->wm_idx[i], pong_addr);
		if (sync)
			vfe->ops_gen1->bus_reload_wm(vfe, output->wm_idx[i]);
	}
}

static void vfe_output_frame_drop(struct vfe_device *vfe,
				  struct vfe_output *output,
				  u32 drop_pattern)
{
	u8 drop_period;
	unsigned int i;

	/* We need to toggle update period to be valid on next frame */
	output->drop_update_idx++;
	output->drop_update_idx %= VFE_FRAME_DROP_UPDATES;
	drop_period = VFE_FRAME_DROP_VAL + output->drop_update_idx;

	for (i = 0; i < output->wm_num; i++) {
		vfe->ops_gen1->wm_set_framedrop_period(vfe, output->wm_idx[i], drop_period);
		vfe->ops_gen1->wm_set_framedrop_pattern(vfe, output->wm_idx[i], drop_pattern);
	}

	vfe->res->hw_ops->reg_update(vfe, container_of(output, struct vfe_line, output)->id);
}

static void vfe_output_update_ping_addr(struct vfe_device *vfe,
					struct vfe_output *output, u8 sync,
					struct vfe_line *line)
{
	u32 addr;
	unsigned int i;

	for (i = 0; i < output->wm_num; i++) {
		if (output->buf[0])
			addr = output->buf[0]->addr[i];
		else
			addr = 0;

		vfe->ops_gen1->wm_set_ping_addr(vfe, output->wm_idx[i], addr);
		if (sync)
			vfe->ops_gen1->bus_reload_wm(vfe, output->wm_idx[i]);
	}
}

static void vfe_output_update_pong_addr(struct vfe_device *vfe,
					struct vfe_output *output, u8 sync,
					struct vfe_line *line)
{
	u32 addr;
	unsigned int i;

	for (i = 0; i < output->wm_num; i++) {
		if (output->buf[1])
			addr = output->buf[1]->addr[i];
		else
			addr = 0;

		vfe->ops_gen1->wm_set_pong_addr(vfe, output->wm_idx[i], addr);
		if (sync)
			vfe->ops_gen1->bus_reload_wm(vfe, output->wm_idx[i]);
	}
}

static void vfe_buf_update_wm_on_next(struct vfe_device *vfe,
				      struct vfe_output *output)
{
	switch (output->state) {
	case VFE_OUTPUT_CONTINUOUS:
		vfe_output_frame_drop(vfe, output, 3);
		break;
	case VFE_OUTPUT_SINGLE:
	default:
		dev_err_ratelimited(vfe->camss->dev,
				    "Next buf in wrong state! %d\n",
				    output->state);
		break;
	}
}

static void vfe_buf_update_wm_on_last(struct vfe_device *vfe,
				      struct vfe_output *output)
{
	switch (output->state) {
	case VFE_OUTPUT_CONTINUOUS:
		output->state = VFE_OUTPUT_SINGLE;
		vfe_output_frame_drop(vfe, output, 1);
		break;
	case VFE_OUTPUT_SINGLE:
		output->state = VFE_OUTPUT_STOPPING;
		vfe_output_frame_drop(vfe, output, 0);
		break;
	default:
		dev_err_ratelimited(vfe->camss->dev,
				    "Last buff in wrong state! %d\n",
				    output->state);
		break;
	}
}

static void vfe_buf_update_wm_on_new(struct vfe_device *vfe,
				     struct vfe_output *output,
				     struct camss_buffer *new_buf,
				     struct vfe_line *line)
{
	int inactive_idx;

	switch (output->state) {
	case VFE_OUTPUT_SINGLE:
		inactive_idx = !output->gen1.active_buf;

		if (!output->buf[inactive_idx]) {
			output->buf[inactive_idx] = new_buf;

			if (inactive_idx)
				vfe_output_update_pong_addr(vfe, output, 0, line);
			else
				vfe_output_update_ping_addr(vfe, output, 0, line);

			vfe_output_frame_drop(vfe, output, 3);
			output->state = VFE_OUTPUT_CONTINUOUS;
		} else {
			vfe_buf_add_pending(output, new_buf);
			dev_err_ratelimited(vfe->camss->dev,
					    "Inactive buffer is busy\n");
		}
		break;

	case VFE_OUTPUT_IDLE:
		if (!output->buf[0]) {
			output->buf[0] = new_buf;

			vfe_output_init_addrs(vfe, output, 1, line);
			vfe_output_frame_drop(vfe, output, 1);

			output->state = VFE_OUTPUT_SINGLE;
		} else {
			vfe_buf_add_pending(output, new_buf);
			dev_err_ratelimited(vfe->camss->dev,
					    "Output idle with buffer set!\n");
		}
		break;

	case VFE_OUTPUT_CONTINUOUS:
	default:
		vfe_buf_add_pending(output, new_buf);
		break;
	}
}

static void vfe_isr_halt_ack(struct vfe_device *vfe)
{
	complete(&vfe->halt_complete);
	vfe->ops_gen1->halt_clear(vfe);
}

static void vfe_isr_sof(struct vfe_device *vfe, enum vfe_line_id line_id)
{
	struct vfe_output *output;
	unsigned long flags;

	spin_lock_irqsave(&vfe->output_lock, flags);
	output = &vfe->line[line_id].output;
	if (output->gen1.wait_sof) {
		output->gen1.wait_sof = 0;
		complete(&output->sof);
	}
	spin_unlock_irqrestore(&vfe->output_lock, flags);
}

static u32 vfe_isr_reg_update(struct vfe_device *vfe, enum vfe_line_id line_id)
{
	struct vfe_output *output;
	struct vfe_line *line = &vfe->line[line_id];
	unsigned long flags;
	u32 stale_wm = 0;
	unsigned int i;

	spin_lock_irqsave(&vfe->output_lock, flags);
	vfe->res->hw_ops->reg_update_clear(vfe, line_id);

	output = &line->output;

	if (output->wait_reg_update) {
		output->wait_reg_update = 0;
		complete(&output->reg_update);
		spin_unlock_irqrestore(&vfe->output_lock, flags);
		return 0;
	}

	if (output->state == VFE_OUTPUT_STOPPING) {
		/*
		 * A WM completion in this IRQ snapshot still refers to the old
		 * buffers. Remember its indices before returning the last buffer
		 * or installing buffers received while stopping.
		 */
		for (i = 0; i < output->wm_num; i++)
			stale_wm |= BIT(output->wm_idx[i]);

		/* Release last buffer when hw is idle */
		if (output->last_buffer) {
			vb2_buffer_done(&output->last_buffer->vb.vb2_buf,
					VB2_BUF_STATE_DONE);
			output->last_buffer = NULL;
		}
		output->state = VFE_OUTPUT_IDLE;

		/* Buffers received in stopping state are queued in */
		/* dma pending queue, start next capture here */

		output->buf[0] = vfe_buf_get_pending(output);
		output->buf[1] = vfe_buf_get_pending(output);

		if (!output->buf[0] && output->buf[1]) {
			output->buf[0] = output->buf[1];
			output->buf[1] = NULL;
		}

		if (output->buf[0])
			output->state = VFE_OUTPUT_SINGLE;

		if (output->buf[1])
			output->state = VFE_OUTPUT_CONTINUOUS;

		switch (output->state) {
		case VFE_OUTPUT_SINGLE:
			vfe_output_frame_drop(vfe, output, 2);
			break;
		case VFE_OUTPUT_CONTINUOUS:
			vfe_output_frame_drop(vfe, output, 3);
			break;
		default:
			vfe_output_frame_drop(vfe, output, 0);
			break;
		}

		vfe_output_init_addrs(vfe, output, 1, &vfe->line[line_id]);
	}

	spin_unlock_irqrestore(&vfe->output_lock, flags);

	return stale_wm;
}

static void vfe_isr_wm_done(struct vfe_device *vfe, u8 wm)
{
	struct camss_buffer *ready_buf;
	struct vfe_output *output;
	dma_addr_t *new_addr;
	unsigned long flags;
	u32 active_index;
	u64 ts = ktime_get_ns();
	unsigned int i;

	active_index = vfe->ops_gen1->wm_get_ping_pong_status(vfe, wm);

	spin_lock_irqsave(&vfe->output_lock, flags);

	if (vfe->wm_output_map[wm] == VFE_LINE_NONE) {
		dev_err_ratelimited(vfe->camss->dev,
				    "Received wm done for unmapped index\n");
		goto out_unlock;
	}
	output = &vfe->line[vfe->wm_output_map[wm]].output;

	if (output->gen1.active_buf == active_index && 0) {
		dev_err_ratelimited(vfe->camss->dev,
				    "Active buffer mismatch!\n");
		goto out_unlock;
	}
	output->gen1.active_buf = active_index;

	ready_buf = output->buf[!active_index];
	if (!ready_buf) {
		dev_err_ratelimited(vfe->camss->dev,
				    "Missing ready buf %d %d!\n",
				    !active_index, output->state);
		goto out_unlock;
	}

	ready_buf->vb.vb2_buf.timestamp = ts;
	ready_buf->vb.sequence = output->sequence++;

	/* Get next buffer */
	output->buf[!active_index] = vfe_buf_get_pending(output);
	if (!output->buf[!active_index]) {
		/* No next buffer - set same address */
		new_addr = ready_buf->addr;
		vfe_buf_update_wm_on_last(vfe, output);
	} else {
		new_addr = output->buf[!active_index]->addr;
		vfe_buf_update_wm_on_next(vfe, output);
	}

	if (active_index)
		for (i = 0; i < output->wm_num; i++)
			vfe->ops_gen1->wm_set_ping_addr(vfe, output->wm_idx[i], new_addr[i]);
	else
		for (i = 0; i < output->wm_num; i++)
			vfe->ops_gen1->wm_set_pong_addr(vfe, output->wm_idx[i], new_addr[i]);

	spin_unlock_irqrestore(&vfe->output_lock, flags);

	if (output->state == VFE_OUTPUT_STOPPING)
		output->last_buffer = ready_buf;
	else
		vb2_buffer_done(&ready_buf->vb.vb2_buf, VB2_BUF_STATE_DONE);

	return;

out_unlock:
	spin_unlock_irqrestore(&vfe->output_lock, flags);
}

const struct vfe_isr_ops vfe_isr_ops_gen1 = {
	.reset_ack = vfe_isr_reset_ack,
	.halt_ack = vfe_isr_halt_ack,
	.reg_update = vfe_isr_reg_update,
	.sof = vfe_isr_sof,
	.comp_done = vfe_isr_comp_done,
	.wm_done = vfe_isr_wm_done,
};

#define vfe_isr_reg_update vfe17x_isr_reg_update

static u32 vfe_isr_reg_update(struct vfe_device *vfe, enum vfe_line_id line_id)
{
	struct vfe_output *output;
	unsigned long flags;

	spin_lock_irqsave(&vfe->output_lock, flags);
	vfe->res->hw_ops->reg_update_clear(vfe, line_id);

	output = &vfe->line[line_id].output;

	if (output->wait_reg_update) {
		output->wait_reg_update = 0;
		complete(&output->reg_update);
	}

	spin_unlock_irqrestore(&vfe->output_lock, flags);

	return 0;
}

#undef vfe_isr_reg_update

static irqreturn_t vfe_isr(int irq, void *dev)
{
	struct vfe_device *vfe = dev;
	u32 value0, value1;
	u32 stale_wm = 0;
	bool stale_pix = false;
	int i, j;

	vfe->res->hw_ops->isr_read(vfe, &value0, &value1);

	dev_dbg(vfe->camss->dev, "VFE: status0 = 0x%08x, status1 = 0x%08x\n",
		value0, value1);

	if (value0 & VFE_0_IRQ_STATUS_0_RESET_ACK)
		vfe->isr_ops.reset_ack(vfe);

	if (value1 & VFE_0_IRQ_STATUS_1_VIOLATION)
		vfe->res->hw_ops->violation_read(vfe);

	if (value1 & VFE_0_IRQ_STATUS_1_BUS_BDG_HALT_ACK)
		vfe->isr_ops.halt_ack(vfe);

	for (i = VFE_LINE_RDI0; i < vfe->res->line_num; i++)
		if (value0 & VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(i)) {
			u32 stale = vfe->isr_ops.reg_update(vfe, i);

			stale_wm |= stale;
			if (i == VFE_LINE_PIX && stale)
				stale_pix = true;
		}

	if (value0 & VFE_0_IRQ_STATUS_0_CAMIF_SOF)
		vfe->isr_ops.sof(vfe, VFE_LINE_PIX);

	for (i = VFE_LINE_RDI0; i <= VFE_LINE_RDI2; i++)
		if (value1 & VFE_0_IRQ_STATUS_1_RDIn_SOF(i))
			vfe->isr_ops.sof(vfe, i);

	for (i = 0; i < MSM_VFE_COMPOSITE_IRQ_NUM; i++)
		if (value0 & VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(i)) {
			if (!stale_pix)
				vfe->isr_ops.comp_done(vfe, i);
			for (j = 0; j < ARRAY_SIZE(vfe->wm_output_map); j++)
				if (vfe->wm_output_map[j] == VFE_LINE_PIX)
					value0 &= ~VFE_0_IRQ_MASK_0_IMAGE_MASTER_n_PING_PONG(j);
		}

	if (value0 & (BIT(4) | BIT(5) | BIT(6) | BIT(7)))
		value0 &= ~(0x7fU << 8);
	for (i = 0; i < MSM_VFE_IMAGE_MASTERS_NUM; i++)
		if ((value0 & VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(i)) &&
		    !(stale_wm & BIT(i)))
			vfe->isr_ops.wm_done(vfe, i);

	return IRQ_HANDLED;
}
/* SPDX-License-Identifier: GPL-2.0-only */
static void init_vfe(struct vfe_device *v, unsigned int phase)
{
 static struct camss camss;
 memset(v, 0, sizeof(*v)); memset(buffers, 0, sizeof(buffers));
 lock_depth = 0; unlock_hook = NULL; current_vfe = v;
 v->camss = &camss; v->res = &resources; v->ops_gen1 = &gen1_hw;
 v->isr_ops = vfe_isr_ops_gen1;
 for (unsigned int i = 0; i < ARRAY_SIZE(v->line); i++) {
  v->line[i].id = (enum vfe_line_id)i;
  INIT_LIST_HEAD(&v->line[i].output.pending_bufs);
  v->line[i].output.state = VFE_OUTPUT_IDLE;
  v->line[i].output.sequence = 7;
 }
 for (unsigned int i = 0; i < ARRAY_SIZE(v->wm_output_map); i++) {
  v->wm_output_map[i] = VFE_LINE_NONE; v->active[i] = phase;
 }
 for (unsigned int i = 0; i < ARRAY_SIZE(buffers); i++) {
  buffers[i].id = i;
  for (unsigned int plane = 0; plane < 3; plane++) buffers[i].addr[plane] = 0x1000 + i * 0x100 + plane * 0x20;
 }
}
static void bind_line(struct vfe_device *v, enum vfe_line_id id, unsigned int first, unsigned int planes)
{
 struct vfe_output *o = &v->line[id].output;
 o->wm_num = planes;
 for (unsigned int i = 0; i < planes; i++) { o->wm_idx[i] = first + i; v->wm_output_map[first + i] = id; }
}
static void queue(struct vfe_device *v, enum vfe_line_id id, unsigned int buf)
{
 unsigned long flags;
 spin_lock_irqsave(&v->output_lock, flags);
 vfe_buf_update_wm_on_new(v, &v->line[id].output, &buffers[buf], &v->line[id]);
 spin_unlock_irqrestore(&v->output_lock, flags);
}
static void stopping(struct vfe_device *v, enum vfe_line_id id, unsigned int old, unsigned int pending)
{
 struct vfe_output *o = &v->line[id].output;
 o->state = VFE_OUTPUT_STOPPING; o->last_buffer = &buffers[old];
 buffers[old].vb.vb2_buf.timestamp = 111;
 v->earliest_ack[old] = 1; v->ack_line[old] = id;
 for (unsigned int i = 0; i < pending; i++) queue(v, id, old + 1 + i);
}
static u32 wm_bits(struct vfe_output *o)
{
 u32 result = 0;
 for (unsigned int i = 0; i < o->wm_num; i++) result |= VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(o->wm_idx[i]);
 return result;
}
static void dispatch(struct vfe_device *v, u32 status)
{
 v->status0 = status; v->status1 = 0;
 CHECK(vfe_isr(95, v) == IRQ_HANDLED, "IRQ_RETURN");
 CHECK(lock_depth == 0, "IRQ_LOCK_LEAK");
}
static void new_untouched(unsigned int id)
{
 CHECK(buffers[id].vb.vb2_buf.timestamp == 0 && buffers[id].vb.sequence == 0 && buffers[id].done == 0,
       "NEW_BUFFER_TOUCHED");
}
static void restart_addresses(struct vfe_device *v, enum vfe_line_id id, unsigned int pending, unsigned int first)
{
 struct vfe_output *o = &v->line[id].output;
 CHECK(o->state == (pending == 0 ? VFE_OUTPUT_IDLE : pending == 1 ? VFE_OUTPUT_SINGLE : VFE_OUTPUT_CONTINUOUS), "RESTART_STATE");
 CHECK(o->buf[0] == (pending ? &buffers[first] : NULL), "RESTART_PING_OWNER");
 CHECK(o->buf[1] == (pending > 1 ? &buffers[first + 1] : NULL), "RESTART_PONG_OWNER");
 for (unsigned int i = 0; i < o->wm_num; i++) {
  unsigned int wm = o->wm_idx[i];
  CHECK(v->ping[wm] == (pending ? buffers[first].addr[i] : 0), "RESTART_PING_ADDR");
  CHECK(v->pong[wm] == (pending > 1 ? buffers[first + 1].addr[i] : pending ? buffers[first].addr[i] : 0), "RESTART_PONG_ADDR");
  CHECK(v->pattern[wm] == (pending == 0 ? 0 : pending == 1 ? 2 : 3), "RESTART_DROP_PATTERN");
 }
}
static void drain_case(unsigned int pending, unsigned int phase, bool pix, bool composite, bool masters)
{
 struct vfe_device v; enum vfe_line_id id = pix ? VFE_LINE_PIX : VFE_LINE_RDI0;
 init_vfe(&v, phase); bind_line(&v, id, pix ? 4 : 0, pix ? 3 : 1);
 stopping(&v, id, 0, pending);
 struct vfe_output *o = &v.line[id].output;
 u32 saved = VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(id);
 if (masters) saved |= wm_bits(o);
 if (composite) saved |= VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0);
 dispatch(&v, saved);
 CHECK(buffers[0].done == 1, "FINAL_RETURN");
 for (unsigned int i = 0; i < pending; i++) new_untouched(1 + i);
 CHECK(v.returns == 1, "UNEXPECTED_BUFFER_RETURN");
 CHECK(v.errors == 0, "STALE_DIAGNOSTIC");
 CHECK(v.reads == 0, "STALE_WM_DISPATCHED");
 CHECK(o->last_buffer == NULL, "LAST_BUFFER_RETAINED");
 CHECK(o->sequence == 7, "STALE_SEQUENCE_INCREMENT");
 restart_addresses(&v, id, pending, 1);
 if (!pending) return;
 /* A later frame still completes normally; suppression cannot be sticky. */
 for (unsigned int i = 0; i < o->wm_num; i++) v.active[o->wm_idx[i]] = 1;
 u32 fresh = wm_bits(o) | (pix ? VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0) : 0);
 if (pending == 1) v.earliest_ack[1] = v.ack[id] + 1;
 v.ack_line[1] = id;
 dispatch(&v, fresh);
 CHECK(buffers[1].vb.vb2_buf.timestamp != 0, "FRESH_FRAME_NOT_CAPTURED");
 if (pending == 1) CHECK(buffers[1].done == 0 && o->last_buffer == &buffers[1], "FRESH_FRAME_RETURNED_BEFORE_ACK");
 else {
  CHECK(buffers[1].done == 1, "CONTINUOUS_FRAME_NOT_RETURNED");
  for (unsigned int i = 0; i < o->wm_num; i++) v.active[o->wm_idx[i]] = 0;
  v.earliest_ack[2] = v.ack[id] + 1; v.ack_line[2] = id;
  dispatch(&v, fresh);
  CHECK(buffers[2].done == 0 && o->last_buffer == &buffers[2], "SECOND_FRAME_RETURNED_BEFORE_ACK");
 }
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(id));
 CHECK(v.returns == pending + 1 && v.errors == 0, "FRESH_DRAIN_COMPLETION");
 CHECK(o->state == VFE_OUTPUT_IDLE, "FRESH_DRAIN_STATE");
}
static void queue_after_unlock(void) { queue(current_vfe, VFE_LINE_RDI0, 1); }
static void queue_after_ack(void)
{
 struct vfe_device v; init_vfe(&v, 1); bind_line(&v, VFE_LINE_RDI0, 0, 1); stopping(&v, VFE_LINE_RDI0, 0, 0);
 unlock_hook = queue_after_unlock;
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(VFE_LINE_RDI0) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 new_untouched(1); CHECK(v.errors == 0 && v.reads == 0, "ACK_UNLOCK_STALE_DISPATCH");
 CHECK(v.line[0].output.state == VFE_OUTPUT_SINGLE && v.line[0].output.buf[0] == &buffers[1], "ACK_UNLOCK_REQUEUE");
}
static void old_ack(void)
{
 struct vfe_device v; init_vfe(&v, 1); bind_line(&v, VFE_LINE_RDI0, 0, 1);
 struct vfe_output *o = &v.line[0].output;
 o->state = VFE_OUTPUT_SINGLE; o->buf[0] = &buffers[0];
 v.earliest_ack[0] = 2;
 u32 saved = VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0);
 dispatch(&v, saved);
 CHECK(buffers[0].done == 0 && o->state == VFE_OUTPUT_STOPPING && o->last_buffer == &buffers[0], "OLD_ACK_PREMATURE_RETURN");
 dispatch(&v, saved);
 CHECK(buffers[0].done == 1 && v.errors == 0, "NEXT_ACK_RETURN");
}
static void continuous(bool pix)
{
 struct vfe_device v; enum vfe_line_id id = pix ? VFE_LINE_PIX : VFE_LINE_RDI0;
 init_vfe(&v, 1); bind_line(&v, id, pix ? 4 : 0, pix ? 3 : 1);
 struct vfe_output *o = &v.line[id].output;
 o->state = VFE_OUTPUT_CONTINUOUS; o->buf[0] = &buffers[0]; o->buf[1] = &buffers[1];
 queue(&v, id, 2);
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(id) | wm_bits(o) | (pix ? VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0) : 0));
 CHECK(buffers[0].done == 1 && v.returns == 1 && v.errors == 0 && v.reads == 1, "NORMAL_COMPLETION_LOST");
 CHECK(o->state == VFE_OUTPUT_CONTINUOUS && o->buf[0] == &buffers[2], "NORMAL_REPLACEMENT");
}
static void unexpected(bool idle, bool unmapped)
{
 struct vfe_device v; init_vfe(&v, 1);
 if (!unmapped) {
  bind_line(&v, VFE_LINE_RDI0, 0, 1);
  v.line[0].output.state = idle ? VFE_OUTPUT_IDLE : VFE_OUTPUT_CONTINUOUS;
 }
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 CHECK(v.errors == 1 && v.returns == 0, "UNEXPLAINED_DIAGNOSTIC_SUPPRESSED");
}
static void late_unexpected(void)
{
 struct vfe_device v; init_vfe(&v, 0); bind_line(&v, VFE_LINE_RDI0, 0, 1); stopping(&v, VFE_LINE_RDI0, 0, 0);
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0));
 CHECK(v.errors == 0 && buffers[0].done == 1, "REG_ONLY_DRAIN");
 dispatch(&v, VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 CHECK(v.errors == 1, "LATER_IRQ_INCORRECTLY_SUPPRESSED");
}
static void wait_ack(bool gen2)
{
 struct vfe_device v; init_vfe(&v, 0); bind_line(&v, VFE_LINE_RDI0, 0, 1); stopping(&v, VFE_LINE_RDI0, 0, 0);
 struct vfe_output *o = &v.line[0].output; o->wait_reg_update = 1;
 if (gen2) {
#if REG_RETURNS_MASK
  CHECK(vfe17x_isr_reg_update(&v, 0) == 0, "GEN2_MASK_CHANGED");
#else
  vfe17x_isr_reg_update(&v, 0);
#endif
 } else dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0));
 CHECK(o->wait_reg_update == 0 && o->reg_update.done == 1 && o->state == VFE_OUTPUT_STOPPING && buffers[0].done == 0,
       "WAIT_ACK_HANDOFF_CHANGED");
}
static void two_lines(bool unrelated)
{
 struct vfe_device v; init_vfe(&v, 1);
 bind_line(&v, VFE_LINE_RDI0, 0, 1); stopping(&v, VFE_LINE_RDI0, 0, 1);
 bind_line(&v, VFE_LINE_RDI1, 2, 1);
 struct vfe_output *other = &v.line[1].output;
 u32 saved = VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(2);
 if (unrelated) { other->state = VFE_OUTPUT_CONTINUOUS; other->buf[0] = &buffers[3]; other->buf[1] = &buffers[4]; }
 else { stopping(&v, VFE_LINE_RDI1, 3, 1); saved |= VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(1); }
 dispatch(&v, saved);
 new_untouched(1); CHECK(v.errors == 0, "MULTILINE_DIAGNOSTIC");
 if (unrelated) CHECK(buffers[3].done == 1 && v.returns == 2 && v.reads == 1, "UNRELATED_COMPLETION_DROPPED");
 else { new_untouched(4); CHECK(buffers[3].done == 1 && v.returns == 2 && v.reads == 0, "MULTILINE_MASK_NOT_ACCUMULATED"); }
}
static void missing_last(bool pix)
{
 struct vfe_device v; enum vfe_line_id id = pix ? VFE_LINE_PIX : VFE_LINE_RDI0;
 init_vfe(&v, 1); bind_line(&v, id, pix ? 4 : 0, pix ? 3 : 1);
 struct vfe_output *o = &v.line[id].output; o->state = VFE_OUTPUT_STOPPING;
 queue(&v, id, 1); queue(&v, id, 2);
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(id) | wm_bits(o) | (pix ? VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0) : 0));
 new_untouched(1); new_untouched(2);
 CHECK(v.returns == 0 && v.errors == 0 && v.reads == 0, "NO_LAST_HANDOFF");
 restart_addresses(&v, id, 2, 1);
}
static void reassign_after_unlock(void)
{
 struct vfe_device *v = current_vfe;
 v->wm_output_map[0] = VFE_LINE_NONE; v->line[0].output.state = VFE_OUTPUT_OFF;
 bind_line(v, VFE_LINE_RDI1, 0, 1);
 struct vfe_output *o = &v->line[1].output;
 o->state = VFE_OUTPUT_CONTINUOUS; o->buf[0] = &buffers[3]; o->buf[1] = &buffers[4];
}
static void reassigned_wm(void)
{
 struct vfe_device v; init_vfe(&v, 1); bind_line(&v, VFE_LINE_RDI0, 0, 1); stopping(&v, VFE_LINE_RDI0, 0, 0);
 unlock_hook = reassign_after_unlock;
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 new_untouched(3); new_untouched(4);
 CHECK(v.errors == 0 && v.reads == 0 && buffers[0].done == 1, "OLD_IRQ_REASSIGNED_WM");
 dispatch(&v, VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 CHECK(buffers[3].done == 1 && v.returns == 2 && v.errors == 0, "REASSIGNED_FRESH_COMPLETION");
}
static void pix_and_unrelated(void)
{
 struct vfe_device v; init_vfe(&v, 1); bind_line(&v, VFE_LINE_PIX, 4, 3); stopping(&v, VFE_LINE_PIX, 0, 1);
 bind_line(&v, VFE_LINE_RDI0, 0, 1);
 struct vfe_output *other = &v.line[0].output;
 other->state = VFE_OUTPUT_CONTINUOUS; other->buf[0] = &buffers[3]; other->buf[1] = &buffers[4];
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(VFE_LINE_PIX) | VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0) |
              wm_bits(&v.line[VFE_LINE_PIX].output) | VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 new_untouched(1);
 CHECK(buffers[0].done == 1 && buffers[3].done == 1 && v.returns == 2 && v.reads == 1 && v.errors == 0,
       "PIX_MASK_DROPPED_UNRELATED_RDI");
}
int main(int argc, char **argv)
{
 CHECK(argc == 2, "CASE_ARGUMENT"); const char *name = argv[1];
 if (!strcmp(name, "empty0")) drain_case(0, 0, false, false, true);
 else if (!strcmp(name, "empty1")) drain_case(0, 1, false, false, true);
 else if (!strcmp(name, "pending1_0")) drain_case(1, 0, false, false, true);
 else if (!strcmp(name, "pending1_1")) drain_case(1, 1, false, false, true);
 else if (!strcmp(name, "pending2_0")) drain_case(2, 0, false, false, true);
 else if (!strcmp(name, "pending2_1")) drain_case(2, 1, false, false, true);
 else if (!strcmp(name, "pix_empty")) drain_case(0, 0, true, true, true);
 else if (!strcmp(name, "pix_pending1")) drain_case(1, 1, true, true, true);
 else if (!strcmp(name, "pix_pending2")) drain_case(2, 0, true, true, true);
 else if (!strcmp(name, "pix_comp_only")) drain_case(2, 1, true, true, false);
 else if (!strcmp(name, "pix_wm_only")) drain_case(2, 1, true, false, true);
 else if (!strcmp(name, "reg_only")) drain_case(1, 0, false, false, false);
 else if (!strcmp(name, "queue_after_ack")) queue_after_ack();
 else if (!strcmp(name, "old_ack")) old_ack();
 else if (!strcmp(name, "continuous")) continuous(false);
 else if (!strcmp(name, "pix_continuous")) continuous(true);
 else if (!strcmp(name, "missing_active")) unexpected(false, false);
 else if (!strcmp(name, "unexpected_idle")) unexpected(true, false);
 else if (!strcmp(name, "unmapped")) unexpected(false, true);
 else if (!strcmp(name, "late_unexpected")) late_unexpected();
 else if (!strcmp(name, "wait_ack")) wait_ack(false);
 else if (!strcmp(name, "gen2_wait_ack")) wait_ack(true);
 else if (!strcmp(name, "two_drains")) two_lines(false);
 else if (!strcmp(name, "unrelated_active")) two_lines(true);
 else if (!strcmp(name, "no_last_pending")) missing_last(false);
 else if (!strcmp(name, "pix_no_last")) missing_last(true);
 else if (!strcmp(name, "reassigned_wm")) reassigned_wm();
 else if (!strcmp(name, "pix_unrelated_active")) pix_and_unrelated();
 else die("UNKNOWN_CASE");
 printf("PASS:%s\n", name); return 0;
}
