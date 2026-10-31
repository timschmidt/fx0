# DRM panel draft submission

A two-patch series for [drm-misc](https://gitlab.freedesktop.org/drm/misc/kernel),
based on `drm-misc-next` at `a1e63ab695ad76850ab9787b9eb6aab695dc2965` (fetched
October 31, 2026). **Not sent:** mailing it needs the owner's approval and
Signed-off-by.

The [submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-lg-fx0-panel-v3)
is `3fba4b1b5fdb`. It replaces the first push (`submission/fx0-lg-fx0-panel`,
`c581fef801d6`), whose driver message claimed the clock-lane flag alone moved
the panel out of sleep. The bring-up log shows that claim was confounded by
an fbdev blank state, and the first working image came from several changes
together, so the message now says so. (`-v2` had the same correction with one
over-long changelog line.)

1. [dt-bindings: display: panel: Add LG Fx0 production panel](0001-dt-bindings-display-panel-Add-LG-Fx0-production-pane.patch)
2. [drm/panel: Add LG Fx0 JDI in-cell panel driver](0002-drm-panel-Add-LG-Fx0-JDI-in-cell-panel-driver.patch).
   This folds the integration commits `a22c81819da3`, `51190c24d336` and
   `9723635946c4` into one driver. It adds an email to `MODULE_AUTHOR` and
   re-wraps five register byte lists to satisfy strict checkpatch. The
   re-wrapped object has identical code and data sections to the installed
   driver; only debug line numbers differ.

## Draft cover letter

> **[PATCH 0/2] Add the LG Fx0 JDI in-cell panel**
>
> The LG Fx0 (MSM8926, 2014) uses a 720x1280 four-lane JDI in-cell video-mode
> panel with separately switched IO and positive/negative bias rails. This
> series adds a binding and a driver translated from LG's GPL kernel for the
> board. On an LG Fx0 running a v6.18-based kernel it drives the panel for a
> Sway/Sxmo session on Freedreno. Touch, on the same in-cell panel, works with
> the existing RMI4 driver.
>
> The JDI part number is unknown, so the compatible names the handset
> (`lg,fx0-panel`), as LG's kernel does. Suggestions for a better name are
> welcome.
>
> Known limitation: turning the display off and on again is not yet reliable on
> this board. The DSI host/PLL shutdown later resets the device, which looks
> outside the panel driver.
>
> The board DTS that uses this binding is not upstream yet.
>
> These patches were developed with an AI coding assistant (Claude Opus 5.5);
> each changelog says how.

## Checks

- **Binding:** `dt_binding_check` for `display/panel/lg,fx0-panel.yaml` passes
  with dtschema from the project venv.
- **Build:** ARM `multi_v7_defconfig` with `DRM_PANEL_LG_FX0=m` builds with
  LLVM W=1 and no warnings.
- **checkpatch:** `--strict` reports only the missing Signed-off-by on each
  patch.
- **Recipients:** `get_maintainer.pl --no-keywords` lists Neil Armstrong,
  Jessica Zhang, the DRM core maintainers (Maarten Lankhorst, Maxime Ripard,
  Thomas Zimmermann, David Airlie, Simona Vetter), the DT maintainers (Rob
  Herring, Krzysztof Kozlowski, Conor Dooley), dri-devel, devicetree and
  linux-kernel. Add linux-arm-msm for context.
- **Hardware:** the native display, GLES2 compositor and touch on the LG Fx0;
  the owner confirmed image and input. See the
  [GPU bring-up](../../docs/gpu-bringup.md) and
  [hardware acceptance](../../docs/hardware-acceptance.md) records.
