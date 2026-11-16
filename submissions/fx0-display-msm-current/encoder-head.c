// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
struct model_bases { u32 base[16]; };
static struct {
	struct model_bases ad, ctl, dspp, intf, lm, pipe_cursor, pipe_dma;
	struct model_bases pipe_rgb, pipe_vig, pp, wb;
} config_data, *mdp5_cfg = &config_data;
static uint32_t INVALID_IDX(uint32_t index)
{
	(void)index; assert(false); return 0;
}
#include "mdp_common.xml.h"
#include "mdp5.xml.h"
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define DBG(...) do { if (0) printf(__VA_ARGS__); } while (0)
#define VERB(...) do { if (0) printf(__VA_ARGS__); } while (0)
static const char *str_on_off(bool enabled) { return enabled ? "on" : "off"; }
static unsigned int warnings;
#define WARN_ON(condition) ((condition) ? (warnings++, true) : false)
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock) = true; (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(flags); assert(*(lock)); *(lock) = false; } while (0)
enum mdp5_intf_mode { MDP5_INTF_MODE_NONE, MDP5_INTF_DSI_MODE_VIDEO,
	MDP5_INTF_DSI_MODE_COMMAND, MDP5_INTF_WB_MODE_BLOCK, MDP5_INTF_WB_MODE_LINE };
struct mdp5_hw_mixer { int lm, pp; };
struct mdp5_interface { int num; enum mdp5_intf_type type; enum mdp5_intf_mode mode; };
struct mdp5_pipeline { struct mdp5_interface *intf; struct mdp5_hw_mixer *mixer, *r_mixer; };
struct mdp5_ctl_manager { u32 flush_hw_mask; };
struct mdp5_ctl {
	struct mdp5_ctl_manager *ctlm;
	u32 id, pending_ctl_trigger, flush_mask;
	bool hw_lock, encoder_enabled;
};
struct drm_display_mode { int unused; };
struct drm_crtc_state { struct drm_display_mode mode, adjusted_mode; };
struct mdp5_crtc_state {
	struct drm_crtc_state base;
	struct mdp5_ctl *ctl;
	struct mdp5_pipeline pipeline;
	bool defer_start;
};
struct drm_crtc { struct drm_crtc_state *state; const char *name; };
struct drm_device { void *dev_private; };
struct drm_encoder { struct drm_device *dev; struct drm_crtc *crtc; };
struct msm_kms { int unused; };
struct mdp5_kms { struct msm_kms base; };
struct msm_drm_private { struct msm_kms *kms; };
struct mdp5_encoder {
	struct drm_encoder base;
	struct mdp5_ctl *ctl;
	struct mdp5_interface *intf;
	bool intf_lock, enabled;
};
#define to_mdp5_encoder(e) container_of(e, struct mdp5_encoder, base)
#define to_mdp5_crtc_state(s) container_of(s, struct mdp5_crtc_state, base)
#define to_mdp_kms(k) (k)
#define to_mdp5_kms(k) ((struct mdp5_kms *)(k))
struct event { u32 offset, value; };
static struct event events[256];
static unsigned int nevents, epoch, flushed_epoch, starts, stale_starts, waits;
static unsigned int command_enables, command_disables, mode_sets;
static u32 required_mask, flushed_mask;
static struct mdp5_encoder *active_encoder;
static void record(u32 offset, u32 value)
{
	assert(nevents < 256);
	events[nevents++] = (struct event){offset, value};
}
static void ctl_write(struct mdp5_ctl *ctl, u32 reg, u32 value)
{
	assert(ctl->hw_lock);
	record(reg, value);
	if (reg == REG_MDP5_CTL_FLUSH(ctl->id)) {
		if (flushed_epoch != epoch) flushed_mask = 0;
		flushed_epoch = epoch;
		flushed_mask |= value;
	}
}
static void mdp5_write(struct mdp5_kms *kms, u32 reg, u32 value)
{
	(void)kms;
	assert(active_encoder->intf_lock);
	record(reg, value);
	if (reg == REG_MDP5_INTF_TIMING_ENGINE_EN(active_encoder->intf->num) && value) {
		starts++;
		if (required_mask && (flushed_epoch != epoch || (flushed_mask & required_mask) != required_mask)) stale_starts++;
	}
}
static void mdp_irq_wait(struct msm_kms *kms, u32 mask)
{
	(void)kms;
	assert(mask); waits++;
}
static void mdp5_cmd_encoder_enable(struct drm_encoder *encoder)
{
	to_mdp5_encoder(encoder)->enabled = true; command_enables++;
}
static void mdp5_cmd_encoder_disable(struct drm_encoder *encoder)
{
	to_mdp5_encoder(encoder)->enabled = false; command_disables++;
}
static void mdp5_encoder_mode_set(struct drm_encoder *encoder,
	struct drm_display_mode *mode, struct drm_display_mode *adjusted)
{
	(void)encoder; (void)mode; (void)adjusted; mode_sets++;
}
