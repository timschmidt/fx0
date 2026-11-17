static struct mdp5_kms *get_kms(struct drm_encoder *encoder)
{
	struct msm_drm_private *priv = encoder->dev->dev_private;
	return to_mdp5_kms(to_mdp_kms(priv->kms));
}

static inline uint32_t intf2vblank(struct mdp5_hw_mixer *mixer,
				   struct mdp5_interface *intf)
{
	/*
	 * In case of DSI Command Mode, the Ping Pong's read pointer IRQ
	 * acts as a Vblank signal. The Ping Pong buffer used is bound to
	 * layer mixer.
	 */

	if ((intf->type == INTF_DSI) &&
			(intf->mode == MDP5_INTF_DSI_MODE_COMMAND))
		return MDP5_IRQ_PING_PONG_0_RD_PTR << mixer->pp;

	if (intf->type == INTF_WB)
		return MDP5_IRQ_WB_2_DONE;

	switch (intf->num) {
	case 0:  return MDP5_IRQ_INTF0_VSYNC;
	case 1:  return MDP5_IRQ_INTF1_VSYNC;
	case 2:  return MDP5_IRQ_INTF2_VSYNC;
	case 3:  return MDP5_IRQ_INTF3_VSYNC;
	default: return 0;
	}
}

static bool start_signal_needed(struct mdp5_ctl *ctl,
				struct mdp5_pipeline *pipeline)
{
	struct mdp5_interface *intf = pipeline->intf;

	if (!ctl->encoder_enabled)
		return false;

	switch (intf->type) {
	case INTF_WB:
		return true;
	case INTF_DSI:
		return intf->mode == MDP5_INTF_DSI_MODE_COMMAND;
	default:
		return false;
	}
}

static void send_start_signal(struct mdp5_ctl *ctl)
{
	unsigned long flags;

	spin_lock_irqsave(&ctl->hw_lock, flags);
	ctl_write(ctl, REG_MDP5_CTL_START(ctl->id), 1);
	spin_unlock_irqrestore(&ctl->hw_lock, flags);
}

int mdp5_ctl_set_encoder_state(struct mdp5_ctl *ctl,
			       struct mdp5_pipeline *pipeline,
			       bool enabled)
{
	struct mdp5_interface *intf = pipeline->intf;

	if (WARN_ON(!ctl))
		return -EINVAL;

	ctl->encoder_enabled = enabled;
	DBG("intf_%d: %s", intf->num, str_on_off(enabled));

	if (start_signal_needed(ctl, pipeline)) {
		send_start_signal(ctl);
	}

	return 0;
}

u32 mdp_ctl_flush_mask_encoder(struct mdp5_interface *intf)
{
	if (intf->type == INTF_WB)
		return MDP5_CTL_FLUSH_WB;

	switch (intf->num) {
	case 0: return MDP5_CTL_FLUSH_TIMING_0;
	case 1: return MDP5_CTL_FLUSH_TIMING_1;
	case 2: return MDP5_CTL_FLUSH_TIMING_2;
	case 3: return MDP5_CTL_FLUSH_TIMING_3;
	default: return 0;
	}
}

u32 mdp_ctl_flush_mask_lm(int lm)
{
	switch (lm) {
	case 0:  return MDP5_CTL_FLUSH_LM0;
	case 1:  return MDP5_CTL_FLUSH_LM1;
	case 2:  return MDP5_CTL_FLUSH_LM2;
	case 3:  return MDP5_CTL_FLUSH_LM3;
	case 4:  return MDP5_CTL_FLUSH_LM4;
	case 5:  return MDP5_CTL_FLUSH_LM5;
	default: return 0;
	}
}

static u32 fix_sw_flush(struct mdp5_ctl *ctl, struct mdp5_pipeline *pipeline,
			u32 flush_mask)
{
	struct mdp5_ctl_manager *ctl_mgr = ctl->ctlm;
	u32 sw_mask = 0;
#define BIT_NEEDS_SW_FIX(bit) \
	(!(ctl_mgr->flush_hw_mask & bit) && (flush_mask & bit))

	/* for some targets, cursor bit is the same as LM bit */
	if (BIT_NEEDS_SW_FIX(MDP5_CTL_FLUSH_CURSOR_0))
		sw_mask |= mdp_ctl_flush_mask_lm(pipeline->mixer->lm);

	return sw_mask;
}

