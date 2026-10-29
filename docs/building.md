# Building Fx0 diagnostic images

These images are development diagnostics. UART/USB are the only board functions described initially. A successful build does not establish physical boot or Nura hardware acceptance.

## Maintained Linux

Use the exact source commit in `evidence/2026-10-29-linux-image-build.json` from the [development fork](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-lts). The recorded initial build used Fedora Clang 21.1.8 and GNU make, plus the usual Linux host dependencies. The committed diagnostic configuration was derived from Nura's shared MSM8226 configuration, updated with Linux 6.18.59 `olddefconfig`, and enabled built-in configfs NCM/ACM USB diagnostics.

```sh
mkdir -p /tmp/fx0-storage/build/linux-6.18.59
cp configs/linux-6.18.59-fx0-diagnostic.armv7 /tmp/fx0-storage/build/linux-6.18.59/.config
make -C src/linux-stable O=/tmp/fx0-storage/build/linux-6.18.59 ARCH=arm LLVM=1 olddefconfig
make -C src/linux-stable O=/tmp/fx0-storage/build/linux-6.18.59 ARCH=arm LLVM=1 -j8 zImage qcom/qcom-msm8926-lg-madai.dtb modules
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

Use the DTB **basename**. Including the `msm8226/` directory in `LK2ND_DTBS` silently filters out the board and can still produce an unusable image. Verify that `qcdt.img` contains one entry and that its embedded `/lk2nd` compatible is `lg,madai`. The explicit `APPSBOOTHEADER_DIR` avoids a legacy relative-output assumption when the build output is absolute. Forced fastboot is for initial diagnostics; its removal needs its own boot/keys qualification.

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
