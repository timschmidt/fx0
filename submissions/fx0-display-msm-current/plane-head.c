// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic DRM/core/SMP services for actual MDP5 ownership functions. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BIT(n) (1U << (n))
#define GFP_KERNEL 0
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define ERR_CAST(p) ((void *)(p))
#define DBG(...) do { if (0) printf(__VA_ARGS__); } while (0)
static unsigned warnings, global_requests, alloc_fault, smp_assigns, smp_releases;
#define WARN_ON(c) ((c) ? (warnings++, true) : false)
static void *kmemdup(const void *s, size_t n, int flags)
{
	(void)flags;
	if (alloc_fault) { alloc_fault--; return NULL; }
	void *p = malloc(n);
	if (p) memcpy(p, s, n);
	return p;
}
#define kfree free
#define to_mdp5_mocks_unused /* no source transformation */
struct drm_device { void *dev_private; };
struct drm_private_state { unsigned generation; };
struct drm_private_obj { struct drm_private_state *state; };
struct drm_atomic_commit {
	struct drm_device *dev;
	struct drm_private_state *private_copy;
	int error;
};
struct msm_format { bool yuv; };
struct drm_framebuffer { struct msm_format format; };
struct drm_plane;
struct drm_plane_state {
	struct drm_plane *plane;
	struct drm_atomic_commit *state;
	struct drm_framebuffer *fb;
	bool visible;
	uint32_t src_w, src_h, crtc_w, crtc_h;
	unsigned rotation;
};
struct drm_plane {
	struct drm_device *dev;
	struct drm_plane_state *state;
	const char *name;
	unsigned type;
};
struct drm_crtc_state { int error; };
struct mdp5_plane_state {
	struct drm_plane_state base;
	struct mdp5_hw_pipe *hwpipe, *r_hwpipe;
};
#define to_mdp5_plane_state(p) container_of(p, struct mdp5_plane_state, base)
#define to_mdp5_global_state(p) container_of(p, struct mdp5_global_state, base)
#define to_mdp5_kms(p) (p)
#define to_mdp_kms(p) (p)
struct msm_drm_private { struct mdp5_kms *kms; };
struct mdp5_cfg_hw {
	struct { uint32_t max_width, max_height; } lm;
	struct { uint32_t caps; } mdp;
};
struct mdp5_cfg { struct mdp5_cfg_hw *hw; };
struct mdp5_smp_state { unsigned owned; };
struct mdp5_global_state {
	struct drm_private_state base;
	struct mdp5_hw_pipe_state hwpipe;
	struct mdp5_smp_state smp;
};
struct mdp5_kms {
	struct drm_private_obj glob_state;
	struct mdp5_cfg *cfg;
	int num_hwpipes;
	struct mdp5_hw_pipe *hwpipes[16];
	void *smp;
};
#define DRM_PLANE_TYPE_CURSOR 2
#define DRM_MODE_ROTATE_0 BIT(0)
#define DRM_MODE_REFLECT_X BIT(4)
#define DRM_MODE_REFLECT_Y BIT(5)
#define MSM_FORMAT_IS_YUV(p) ((p)->yuv)
#define FRAC_16_16(a, b) (((a) << 16) / (b))
#define DRM_RECT_FP_FMT "%u,%u"
#define DRM_RECT_FP_ARG(p) (p)->w, (p)->h
struct drm_rect { uint32_t w, h; };
static struct drm_rect drm_plane_state_src(struct drm_plane_state *p)
{ return (struct drm_rect){p->src_w, p->src_h}; }
static struct mdp5_cfg *mdp5_cfg_get_config(struct mdp5_cfg *cfg) { return cfg; }
static const struct msm_format *msm_framebuffer_format(struct drm_framebuffer *fb)
{ assert(fb); return &fb->format; }
static unsigned drm_rotation_simplify(unsigned rotation, unsigned supported)
{ assert(!(rotation & ~supported)); return rotation; }
static int drm_atomic_helper_check_plane_state(struct drm_plane_state *state,
	struct drm_crtc_state *crtc, int min, int max, bool position, bool disable)
{
	(void)state;
	assert(min == (1 << 13) && max == (8 << 16) && position && disable);
	return crtc->error;
}
static void __drm_atomic_helper_plane_duplicate_state(struct drm_plane *p,
	struct drm_plane_state *s) { assert(p == s->plane); s->state = NULL; }
static void __drm_atomic_helper_private_obj_duplicate_state(struct drm_private_obj *o,
	struct drm_private_state *s) { s->generation = o->state->generation + 1; }
static struct drm_private_state *mdp5_global_duplicate_state(struct drm_private_obj *);
static struct drm_private_state *drm_atomic_get_private_obj_state(
	struct drm_atomic_commit *s, struct drm_private_obj *o)
{
	global_requests++;
	if (s->error) return ERR_PTR(s->error);
	if (!s->private_copy) s->private_copy = mdp5_global_duplicate_state(o);
	return s->private_copy ? s->private_copy : ERR_PTR(-ENOMEM);
}
static unsigned hweight_long(unsigned long n) { return __builtin_popcountl(n); }
static uint32_t mdp5_smp_calculate(void *smp, const struct msm_format *f,
	unsigned width, bool hdecim)
{ assert(smp && !hdecim); return (width + 255) / 256 + (f->yuv ? 2 : 0); }
static int smp_error;
static int mdp5_smp_assign(void *smp, struct mdp5_smp_state *s,
	enum mdp5_pipe pipe, uint32_t blkcfg)
{
	assert(smp && blkcfg); smp_assigns++;
	if (smp_error) return smp_error;
	s->owned |= BIT(pipe); return 0;
}
static void mdp5_smp_release(void *smp, struct mdp5_smp_state *s, enum mdp5_pipe pipe)
{ assert(smp); smp_releases++; s->owned &= ~BIT(pipe); }
