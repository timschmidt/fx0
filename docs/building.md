# Building Fx0 diagnostic images

These images are development diagnostics. UART/USB are the only board functions described initially. A successful build does not establish physical boot or Nura hardware acceptance.

## Maintained Linux

Use the current exact source commit in `manifests/sources.json` and `evidence/2026-10-29-current-kernel-build.json` from the [development fork](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-lts). The recorded initial build used Fedora Clang 21.1.8 and GNU make, plus the usual Linux host dependencies. The current `simplefb` diagnostic configuration was derived from Nura's shared MSM8226 configuration, updated with Linux 6.18.59 `olddefconfig`, and enabled built-in configfs NCM/ACM USB diagnostics.

```sh
mkdir -p /tmp/fx0-storage/build/linux-6.18.59
cp configs/linux-6.18.59-fx0-diagnostic-simplefb.armv7 /tmp/fx0-storage/build/linux-6.18.59/.config
make -C src/linux-stable O=/tmp/fx0-storage/build/linux-6.18.59 ARCH=arm LLVM=1 olddefconfig
make -C src/linux-stable O=/tmp/fx0-storage/build/linux-6.18.59 ARCH=arm LLVM=1 -j8 zImage dtbs modules
```

The original build output lived at `/tmp/fx0-linux-lts`, then moved to Disk B after completion, retaining that old path as a symlink. Build timestamps and embedded host identity affect byte reproducibility; retain the exact artifacts/hashes used for each physical test rather than claiming independently identical binaries. No kernel module signing keys are published.

## lk2nd

Check out the pinned lk2nd base and apply `patches/lk2nd/0001-select-fx0-linux-device-tree.patch`, or use the public integration commit in the manifest. Build the secondary variant, leaving the stock primary bootloader intact:

```sh
make -C src/lk2nd \
  BOOTLOADER_OUT=/tmp/fx0-storage/build/lk2nd \
  APPSBOOTHEADER_DIR=/tmp/fx0-storage/build/lk2nd/build-lk2nd-msm8226 \
  TOOLCHAIN_PREFIX=arm-none-eabi- \
  LK2ND_DTBS=msm8926-lg-madai.dtb \
  LK2ND_VERSION=fx0-fd380ac6 \
  LK2ND_FORCE_FASTBOOT=1 lk2nd-msm8226 -j8
```

Use the DTB **basename**. Including the `msm8226/` directory in `LK2ND_DTBS` silently filters out the board and can still produce an unusable image. Verify that `qcdt.img` contains one entry and that its embedded `/lk2nd` compatible is `lg,madai`. The explicit `APPSBOOTHEADER_DIR` avoids a legacy relative-output assumption when the build output is absolute. Forced fastboot was used for initial diagnostics. A separate build with `LK2ND_FORCE_FASTBOOT=0` was installed and automatic Nura warm boot verified. Native display investigation temporarily reinstalls the verified forced-fastboot prefix so failures return to the menu. Full cold/key recovery qualification remains pending.

## Nura rootfs

The initial rootfs uses the verified live `v26.06` pmaports branch and pmbootstrap 3.12.1. Configure vendor `qcom`, device `msm8226`, console UI, developer USB profile, and a private development SSH key. Persistent work path is `/tmp/fx0-storage/pmbootstrap`. Initial installation creates a rootfs without writing any device: `pmbootstrap install --no-image --add busybox-static`. Authentication secrets/config stay under ignored `local/`.

The stable generic package currently supplies Linux 6.16.12. Creating that rootfs does not meet the maintained-kernel endpoint: deploy and package the maintained Fx0 kernel, correct DTBs and modules before qualifying an installed Nura system. The full graphical interface follows display/touch enablement.

## RAM diagnostic image

The image builder validates the ARM zImage, FDT and static ARM ELF inputs, then constructs a deterministic gzip/newc initramfs and legacy Android v0 header using the verified Fx0 load addresses. It performs no device writes:

```sh
python3 scripts/make_diagnostic_image.py \
  --kernel /tmp/fx0-linux-lts/arch/arm/boot/zImage \
  --dtb /tmp/fx0-linux-lts/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb \
  --busybox /tmp/fx0-storage/artifacts/busybox-static-armv7 \
  --simplefb \
  --output /tmp/fx0-storage/artifacts/fx0-linux-diagnostic.img
```

Use `--simplefb` only with built-in simpledrm. It requests lk2nd's inherited framebuffer console; this is an early diagnostic, not native DRM/panel qualification. Initial diagnostics provide an unauthenticated root shell on USB ACM and HTTP status/logs at `172.16.42.1` on the isolated USB NCM link. Keep these images for attended physical development; normal Nura uses the separately configured SSH key and login policy. No eMMC filesystem is mounted by the diagnostic initramfs.

The initial image was independently unpacked with host `cpio`, checked for Android header alignment, and its init script checked with `sh -n`. Each boot record must identify the exact generated image hash; subsequent source builds overwrite the shared kernel output.

For automatic persistent-log capture, build `INPUT_PM8941_PWRKEY=y` into the standalone kernel (the shared configuration normally makes it a module). Apply `configs/diagnostic-warmreset.fragment` with the kernel configuration tools and rebuild. `--return-after 90 --usb-debug` generates a diagnostic init that requests a warm reboot after 90 seconds, with verbose USB probe logging and `reboot=w`. The intended next step is lk2nd `oem ramoops console` followed by `get_staged`; successful RAM retention must be verified on this boot chain. Warm reboot and complete console/raw ramoops retrieval are now physically verified.