static void fix_for_single_flush(struct mdp5_ctl *ctl, u32 *flush_mask,
		u32 *flush_id)
{
	struct mdp5_ctl_manager *ctl_mgr = ctl->ctlm;

	if (ctl->pair) {
		DBG("CTL %d FLUSH pending mask %x", ctl->id, *flush_mask);
		ctl->flush_pending = true;
		ctl_mgr->single_flush_pending_mask |= (*flush_mask);
		*flush_mask = 0;

		if (ctl->pair->flush_pending) {
			*flush_id = min_t(u32, ctl->id, ctl->pair->id);
			*flush_mask = ctl_mgr->single_flush_pending_mask;

			ctl->flush_pending = false;
			ctl->pair->flush_pending = false;
			ctl_mgr->single_flush_pending_mask = 0;

			DBG("Single FLUSH mask %x,ID %d", *flush_mask,
				*flush_id);
		}
	}
}

u32 mdp5_ctl_commit(struct mdp5_ctl *ctl,
		    struct mdp5_pipeline *pipeline,
		    u32 flush_mask, bool start)
{
	struct mdp5_ctl_manager *ctl_mgr = ctl->ctlm;
	unsigned long flags;
	u32 flush_id = ctl->id;
	u32 curr_ctl_flush_mask;

	VERB("flush_mask=%x, trigger=%x", flush_mask, ctl->pending_ctl_trigger);

	if (ctl->pending_ctl_trigger & flush_mask) {
		flush_mask |= MDP5_CTL_FLUSH_CTL;
		ctl->pending_ctl_trigger = 0;
	}

	flush_mask |= fix_sw_flush(ctl, pipeline, flush_mask);

	flush_mask &= ctl_mgr->flush_hw_mask;

	curr_ctl_flush_mask = flush_mask;

	fix_for_single_flush(ctl, &flush_mask, &flush_id);

	if (!start) {
		ctl->flush_mask |= flush_mask;
		return curr_ctl_flush_mask;
	} else {
		flush_mask |= ctl->flush_mask;
		ctl->flush_mask = 0;
	}

	if (flush_mask) {
		spin_lock_irqsave(&ctl->hw_lock, flags);
		ctl_write(ctl, REG_MDP5_CTL_FLUSH(flush_id), flush_mask);
		spin_unlock_irqrestore(&ctl->hw_lock, flags);
	}

	if (start_signal_needed(ctl, pipeline)) {
		send_start_signal(ctl);
	}

	return curr_ctl_flush_mask;
}

struct mdp5_pipeline *mdp5_crtc_get_pipeline(struct drm_crtc *crtc)
{
	struct mdp5_crtc_state *mdp5_cstate;

	if (WARN_ON(!crtc))
		return ERR_PTR(-EINVAL);

	mdp5_cstate = to_mdp5_crtc_state(crtc->state);

	return &mdp5_cstate->pipeline;
}

struct mdp5_hw_mixer *mdp5_crtc_get_mixer(struct drm_crtc *crtc)
{
	struct mdp5_crtc_state *mdp5_cstate;

	if (WARN_ON(!crtc))
		return ERR_PTR(-EINVAL);

	mdp5_cstate = to_mdp5_crtc_state(crtc->state);

	return WARN_ON(!mdp5_cstate->pipeline.mixer) ?
		ERR_PTR(-EINVAL) : mdp5_cstate->pipeline.mixer;
}

static u32 crtc_flush(struct drm_crtc *crtc, u32 flush_mask)
{
	struct mdp5_crtc_state *mdp5_cstate = to_mdp5_crtc_state(crtc->state);
	struct mdp5_ctl *ctl = mdp5_cstate->ctl;
	struct mdp5_pipeline *pipeline = &mdp5_cstate->pipeline;
	bool start = !mdp5_cstate->defer_start;

	mdp5_cstate->defer_start = false;

	DBG("%s: flush=%08x", crtc->name, flush_mask);

	return mdp5_ctl_commit(ctl, pipeline, flush_mask, start);
}

