static struct mdp5_kms *get_kms(struct drm_plane *plane)
{
	struct msm_drm_private *priv = plane->dev->dev_private;
	return to_mdp5_kms(to_mdp_kms(priv->kms));
}

static bool plane_enabled(struct drm_plane_state *state)
{
	return state->visible;
}

static struct drm_private_state *
mdp5_global_duplicate_state(struct drm_private_obj *obj)
{
	struct mdp5_global_state *state;

	state = kmemdup(obj->state, sizeof(*state), GFP_KERNEL);
	if (!state)
		return NULL;

	__drm_atomic_helper_private_obj_duplicate_state(obj, &state->base);

	return &state->base;
}

struct mdp5_global_state *
mdp5_get_existing_global_state(struct mdp5_kms *mdp5_kms)
{
	return to_mdp5_global_state(mdp5_kms->glob_state.state);
}

struct mdp5_global_state *mdp5_get_global_state(struct drm_atomic_state *s)
{
	struct msm_drm_private *priv = s->dev->dev_private;
	struct mdp5_kms *mdp5_kms = to_mdp5_kms(to_mdp_kms(priv->kms));
	struct drm_private_state *priv_state;

	priv_state = drm_atomic_get_private_obj_state(s, &mdp5_kms->glob_state);
	if (IS_ERR(priv_state))
		return ERR_CAST(priv_state);

	return to_mdp5_global_state(priv_state);
}

int mdp5_pipe_assign(struct drm_atomic_state *s, struct drm_plane *plane,
		     uint32_t caps, uint32_t blkcfg,
		     struct mdp5_hw_pipe **hwpipe,
		     struct mdp5_hw_pipe **r_hwpipe)
{
	struct msm_drm_private *priv = s->dev->dev_private;
	struct mdp5_kms *mdp5_kms = to_mdp5_kms(to_mdp_kms(priv->kms));
	struct mdp5_global_state *new_global_state, *old_global_state;
	struct mdp5_hw_pipe_state *old_state, *new_state;
	int i, j;

	new_global_state = mdp5_get_global_state(s);
	if (IS_ERR(new_global_state))
		return PTR_ERR(new_global_state);

	/* grab old_state after mdp5_get_global_state(), since now we hold lock: */
	old_global_state = mdp5_get_existing_global_state(mdp5_kms);

	old_state = &old_global_state->hwpipe;
	new_state = &new_global_state->hwpipe;

	for (i = 0; i < mdp5_kms->num_hwpipes; i++) {
		struct mdp5_hw_pipe *cur = mdp5_kms->hwpipes[i];

		/* skip if already in-use.. check both new and old state,
		 * since we cannot immediately re-use a pipe that is
		 * released in the current update in some cases:
		 *  (1) mdp5 can have SMP (non-double-buffered)
		 *  (2) hw pipe previously assigned to different CRTC
		 *      (vblanks might not be aligned)
		 */
		if (new_state->hwpipe_to_plane[cur->idx] ||
				old_state->hwpipe_to_plane[cur->idx])
			continue;

		/* skip if doesn't support some required caps: */
		if (caps & ~cur->caps)
			continue;

		/*
		 * don't assign a cursor pipe to a plane that isn't going to
		 * be used as a cursor
		 */
		if (cur->caps & MDP_PIPE_CAP_CURSOR &&
				plane->type != DRM_PLANE_TYPE_CURSOR)
			continue;

		/* possible candidate, take the one with the
		 * fewest unneeded caps bits set:
		 */
		if (!(*hwpipe) || (hweight_long(cur->caps & ~caps) <
				   hweight_long((*hwpipe)->caps & ~caps))) {
			bool r_found = false;

			if (r_hwpipe) {
				for (j = i + 1; j < mdp5_kms->num_hwpipes;
				     j++) {
					struct mdp5_hw_pipe *r_cur =
							mdp5_kms->hwpipes[j];

					/* Both halves must be free in both states. */
					if (new_state->hwpipe_to_plane[r_cur->idx] ||
					    old_state->hwpipe_to_plane[r_cur->idx])
						continue;

					/* reject different types of hwpipes */
					if (r_cur->caps != cur->caps)
						continue;

					/* respect priority, eg. VIG0 > VIG1 */
					if (cur->pipe > r_cur->pipe)
						continue;

					*r_hwpipe = r_cur;
					r_found = true;
					break;
				}
			}

			if (!r_hwpipe || r_found)
				*hwpipe = cur;
		}
	}

	if (!(*hwpipe))
		return -ENOMEM;

	if (r_hwpipe && !(*r_hwpipe))
		return -ENOMEM;

