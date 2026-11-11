# Nura integration layer

**Update 2026-11-01:** `device-lg-madai` now replaces `device-qcom-msm8226` on
the phone and carries the deviceinfo, kernel cmdline, initramfs modules and
speaker UCM. The local deviceinfo, cmdline and module overrides are gone
([evidence](../evidence/2026-11-01-device-package-installed.json)). The tables
below are the original inventory, annotated.

The installed Fx0 ran Nura v26.06 with the generic `device-qcom-msm8226`
package plus hand-placed overrides. This inventory, taken on 2026-10-31 from
`apk audit` and the override directories, sorts each override into two groups:
what belongs in an Fx0 device package, and development fixtures that must go
before the final installation is qualified. A fresh install reproduces none of
it today.

## For an Fx0 device package

| Override | Content | Purpose |
| --- | --- | --- |
| `/etc/deviceinfo` | `deviceinfo_dtb="qcom-msm8926-lg-madai"`, `generate_extlinux_config="false"`, `generate_bootimg`, `flash_kernel_on_update`, `flash_bootimg_offset="524288"`, `append_dtb`, page size 2048, base 0 and the kernel/ramdisk/second/tags offsets | Raw boot image after the lk2nd prefix ([storage layout](storage-layout.md)); needs boot-deploy with the offset key and the pmaports schema entry — **in `device-lg-madai`** |
| `/etc/kernel-cmdline.d/50-device-qcom-msm8226.conf` | `earlycon console=ttyMSM0,115200 cma=256m` | Replaces the generic fragment without the obsolete `msm.allow_vram_carveout`/`msm.vram` — **in `device-lg-madai`** |
| `/etc/kernel-cmdline.d/60-fx0-stowaway.conf` | `pmos.stowaway` | `/boot` as a directory on the single root — **in `device-lg-madai`** |
| `/etc/kernel-cmdline.d/50-fx0-development.conf` (part) | `console=tty0`, `reboot=w` | Console on the panel; warm reboot (keeps ramoops) — **in `device-lg-madai`** |
| `/etc/fstab` | Root by UUID, no `/boot` line | Final single-root layout |
| `/usr/local/bin/sxmo_deviceprofile_lg,madai.sh` | Power/volume input names, scale 1.5, lisgd thresholds measured on the panel | Sxmo device profile; belongs in Sxmo's device profiles upstream |
| `/usr/local/libexec/fx0-sxmo-test` and `fx0-sxmo.desktop` | `WLR_RENDERER=gles2`, the display card's by-path node, `LIBSEAT_BACKEND=logind`, scale, `SXMO_NO_MODEM=1` | Session settings. The by-path node is needed because the GPU and display are separate DRM cards. `SXMO_NO_MODEM` goes when cellular works |
| `pmos@local-6ae3f5f3` key and local packages | boot-deploy 0.23.0-r1, kernel r8 | Until the changes are in Nura's repositories |
| `wlroots0.20` 0.20.2-r1 (fx0-pmaports `temp/wlroots0.20`, 2026-11-01) | Alpine 3.24 aport plus the gamma-reset fix | sway re-enables the panel at the first attempt; drop once the fix is in an Alpine wlroots release ([draft](../submissions/wlroots/README.md)) |
| `libcamera` 99990.7.1-r1 (fx0-pmaports `temp/libcamera`, 2026-11-01) | IMX179 sensor helper and tuning file | Rear-camera auto-exposure; until the helper is upstream in libcamera |

## Development fixtures to remove

| Fixture | What it does | Needed before removal |
| --- | --- | --- |
| `/etc/kernel-cmdline.d/60-fx0-native-display-test.conf` | `drm.debug=0x06 panic=60` | Display debugging; drop once display power transitions are qualified — **removed 2026-11-01** |
| `lk2nd.pass-simplefb=autorefresh`, `lk2nd.pass-ramoops` (in `50-fx0-development.conf`) | Early framebuffer and ramoops handoff for debugging | Decide after the display fixture goes; ramoops may stay as a feature — **kept and packaged**: lk2nd must fill the framebuffer node that holds the MDSS power domain |
| `SXMO_STATES=unlock` in the session wrapper | Keeps Sxmo from locking or suspending | Suspend and lock qualification |
| `/etc/sway/fx0-console.conf`, `/usr/local/libexec/fx0-sway-test` | Fallback console session | Not needed once Sxmo is the qualified session |
| `fx0-system-soak.sh`, `fx0-wifi-soak.sh` | Test harnesses | Keep in the repository; not part of an install |
| `*.fx0-before-*`, `*.pixman`, `*.noaudio` | Rollback copies made during bring-up | Delete after the final configuration is qualified |

## Order of work

1. **Done 2026-11-01.** The display holds and the UI gate are gone. The kernel
   startup fault was the MDSS power domain and bus clocks switching off under
   lk2nd's running display. Since r15 the board DT gives lk2nd's framebuffer
   node the MDSS GDSC and clocks, so simpledrm holds them until msm takes over.
   Twenty unattended boots (10 warm, 10 power-off) started Sxmo by themselves
   ([evidence](../evidence/2026-11-01-display-startup-fix.json)). The
   `99-fx0-display.modules` initramfs list stays for the device package.