static void mdp5_vid_encoder_disable(struct drm_encoder *encoder)
{
	struct mdp5_encoder *mdp5_encoder = to_mdp5_encoder(encoder);
	struct mdp5_kms *mdp5_kms = get_kms(encoder);
	struct mdp5_ctl *ctl = mdp5_encoder->ctl;
	struct mdp5_pipeline *pipeline = mdp5_crtc_get_pipeline(encoder->crtc);
	struct mdp5_hw_mixer *mixer = mdp5_crtc_get_mixer(encoder->crtc);
	struct mdp5_interface *intf = mdp5_encoder->intf;
	int intfn = mdp5_encoder->intf->num;
	unsigned long flags;

	if (WARN_ON(!mdp5_encoder->enabled))
		return;

	mdp5_ctl_set_encoder_state(ctl, pipeline, false);

	spin_lock_irqsave(&mdp5_encoder->intf_lock, flags);
	mdp5_write(mdp5_kms, REG_MDP5_INTF_TIMING_ENGINE_EN(intfn), 0);
	spin_unlock_irqrestore(&mdp5_encoder->intf_lock, flags);
	mdp5_ctl_commit(ctl, pipeline, mdp_ctl_flush_mask_encoder(intf), true);

	/*
	 * Wait for a vsync so we know the ENABLE=0 latched before
	 * the (connector) source of the vsync's gets disabled,
	 * otherwise we end up in a funny state if we re-enable
	 * before the disable latches, which results that some of
	 * the settings changes for the new modeset (like new
	 * scanout buffer) don't latch properly..
	 */
	mdp_irq_wait(&mdp5_kms->base, intf2vblank(mixer, intf));

	mdp5_encoder->enabled = false;
}

static void mdp5_vid_encoder_enable(struct drm_encoder *encoder)
{
	struct mdp5_encoder *mdp5_encoder = to_mdp5_encoder(encoder);
	struct mdp5_kms *mdp5_kms = get_kms(encoder);
	struct mdp5_ctl *ctl = mdp5_encoder->ctl;
	struct mdp5_interface *intf = mdp5_encoder->intf;
	struct mdp5_pipeline *pipeline = mdp5_crtc_get_pipeline(encoder->crtc);
	int intfn = intf->num;
	unsigned long flags;

	if (WARN_ON(mdp5_encoder->enabled))
		return;

	/*
	 * Flush the staged scanout state before starting the video timing
	 * engine. Otherwise the first scanout can begin with stale state and
	 * underrun before the encoder flush reaches the hardware.
	 */
	mdp5_ctl_set_encoder_state(ctl, pipeline, true);

	spin_lock_irqsave(&mdp5_encoder->intf_lock, flags);
	mdp5_write(mdp5_kms, REG_MDP5_INTF_TIMING_ENGINE_EN(intfn), 1);
	spin_unlock_irqrestore(&mdp5_encoder->intf_lock, flags);
	mdp5_ctl_commit(ctl, pipeline, mdp_ctl_flush_mask_encoder(intf), true);

	mdp5_encoder->enabled = true;
}

static void mdp5_encoder_disable(struct drm_encoder *encoder)
{
	struct mdp5_encoder *mdp5_encoder = to_mdp5_encoder(encoder);
	struct mdp5_interface *intf = mdp5_encoder->intf;

	if (intf->mode == MDP5_INTF_DSI_MODE_COMMAND)
		mdp5_cmd_encoder_disable(encoder);
	else
		mdp5_vid_encoder_disable(encoder);
}

static void mdp5_encoder_enable(struct drm_encoder *encoder)
{
	struct mdp5_encoder *mdp5_encoder = to_mdp5_encoder(encoder);
	struct mdp5_interface *intf = mdp5_encoder->intf;
	/* this isn't right I think */
	struct drm_crtc_state *cstate = encoder->crtc->state;

	mdp5_encoder_mode_set(encoder, &cstate->mode, &cstate->adjusted_mode);

	if (intf->mode == MDP5_INTF_DSI_MODE_COMMAND)
		mdp5_cmd_encoder_enable(encoder);
	else
		mdp5_vid_encoder_enable(encoder);
}