The initial rootfs contains 399 packages on Alpine 3.24.3, including systemd 261. The stable OS branding files still say postmarketOS v26.06. Its exact package/repository manifest is recorded in `evidence/2026-10-29-nura-rootfs-packages.json`. This is an isolated chroot artifact, not an on-device installation claim.

The Linux source and output now live together at `/tmp/fx0-storage/src/linux-stable` and its `.output` directory, with `src/linux-stable` and the original output aliases retained as symlinks. This layout supports pmbootstrap `build --envkernel` packaging. The source move caused one full rebuild because recorded compiler paths changed; keep the canonical layout stable for subsequent incremental work.

For current physical images, use the pinned integration branch. The original `patches/linux-stable` source-subset candidate is a historical DTB check and lacks the SMEM, VBUS, storage and firmware-hole fixes. Apply the ordered `patches/linux-integration` followups in a full source checkout when reproducing those changes manually.

The maintained Nura package is developed in the public pmaports fork on `integration/fx0-v26.06`. Its source archive pins the Linux integration commit and records SHA-512 alongside the updated configuration. For a normal native package build, use `pmbootstrap build linux-postmarketos-qcom-msm8226`; Strict native clean builds now pass for both the preceding integration revision and the exact latest regulator-load fix. Final hardware, update/recovery and submission-base qualification remain separate. The initial development APK uses `build --envkernel` to package the verified host build. On this glibc host, that path needed an Alpine-built signing helper and a temporary private signing-key copy readable by the chroot's `pmos` UID (12345). The host helper was restored and the temporary key copy removed after packaging. The original key's permissions were preserved.

`pmbootstrap kconfig check linux-postmarketos-qcom-msm8226` now passes. Linux 6.18's explicit legacy xtables gate and dependent modules had to be enabled after olddefconfig migration; those are required by the current Nura checks. Remaining preference messages for built-in USB gadget support and modular optional filesystems are informational.

Use `pmbootstrap install --no-split` for the generic MSM8226 image containing the ext2 boot and root subpartitions. A development command-line drop-in at `/etc/kernel-cmdline.d/50-fx0-development.conf` requests inherited framebuffer, ramoops and warm reboot support. Verify the generated extlinux configuration contains the Fx0 DTB search path and correct root/boot UUIDs. The combined image must fit entirely within the independently reverified `userdata` partition before any deployment.

The installed console development system now uses the `postmarketos-base-nosplash` provider after a Plymouth crash. Keep the four development command-line entries shown above; the trial `clk_ignore_unused` and `pd_ignore_unused` flags did not restore visible display and have been removed. The owner still sees a blank screen despite working SSH. Final native display support remains required.

## Experimental display IOMMU build

The native panel candidate on `integration/fx0-lts` fails at the maintained MDP5 IOMMU requirement. The separate public `integration/fx0-iommu` branch, pinned by `evidence/2026-10-29-display-iommu-candidate.json`, carries the upstream QSMMU dependencies plus MSM8226-specific configuration/wiring. Its kernel/module build and targeted schema checks pass; it has not yet passed physical scanout or a Nura package boot. Keep the previous diagnostic artifacts frozen.

Use a separate full source worktree/output to preserve the verified baseline. Starting from this repository's diagnostic config, enable `CONFIG_QCOM_IOMMU=y` with the kernel `scripts/config` tool and run `olddefconfig`, then build `zImage modules qcom/qcom-msm8926-lg-madai.dtb` with `ARCH=arm LLVM=1`. Record the resulting exact source/config/artifact hashes. For controlled testing, generate a RAM diagnostic with `--return-after 180`; load matching signed modules only after USB log capture is established. The image generator now advertises 500 mA using ConfigFS's milliamps unit; it does not itself implement charger-current negotiation.

## Optional raw-image boot preparation

The separate public lk2nd branch `integration/fx0-rawboot` at `b106e16d0f3fc0e11c55aa58e4c617b89a0e3ef5` adds `LK2ND_EXTLINUX=0`. Use the existing MSM8226 recipe with that option and a separate output directory to omit filesystem discovery. Default `1` retains the existing path. Both configurations and a disabled-search/forced-fastboot diagnostic configuration build; invalid values are rejected. Check `evidence/2026-10-29-lk2nd-rawboot-preparation.json` for the exact artifacts. These are host-built preparation images and have not been flashed.

For a future controlled raw-image test, the forced-fastboot variant permits explicitly selecting `fastboot continue` while automatic diagnostic reboots return to the menu. Its virtual boot partition still starts at the existing 512 KiB offset. Validate that handoff, offset writes/readback and physical key/cold recovery before enabling a normal raw-image configuration. A host regular-file test with the actual RAM image validates updater byte preservation only.


## Display power candidate

The latest RAM-tested display source is `integration/fx0-display-power` at
`476e36e72527b4115b656117634fb17a4b6e77dc`. It includes the camera DT on top of
compiled39, panel shutdown ordering and the shared CPU-PLL L8 supply fix.
Image26 deliberately retains the compiled39 kernel/initramfs and changes only
the DTB; it loads the exact39 signed panel candidate and original MSM module.
It is not an installed Nura update. One complete CRTC off/on visibly passes;
three additional cycles complete with automatic MDSS/IOMMU PM. Full kernel44
build/package/boot qualification follows separately.
