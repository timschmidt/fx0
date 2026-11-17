// SPDX-License-Identifier: GPL-2.0-only
static unsigned int checks, failures, cases;
static void check(bool ok, const char *label)
{
	checks++;
	if (!ok) { if (failures < 8) printf("FAIL %s\n", label); failures++; }
}
int main(void)
{
	for (unsigned int i = 0; i < 16; i++) {
		config_data.ctl.base[i] = 0x1000 + i * 0x100;
		config_data.intf.base[i] = 0x4000 + i * 0x1000;
		config_data.lm.base[i] = 0x2000 + i * 0x100;
	}
	const enum mdp5_intf_type types[] = {INTF_DSI, INTF_HDMI, INTF_eDP};
	const u32 masks[] = {MDP5_CTL_FLUSH_RGB0|MDP5_CTL_FLUSH_LM0,
		MDP5_CTL_FLUSH_VIG0|MDP5_CTL_FLUSH_LM1,
		MDP5_CTL_FLUSH_RGB1|MDP5_CTL_FLUSH_LM2,
		MDP5_CTL_FLUSH_CURSOR_0|MDP5_CTL_FLUSH_LM0, 0};
	for (unsigned int t = 0; t < 3; t++)
	for (unsigned int intfnum = 0; intfnum < 4; intfnum++)
	for (unsigned int m = 0; m < 5; m++)
	for (unsigned int deferred = 0; deferred < 2; deferred++)
	for (unsigned int shared_cursor = 0; shared_cursor < 2; shared_cursor++) {
		struct mdp5_kms kms = {0};
		struct msm_drm_private priv = {.kms = &kms.base};
		struct drm_device device = {.dev_private = &priv};
		struct mdp5_interface intf = {.num = intfnum, .type = types[t], .mode = MDP5_INTF_DSI_MODE_VIDEO};
		struct mdp5_hw_mixer mixer = {.lm = 0, .pp = 0};
		struct mdp5_ctl_manager manager = {.flush_hw_mask = shared_cursor ? ~MDP5_CTL_FLUSH_CURSOR_0 : 0xffffffff};
		struct mdp5_ctl ctl = {.ctlm = &manager, .id = 0};
		struct mdp5_crtc_state cstate = {.ctl = &ctl, .pipeline = {.intf = &intf, .mixer = &mixer}};
		struct drm_crtc crtc = {.state = &cstate.base, .name = "synthetic-crtc"};
		struct mdp5_encoder encoder = {.base = {.dev = &device, .crtc = &crtc}, .ctl = &ctl, .intf = &intf};
		active_encoder = &encoder;
		nevents = epoch = flushed_epoch = starts = stale_starts = waits = warnings = 0;
		flushed_mask = 0;
		cases++;
		for (unsigned int cycle = 0; cycle < 3; cycle++) {
			epoch++;
			cstate.defer_start = deferred;
			ctl.pending_ctl_trigger = MDP5_CTL_FLUSH_LM0;
			u32 stage = crtc_flush(&crtc, masks[m]);
			required_mask = stage;
			unsigned int stale_before = stale_starts;
			mdp5_vid_encoder_enable(&encoder.base);
			check(stale_starts == stale_before, "staged scanout flush precedes video timing start");
			check(encoder.enabled && ctl.encoder_enabled && !ctl.flush_mask && !cstate.defer_start,
			      "encoder and deferred-flush bookkeeping settles after enable");
			unsigned int events_before = nevents;
			mdp5_vid_encoder_enable(&encoder.base);
			check(nevents == events_before && warnings == cycle + 1, "duplicate video enable is guarded");
			mdp5_vid_encoder_disable(&encoder.base);
			check(!encoder.enabled && !ctl.encoder_enabled && waits == cycle + 1 &&
			      !encoder.intf_lock && !ctl.hw_lock, "disable, vblank wait and lock balance preserved");
		}
		check(starts == 3, "three modeled video starts completed");
	}
	struct mdp5_kms kms = {0};
	struct msm_drm_private priv = {.kms = &kms.base};
	struct drm_device device = {.dev_private = &priv};
	struct mdp5_interface intf = {.num = 1, .type = INTF_DSI, .mode = MDP5_INTF_DSI_MODE_COMMAND};
	struct mdp5_hw_mixer mixer = {.lm = 0, .pp = 0};
	struct mdp5_ctl_manager manager = {.flush_hw_mask = 0xffffffff};
	struct mdp5_ctl ctl = {.ctlm = &manager};
	struct mdp5_crtc_state cstate = {.ctl = &ctl, .pipeline = {.intf = &intf, .mixer = &mixer}};
	struct drm_crtc crtc = {.state = &cstate.base};
	struct mdp5_encoder encoder = {.base = {.dev = &device, .crtc = &crtc}, .ctl = &ctl, .intf = &intf};
	active_encoder = &encoder;
	nevents = 0;
	mdp5_encoder_enable(&encoder.base);
	mdp5_encoder_disable(&encoder.base);
	check(command_enables == 1 && command_disables == 1 && mode_sets == 1 && !nevents,
	      "outer command-mode dispatch keeps modeled command operations");
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases + 1, checks, failures);
	return failures ? 1 : 0;
}