	if (mdp5_kms->smp) {
		int ret;

		/* We don't support SMP and 2 hwpipes/plane together */
		WARN_ON(r_hwpipe);

		DBG("%s: alloc SMP blocks", (*hwpipe)->name);
		ret = mdp5_smp_assign(mdp5_kms->smp, &new_global_state->smp,
				(*hwpipe)->pipe, blkcfg);
		if (ret)
			return -ENOMEM;

		(*hwpipe)->blkcfg = blkcfg;
	}

	DBG("%s: assign to plane %s for caps %x",
			(*hwpipe)->name, plane->name, caps);
	new_state->hwpipe_to_plane[(*hwpipe)->idx] = plane;

	if (r_hwpipe) {
		DBG("%s: assign to right of plane %s for caps %x",
		    (*r_hwpipe)->name, plane->name, caps);
		new_state->hwpipe_to_plane[(*r_hwpipe)->idx] = plane;
	}

	return 0;
}

int mdp5_pipe_release(struct drm_atomic_state *s, struct mdp5_hw_pipe *hwpipe)
{
	struct msm_drm_private *priv = s->dev->dev_private;
	struct mdp5_kms *mdp5_kms = to_mdp5_kms(to_mdp_kms(priv->kms));
	struct mdp5_global_state *state;
	struct mdp5_hw_pipe_state *new_state;

	if (!hwpipe)
		return 0;

	state = mdp5_get_global_state(s);
	if (IS_ERR(state))
		return PTR_ERR(state);

	new_state = &state->hwpipe;

	if (WARN_ON(!new_state->hwpipe_to_plane[hwpipe->idx]))
		return -EINVAL;

	DBG("%s: release from plane %s", hwpipe->name,
		new_state->hwpipe_to_plane[hwpipe->idx]->name);

	if (mdp5_kms->smp) {
		DBG("%s: free SMP blocks", hwpipe->name);
		mdp5_smp_release(mdp5_kms->smp, &state->smp, hwpipe->pipe);
	}

	new_state->hwpipe_to_plane[hwpipe->idx] = NULL;

	return 0;
}

static struct drm_plane_state *
mdp5_plane_duplicate_state(struct drm_plane *plane)
{
	struct mdp5_plane_state *mdp5_state;

	if (WARN_ON(!plane->state))
		return NULL;

	mdp5_state = kmemdup(to_mdp5_plane_state(plane->state),
			sizeof(*mdp5_state), GFP_KERNEL);
	if (!mdp5_state)
		return NULL;

	__drm_atomic_helper_plane_duplicate_state(plane, &mdp5_state->base);

	return &mdp5_state->base;
}

static int mdp5_plane_drop_stale_hwpipes(struct drm_plane_state *state)
{
	struct mdp5_plane_state *mdp5_state = to_mdp5_plane_state(state);
	struct mdp5_global_state *global;
	struct drm_plane **owner;

	if (!mdp5_state->hwpipe && !mdp5_state->r_hwpipe)
		return 0;

	global = mdp5_get_global_state(state->state);
	if (IS_ERR(global))
		return PTR_ERR(global);

	owner = global->hwpipe.hwpipe_to_plane;
	if (mdp5_state->hwpipe && owner[mdp5_state->hwpipe->idx] != state->plane)
		mdp5_state->hwpipe = NULL;
	if (mdp5_state->r_hwpipe &&
	    owner[mdp5_state->r_hwpipe->idx] != state->plane)
		mdp5_state->r_hwpipe = NULL;

	return 0;
}

static int mdp5_plane_atomic_check_with_state(struct drm_crtc_state *crtc_state,
					      struct drm_plane_state *state)
{
	struct mdp5_plane_state *mdp5_state = to_mdp5_plane_state(state);
	struct drm_plane *plane = state->plane;
	struct drm_plane_state *old_state = plane->state;
	struct mdp5_cfg *config = mdp5_cfg_get_config(get_kms(plane)->cfg);
	bool new_hwpipe = false;
	bool need_right_hwpipe = false;
	uint32_t max_width, max_height;
	bool out_of_bounds = false;
	uint32_t caps = 0;
	int min_scale, max_scale;
	int ret;

	DBG("%s: check (%d -> %d)", plane->name,
			plane_enabled(old_state), plane_enabled(state));

	ret = mdp5_plane_drop_stale_hwpipes(state);
	if (ret)
		return ret;

	max_width = config->hw->lm.max_width << 16;
	max_height = config->hw->lm.max_height << 16;

	/* Make sure source dimensions are within bounds. */
	if (state->src_h > max_height)
		out_of_bounds = true;

	if (state->src_w > max_width) {
		/* If source split is supported, we can go up to 2x
		 * the max LM width, but we'd need to stage another
		 * hwpipe to the right LM. So, the drm_plane would
		 * consist of 2 hwpipes.
		 */
		if (config->hw->mdp.caps & MDP_CAP_SRC_SPLIT &&
		    (state->src_w <= 2 * max_width))
			need_right_hwpipe = true;
		else
			out_of_bounds = true;
	}