2. **Done 2026-11-01.** `device-lg-madai-1-r1` (fx0-pmaports
   `integration/fx0-device` `b9491f835c90`) replaced `device-qcom-msm8226` in one
   apk transaction. The local deviceinfo, cmdline and module overrides and the
   debug cmdline are gone, and ten unattended boots passed
   ([evidence](../evidence/2026-11-01-device-package-installed.json)).
   `/etc/deviceinfo` has to stay, as the empty template: the initramfs file
   list includes it. Still local: the Sxmo device profile (headed for
   sxmo-utils, [draft](../submissions/sxmo-utils/README.md)) and the session
   wrapper settings.
3. Reinstall from scratch with that package and the final layout, then rerun
   the boot, Wi-Fi, Bluetooth, display, audio-service and soak checks.

## Hotspot default integration (2026-11-06)

The installed kernel's wcn36xx driver exposes no BIP cipher. A WPA2 hotspot
using NetworkManager's default PMF value fails AP initialization; setting the
driver-specific default to disabled allows that same unmodified profile to
activate. The tested file is installed at
`/usr/lib/NetworkManager/conf.d/50-wcn36xx-pmf.conf` and matches only
`driver:wcn36xx`. Explicit profile settings still follow NetworkManager's
normal precedence; this does not implement PMF support.

The file is included in the `device-lg-madai-1-r2` source candidate on local
fx0-pmaports branch `development/fx0-hotspot`, based on `integration/fx0-device`.
The phone still has r1 with this file copied to the intended package path;
no native r2 APK build/install is claimed. APKBUILD shell syntax, source
checksums and patch applicability pass. No existing packaged audio files were
changed or installed. See the [package diff](../patches/pmaports/device-lg-madai-wcn36xx-pmf.diff)
and [physical client evidence](../evidence/2026-11-06-hotspot-default-and-client.json).
Remove this default when wcn36xx provides working BIP support.

**Package follow-up:** `device-lg-madai-1-r2` is now built and signed in an
Alpine ARMv7 container (QEMU), verified and installed by the phone's apk-tools.
All eight package-file hashes matched the already installed contents before
the upgrade and the APK contents after reboot. Normal mkinitfs/boot-deploy
triggers ran, and the deployed boot image matched readback while the lk2nd
prefix and unused partition tail remained unchanged. The configuration is now
package-owned. Default `nmcli device wifi hotspot` succeeds after reboot with
the generated profile still at `pmf=0`. See
[package/update evidence](../evidence/2026-11-06-hotspot-package-installed.json).

## Fx0 Sxmo haptics profile

The existing `/usr/local/bin/sxmo_deviceprofile_lg,madai.sh` now exports the persistent PM8226 vibrator event path and strength 39168. The original profile is backed up on the phone. A graphical-user command through Sxmo's normal environment loader activates the vibrator and returns it off. The file remains a local device-profile override covered by the expanded upstream draft. The next native boot after the vibrator transfer timeout verifies that Sway inherits the device path and strength. The original boot, module and package hashes remain intact. The corrected driver RAM image did not reach BOOT. [Recovery evidence](../evidence/2026-11-10-vibrator-ram-transfer-timeout.json) [Procedure and evidence](../diagnostics/vibrator/README.md)


## Fx0 notification haptics and write completion

The installed `/usr/bin/sxmo_notifs.sh` has a backed-up local correction to handle close-write and atomic move events instead of attributes. The original is retained at `/var/tmp/fx0-notifications-01/sxmo_notifs.before.sh`. The login user's `sxmo/hooks/lg,madai/sxmo_hook_notification.sh` requests one 300 ms pulse and respects `.novibrate`. Only `superctl`'s notification service restarts; the existing Sway session stays active. Normal/muted/re-enabled real notifications pass, including exact Dunst replies, PMIC timing and cleanup. The APK database is unchanged: this file correction and user hook still need reproducible package/configuration integration for the final installation. [Repair and rollback](../diagnostics/sxmo-notifications/README.md)


**r7 packaging candidate:** The signed reproducible [Sxmo r7 manifest](../manifests/sxmo-utils-r7.json) now packages the profile and board notification hook and selects shared device hooks below user overrides. A temporary native probe of the exact packaged loader and helper passes normal/muted/re-enabled notifications. Both full source builds produce identical APKs, and offline resolution plans only the eight Sxmo upgrades. The phone still runs r6 with the existing local files; current phone/host backups and an isolated exact restoration rehearsal now pass. The controller and eight-package plan are staged and native preflight passes. Normal package deployment and retirement of the two superseded overrides await explicit approval after automatic review rejected the launch; no installation or service restart occurs. Later-session qualification remains open. [Preparation evidence](../evidence/2026-11-10-sxmo-r7-deployment-preparation.json)
