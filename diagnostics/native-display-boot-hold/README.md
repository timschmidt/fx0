# Temporary native Nura RAM boot

These are development workarounds for testing the native r1 package while the
intermittent initial DSI register-read failure remains unresolved. They are not
upstream fixes or the desired final power policy. They do not qualify suspend.
The files are intended for a controlled Fx0 initramfs, not another device's
normal installation.

`init` mounts sysfs before the original Nura init script starts udev or loads
MSM. On `lg,madai` it sets MDSS and IOMMU runtime policy to `on`, unmounts sysfs
and executes `/init.fx0-original`. Missing controls fail explicitly.
`90-fx0-display-auto.sh` runs as a mkinitfs cleanup hook. It restores both
controls to `auto` only after `fb0` identifies itself as `msmdrmfb`. An absent
native framebuffer leaves the temporary holds in place and reports the failure.
The eventual kernel fix must remove this workaround.

For a RAM test against a root filesystem whose installed kernel is older,
`85-fx0-ram-modules.sh` copies the complete matching native module tree to a
64 MiB tmpfs and moves that mount over the target root's existing module
directory before switch_root. This avoids mixing kernel/module releases and
keeps the older installed modules hidden for this boot. It does not install or
replace the old kernel package. This hook is specifically guarded for release
`6.18.59`; it is unnecessary after a normal matching APK installation.

The first generated image reaches systemd emergency mode: the owner sees an
unsupported Arbitrary Executable File Formats File System Automount Point error,
and SSH remains unavailable. A complete matching-module variant reaches the
pre-root debug shell and binds native DRM. Its larger ramdisk overlaps the
inherited framebuffer, however, causing a reservation failure and memremap
warning. Changing the Android header load address does not move it: this lk2nd
target overrides it, and the live chosen initrd address confirms 32 MiB.

The working RAM variant omits 36 identical module files from the appended
archive and compresses both newc members together using XZ with CRC32. Its
17,819,112-byte ramdisk ends at 0x030fe5e8, below the framebuffer at 0x03200000.
Native CONFIG_RD_XZ is enabled. The debug shell verifies kernel taint 0 and
msmdrmfb. After continuing, the module overlay is mounted, both initial holds
are released, all four display controls are auto, and SSH works. The owner
confirms a readable login/text console. At the observed systemd check there
are no failed units; time synchronization remains pending without an upstream
network. This is one boot with a workaround, not startup/suspend qualification.
Normal Nura startup writes mutable root state even though the boot image was
loaded from RAM. The installed kernel package/boot configuration are unchanged.

## Reproduction inputs

Use the exported, signature-verified native APK from source
`476e36e72527b4115b656117634fb17a4b6e77dc`, release `6.18.59`, and its matching
modules. The physical test APK is
`linux-postmarketos-qcom-msm8226-6.18.59-r1.apk`, SHA256
`0ca7a2e3f1b3504cbf46a5fbd430895305adf2fb4286018828996291615dd633`.
It is distinct from the host-built full44 or pmdebug1 module sets.

Generate using installed mkinitfs2.11 and boot-deploy0.23, with the root mounted
read-only and all changes bound from RAM. Bind writable tmpfs directories over
the chroot's `/tmp` and `/boot`, copying the native package's kernel/DTBs into
the latter. A rootfs bind mount was rejected by BusyBox df; explicit tmpfs
mounts pass the normal free-space checks. Bind a RAM `kernel.release` containing
`6.18.59`, the matching module tree with normal depmod metadata, a copied
mkinitfs configuration and a copied deviceinfo file. Override deviceinfo with
`deviceinfo_flash_kernel_on_update="false"` and
`deviceinfo_generate_extlinux_config="false"` for this generation only.

Add the following to `/etc/mkinitfs/files/99-fx0-display.files`, using a RAM
copy of this directory:

```text
/usr/share/initramfs/init.sh:/init.fx0-original
/tmp/fx0-init:/init
```

Place the executable prefix at `/tmp/fx0-init` inside the chroot. Install the
executable cleanup hook in the copied `/etc/mkinitfs/hooks-cleanup/`. Include
`panel_lg_fx0`, `qcom_wled` and `rmi_i2c` in an additional mkinitfs module list.
Run `mkinitfs -d /boot`; the ordinary boot-deploy path copies archives to tmpfs
without flashing. In this mkinitfs version, `-no-bootdeploy` removes the temporary
work directory without exporting the generated archive, so it is unsuitable
for retrieving this test image.

Inspect the generated archive: both init scripts and cleanup hook must match
their source bytes, all module paths must use the native release, and the Fx0
panel/backlight/input modules must be present. For the complete-module variant,
include every native module and regenerate normal dependency indexes; the host
and target kmod versions used here are both 34.2. Include the module-overlay hook
and its empty `/fx0-ram-modules` mountpoint. The first full-module variant appended a complete gzip/newc member, duplicating
some module files. The working image instead appends only new or different
entries to the original uncompressed newc archive, omits 36 identical module
files and compresses the two members together using XZ/CRC32. Inspect both newc
members and compare the final module tree against every native module and
metadata file;438 files pass in this test.


Build an Android v0 RAM image with the exact native kernel and Fx0 DTB using
[make_diagnostic_image.py](../../scripts/make_diagnostic_image.py), preserving the
measured native Nura root/boot discovery command line privately. Use
`pmos.debug-shell` for the debug variant. Check both image size and actual ramdisk memory placement. This lk2nd target
forces the load address to0x02000000 regardless of the header. An inherited
framebuffer begins at 0x03200000, so the compressed ramdisk must be at most 18 MiB
when passing it to Linux. Changing the header is insufficient. The image helper
now rejects this overlap. XZ support must be enabled in the exact target kernel. Save hashes, boot from selected fastboot, and inspect the
initramfs log, module release, native framebuffer, PM controls and root discovery
before continuing. Keep a working RAM recovery image available and capture
retained logs before the next boot. No installed boot configuration or GPT
change is required for this test.
