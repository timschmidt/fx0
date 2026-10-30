# LG Fx0 Nura research

## Baseline and source limits

Research baseline: October 29, 2026. The sources below establish starting points for development. No physical device qualification has been performed in this project.

The requested [LPCWiki Fx0 page](https://lpcwiki.miraheze.org/wiki/LG_Fx0) returned HTTP 403. Nura's device wiki and current GitLab forge also blocked automated access. Recheck them from the development host before implementation. An inspected pmaports fork at commit `c8dafb0aedb685b61387c879c246fc46bc49b98c`, dated October 20, 2026, provides a recent snapshot; it is not proof of the live upstream branch state.

## Hardware facts

[KDDI's original product overview](https://news.kddi.com/kddi/corporate/english/newsrelease/2014/12/23/besshi844.html) identifies the LG Fx0 as an MSM8926 1.2 GHz quad-core device with approximately 1.5 GB RAM, 16 GB storage, a 4.7-inch IPS display, 8 MP rear and 2.1 MP front cameras, and a 2,370 mAh battery. Its [Japanese specification](https://news.kddi.com/kddi/corporate/newsrelease/2014/12/23/besshi843.html) lists microSDXC expansion up to 64 GB.

The historical [Fx0 deviceinfo](https://gitlab.com/postmarketOS/pmaports/-/blob/f1ebab347f7b456b60e45446f4e0cc785377873d/device/testing/device-lg-madai/deviceinfo) specifies `armv7`, a 720 by 1280 display, fastboot, and vendor boot-image configuration. Verify header parameters against this unit's original boot image before reuse.

The [vendor kernel](https://github.com/peremen/android-kernel-lg-madai) contains board sources under `arch/arm/boot/dts/msm8226-madai/`, including panel, input, power, USB, sensor, camera, and NFC descriptions. These require revision matching and translation into current bindings.

The [panel source](https://github.com/peremen/android-kernel-lg-madai/blob/main/arch/arm/boot/dts/msm8226-madai/msm8226-madai-panel.dtsi) describes JDI panel configuration. The [touch source](https://github.com/peremen/android-kernel-lg-madai/blob/main/arch/arm/boot/dts/msm8226-madai/msm8226-madai-input.dtsi) includes Synaptics S3320 and earlier S7020 configurations. The [power source](https://github.com/peremen/android-kernel-lg-madai/blob/main/arch/arm/boot/dts/msm8226-madai/msm8226-madai-pm.dtsi) includes revision-specific supplies and charger settings. These are hardware leads, not confirmation of the installed components or safe settings for a replacement battery.

## MPU-6515M and DMP follow-up (October 30, 2026)

The owner identifies the IMU as MPU-6515M and requires DMP access and DMP
interrupt wake. Physical identification, the M suffix, bus ownership and interrupt
routing remain to be verified. The pinned Linux 6.18.59
[`inv_mpu6050` family](https://github.com/gregkh/linux/tree/1253a6aa5d104312bf0992afacc15220ae35bdf9/drivers/iio/imu/inv_mpu6050)
matches MPU6515 over I²C/SPI and defines WHO_AM_I 0x74. This directory audit
finds raw-sensor support but no DMP firmware-loading/execution interface; a
matching device ID does not establish DMP functionality.

The historical InvenSense
[`inv_mpu6515` driver and README](https://android.googlesource.com/kernel/msm/+/04a77e80d63a6b792970c8567447f70d76ac7be4/drivers/iio/imu/inv_mpu6515/)
provide a primary implementation reference for DMP firmware, FIFO/events and
suspend handling. The repository commit is pinned in the source manifest; the
README Git blob is `0963954a844106b3cd1c61d1268b899d320d9aab`.
It is historical platform code, not proof of this unit's wiring, firmware
compatibility, redistribution rights or an acceptable modern upstream ABI.
The checked-out Fx0 vendor sensor DTS is empty and its tree does not contain
that IIO driver, so it does not resolve the physical control path. Inspection of
the privately preserved stock boot DT finds `qcom,msm-adsp-sensors` and no direct
MPU6515 compatible. Investigate ADSP sensor ownership/transport before AP bus
access. This node is a topology lead, not identification of the connected IMU,
proof that the node is active, or verification of the DMP interrupt route.

[Plan section 6.1](bringup-plan.md#61-mpu-6515m-dmp-access-and-interrupt-wake)
requires separate raw-data, DMP execution/output and actual DMP-event suspend-wake
evidence. These remain unverified acceptance gates.

The later [sensor work record](sensor-bringup.md) finds the original registry in
the `sns` partition, validates 72 static topology keys and records a guarded
native identity trial. ADSP shutdown succeeds, but low bus lines stop the trial
before any I2C transaction. Silicon identity, raw data and DMP/wake remain open.

## Existing operating system work

| Source | Established finding | Development use |
| --- | --- | --- |
| [Nura rename announcement](https://nura.eco/blog/2026/09/27/nura-rename/) | postmarketOS became Nura on September 27, 2026 | Search both project names and preserve actual repository/tool names |
| [Nura installation page](https://nura.eco/install/) | Current stable is v26.06; edge is development | Start from a coherent current stable system; refresh target at acceptance |
| [Archived Fx0 package snapshot](https://github.com/iLtanaka/pmaports/blob/c8dafb0aedb685b61387c879c246fc46bc49b98c/device/archived/device-lg-madai/APKBUILD) | Marked unmaintained; depends on vendor kernel and framebuffer helpers | Hardware/diagnostic reference, not final architecture |
| [Historical kernel APKBUILD](https://github.com/mainlining/pmaports/blob/danila/courbet/device/testing/linux-lg-madai/APKBUILD) | Linux 3.4.0; uses the peremen vendor tree and compiler/build patches | Recover known board configuration and diagnostic build history |
| [Earlier Fx0 Linux branch](https://github.com/omasanori/linux/tree/lg-madai) | Branch Makefile identifies Linux 6.9.1 | Recover earlier mainline work with attribution |
| [Earlier Fx0 DTS](https://github.com/omasanori/linux/blob/lg-madai/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts) | `lg,madai` board description enables UART and USB with PHY initialization | Minimal headless boot starting point; no complete hardware support implied |
| [lk2nd Fx0 source](https://github.com/msm8916-mainline/lk2nd/blob/main/lk2nd/device/dts/msm8226/msm8926-lg-madai.dts) | MSM8926 ID, board ID 150, volume GPIOs; DTB mapping remains a FIXME | Complete and test selection/handoff |
| [lk2nd original Fx0 commit](https://github.com/msm8916-mainline/lk2nd/commit/dcb17959b11b40f92e732b75f6993cde9e41fcf7) | Fx0 recognition added by Masanori Ogino in 2024 | Preserve attribution when extending it |
| [Shared MSM8226 kernel package](https://pkgs.nura.eco/package/main/postmarketos/armv7/linux-postmarketos-qcom-msm8226) | Package 6.16.12-r3 covers APQ8026/MSM8226/MSM8926 | Reproduce SoC baseline, then move needed support to maintained kernel |
| [MSM8226 kernel tree](https://github.com/msm8226-mainline/linux) | Inspected default branch is `qcom-msm8226-6.16.y`; inspected Qualcomm DTS directory lacks Fx0 board DTS | Recheck newer work and add/rebase missing board support |
| [Generic device package snapshot](https://github.com/iLtanaka/pmaports/blob/c8dafb0aedb685b61387c879c246fc46bc49b98c/device/testing/device-qcom-msm8226/deviceinfo) | Generic DTBs, ext2 boot filesystem, extlinux generation and MBR partition type | Prefer shared packaging where appropriate |

## Boot and recovery references

[Preserved Fx0 instructions](https://github.com/stephanfriedrich/ffos_on_lgfx0/blob/master/README.md) describe privileged ADB access, backing up LAF, clearing LAF to expose fastboot, and Volume Up plus USB entry. They also retain TWRP and Firefox OS update material. These are historical device-specific procedures: verify the actual partition map and recovery path before mutation. They do not justify applying another LG model's unlock procedure.

[lk2nd's README](https://github.com/msm8916-mainline/lk2nd/blob/main/README.md) describes a secondary bootloader loaded as an Android boot image, filesystem boot, and the distinction between stock and lk2nd fastboot writes. Its 512 KiB offset behavior matters for installation and restoration.

## Current platform and workflow references

- [pmbootstrap installation](https://docs.nura.eco/pmbootstrap/main/installation.html) and [usage](https://docs.nura.eco/pmbootstrap/main/usage.html): host setup, image generation/export, kernel configuration checks and flashing interfaces.
- [Branch rename announcement](https://nura.eco/edge/2026/03/15/pmaports-default-branch-changed/): pmaports and pmbootstrap moved their default branches to `main`.
- [Firmware packaging](https://docs.nura.eco/pmaports/main/packaging/firmware-packages.html): firmware packaging and loading unit-specific material from existing partitions.
- [Kernel archives](https://www.kernel.org/): at the baseline, 6.18 and 6.12 have maintained long-term releases; refresh versions during implementation.
- [Nura device categorization](https://docs.nura.eco/pmaports/main/packaging/device-categorization.html): packaging category, build, kernel and maintenance expectations. Complete hardware functionality does not automatically imply the organizational requirements of the `main` category.
- [Linux patch submission](https://docs.kernel.org/process/submitting-patches.html) and [DT binding submission](https://docs.kernel.org/devicetree/bindings/submitting-patches.html): current-tree bases, focused series, attribution, checking, routing, and schema requirements.

## Boot regressions to distinguish from board defects

Before edge testing, refresh [Nura's breakage reports](https://nura.eco/edge/). Recent relevant reports include [initramfs-extra compression](https://nura.eco/edge/2026/10/13/initramfs-extra-boot-broken/), [root filesystem identification](https://nura.eco/edge/2026/10/10/etc-os-release-symlink-boot-broken/), [F2FS boot](https://nura.eco/edge/2026/10/12/f2fs-tools-1.17.0-break-boot/), and [systemd nsresourced on older kernels](https://nura.eco/edge/2026/10/04/System-may-not-boot-on-kernels-older-than-7.2-with-recent-systemd-update/). Check the actual installed package versions and whether fixes have landed; do not preserve historical workarounds blindly.

## Questions resolved through implementation

- What firmware, board revision, root access, and recovery modes does the physical unit currently have?
- Which panel, touch, cameras, codec, sensors, and additional interfaces are actually installed/exposed?
- Can stock fastboot temporarily boot our diagnostic image, and can original boot/LAF be restored through a verified environment?
- Has newer upstream work completed or superseded the recovered Fx0 patches?
- What camera, modem, and power infrastructure remains missing on a maintained kernel?
- Which SIM/network or controlled test facility can qualify the cellular modes supported by this hardware?

Resolve these through host access, stock inventory, source comparison, and physical tests. They are tracked dependencies, not grounds to reduce the full-hardware objective.
