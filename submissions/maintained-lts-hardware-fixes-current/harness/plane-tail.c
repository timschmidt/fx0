static unsigned checks, failures, cases;
static const char *case_name;
#define CHECK(c) do { checks++; if (!(c)) { failures++; \
	if (failures < 25) printf("FAIL %s line %d: %s\n", case_name, __LINE__, #c); } } while (0)
struct fixture {
	struct mdp5_cfg_hw hw;
	struct mdp5_cfg cfg;
	struct mdp5_kms kms;
	struct msm_drm_private priv;
	struct drm_device dev;
	struct mdp5_global_state global;
	struct mdp5_hw_pipe pipes[8];
	struct drm_plane plane, other;
	struct mdp5_plane_state live;
	struct drm_framebuffer fb;
	struct drm_crtc_state crtc;
};
static void init(struct fixture *f, unsigned feature, bool smp)
{
	memset(f, 0, sizeof(*f)); warnings = 0; alloc_fault = 0; smp_error = 0;
	f->hw.lm.max_width = f->hw.lm.max_height = 2048;
	f->hw.mdp.caps = MDP_CAP_SRC_SPLIT;
	f->cfg.hw = &f->hw; f->kms.cfg = &f->cfg;
	f->kms.glob_state.state = &f->global.base;
	f->kms.num_hwpipes = 8; f->kms.smp = smp ? f : NULL;
	f->priv.kms = &f->kms; f->dev.dev_private = &f->priv;
	f->plane = (struct drm_plane){&f->dev, &f->live.base, "test", feature == 5 ? DRM_PLANE_TYPE_CURSOR : 0};
	f->other = (struct drm_plane){.dev = &f->dev, .name = "other"};
	f->fb.format.yuv = feature == 1;
	f->live.base = (struct drm_plane_state){.plane = &f->plane, .fb = &f->fb,
		.visible = true, .src_w = 640 << 16, .src_h = 480 << 16,
		.crtc_w = feature == 2 ? 320 : 640, .crtc_h = 480,
		.rotation = feature == 3 ? DRM_MODE_REFLECT_X : feature == 4 ? DRM_MODE_REFLECT_Y : DRM_MODE_ROTATE_0};
	for (unsigned i = 0; i < 8; i++) {
		f->pipes[i] = (struct mdp5_hw_pipe){.idx = i, .name = "pipe",
			.pipe = (enum mdp5_pipe)(i + 1),
			.caps = MDP_PIPE_CAP_HFLIP | MDP_PIPE_CAP_VFLIP | MDP_PIPE_CAP_SCALE | MDP_PIPE_CAP_CSC,
			.blkcfg = smp ? mdp5_smp_calculate(f, &f->fb.format, 640, false) : 0};
		if (feature == 5) f->pipes[i].caps |= MDP_PIPE_CAP_CURSOR;
		f->kms.hwpipes[i] = &f->pipes[i];
	}
}
static struct mdp5_plane_state *copy(struct fixture *f, struct drm_atomic_state *s)
{
	struct drm_plane_state *p = mdp5_plane_duplicate_state(&f->plane);
	assert(p); p->state = s; return to_mdp5_plane_state(p);
}
static struct mdp5_global_state *current(struct fixture *f, struct drm_atomic_state *s)
{ return s->private_copy ? to_mdp5_global_state(s->private_copy) : &f->global; }
static void clean(struct drm_atomic_state *s, struct mdp5_plane_state *p)
{ free(s->private_copy); s->private_copy = NULL; free(p); }
static void accept(struct fixture *f, struct drm_atomic_state *s, struct mdp5_plane_state *p)
{
	if (s->private_copy) f->global = *to_mdp5_global_state(s->private_copy);
	f->live = *p; f->live.base.state = NULL;
	clean(s, p);
}
static void ownership(struct fixture *f, struct drm_atomic_state *s,
	struct mdp5_plane_state *p, bool split)
{
	struct mdp5_global_state *g = current(f, s);
	CHECK(p->hwpipe != NULL);
	if (p->hwpipe) CHECK(g->hwpipe.hwpipe_to_plane[p->hwpipe->idx] == &f->plane);
	CHECK((p->r_hwpipe != NULL) == split);
	if (p->r_hwpipe) CHECK(g->hwpipe.hwpipe_to_plane[p->r_hwpipe->idx] == &f->plane);
}
static void lifecycle(unsigned feature, bool smp, bool split)
{
	struct fixture f; init(&f, feature, smp);
	case_name = "duplicate-disable-restore-disable"; cases++;
	if (split) { f.live.base.src_w = 3000 << 16; f.live.base.crtc_w = 3000; }
	f.live.hwpipe = &f.pipes[0]; f.global.hwpipe.hwpipe_to_plane[0] = &f.plane;
	if (split) { f.live.r_hwpipe = &f.pipes[1]; f.global.hwpipe.hwpipe_to_plane[1] = &f.plane; }
	for (unsigned cycle = 0; cycle < 3; cycle++) {
		struct drm_atomic_state restore = {.dev = &f.dev}, off = {.dev = &f.dev};
		struct mdp5_plane_state *saved = copy(&f, &restore), *disabled = copy(&f, &off);
		disabled->base.visible = false;
		CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &disabled->base) == 0);
		CHECK(current(&f, &off)->hwpipe.hwpipe_to_plane[0] == NULL);
		CHECK(!disabled->hwpipe && !disabled->r_hwpipe);
		accept(&f, &off, disabled);
		CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &saved->base) == 0);
		ownership(&f, &restore, saved, split);
		accept(&f, &restore, saved);
	}
	struct drm_atomic_state off = {.dev = &f.dev};
	struct mdp5_plane_state *disabled = copy(&f, &off);
	disabled->base.visible = false;
	CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &disabled->base) == 0);
	CHECK(!disabled->hwpipe && !disabled->r_hwpipe);
	CHECK(warnings == 0);
	clean(&off, disabled);
}
static void stale(unsigned feature, bool smp, unsigned owner, bool enabled)
{
	struct fixture f; init(&f, feature, smp);
	case_name = "cached-left-owner"; cases++;
	f.live.hwpipe = &f.pipes[0];
	f.global.hwpipe.hwpipe_to_plane[0] = owner == 1 ? &f.plane : owner == 2 ? &f.other : NULL;
	struct drm_atomic_state s = {.dev = &f.dev};
	struct mdp5_plane_state *p = copy(&f, &s);
	p->base.visible = enabled;
	CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &p->base) == 0);
	if (enabled) {
		ownership(&f, &s, p, false);
		if (owner == 1) CHECK(p->hwpipe == &f.pipes[0]);
	} else CHECK(!p->hwpipe && !p->r_hwpipe);
	CHECK(current(&f, &s)->hwpipe.hwpipe_to_plane[0] ==
		(owner == 2 ? &f.other : enabled && owner != 2 ? &f.plane : NULL));
	CHECK(f.global.hwpipe.hwpipe_to_plane[0] == (owner == 1 ? &f.plane : owner == 2 ? &f.other : NULL));
	CHECK(f.live.hwpipe == &f.pipes[0]);
	CHECK(warnings == 0);
	clean(&s, p);
}
static void stale_right(unsigned feature, bool smp, bool enabled, bool valid_left)
{
	struct fixture f; init(&f, feature, smp);
	case_name = "cached-foreign-right"; cases++;
	if (valid_left) { f.live.hwpipe = &f.pipes[0]; f.global.hwpipe.hwpipe_to_plane[0] = &f.plane; }
	f.live.r_hwpipe = &f.pipes[1]; f.global.hwpipe.hwpipe_to_plane[1] = &f.other;
	struct drm_atomic_state s = {.dev = &f.dev}; struct mdp5_plane_state *p = copy(&f, &s);
	p->base.visible = enabled;
	CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &p->base) == 0);
	CHECK(current(&f, &s)->hwpipe.hwpipe_to_plane[1] == &f.other);
	if (enabled) ownership(&f, &s, p, false);
	else CHECK(!p->hwpipe && !p->r_hwpipe);
	if (enabled && valid_left) CHECK(p->hwpipe == &f.pipes[0]);
	CHECK(warnings == 0); clean(&s, p);
}
static void errors(unsigned feature, bool smp)
{
	for (unsigned right = 0; right < 2; right++) for (unsigned e = 0; e < 3; e++) {
		struct fixture f; init(&f, feature, smp);
		case_name = "global-state-error-rollback"; cases++;
		if (right) f.live.r_hwpipe = &f.pipes[1]; else f.live.hwpipe = &f.pipes[0];
		int expected = e == 1 ? -EDEADLK : -ENOMEM;
		struct drm_atomic_state s = {.dev = &f.dev, .error = e == 2 ? 0 : expected};
		struct mdp5_plane_state *p = copy(&f, &s), before = *p;
		if (e == 2) alloc_fault = 1;
		CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &p->base) == expected);
		CHECK(memcmp(p, &before, sizeof(before)) == 0);
		CHECK(s.private_copy == NULL); CHECK(warnings == 0); clean(&s, p);
	}
	struct fixture f; init(&f, feature, smp);
	case_name = "no-cached-pipe-disabled-skips-global-state"; cases++;
	struct drm_atomic_state s = {.dev = &f.dev, .error = -EDEADLK};
	struct mdp5_plane_state *p = copy(&f, &s); p->base.visible = false;
	unsigned requests = global_requests;
	CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &p->base) == 0);
	CHECK(global_requests == requests); clean(&s, p);
	case_name = "starved-pipe-does-not-steal"; cases++;
	for (unsigned i = 0; i < 8; i++) f.global.hwpipe.hwpipe_to_plane[i] = &f.other;
	s = (struct drm_atomic_state){.dev = &f.dev}; p = copy(&f, &s); p->hwpipe = &f.pipes[0];
	CHECK(mdp5_plane_atomic_check_with_state(&f.crtc, &p->base) == -ENOMEM);
	for (unsigned i = 0; i < 8; i++) CHECK(current(&f, &s)->hwpipe.hwpipe_to_plane[i] == &f.other);
	clean(&s, p);
}
static void split_owner(unsigned owner_mask, unsigned new_mask, bool release_old)
{
	struct fixture f; init(&f, 0, false);
	case_name = "split-allocator-old-and-new-ownership"; cases++;
	for (unsigned i = 0; i < 8; i++)
		if (owner_mask & BIT(i)) f.global.hwpipe.hwpipe_to_plane[i] = &f.other;
	struct drm_atomic_state s = {.dev = &f.dev};
	struct mdp5_global_state *g = mdp5_get_global_state(&s); assert(!IS_ERR(g));
	if (release_old) memset(&g->hwpipe, 0, sizeof(g->hwpipe));
	for (unsigned i = 0; i < 8; i++)
		if (new_mask & BIT(i)) g->hwpipe.hwpipe_to_plane[i] = &f.other;
	struct mdp5_hw_pipe *left = NULL, *right = NULL;
	int ret = mdp5_pipe_assign(&s, &f.plane, 0, 0, &left, &right);
	unsigned unavailable = owner_mask | new_mask;
	unsigned free_count = 8 - hweight_long(unavailable);
	CHECK(ret == (free_count >= 2 ? 0 : -ENOMEM));
	if (!ret) {
		CHECK(left && right && left != right);
		CHECK(!(unavailable & BIT(left->idx)));
		CHECK(!(unavailable & BIT(right->idx)));
		CHECK(left->caps == right->caps && left->pipe <= right->pipe);
	}
	for (unsigned i = 0; i < 8; i++) {
		if (unavailable & BIT(i)) CHECK(g->hwpipe.hwpipe_to_plane[i] ==
			(((release_old ? new_mask : unavailable) & BIT(i)) ? &f.other : NULL));
		CHECK(f.global.hwpipe.hwpipe_to_plane[i] == ((owner_mask & BIT(i)) ? &f.other : NULL));
	}
	CHECK(warnings == 0); free(s.private_copy);
}
int main(void)
{
	for (unsigned feature = 0; feature < 6; feature++) for (unsigned smp = 0; smp < 2; smp++) {
		lifecycle(feature, smp, false);
		if (!smp) lifecycle(feature, false, true);
		for (unsigned owner = 0; owner < 3; owner++) for (unsigned visible = 0; visible < 2; visible++)
			stale(feature, smp, owner, visible);
		for (unsigned visible = 0; visible < 2; visible++) for (unsigned left = 0; left < 2; left++)
			stale_right(feature, smp, visible, left);
		errors(feature, smp);
	}
	for (unsigned old = 0; old < 256; old++) {
		split_owner(old, 0, false);
		split_owner(0, old, false);
		split_owner(old, (old << 1) & 255, false);
		split_owner(old, (old << 1) & 255, true);
	}
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
	return failures != 0;
}
