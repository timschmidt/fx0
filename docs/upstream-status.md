# Upstream submission status

This lists every downstream change in the installed Fx0 stack: its target, its
status and what it waits for. It covers kernel `integration/fx0-gpu` at
`962a378204d6` (r8, 61 commits on v6.18.59), lk2nd, boot-deploy, pmaports and
userspace. Nothing has been sent; sending needs the owner's approval
([gate](upstream-development.md#submission-readiness-checklist)).

"Prepared" means a focused branch on the current maintainer base, exported
patches, a README with checks and recipients, and hardware evidence. Kernel
patches also carry the AI-assistance disclosure and `Assisted-by: LLM`
trailer required by the target tree's `Documentation/process/coding-assistants.rst`,
and no Signed-off-by, which the owner adds before sending.

## Prepared, not sent

| Change | Target | Material |
| --- | --- | --- |
| Pronto v1/v2 PD regulator selection (`61c60256c94a`) | remoteproc `for-next` | [submissions/remoteproc](../submissions/remoteproc/README.md) |
| cfg80211 deferred scan-done flush (`34c341b90393`) | wireless `main` | [submissions/wireless](../submissions/wireless/README.md) |
| Charge control, charger manager, battery info series | power-supply `for-next` | [submissions/power-supply](../submissions/power-supply/README.md) |
| UPower CLI test and battery-interface check | UPower | [submissions/upower](../submissions/upower/README.md) |
| lk2nd Fx0 DTB selection, `LK2ND_EXTLINUX`, `LK2ND_PON_REBOOT_MODE` | lk2nd `main` (GitHub PR) | [submissions/lk2nd](../submissions/lk2nd/README.md) |
| boot-deploy `deviceinfo_flash_bootimg_offset` | boot-deploy `main` (GitLab MR) | [submissions/boot-deploy](../submissions/boot-deploy/README.md) |
| qcom-spmi-iadc current sign and units (`5c3efd4c7fa8`) | IIO `togreg` | [submissions/iio](../submissions/iio/README.md) |
| qcom-usb-hs init sequences starting at offset zero (`c7b37b2f2132`, rewritten for the flexible array) | PHY `next` | [submissions/phy](../submissions/phy/README.md) |
| Sxmo device profile for `lg,madai` | sxmo-utils `master` (email) | [submissions/sxmo-utils](../submissions/sxmo-utils/README.md) |
| LG Fx0 JDI panel binding and driver (`dc2430e91f81`, `a22c81819da3`, `51190c24d336`, `9723635946c4`) | drm-misc `drm-misc-next` | [submissions/drm-panel](../submissions/drm-panel/README.md) |

## Already in mainline (backports)

- `f9ab01c7e7b8` drm/msm: detach the ARM DMA mapping before attaching our own domain
- `341246daef48` dt-bindings: Fix emails with spaces or missing brackets

Both drop out when the integration branch moves to a kernel that contains them.

## Superseded upstream

- `d260404eef69` dt-bindings: remoteproc: qcom,wcnss: Bound the stop-state
  specifier. Mainline fixed the same dtschema diagnostic differently in
  `37534121c4e4` ("dt-bindings: Fix phandle-array constraints, again"). Drop it
  at the next rebase.

## Other authors' posted work carried downstream

These are not ours to submit. Track them upstream, test them on the Fx0 and
reply with `Tested-by` once the owner approves.

| Commits | Author | Topic | Fx0 dependency |
| --- | --- | --- | --- |
| `5c8adf91fca5`…`a29fb8276519`, `705eaaee8b60` | Dmitry Baryshkov | MSM8974 `qcom_iommu` support (short descriptors, non-TZ instances, halt, BFB, context restore) and the MMCC GENPD flag | Display and GPU IOMMUs; Freedreno |
| `9587367f58f6`, `5519845f0bd8`, `3cc8fd9f5851` | Matti Lehtimäki | WCN3660A compatible for WCNSS and wcn36xx | Wi-Fi/Bluetooth |
| `c8d156a3bee3` | Bartosz Dudziak | MSM8226 WCNSS remoteproc node | Wi-Fi/Bluetooth |
| `ff0d3662b804` | Roman Vivchar | Synaptics RMI4 reset GPIOs | Touchscreen |

## Ours, not yet prepared

Ordered roughly by how independent they are.

| Change | Target | Waits for |
| --- | --- | --- |
| `b2512c53f035` msm8226 WCNSS DXE level interrupts | Review comment on Dudziak's MSM8226 WCNSS node (mainline has no node yet) | Owner approval to reply on that series |
| `7297314a644f` Input: rmi4 assert reset before releasing supplies | input | Vivchar's reset-GPIO patch |
| `a434ee44e3df` drm/msm/dsi/phy per-lane CFG4 on MSM8226 | drm/msm | Evidence that it is needed: applying it alone did not fix the display, and the first working image combined several changes. Run an on/off A/B on the Fx0 (after the soak). Downstream MSM8974 and MSM8226 both use CFG4 0/5/a/f, so if it is needed, ask whether it should apply to the whole 28nm PHY |
| MSM8226 display and GPU IOMMU bindings and configuration (`32fd8a21c5a3`, `b506b8cd827d`, `ca397d0f4501`, `60fa2a06552b`) | iommu | Baryshkov's MSM8974 series |
| MSM8226 SoC DTS: display IOMMU and secured contexts, GPU IOMMU, CCI clock rate, PON label (`6c99f0648715`, `abe11294089a`, `dad2d15ff6ba`, `8cfcb0fedcd9`, `7e5f8f6b2250`) | qcom arm32 DTS | IOMMU bindings above |
| LG Fx0 board: binding `933d3593e3ab` and the `lg-madai` DTS commits (UART/USB through PON reboot modes) | qcom arm32 DTS (`qcom/for-next`; new files drop the `qcom-` prefix, e.g. `msm8926.dtsi`) | **Attribution first:** the initial DTS (`3bfdc9d2da6a`) restores Masanori Ogino's work from `omasanori/linux` `lg-madai`. Upstream needs his authorship or `Co-developed-by` with his own Signed-off-by, so the owner should contact him before a board series is posted. Then a first version limited to mainline-supported hardware (UART, USB/VBUS, eMMC, RPM regulators, buttons, reserved memory, PMIC ADC, ADSP, PON modes). Touch waits for RMI4 reset-GPIO driver support; WCNSS, display, GPU and camera wait for their series |
| `linux-postmarketos-qcom-msm8226` r8 config (`PM_DEVFREQ`, ADSP, GPU IOMMU) | pmaports | The kernel features above reaching a release the package follows |
| boot-deploy offset key in `deviceinfo_schema.toml` | pmaports | The boot-deploy merge request |
| `device-lg-madai` (fx0-pmaports `integration/fx0-device` c87f356c5d2a; built and signed, not yet installed) | pmaports | lk2nd and boot-deploy changes accepted; install and fresh-install test on the phone after the soak |

## Maintenance plan

Each integration rebase drops commits that have landed upstream. Each
downstream commit keeps a row here until it is merged or replaced. Hardware
retests use the existing evidence harnesses: Wi-Fi association and soak,
Bluetooth pairing, display and GPU, reboot loops and the system soak.
