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

## 2026-11-11 vibrator drafts on the current input tree

The three PM8xxx voltage/active-strength fixes now have
[unsigned review material](../submissions/pm8xxx-vibrator/README.md) based on
input `master`/`next` at `8e16f8bbf1bd528975fd6f4081eaf00513c1d83e`.
The base and all three prefixes pass ARM `W=1` object builds with KCFI and
compressed DWARF5; each patch passes strict checkpatch with only sign-off
checking disabled. The existing 768-case actual-C fixtures are byte-identical
and their earlier sanitizer results are reused. Earlier Fx0 RAM tests cover
the same voltage functions; this full maintainer kernel has not been linked
or booted, and PMI632 upper-byte encoding remains outside the fixtures.

The pinned current tree requires AI-assistance disclosure in the cover letter
or changelog, and prohibits agents from adding sign-offs or sending patches.
This bundle follows those current rules; the older draft requirements described
above belong to their respective pinned trees. Human review/certification and
additional physical qualification remain. No email or PR was sent.

## 2026-11-11 NFC removal drafts on the advertised fixes branch

The two [NXP removal drafts](../submissions/nxp-nci-remove/README.md) target
the NFC maintainer's Codeberg `for-linus` tip
`b61732f47316d45f27706db7812950145d3327b5`. Both advertised NFC branch tips
are older than the newer input tree checked above; that newer source still
contains the same removal problems. The series preserves intervening upstream
changes, separates clock/binding/board features, and avoids exporting the
intermediate ordering that stopped receive before the closing reset.

Six host tests pass nine modeled lifecycle cases and reject six independent
regression controls. Matching core/I2C/firmware objects pass `W=1` on the base
and both prefixes: nine ARM objects with KCFI and compressed DWARF5. Strict
checkpatch and exported-tree replay pass. The pinned NFC tree requires the
included `Assisted-by: LLM` tags and prohibits agent-added DCO sign-offs.

These remain review drafts. Full kernel/module and broader networking config
builds, GCC, physical open/unregister/IRQ timing, concurrent firmware, RF/PM
and human certification remain open. No email or PR was sent.

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
| `2ebba2c0ab26` iio: imu: inv_mpu6050: fix accel calibbias registers on MPU-6500 parts (Fixes 33da559f861b) | iio `fixes-togreg` | Owner approval; drafted on fx0-linux `integration/fx0-imu-calibbias`, tested on the MPU-6515 ([evidence](../evidence/2026-11-01-imu-accuracy-and-offsets.json)); confirm the ICM-20602/ICM-206xx register maps before claiming them |
| `21508b9dbbcb` iio: imu: inv_mpu6050: resume the chip before reading calibbias (Fixes 4599cac84614) | iio `fixes-togreg` | Owner approval; same branch and evidence |
| LG Fx0 board DTS: boot framebuffer holds MDSS (`683f457c18f4`), IMU core supply (`d02a6c3f57d2`), IMU mounting matrix (`6161d5c2ee3a`), touchscreen follows the panel (`5cd0d520ab72`) | qcom arm32 DTS | Folds into the Fx0 board submission above |
| `6d3c6c42f7bb` Input: rmi4 - don't fail system suspend after powering off the device (Fixes 946c8432aab0) | input | Owner approval; fx0-linux `integration/fx0-touch-follower` ([evidence](../evidence/2026-11-01-s2idle-touch-mdp5.json)) |
| `5adb175d6639` dt-bindings syna,rmi4 `panel` and `5a30fcb447dd` Input: rmi4 - power sequence an in-cell touchscreen with its panel | input, DT bindings | Owner approval; run `dt_binding_check` (dtschema is not installed on the build host) |
| `33befe7a7534` drm/msm/mdp5: reassign hwpipes the global state does not record (Fixes ca8199f13498) | drm/msm | Owner approval; fx0-linux `integration/fx0-mdp5-resume`; 20 of 20 suspend cycles pass with it |
| New WCD9306 (Tapan) codec driver `121c6e3ceac8` with main-microphone capture `839598eaea05` the RX port sample format `0ca1aca862f4` and the TX port sample format (fx0-linux `integration/fx0-txsb-format`; capture still under investigation); board links `e9a5a8f1eb96`. Line out 2 (`7c3b47e6f0bb`, buck supplies `1d9b341caee8`) is drafted but made no audible difference, so it stays out unless the speaker investigation shows it is needed | ASoC, qcom arm32 DTS | The speaker reaching its stock level (about 30 dB short, [evidence](../evidence/2026-11-01-speaker-regression-open.json)); owner approval. fx0-linux `integration/fx0-mic` … `integration/fx0-rxsb-format` |
| `fb084baee886` ASoC: qcom: apq8096: run the SLIMbus back ends at 24 bits | ASoC | The MSM8226 ADSP rejects 16-bit SLIMbus port starts. Needs a per-SoC or per-port approach before it can go to the shared apq8096 machine driver; owner approval |
| New Sony IMX179 binding `6776d3a5415a` and sensor driver `46f1cedb2a38`, crop rectangles `5371aa4768c8`, 2×2 binned 1640×1232 mode `5ff9bed4160f`; rear-camera location `4c36987daa8e` | media, qcom arm32 DTS | Binned-mode test on the phone; owner approval (`dt_binding_check` passes, 2026-11-01). fx0-linux `integration/fx0-imx179-bin` |
| wlroots: treat a gamma reset as a no-op on CRTCs without gamma ([draft](../submissions/wlroots/README.md)) | wlroots (GitLab MR) | Owner approval; fixes sway failing the first screen-on after blanking on MDP5 |
| New Sony IMX132 binding `a3ce062e9cf9`, driver `b671973c0a6c`, Fx0 front camera `ba6982590133` | media, qcom arm32 DTS | Owner approval; MAINTAINERS entries for IMX132 and IMX179; orientation check. fx0-linux `integration/fx0-imx132` (`dt_binding_check` passes) |
| `c4e259382709` slimbus: qcom-ngd-ctrl: Remove stream channels when disabling a stream | slimbus | Owner approval; fixes 16/24-bit stream switching on MSM8226. fx0-linux `integration/fx0-ngd-disable-v2` |
| `4b800b920c7d` ARM: dts: qcom: msm8226: Add the standalone power collapse idle state | qcom arm32 DTS | Owner approval; fx0-linux `integration/fx0-cpuidle`; applies to every MSM8226 board |
| `linux-postmarketos-qcom-msm8226` r8 config (`PM_DEVFREQ`, ADSP, GPU IOMMU) | pmaports | The kernel features above reaching a release the package follows |
| boot-deploy offset key in `deviceinfo_schema.toml` | pmaports | The boot-deploy merge request |
| `device-lg-madai` (fx0-pmaports `integration/fx0-device` b9491f835c90; 1-r1 installed on the phone 2026-11-01) | pmaports | lk2nd and boot-deploy changes accepted; fresh-install test on the phone after the soak |

## Maintenance plan

Each integration rebase drops commits that have landed upstream. Each
downstream commit keeps a row here until it is merged or replaced. Hardware
retests use the existing evidence harnesses: Wi-Fi association and soak,
Bluetooth pairing, display and GPU, reboot loops and the system soak.