	if (out_of_bounds) {
		struct drm_rect src = drm_plane_state_src(state);
		DBG("Invalid source size "DRM_RECT_FP_FMT,
				DRM_RECT_FP_ARG(&src));
		return -ERANGE;
	}

	min_scale = FRAC_16_16(1, 8);
	max_scale = FRAC_16_16(8, 1);

	ret = drm_atomic_helper_check_plane_state(state, crtc_state,
						  min_scale, max_scale,
						  true, true);
	if (ret)
		return ret;

	if (plane_enabled(state)) {
		unsigned int rotation;
		const struct msm_format *format;
		struct mdp5_kms *mdp5_kms = get_kms(plane);
		uint32_t blkcfg = 0;

		format = msm_framebuffer_format(state->fb);
		if (MSM_FORMAT_IS_YUV(format))
			caps |= MDP_PIPE_CAP_SCALE | MDP_PIPE_CAP_CSC;

		if (((state->src_w >> 16) != state->crtc_w) ||
				((state->src_h >> 16) != state->crtc_h))
			caps |= MDP_PIPE_CAP_SCALE;

		rotation = drm_rotation_simplify(state->rotation,
						 DRM_MODE_ROTATE_0 |
						 DRM_MODE_REFLECT_X |
						 DRM_MODE_REFLECT_Y);

		if (rotation & DRM_MODE_REFLECT_X)
			caps |= MDP_PIPE_CAP_HFLIP;

		if (rotation & DRM_MODE_REFLECT_Y)
			caps |= MDP_PIPE_CAP_VFLIP;

		if (plane->type == DRM_PLANE_TYPE_CURSOR)
			caps |= MDP_PIPE_CAP_CURSOR;

		/* (re)allocate hw pipe if we don't have one or caps-mismatch: */
		if (!mdp5_state->hwpipe || (caps & ~mdp5_state->hwpipe->caps))
			new_hwpipe = true;

		/*
		 * (re)allocte hw pipe if we're either requesting for 2 hw pipes
		 * or we're switching from 2 hw pipes to 1 hw pipe because the
		 * new src_w can be supported by 1 hw pipe itself.
		 */
		if ((need_right_hwpipe && !mdp5_state->r_hwpipe) ||
		    (!need_right_hwpipe && mdp5_state->r_hwpipe))
			new_hwpipe = true;

		if (mdp5_kms->smp) {
			const struct msm_format *format =
				msm_framebuffer_format(state->fb);

			blkcfg = mdp5_smp_calculate(mdp5_kms->smp, format,
					state->src_w >> 16, false);

			if (mdp5_state->hwpipe && (mdp5_state->hwpipe->blkcfg != blkcfg))
				new_hwpipe = true;
		}

		/* (re)assign hwpipe if needed, otherwise keep old one: */
		if (new_hwpipe) {
			/* TODO maybe we want to re-assign hwpipe sometimes
			 * in cases when we no-longer need some caps to make
			 * it available for other planes?
			 */
			struct mdp5_hw_pipe *old_hwpipe = mdp5_state->hwpipe;
			struct mdp5_hw_pipe *old_right_hwpipe =
							  mdp5_state->r_hwpipe;
			struct mdp5_hw_pipe *new_hwpipe = NULL;
			struct mdp5_hw_pipe *new_right_hwpipe = NULL;

			ret = mdp5_pipe_assign(state->state, plane, caps,
					       blkcfg, &new_hwpipe,
					       need_right_hwpipe ?
					       &new_right_hwpipe : NULL);
			if (ret) {
				DBG("%s: failed to assign hwpipe(s)!",
				    plane->name);
				return ret;
			}

			mdp5_state->hwpipe = new_hwpipe;
			if (need_right_hwpipe)
				mdp5_state->r_hwpipe = new_right_hwpipe;
			else
				/*
				 * set it to NULL so that the driver knows we
				 * don't have a right hwpipe when committing a
				 * new state
				 */
				mdp5_state->r_hwpipe = NULL;


			ret = mdp5_pipe_release(state->state, old_hwpipe);
			if (ret)
				return ret;

			ret = mdp5_pipe_release(state->state, old_right_hwpipe);
			if (ret)
				return ret;

		}
	} else {
		ret = mdp5_pipe_release(state->state, mdp5_state->hwpipe);
		if (ret)
			return ret;

		ret = mdp5_pipe_release(state->state, mdp5_state->r_hwpipe);
		if (ret)
			return ret;

		mdp5_state->hwpipe = mdp5_state->r_hwpipe = NULL;
	}

	return 0;
}
