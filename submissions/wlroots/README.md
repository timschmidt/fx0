# wlroots draft submission

One patch for [wlroots](https://gitlab.freedesktop.org/wlroots/wlroots), based
on `master` at `07438f5492a8173d6429b77235b902b6d84b1805` (fetched November 1,
2026). wlroots takes GitLab merge requests. **Not sent:** sending needs the
owner's approval. The patch was prepared with the help of an AI coding
assistant; say so in the merge request.

[The patch](0001-backend-drm-treat-a-gamma-reset-as-a-no-op-on-CRTCs-.patch)
makes `drm_legacy_crtc_set_gamma()` succeed when asked to reset the gamma LUT of
a CRTC that has no gamma table at all.

## The bug

On the Fx0 (msm MDP5, which registers neither `GAMMA_LUT` nor a legacy gamma
table), `swaymsg output DSI-1 power on` after `power off` failed every time
with "Backend commit failed" and left the panel off; a second `power on`
worked. The chain:

1. Disabling an output sets the scene's `gamma_lut_changed`, so the next
   enable re-applies the gamma LUT.
2. `scene_output_state_attempt_gamma()` adds a color transform reset (`NULL`)
   to the state and checks it with `wlr_output_test_state()`. That function
   drops fields equal to the current state (`NULL == NULL`), so the test never
   reaches the gamma code and passes.
3. sway commits through `wlr_backend_commit()`, which keeps the field. The DRM
   backend has no `GAMMA_LUT` property, falls back to the legacy interface, and
   `drm_legacy_crtc_set_gamma()` returns false for a legacy gamma size of 0,
   without logging.
4. `gamma_lut_changed` was cleared in step 2, so the next attempt succeeds.

strace of sway confirmed the real commit stops right after creating the mode
blob, with no further ioctl. There is nothing to reset on such a CRTC, so the
patch reports success. Setting a real LUT on it still fails.

An alternative or additional fix would be for `wlr_backend_commit()` to drop
unchanged fields like `wlr_output_commit_state()` does; that is a broader
change and is left to the maintainers.

## Testing

Alpine 3.24 `wlroots0.20` 0.20.2 rebuilt with the patch (fx0-pmaports
`temp/wlroots0.20`), sway 1.12-rc3, Nura v26.06 on the Fx0. Five `power off`/
`power on` cycles: unpatched 0 of 5 came back on (5 "Backend commit failed"),
patched 5 of 5 (none). See the
[evidence](../../evidence/2026-11-01-sway-power-on-gamma.json).
