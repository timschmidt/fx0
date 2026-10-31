# Nura integration layer

The installed Fx0 runs Nura v26.06 with the generic `device-qcom-msm8226`
package plus hand-placed overrides. This inventory, taken on 2026-10-31 from
`apk audit` and the override directories, sorts each override into two groups:
what belongs in an Fx0 device package, and development fixtures that must go
before the final installation is qualified. A fresh install reproduces none of
it today.

## For an Fx0 device package

| Override | Content | Purpose |
| --- | --- | --- |
| `/etc/deviceinfo` | `deviceinfo_dtb="qcom-msm8926-lg-madai"`, `generate_extlinux_config="false"`, `generate_bootimg`, `flash_kernel_on_update`, `flash_bootimg_offset="524288"`, `append_dtb`, page size 2048, base 0 and the kernel/ramdisk/second/tags offsets | Raw boot image after the lk2nd prefix ([storage layout](storage-layout.md)); needs boot-deploy with the offset key and the pmaports schema entry |
| `/etc/kernel-cmdline.d/50-device-qcom-msm8226.conf` | `earlycon console=ttyMSM0,115200 cma=256m` | Replaces the generic fragment without the obsolete `msm.allow_vram_carveout`/`msm.vram` |
| `/etc/kernel-cmdline.d/60-fx0-stowaway.conf` | `pmos.stowaway` | `/boot` as a directory on the single root |
| `/etc/kernel-cmdline.d/50-fx0-development.conf` (part) | `console=tty0`, `reboot=w` | Console on the panel; warm reboot (keeps ramoops) |
| `/etc/fstab` | Root by UUID, no `/boot` line | Final single-root layout |
| `/usr/local/bin/sxmo_deviceprofile_lg,madai.sh` | Power/volume input names, scale 1.5, lisgd thresholds measured on the panel | Sxmo device profile; belongs in Sxmo's device profiles upstream |
| `/usr/local/libexec/fx0-sxmo-test` and `fx0-sxmo.desktop` | `WLR_RENDERER=gles2`, the display card's by-path node, `LIBSEAT_BACKEND=logind`, scale, `SXMO_NO_MODEM=1` | Session settings. The by-path node is needed because the GPU and display are separate DRM cards. `SXMO_NO_MODEM` goes when cellular works |
| `pmos@local-6ae3f5f3` key and local packages | boot-deploy 0.23.0-r1, kernel r8 | Until the changes are in Nura's repositories |

## Development fixtures to remove

| Fixture | What it does | Needed before removal |
| --- | --- | --- |
| `/usr/local/libexec/fx0-init` with `/etc/mkinitfs/files/99-fx0-display.files`, `modules/99-fx0-display.modules` and `hooks-cleanup/90-fx0-display-auto.sh` | Wraps the initramfs init to hold the display subsystem and MDP IOMMU runtime-PM `on` until the native framebuffer binds, then sets them to `auto` | Fix the kernel startup fault the hold works around ([GPU bring-up](gpu-bringup.md) and the display records), then boot repeatedly without it |
| `tinydm.service.d/50-fx0-first-start.conf` | `ConditionPathExists=/run/fx0-ui-start-ready`, `Restart=no`: the UI starts only on request | Show the session starts unattended at boot, across the reboot runs |
| `/etc/kernel-cmdline.d/60-fx0-native-display-test.conf` | `drm.debug=0x06 panic=60` | Display debugging; drop once display power transitions are qualified |
| `lk2nd.pass-simplefb=autorefresh`, `lk2nd.pass-ramoops` (in `50-fx0-development.conf`) | Early framebuffer and ramoops handoff for debugging | Decide after the display fixture goes; ramoops may stay as a feature |
| `SXMO_STATES=unlock` in the session wrapper | Keeps Sxmo from locking or suspending | Suspend and lock qualification |
| `/etc/sway/fx0-console.conf`, `/usr/local/libexec/fx0-sway-test` | Fallback console session | Not needed once Sxmo is the qualified session |
| `fx0-system-soak.sh`, `fx0-wifi-soak.sh` | Test harnesses | Keep in the repository; not part of an install |
| `*.fx0-before-*`, `*.pixman`, `*.noaudio` | Rollback copies made during bring-up | Delete after the final configuration is qualified |

## Order of work

1. Remove the display holds and the UI gate once the kernel startup fault is
   fixed, using the reboot harness to show unattended starts.
2. Package the first table as a device package. **Drafted:** `device-lg-madai`
   on fx0-pmaports `integration/fx0-device` (`c87f356c5d2a`), with the schema
   entry for `deviceinfo_flash_bootimg_offset`. It is built and signed
   (`device-lg-madai-1-r0`, sha256 `cbf35443…`) but not installed. Swapping it
   for `device-qcom-msm8226` must happen in one transaction because both ship
   `/etc/machine-info`. Also check whether the plain
   `/usr/share/deviceinfo/deviceinfo` file on the phone comes from the generic
   package. The Sxmo profile goes to sxmo-utils instead
   ([draft](../submissions/sxmo-utils/README.md)), which ships all device
   profiles. The session wrapper settings remain to be packaged.
3. Reinstall from scratch with that package and the final layout, then rerun
   the boot, Wi-Fi, Bluetooth, display, audio-service and soak checks.
