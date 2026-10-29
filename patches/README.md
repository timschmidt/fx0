# Fx0 development patches

These patches are implementation candidates, not qualified upstream submissions. They have not been booted on the physical Fx0 or tested as complete kernel/lk2nd images. They include a Linux 6.18.59 LTS target and the earlier shared SoC development reference. A complete maintained kernel installation remains required for final acceptance.

## Maintained Linux target

`linux-stable/0001-document-lg-fx0-compatible.patch` adds `lg,madai` to the MSM8926/MSM8226 compatible tuple in the Qualcomm board binding. `linux-stable/0002-restore-fx0-uart-usb-device-tree.patch` adds the recovered board DTS and its DTB build entry against Linux 6.18.59, commit `1253a6aa5d104312bf0992afacc15220ae35bdf9` in the stable maintainer's tree.

The default build command below uses this maintained source target. Both the unchanged SoC baseline and the Fx0 candidate compile with the same four DTC warnings; the board adds none. The patched YAML parses and contains the expected compatible tuple. Full schema checks, complete kernel builds, and physical tests remain pending. See the [maintained-kernel report](../evidence/2026-10-29-maintained-device-tree-build.json).

The shared SoC development tree still contains wireless definitions missing from this LTS tree. Carrying the necessary SoC support forward is a separate task; the minimal DTS alone cannot provide all hardware support. See the [kernel gap assessment](../docs/kernel-gaps.md).

## Linux

`linux/0001-restore-fx0-uart-usb-device-tree.patch` restores the minimal UART/USB board description from Masanori Ogino's earlier [Fx0 Linux branch](https://github.com/omasanori/linux/blob/17429c77ef96df09f6bbf21360d0f6a235463d1c/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts) and adds its DTB build entry to the pinned MSM8226 tree. The board source retains its original copyright and BSD license. Recover the original Git commit and attribution when preparing the actual kernel series.

The tree enables neither storage nor the remaining peripherals. It is intended to establish a headless diagnostic boot once recovery and image handoff have been verified. Binding/schema checks, full kernel builds, current maintainer-tree rebasing, and physical tests remain outstanding.

## lk2nd

`lk2nd/0001-select-fx0-linux-device-tree.patch` fills the existing Fx0 entry's `lk2nd,dtb-files` property with `msm8926-lg-madai`. This follows lk2nd's [documented filename convention](https://github.com/msm8916-mainline/lk2nd/blob/fd380ac637d1af38598e3f3c5321d4c962b96315/Documentation/dt-bindings.md), which omits `qcom/`, `qcom-`, and `.dtb` from the selector.

Stock bootloader loading, device matching, full image build, and actual Linux file selection still require device tests. Do not infer boot success from successful DTB compilation.

## Reproduction

The exact upstream commits and source-file Git blob hashes are recorded under `manifests/`. With host network access, fetch the minimal public source subset and compile the DTBs:

```sh
python3 scripts/fetch_sources.py
python3 scripts/build_device_trees.py
```

With an existing cache, verify it without network access:

```sh
python3 scripts/fetch_sources.py --verify-only
```

To reproduce the older shared SoC reference separately:

```sh
python3 scripts/build_device_trees.py --linux-source linux --output build/device-trees-reference
```

The build requires Python 3, Git, GCC, the C preprocessor, Bison, and Flex. It builds the device-tree compiler from pinned kernel sources. Source caches and build products stay in ignored directories. The script checks patch application, compiles an unchanged SoC baseline, compiles both Fx0 candidates, and reports any additional Linux DTC warnings. These checks do not replace schema or hardware validation.
