# LG Fx0 Nura bringup

Bring a physical LG Fx0 LGL25 to the current Nura release with all hardware working, reliable updates, and patches prepared for submission to the appropriate upstream projects. Development takes place in this folder.

The device is available for development and flashing. No personal data needs to be retained. Original firmware and device calibration must still be preserved for recovery and hardware operation. No SIM is currently available; cellular acceptance remains pending until it can be tested.

## Project documents

| Document | Purpose |
| --- | --- |
| [Bringup plan](docs/bringup-plan.md) | Ordered implementation steps, dependencies, recovery requirements, and completion criteria |
| [Storage consolidation](docs/storage-layout.md) | Measured root layout, boot-image update preparation and remaining restoration gates |
| [Stock hardware](docs/stock-hardware.md) | Physical inventory and implications for board support |
| [Hardware acceptance](docs/hardware-acceptance.md) | Full hardware inventory and tests required before declaring completion |
| [Upstream development](docs/upstream-development.md) | Public repository structure, patch ownership, validation, and submission preparation |
| [Research](docs/research.md) | Source references, recovered work, and facts that need physical confirmation |
| [Device operations](docs/device-operations.md) | Read-only inventory, verified partition backups, and helper usage |
| [Image builds](docs/building.md) | Full diagnostic kernel/lk2nd recipes and rootfs preparation |
| [Development patches](patches/README.md) | Initial Linux and lk2nd candidates with reproducible DTB checks |
| [Development log](docs/development-log.md) | Observed device/host state, completed checks, and the next executable work |
| [Battery work](docs/battery-bringup.md) | Stock pack/profile evidence, current sensing, native BMS and charging sequence |
| [Camera work](docs/camera-bringup.md) | Confirmed sensor IDs, wiring, capture-engine gaps and verified private EEPROM readbacks |
| [Kernel gaps](docs/kernel-gaps.md) | Maintained-kernel target and missing shared SoC/camera infrastructure |

## Current state

Nura v26.06 now boots from eMMC through lk2nd with the signed native
`linux-postmarketos-qcom-msm8226-6.18.59-r4` package, matching persistent modules,
SSH, native 720×1280 DRM and a Sxmo terminal/keyboard using Pixman. Kernel taint
is 0. The installed r3 physical test confirms typing, both keyboard gestures,
and matched Home/VolumeDown/VolumeUp input; r4 retains that exact DTB. Its new
IADC correction passes actual-function regression tests and signed native
conversion-log checks. Current source/artifact pins and limits are recorded in
[the manifest](manifests/sources.json) and
[r4 evidence](evidence/2026-10-30-native-r4-installed-boot.json).

A frozen, self-contained r3 rescue now boots from its saved filesystem entry
after the r4 module update, with 22 embedded signed modules, no installed-root
mount, all 42 exposed internal eMMC block nodes read-only, and taint 0. A bounded
boot-only repair restores the normal menu and returns storage to read-only;
raw boot and GPT readbacks match. The earlier native16 fallback fails startup
acceptance and remains unqualified. See
[recovery results](evidence/2026-10-30-standalone-rescue.json).
Independent package/root rollback and factory-stock restoration still require
rehearsal; this result does not close those gates.

Initial display loading still needs a temporary initramfs power hold; it releases
after DRM binds and all four display controls become automatic. Controlled native
display off/on and touch tests pass, but startup without the workaround, full
suspend and reliability remain open. The Fx0 gesture profile is physically
confirmed on r3. GPU acceleration is disabled; software rendering and development
idle/suspend restrictions remain in use. UPower r3 avoids the observed incomplete-
battery NaN/false shutdown, with 90 configured Linux tests passing. Battery capacity
is still unknown. The generic charger alternates Charging/Good and
Discharging/Overheat near room temperature; no safety thresholds are bypassed.
The native non-VM BMS now has verified coherent output capture and a stock-kernel
RAM baseline. Separate IIO reference/voltage patches pass brief RAM hardware tests;
the new battery voltage inputs also pass standard millivolt/consumer-precision
checks. Protected trim and source-epoch experiments establish load-responsive
BMS current/counter data and the required forced restart writes. The installed
r4 package is unchanged. Calibrated fuel-gauge reporting, thermistor
protection and automatic USB current negotiation remain open. Stock uses software
charging limits in addition to extended hardware comparators; those hardware
limits are not enabled by themselves. RAM thermistor conversion and three
standard charge-inhibit/resume cycles now pass. Stock reproduces the native
window's HOT trip around 31.6°C; complete native temperature/fault/suspend policy
is still required. Separate generic Charger Manager fault fixes pass host/ARM
checks but are not loaded on the phone. See [battery work](docs/battery-bringup.md).

Stock inventory, 29 critical partition backups, GPT metadata and a separately
verified 1 GiB original-system image are private. A complete **development-state**
snapshot of the 15,758,000,128-byte eMMC user area and both 4 MiB boot areas passes
two independent device reads and verified copies on two host filesystems, with
all eMMC filesystems unmounted. Original userdata was not captured before its
authorized Nura overwrite; an untouched full stock image is not claimed. Exact
pre-r4 boot/modules/configuration and the r3 APK also have verified two-filesystem
rollback copies. Development and backups use `/run/media/tim/Disk B/fx0` through
`/tmp/fx0-storage`; re-establish that bind mount after a host reboot.

All four CPUs and eMMC HS200 are operational in development tests. Earlier full
image write/readback and selected storage/USB tests pass, with sustained I/O still
open. Native CCI EEPROM reads match two complete private 64 KiB captures; this does
not qualify camera streaming, CAMSS, OIS or calibration validity. Wi-Fi/Bluetooth,
audio, sensors, cameras, NFC/haptics, cellular/GNSS, SD/OTG and the remaining
[hardware acceptance matrix](docs/hardware-acceptance.md) need further work.
No SIM is available for final cellular network acceptance. No unattended/cold
startup, full suspend or final reliability qualification is claimed.

The host-only storage preview combines adjacent Android payload partitions into
one approximately 14.30 GiB modern ext4 root. GPT/filesystem checks and embedded
readback pass. The proposed raw-boot updater preserves lk2nd's prefix and may
avoid a separate boot filesystem; its source CI passes, while physical final-
layout boot/update/recovery and the minimum retained-partition audit remain open.
**No repartitioning has occurred.** The [plan](docs/bringup-plan.md), section 2.1,
requires complete restoration coverage and demonstrated factory-stock rollback
before that migration. External SD will remain ordinary removable Linux media.

Public source, recipe and diagnostic changes are being committed for eventual
upstream review. PR/email submission, final series qualification and personal DCO
certification remain separate unfinished work. Current recipes are in
[the build guide](docs/building.md); the dated minimal DTB fixture is retained
for historical reproduction and lacks the later physical bringup fixes.

## Local and public material

Keep reproducible source changes, documentation, sanitized test evidence, and source revisions in public Git repositories. Keep original device dumps, calibration, identifiers, credentials, firmware without redistribution rights, build products, and full source checkouts in ignored local directories. The initial [ignore rules](.gitignore) establish that separation; inspect every staged change before committing.

The root Git working tree is initialized. Public repository URLs and tested revisions are recorded as they are provisioned; upstream submissions remain a separate final step.

## Licensing

Original coordination documentation and helper code use the [MIT license](LICENSE). Third-party patches and recovered device descriptions retain the licenses and copyright notices of their respective projects/files. The root license does not relicense those materials or device firmware.
