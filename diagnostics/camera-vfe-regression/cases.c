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
static void dispatch_status(struct vfe_device *v, u32 status0, u32 status1)
{
 v->status0 = status0; v->status1 = status1;
 CHECK(vfe_isr(95, v) == IRQ_HANDLED, "IRQ_RETURN");
 CHECK(lock_depth == 0, "IRQ_LOCK_LEAK");
}
static void dispatch(struct vfe_device *v, u32 status)
{
 dispatch_status(v, status, 0);
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
static void check_stopping_handoff(void)
{
 struct vfe_output *o = &current_vfe->line[VFE_LINE_RDI0].output;
 CHECK(o->state == VFE_OUTPUT_STOPPING && o->last_buffer == &buffers[0], "STOPPING_OWNER_AT_UNLOCK");
}
static void stopping_handoff(void)
{
 struct vfe_device v; init_vfe(&v, 1); bind_line(&v, VFE_LINE_RDI0, 0, 1);
 queue(&v, VFE_LINE_RDI0, 0);
 v.earliest_ack[0] = 1;
 unlock_hook = check_stopping_handoff;
 dispatch(&v, VFE_0_IRQ_STATUS_0_IMAGE_MASTER_n_PING_PONG(0));
 CHECK(v.returns == 0, "STOPPING_EARLY_RETURN");
 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(0));
 CHECK(buffers[0].done == 1, "STOPPING_HANDOFF_RETURN");
}
static void stopping_before_ack(bool pix, unsigned int active)
{
 struct vfe_device v; enum vfe_line_id id = pix ? VFE_LINE_PIX : VFE_LINE_RDI0;
 init_vfe(&v, active); bind_line(&v, id, pix ? 4 : 0, pix ? 3 : 1);
 struct vfe_output *o = &v.line[id].output;
 o->state = VFE_OUTPUT_SINGLE;
 o->buf[!active] = &buffers[0];
 v.earliest_ack[0] = 1; v.ack_line[0] = id;
 u32 done = pix ? VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0) : wm_bits(o);
 dispatch(&v, done);
 CHECK(o->state == VFE_OUTPUT_STOPPING && o->last_buffer == &buffers[0] && o->sequence == 8,
       "STOPPING_FIRST_COMPLETION");

 queue(&v, id, 1); queue(&v, id, 2);
 for (unsigned int i = 0; i < o->wm_num; i++) v.active[o->wm_idx[i]] = !active;
 dispatch(&v, done);
 CHECK(v.errors == 0, "STOPPING_STRAY_DIAGNOSTIC");
 CHECK(o->state == VFE_OUTPUT_STOPPING && o->last_buffer == &buffers[0] && v.returns == 0,
       "STOPPING_STRAY_RETURN");
 CHECK(o->gen1.active_buf == active && o->sequence == 8, "STOPPING_STRAY_PINGPONG");
 CHECK(v.writes[id] == 1, "STOPPING_STRAY_REGISTER_UPDATE");

 dispatch(&v, VFE_0_IRQ_STATUS_0_line_n_REG_UPDATE(id));
 CHECK(buffers[0].done == 1 && o->last_buffer == NULL && v.returns == 1, "STOPPING_LATER_ACK");
 new_untouched(1); new_untouched(2);
 restart_addresses(&v, id, 2, 1);

 for (unsigned int i = 0; i < o->wm_num; i++) v.active[o->wm_idx[i]] = 1;
 dispatch(&v, done);
 CHECK(buffers[1].done == 1 && buffers[1].vb.sequence == 8 && v.errors == 0 && v.returns == 2,
       "STOPPING_FRESH_COMPLETION");
 new_untouched(2);
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
static void rearm_at_sof(bool enabled, bool pix, bool coalesced, bool drain)
{
 struct vfe_device v;
 enum vfe_line_id id = pix ? VFE_LINE_PIX : VFE_LINE_RDI0;
 init_vfe(&v, 1);
 if (enabled) v.res = &sof_resources;
 bind_line(&v, id, pix ? 4 : 0, pix ? 3 : 1);
 struct vfe_output *o = &v.line[id].output;
 o->state = VFE_OUTPUT_CONTINUOUS;
 o->buf[0] = &buffers[0]; o->buf[1] = &buffers[1];
 queue(&v, id, 2);
 u32 completion = pix ? VFE_0_IRQ_STATUS_0_IMAGE_COMPOSITE_DONE_n(0) : wm_bits(o);
 u32 sof = VFE_0_IRQ_STATUS_1_RDIn_SOF(0);
 dispatch_status(&v, completion, coalesced ? sof : 0);
 CHECK(buffers[0].done == 1 && o->buf[0] == &buffers[2], "SOF_REARM_REPLACEMENT");
 CHECK(v.ping[o->wm_idx[0]] == buffers[2].addr[0], "SOF_REARM_ADDRESS");
 if (pix || !enabled) {
  CHECK(v.writes[id] == 1 && v.pattern[o->wm_idx[0]] == 3, "OTHER_OUTPUT_REARM_CHANGED");
  return;
 }
 CHECK(v.writes[id] == 0, "REARMED_BEFORE_RDI_SOF");
 dispatch_status(&v, 0, VFE_0_IRQ_STATUS_1_RDIn_SOF(1));
 CHECK(v.writes[id] == 0, "OTHER_LINE_CONSUMED_REARM");
 if (drain) {
  v.active[0] = 0;
  dispatch(&v, completion);
  CHECK(o->state == VFE_OUTPUT_SINGLE && v.pattern[0] == 1 && buffers[1].done == 1,
        "SOF_REARM_DRAIN_CHANGED");
  dispatch_status(&v, 0, sof);
  CHECK(v.writes[id] == 1 && v.pattern[0] == 1, "DEFERRED_REARM_SURVIVED_DRAIN");
 } else {
  dispatch_status(&v, 0, sof);
  CHECK(v.writes[id] == 1 && v.pattern[0] == 3, "RDI_SOF_DID_NOT_REARM");
  dispatch_status(&v, 0, sof);
  CHECK(v.writes[id] == 1 && v.returns == 1, "RDI_SOF_REARM_REPEATED");
 }
 CHECK(v.errors == 0, "RDI_SOF_DIAGNOSTIC");
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
 else if (!strcmp(name, "stopping_handoff")) stopping_handoff();
 else if (!strcmp(name, "rdi_stopping_phase0")) stopping_before_ack(false, 0);
 else if (!strcmp(name, "rdi_stopping_phase1")) stopping_before_ack(false, 1);
 else if (!strcmp(name, "pix_stopping_phase0")) stopping_before_ack(true, 0);
 else if (!strcmp(name, "pix_stopping_phase1")) stopping_before_ack(true, 1);
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
 else if (!strcmp(name, "rdi_sof_rearm")) rearm_at_sof(true, false, false, false);
 else if (!strcmp(name, "rdi_sof_coalesced")) rearm_at_sof(true, false, true, false);
 else if (!strcmp(name, "rdi_sof_drain")) rearm_at_sof(true, false, false, true);
 else if (!strcmp(name, "rdi_sof_unsupported")) rearm_at_sof(false, false, false, false);
 else if (!strcmp(name, "pix_sof_unchanged")) rearm_at_sof(true, true, false, false);
 else die("UNKNOWN_CASE");
 printf("PASS:%s\n", name); return 0;
}
