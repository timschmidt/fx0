# lk2nd draft submission

Three changes for [lk2nd](https://github.com/msm8916-mainline/lk2nd), based on
`main` at `fd380ac637d1af38598e3f3c5321d4c962b96315` (unchanged upstream as of
October 31, 2026). lk2nd takes pull requests on GitHub. **Not sent:** opening
the pull request needs the owner's approval.

The [submission branch](https://github.com/timschmidt/fx0-lk2nd/tree/submission/fx0-rawboot-pon)
is `8fbf21a4fd2d`. Its tree is identical to the build installed on the Fx0
(`integration/fx0-pon-reboot` 079eebe); only the commit messages were updated
with the hardware results.

1. [Select the Linux device tree for the LG Fx0](0001-dts-msm8226-Select-Linux-device-tree-for-LG-Fx0.patch):
   sets `lk2nd,dtb-files` to `msm8926-lg-madai`. The matching Linux board file is
   not in mainline yet, so this can wait for it or go in alone.
2. [`LK2ND_EXTLINUX=0`](0002-boot-Allow-excluding-extlinux-filesystem-discovery.patch):
   a build option to skip filesystem discovery and boot only the Android image
   at the 512 KiB offset. The default keeps the current behaviour.
3. [`LK2ND_PON_REBOOT_MODE=1`](0003-aboot-Optionally-honour-the-PON-spare-reboot-reason.patch):
   also reads the reboot reason from the PMIC PON spare register when the IMEM
   reason is empty. The LG stock bootloader consumes the IMEM reason before
   lk2nd runs. The default is off.

## Checks

- **Hardware (LG Fx0, MSM8926):** the installed prefix is built from this tree
  with `LK2ND_EXTLINUX=0 LK2ND_PON_REBOOT_MODE=1`. It boots Linux from the
  Android image on warm and cold starts (20 consecutive warm reboots passed).
  Volume Down enters fastboot from a cold start, and `systemctl reboot
  --reboot-argument=bootloader` reaches fastboot through the PON register. See
  the [installation](../../evidence/2026-10-31-lk2nd-production-install.json),
  [key entry](../../evidence/2026-10-31-lk2nd-key-entry.json) and
  [remote bootloader](../../evidence/2026-10-31-remote-reboot-bootloader.json)
  evidence.
- **Default builds:** `lk2nd-msm8916` built from the same path at the base and
  at this branch with default options has identical symbol sizes. The only
  instruction differences are `__LINE__` constants in `aboot.c` shifted by the
  four added lines.
- **Option checks:** invalid values for either option stop the build.
- **Reproducibility:** with the same toolchain the base Fx0 configuration
  rebuilds the previously installed image bit for bit.
- **Patch check:** `git am` of the exported patches on the base reproduces the
  branch tree.

The patches carry no Signed-off-by; the owner adds it before sending.
