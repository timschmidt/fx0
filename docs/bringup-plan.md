# LG Fx0 Nura bringup plan

## Objective and completion

Develop in this repository's workspace and publish the resulting development history in repositories intended for upstream contribution. The endpoint is a fully updated Nura installation on the physical LG Fx0 LGL25, all hardware qualified, and complete patch series ready for Nura, Linux, lk2nd, and any affected userspace projects.

The owner permits flashing and development against the device. No personal data requires preservation. Keep firmware, calibration, and recovery backups because they are needed to operate and restore the hardware. No SIM is available at the planning baseline; this prevents final cellular qualification but does not prevent the rest of the work.

Completion requires all of the following:

- The newest stable Nura release available at acceptance, with current packages from its supported repositories. Development and compatibility testing also cover current edge. Record the exact release and acceptance date rather than treating v26.06 as a permanent target.
- A maintained Linux kernel with current fixes and the necessary hardware patches. Historical 3.4, 6.9.1, and 6.16 baselines can help diagnosis, but are not the maintenance endpoint.
- Every physically present hardware function passes the [hardware acceptance matrix](hardware-acceptance.md), including cameras, charging, suspend, cellular data and calls where the network supports them, and peripheral interactions.
- Installation, recovery, kernel updates, userspace updates, and a clean rebuild work from the documented procedure. No essential operation depends on an undocumented manual fix.
- Verified backups and a rehearsed factory-stock restoration precede final repartitioning. The final layout uses one large native Linux root filesystem across all safely reclaimable eMMC space, with the fewest additional boot/firmware/calibration partitions the device actually requires. External microSD is ordinary removable Linux media; it is not required for boot or used as Android-style internal storage.
- Public development commits preserve attribution and licenses. Each outstanding upstream change has a suitable base, tests, dependency description, and reviewable submission material as specified in [upstream development](upstream-development.md).
- Kernel submission branches apply to the appropriate current maintainer trees. A functional Nura integration branch alone is insufficient for kernel submission readiness.

Upstream acceptance and merge timing are controlled by maintainers. The project can finish with submission-ready changes that have not yet been merged. The absence of a SIM leaves cellular tests pending and therefore prevents claiming the full hardware objective complete. A feature can be marked absent only with device evidence; difficulty implementing it is not grounds to remove it from scope.

## Implementation checkpoint on October 30, 2026

Phase 0 has verified selected original-partition/GPT backups and a tested original-image write/read path, installed lk2nd and public repositories. Complete factory-stock restoration coverage and rehearsal remain required by section 2.1. Phase 1 has reached maintained Linux diagnostic userspace, four CPUs, inherited framebuffer, USB NCM/ACM, and 200 MHz HS200 eMMC reads. Both complete stock firmware memory exclusions are required; after fixing them, two 1 GiB reads match the original-system backup. These are initial tests, not final reliability acceptance.

Phase 2 now runs installed Nura v26.06 with the signed 6.18.59-r4 kernel,
matching modules, SSH, native 720×1280 DRM and a Sxmo terminal/keyboard using
software rendering. The installed r3 physical test confirms typing, keyboard
gestures and Home/Volume buttons; r4 retains that DTB. Taint is zero after normal
boots. Full-image write/readback, root expansion within userdata, repository
refresh, filesystem persistence and a self-contained filesystem rescue have
passed their documented tests. Package/root rollback and factory-stock rehearsal
remain open. The final partition layout has not been applied.

Display startup still uses temporary power holds, released after binding so all
four display controls become automatic. Controlled RGB/off-on/touch tests pass;
startup without the workaround, the observed INTF1 underrun, full suspend and
reliability remain open. The owner's later console photograph confirms readable
text outside the GUI. See the [warning audit](kernel-gaps.md).

Power work has signed IADC corrections, experimental BMS/thermistor measurements
and a RAM-tested standard charge-inhibit actuator. The original stock kernel
reproduces a hardware HOT trip around 31.6°C under native's comparator window;
stock uses a wider window plus LG software policy. Native still needs complete
temperature/fault/suspend protection before adopting that wider range. Generic
Charger Manager prerequisites have host/ARM tests but are not enabled on device.
Current/capacity accuracy and automatic USB budgeting remain open. See
[battery bringup](battery-bringup.md). The later hardware, storage, reliability
and upstream-submission phases remain in scope; no SIM is available for final
cellular acceptance.

Runtime pack-profile handoff now passes through RAM firmware and installed r4,
including all 155 source OCV points and standard design attributes. The firmware
is not installed persistently, and no state-of-charge estimate or usable UPower
battery interface is qualified by that result. Charger-local policy with strict
profile/sensor initialization is the selected architecture; the legacy Charger
Manager will not be expanded for this port.

The next charger-control foundation now has verified writes, separate setup/
user/fault restrictions, host fault/concurrency tests and three RAM device
cycles. This does not qualify actual charging response: IADC was unchanged
across those cycles. Complete temperature/profile/stale-sample/suspend policy
and connect the early firmware gate before changing the hardware comparator window.
See [the detailed battery work](battery-bringup.md#verified-control-foundation).

An opt-in RAM firmware now verifies inhibition and conservative BTC before an
intentionally disabled native charger can probe. Its first run discovers an
inherited 0x82 window; the revised gate explicitly narrows to 0x81 while charging
is off. That earlier diagnostic does not enable charging or install firmware
persistently.

A later RAM integration now validates the handoff and runs a policy child with
managed raw thermistor/voltage inputs, the stock LG state transitions, independent
restrictions and stale-data inhibition. Real supplier deferral and forced unbind
leave the parent USB/extcon available; HTTP packets verify that separation. Fresh
policy operation returns after explicit `drivers_probe` following supplier rebind.
Host fault/quiesce tests pass, but real system suspend, hardware-watchdog timing,
physical thermal boundaries, charging accuracy and complete power acceptance
remain open. No new firmware/kernel package is installed. See
[native policy evidence](../evidence/2026-10-30-smbb-native-policy.json).

UPower `99991.91.0-r4` now carries the existing upstream CLI error fix and expanded
incomplete-battery tests. Current upstream passes 103 configured tests and the
Nura 1.91.0 backport passes 94, including genuine zero-charge handling. Signed
native installation, CLI/service state and regenerated boot files are verified
without rebooting or changing the kernel/firmware. This retains the channel's
userspace base; whole-system currency and capacity/charging acceptance remain
open. See [UPower drafts and validation](../submissions/upower/README.md).

Phase 4 now runs on the installed signed 6.18.59-r6 kernel. WCNSS starts
stock-matching firmware from the original partitions. Wi-Fi association,
DHCP/DNS, sustained traffic, reconnect and radio toggling pass on an
owner-designated WPA2 network with taint 0. Bluetooth discovery works. Three
shared defects found here are fixed in r6: the Pronto v1/v2 regulator
selection, the MSM8226 DXE interrupt trigger and a cfg80211 scan-done
regression that blocked scanning after reconnect. Upstream drafts exist but are
not sent; submission needs the owner's approval. Bluetooth pairing, MAC policy,
suspend/resume, hotspot, coexistence and soak remain open. See
[wireless work](wireless-bringup.md).

## Technical baseline

As researched on October 29, 2026, Nura is the renamed postmarketOS project and its latest stable release is v26.06. The Fx0 uses MSM8926 and the `armv7` architecture. The old `lg-madai` package uses Linux 3.4 and is archived in the inspected October 2026 pmaports snapshot. Nura also provides a generic `qcom-msm8226` package and shared APQ8026/MSM8226/MSM8926 kernel.

An earlier Fx0 Linux branch based on 6.9.1 provides serial and USB configuration. lk2nd identifies `lg,madai`, with board ID 150 and volume-key definitions, but its Fx0 entry still lacks a completed Linux DTB mapping. The shared kernel tree inspected during research has no Fx0 board DTS. These findings define work to complete, not tested support on this unit. [Research sources and qualifications](research.md).

Prefer shared SoC packages, existing drivers, and small board descriptions. Use the vendor kernel as a source of hardware information and a diagnostic fallback. A permanent vendor-kernel installation does not satisfy this project.

## Workspace and development records

Use the root project for plans, manifests, reproducible orchestration, sanitized evidence, and exported submission material. Put independent source repositories under ignored `src/` or `worktrees/`; changes within those checkouts are committed to their own upstream-oriented repositories.

Proposed layout as implementation proceeds:

```text
fx0/
  README.md
  docs/
  manifests/               pinned source revisions and tool versions
  scripts/                 reproducible build and collection helpers
  evidence/                reviewed public logs and measurements
  submissions/             cover letters and series dependency records
  src/                     ignored independent source repositories
  worktrees/               ignored additional source worktrees
  local/                   ignored unit inventory and private configuration
  backups/                 ignored original images and calibration
  firmware-local/          ignored extracted firmware
  artifacts/               ignored build outputs and exported images
```

Create directories when needed. Keep separate known-good and candidate images, with hashes and source revisions. For each hardware run, record device revision, power source, battery condition, image hash, kernel command line, package versions, test procedure, result, and log location. Sanitize public copies without destroying private originals.

## Phase 0 Establish development and recovery

### 0.1 Prepare the host and repositories

1. Obtain direct USB access from a Linux host. Install current pmbootstrap, ADB, fastboot, device-tree tools, boot-image tools, and appropriate build dependencies. The current restricted execution environment lacks working ADB and fastboot and cannot enumerate USB; resolve host access before device work.
2. Allow approximately 50 to 100 GB for sources and build state initially; measure actual usage. Provide a known-good data cable and stable power. A microSD card and reader are useful but not assumed available.
3. Establish writable Git metadata without removing the supplied read-only `.git` directory. Initialize or attach the root project repository through the supported workspace mechanism. Configure the actual contributor identity before making signed commits.
4. Prepare public upstream-oriented repositories and remotes following [the repository plan](upstream-development.md). Keep the root documentation repository separate from kernel, pmaports, and lk2nd histories.
5. Record a source manifest. Check the current Nura forge, release, edge breakage reports, and source branches; several research endpoints were blocked during planning. Search for newer Fx0 work before duplicating patches.

**Exit:** host communication works; source changes have a valid local Git home; public destinations and author identity are recorded; build and private-data locations are established.

### 0.2 Inventory stock operation

1. Charge and inspect the phone and battery. Record the model, physical revision, existing OS build, storage card, and visible defects.
2. Enable Firefox OS developer access and ADB. Determine whether the existing OS provides root. Do not assume every device has the software state described by historical guides.
3. Capture properties, `uname`, `/proc/cmdline`, CPU and memory information, partition information, mounts, `dmesg`, and the kernel configuration if exposed. Resolve named partition links to their actual block devices and sizes.
4. Capture input enumeration, framebuffer details, power-supply attributes, USB identifiers, I2C/SPI devices where exposed, driver bindings, firmware paths, and hardware revision information.
5. Run the stock-system baseline tests in [hardware acceptance](hardware-acceptance.md). Identify actual panel, touch, camera, sensor, radio, PMIC, and codec variants from logs and source comparisons.

**Exit:** a private unit inventory and a sanitized hardware description distinguish verified hardware, source hypotheses, and existing stock faults.

### 0.3 Preserve recovery and calibration

1. Save partition-table metadata and a name, device, offset, and byte-size map. Preserve primary and backup partition metadata where applicable.
2. Back up original boot, recovery, LAF, boot-chain partitions, firmware partitions, and all calibration/provisioning storage discovered on this unit. Names such as `modemst1`, `modemst2`, `fsg`, and `persist` are candidates to verify, not a substitute for inventory.
3. Preserve a firmware file manifest and relevant stock configuration. Before final repartitioning, complete the mandatory whole-storage and factory-restoration checkpoint in section 2.1; the current selected critical-partition backups alone do not satisfy that checkpoint.
4. Copy backups to the host and a second storage location. Verify sizes, hashes, and independent rereads of critical images. Do not put original dumps in public Git.
5. Write a restoration procedure against the actual partition map. Determine which available environment can restore boot, recovery, and LAF. Do not regard a backup alone as proof that it can be restored.

**Exit:** verified off-device backups and a specific restoration procedure exist before destructive writes.

### 0.4 Obtain repeatable stock fastboot access

1. Test current bootloader and recovery entry paths before changing them. Record USB enumeration and supported fastboot commands.
2. If stock fastboot is inaccessible, evaluate the historical Fx0 LAF workaround. It clears the backed-up LAF partition to expose fastboot through the Volume Up plus USB path. Verify the exact partition and restoration route before applying it. This is not a generic Android unlock recipe. [Historical Fx0 instructions](https://github.com/stephanfriedrich/ffos_on_lgfx0/blob/master/README.md).
3. Determine whether temporary image boot works. Prefer it for early experiments when supported. Test battery-removal/cold-start recovery into the available flashing mode.
4. Preserve stock recovery unless replacement is needed for a concrete recovery capability. Evaluate temporary recovery boot before permanent installation.
5. Do not replace the primary boot chain as part of routine bringup. Treat EDL recovery as unavailable until a compatible loader and restoration method are verified.

**Exit:** repeatable stock fastboot entry, documented supported operations, and a usable boot restoration path.

## Phase 1 Reproduce Linux execution

### 1.1 Recover and rebase existing work

1. Fetch the historical Fx0 Linux branch, vendor kernel, current MSM8226 tree, current pmaports, and lk2nd. Preserve original authorship when recovering commits.
2. Inspect the recovered DTS and any historical conversion patches. Compare the actual unit with the source board ID, USB initialization, regulators, memory map, and pin assignments.
3. Build an unmodified shared SoC baseline to establish the toolchain, then add the minimal Fx0 board tree and DTB build entry. Begin with CPU, timer, interrupt controller, memory, essential clocks/regulators, UART, and USB only.
4. Validate firmware-reserved memory and RAM handoff. Leave optional remote processors and peripherals disabled until their resources are understood.
5. Build a small diagnostic initramfs with a shell, USB support, and log collection. Inspect image headers, load addresses, DTB attachment/selection, compression support, and image size against the actual boot path.
6. Produce an early driver gap assessment for camera/ISP, modem/audio transport, charging, and suspend on the maintained-kernel target. Identify missing SoC infrastructure, available patches, and dependencies before scheduling the later hardware phases.

**Exit:** a repeatable build produces an identified kernel, Fx0 DTB, and diagnostic image, with no guessed partition writes.

### 1.2 Integrate lk2nd

1. Build or obtain a pinned MSM8226 lk2nd image with the existing Fx0 recognition entry. Verify the appropriate output variant for this bootloader.
2. Temporarily boot it if supported; otherwise install only to the verified boot partition after phase 0.
3. Verify device identification, key handling, fastboot communication, CPU handoff, and cold-start behavior. Complete the Fx0 Linux DTB mapping and check which file is actually selected.
4. Record whether every flash command addresses stock fastboot or lk2nd. lk2nd can preserve itself by writing the OS image at a 512 KiB offset. Restoration of an original boot image must use the intended raw partition semantics. [lk2nd behavior](https://github.com/msm8916-mainline/lk2nd/blob/main/README.md).

**Exit:** repeatable lk2nd entry and correct Fx0 kernel/DTB selection, with a documented route back to stock boot.

### 1.3 Obtain an interactive shell

1. Boot the diagnostic image and capture host USB events. Configure a supported USB gadget transport and verify an interactive shell and complete boot log.
2. Diagnose failures in order: image acceptance and handoff, early kernel execution and memory, USB PHY/clocks/VBUS, then userspace. Use the recovered board USB PHY sequence as a starting point.
3. If necessary, investigate UART pads and voltage levels before attaching hardware. Use a vendor-kernel/custom-initramfs experiment to distinguish boot-image problems from mainline driver problems.
4. Verify reboot, power-off, and repeated cold starts. Save a known-good diagnostic image before adding peripherals.

**Exit:** reproducible Linux execution and a reliable debug connection. Display output is a later milestone.

## Phase 2 Boot current Nura from persistent storage

1. Enable eMMC, pin control, supplies, and bus configuration. Identify partitions read-only and compare with the stock inventory before exercising writes. Add microSD and card detection separately.
2. Build current stable Nura for `armv7` with a minimal console userspace. Start with ext4 and no disk encryption to reduce boot variables. Keep the distribution repositories internally consistent.
3. Reuse the generic `qcom-msm8226` packaging if it can represent the Fx0 cleanly; otherwise maintain a small Fx0 development package and document what must later be shared. Do not simply select archived `lg-madai` and treat that as a modern port.
4. Evaluate the generic package's ext2 boot filesystem, extlinux configuration, DTB selection, and MBR subpartition requirements. Use verified userdata space as the initial development installation, preserving firmware and calibration partitions. The nested boot/root layout is transitional. Keep external microSD available as ordinary removable media, with no boot dependency.
5. Export and inspect images before flashing. Record target partition, expanded image size, and bootloader context. Perform the explicitly required final repartitioning only after section 2.1 establishes complete restoration coverage and a validated layout.
6. Boot to a console and USB SSH. Verify root mounting, persistent writes, clock/time synchronization, package management through USB networking, and clean shutdown.
7. Move the working SoC patch stack to a maintained kernel with current fixes. Evaluate current 6.18 LTS first, revisiting that choice against Nura integration and kernel maintenance status at implementation time. Keep separate current maintainer-tree branches for submissions.

**Exit:** current stable Nura boots persistently with a maintained kernel, or a tracked kernel-maintenance blocker explicitly prevents this phase from closing. A historical-kernel diagnostic image cannot satisfy the exit.

### 2.1 Verify full stock restoration, then consolidate internal storage

This is a required final configuration step requested by the owner. It can proceed once storage and recovery are reliable; it must finish before phase 9 qualifies the final installation. Keep the current userdata installation until the restoration checkpoint passes.

1. **Audit restoration coverage.** Reconcile every original GPT entry, gap, filesystem, eMMC hardware area and device-specific firmware/calibration item against the private manifests. Record names, original start/end sectors, sizes, filesystem types/features, labels/UUIDs, GPT GUIDs and bootloader expectations. Distinguish original stock bytes, unchanged areas backed up later, current Nura bytes, and stock-recovery-recreatable state. Preserve the stock fstab, recovery/factory-reset behavior and all required firmware assets. Audit non-eMMC calibration separately: the camera EEPROM is not in a whole-eMMC image, and the original cached read omits some candidate OIS calibration addresses. The [camera work record](camera-bringup.md) records three matching full16-bit-address-space reads at0x50 on two host filesystems and the remaining capacity/other-bank/integrity checks; touch-controller and authenticated hardware state remain preserved in place.
2. **Complete consistent backups.** Boot the independently recoverable RAM environment and unmount every eMMC filesystem. Capture the complete 15,758,000,128-byte eMMC user area, primary/backup GPT and protective MBR, and the separate 4 MiB `mmcblk0boot0`/`mmcblk0boot1` areas by read-only operations. Capture readable CID/CSD/EXT_CSD and boot-configuration metadata privately. Preserve original partition images as well as a dated current whole-disk recovery snapshot. The GPT partition named `rpmb` is distinct from the hardware authenticated RPMB area: preserve the latter in place, without key programming, erase, OTP or permanent-lock changes. Linux documents the boot areas separately from the user area. [MMC hardware-area documentation](https://docs.kernel.org/driver-api/mmc/mmc-dev-parts.html).
3. **Verify and move recovery copies off the phone.** Check exact lengths and SHA-256; independently reread immutable stock-critical/system data and any complete snapshot being claimed as verified. Maintain manifests for each consistent snapshot, distinguishing legitimate mutable changes from corruption. Verify complete copies on two independent off-device storage locations, including Disk B. Copy and verify the internal `/sdcard/fx0-recovery` material and everything else required from internal SD before reclaiming it or running stock factory reset. A copy on the eMMC being repartitioned is not an off-device recovery copy.
4. **Assemble and rehearse factory-stock restoration.** Prepare an exact-sector rollback procedure that restores the original GPT and named partitions, the original stock boot/recovery/LAF/system and preserved device-specific state, then uses stock recovery to recreate stock mutable filesystems where needed. Current backups include 29 original critical partitions, GPT and the original system image; original userdata was not captured before the authorized Nura writes. Therefore a current whole-disk snapshot must not be labelled an untouched original stock image. The required proof is a working factory-stock restoration using preserved stock data and the verified stock initialization path. Confirm stock boot, display/input, original firmware/calibration visibility, stock storage layout and recovery/USB access, without requiring a SIM. Save the exact restore recipe, hashes and evidence. Reinstall the known-good development system after this rehearsal. Do not claim this checkpoint passed from backup files or a byte-identical LAF/boot rewrite alone.
5. **Design the minimum required layout.** Audit boot-ROM/SBL/aboot/lk2nd, recovery and firmware-loader dependencies before removing or moving any partition. Preserve required firmware, NV/calibration and boot-chain labels/offsets until a tested alternative exists. Start with the reclaimable Android `system`, `cache`, `userdata` and internal `sdcard` space; audit `grow`, padding and obsolete update slots individually. The measured five-entry range through `grow` is contiguous and supports an approximately 14.30 GiB host root preview; final metadata/alignment and boot-chain compatibility remain to be qualified. Produce an original-versus-target sector map with a reason for every retained partition and every remaining reserved byte. Do not infer that a partition is disposable from its name.
6. **Prefer one native root filesystem.** Allocate the maximum safely reclaimable contiguous region to one native Linux root/data filesystem, initially ext4. Avoid a nested Android userdata image and a separate internal FAT/shared-storage volume in the final installation. First qualify the documented Android-format Linux image path in the existing boot partition after lk2nd's 512 KiB prefix: its 31.5 MiB tail may remove the need for any separate boot filesystem. Package the maintained kernel, correct DTB and matching initramfs, then verify image fit, native-root selection, automatic boot, prefix-preserving on-device updates and interrupted-update recovery. The inspected boot-deploy write starts at byte zero, so it must be corrected and qualified before enabling raw-image updates. If filesystem boot remains necessary, determine exactly which root features lk2nd can read; its pinned ext2 parser cannot be assumed to support modern ext4. Allocate a small, justified boot filesystem only if the tested raw-image/root path requires it, with room for the kernel, DTBs, initramfs, known-good fallback and safe updates. Keep modern root integrity/features. The [storage work record](storage-layout.md) contains the measured host preview and open gates; it is not a completed minimum-layout audit. [lk2nd boot formats](https://github.com/msm8916-mainline/lk2nd/blob/main/Documentation/boot.md).
7. **Validate before writing GPT.** (2026-10-31 owner decision: keep the original 40-entry GPT capacity rather than test a 128-entry table, because a boot-chain parse failure would be unrecoverable without EDL; see the [storage work record](storage-layout.md).) Build and inspect both target GPT copies and filesystems on a host loop image using the measured sector geometry. Check alignment, non-overlap, required retained locations, firmware lookup labels, bootloader filesystem/features, image fit and rollback manifests. Prepare an installation/migration tool that verifies the physical device and original layout, refuses mounted target filesystems and unexpected geometry, and targets eMMC only. Demonstrate that RAM recovery and restoration remain available independently of the Linux root filesystem. Establish stable power before long backup/restore or layout writes.
8. **Repartition and migrate offline.** From RAM recovery with eMMC filesystems unmounted, preserve required partitions and write the validated target layout. Create the single large root filesystem and deploy Nura. Install the qualified Linux boot image at the reserved offset while preserving lk2nd, or create/restore a small boot filesystem if it remains necessary. Configure the tested update path and update DTB/initramfs paths, root/boot UUIDs, extlinux if used, and `/etc/fstab` for native partitions. Remove reliance on userdata subpartition discovery, Android internal-SD paths and fixed old partition numbers. Do not overwrite an attached external SD card. Independently reread both GPTs, required retained partitions and filesystem metadata; verify filesystems and installed contents before first boot.
9. **Qualify the final configuration and recovery.** Check root capacity against the target sector budget, persistent writes, cold/warm boots, kernel/userspace updates and interrupted-update recovery. Repeat full stock rollback and return to the final Nura layout if required to prove restoration from the consolidated layout. Exercise representative firmware-dependent hardware to catch lost label/offset assumptions. External SD uses normal Linux removable-media detection, filesystem mounting, permissions and safe removal, with no required card, adopted storage, root overlay or permanent OS-directory dependency. Test boot and normal operation both with and without a card; retain SD boot only as an explicitly selected recovery option if useful.

The fully unmounted development-state capture now passes independent reads and verified copies on two host filesystems, including the user area, both boot areas and private eMMC identity/configuration metadata. See the [checkpoint evidence](../evidence/2026-10-29-unmounted-development-checkpoint.json). Step 4 passed on 2026-10-31. Original partitions were restored, stock recovery's `--wipe_data` initialized userdata and cache, Firefox OS booted and was checked, and the original LAF entered download mode. The development state was then restored from a verified whole-eMMC snapshot. See the [rehearsal evidence](../evidence/2026-10-31-factory-stock-rehearsal.json). The minimum-layout steps 5–9 remain open.

**Exit:** independently verified off-device restoration material and a demonstrated factory-stock recovery exist; Nura uses one maximum-capacity native root filesystem plus only justified extra partitions; external SD behaves as removable media; installation, rollback and updates work on this final layout. Repartitioning remains pending until this checkpoint's prerequisites pass.

## Phase 3 Make the local interface usable

1. Confirm the installed panel and touchscreen revision. Vendor sources describe JDI panel configurations and Synaptics variants; derive the actual selection from the device. Translate hardware descriptions into current bindings rather than copying obsolete vendor properties.
2. Bring up panel supplies, reset and sleep sequences, DSI timings/commands, backlight, and DRM/KMS. Resolve the maintained driver's IOMMU dependency first: the current MDP5 path removes simpledrm then rejects a device without an IOMMU. Review the upstream MSM8974 QSMMU series and ARM32 DMA-domain fix, adapt MSM8226-specific prefetch settings and power/context handling from stock, and qualify mapping, scanout, power collapse and error recovery in RAM before making it the default boot. Keep that shared SoC work separate from the panel driver. Validate generated patterns, brightness, blank/unblank, and independent kernel control of the display. A retained firmware logo does not pass.
3. Bring up touch supply, I2C, interrupts, coordinate mapping, multitouch, and wake behavior. Use input-event tools before relying on the desktop. Verify power, volume, and home buttons independently.
4. Enable MSM graphics and Mesa Freedreno. Record the actual renderer, rendering correctness, memory use, and stability. Retain existing SoC workarounds until measured tests justify changing them.
5. Use Sxmo as an initial lightweight interface candidate, then evaluate Phosh as a fuller mobile interface. Select the final supported UI from measured usability and current Nura support. Keep USB debugging available throughout.
6. Validate on-screen keyboard, rotation, application launch, compositor restart, lock/unlock, and recovery to a console.

**Exit:** a usable mobile session with accelerated graphics, reliable display/touch/buttons, and measured memory behavior. The UI milestone does not close unfinished hardware work.

## Phase 4 Establish wireless connectivity

1. Identify WCNSS firmware, calibration, supplies, clocks, pin control, and remote-processor dependencies from this unit and the vendor sources.
2. Reuse Nura's firmware loading infrastructure, preserving partition data and device calibration. Verify actual lookup paths and initialization order. Package only redistributable firmware; retain an extraction/loading method for local-only material.
3. Bring up Wi-Fi scanning, connection, DHCP, DNS, sustained traffic, reconnect, and supported frequency bands. Verify the reported MAC is stable and derived correctly. Test hotspot/tethering if supported by the hardware and firmware.
4. Bring up Bluetooth discovery, pairing, reconnect, data transfer, HID, and supported audio profiles. Test Wi-Fi/Bluetooth coexistence under traffic.
5. Investigate FM radio only if physical-device or vendor evidence establishes that the product exposes it; a multifunction chip alone does not prove a usable product feature.

**Exit:** all verified wireless functions pass their matrix entries, including resume and coexistence tests.

## Phase 5 Complete power management

Conservative power configuration starts during phase 1. This phase qualifies the complete system after drivers and userspace are operating together.

1. Map PMIC, charger, battery sensing, thermistors, fuel gauge, USB current detection, external protection, and power-key functions. Use verified battery specifications and board revision when configuring limits.
2. Validate readings against independent measurements where available. Check charging, charge termination, unplug/replug, low-battery behavior, thermal response, shutdown, and powered-off charging behavior supported by the device.
3. Implement native battery temperature policy before widening the hardware comparator range. Require valid sensor input at boot and after resume; inhibit charging on missing, stale, open/short or failed input. Cover pack-specific current/voltage limits, hysteresis, independent user inhibition, actuator errors and supplier removal. Prove protection while suspended or inhibit charging before suspend. Timer expiry must not override thermal stops. Retain the [stock comparison and current prerequisites](battery-bringup.md) as the starting evidence.
4. Enable and validate CPU frequency scaling, idle states, thermal throttling, and all CPU cores. Measure behavior under CPU, GPU, network, and camera load.
5. Implement suspend and wake sources. Test each driver across suspend, including display, touch, USB, wireless, audio, sensors, and modem.
6. Measure unplugged idle and suspend consumption. Record battery condition and compare with the stock baseline or a justified measured target. USB-powered testing cannot establish standby behavior.

**Exit:** stable charge/discharge operation, credible battery reporting, thermal control, functional suspend/wake, and measured power consumption without unexplained awake loops.

## Phase 6 Complete audio sensors and peripheral interfaces

1. Bring up codec clocks, audio routing, amplifier supplies, jack detection, microphones, speaker, earpiece, and headset paths. Prepare appropriate ALSA UCM configuration and integrate it upstream.
2. Test recording and playback separately, then simultaneous use, route changes, supported sample rates, volume, and suspend. Qualify Bluetooth and call routes again after modem work.
3. Enable each physically present sensor, establish its mounting/orientation, and validate raw data before desktop integration. Complete the MPU-6515M raw-sensor, DMP access and DMP interrupt wake requirements in section 6.1. Test rotation, ambient-light control and proximity blanking.
4. Qualify vibration, notification/home/button lighting, NFC, GNSS, USB device profiles, USB host/OTG where exposed, microSD handling, and any additional discovered hardware.
5. For GNSS, record cold and warm acquisition under suitable outdoor conditions, time to fix, reported position, and behavior without SIM or assistance data. For NFC, use a suitable test tag rather than just checking device enumeration.

**Exit:** every inventoried peripheral has a passing functional test, or remains an explicit open item that prevents final completion.

### 6.1 MPU-6515M, DMP access and interrupt wake

The owner identifies the IMU as an MPU-6515M. Treat that as the target part, with the installed silicon revision and board wiring still to be confirmed. **Access to its Digital Motion Processor (DMP), including waking the application processor from system suspend on a DMP interrupt, is required for completion.** Raw accelerometer/gyroscope support alone does not satisfy this requirement.

The [sensor work record](sensor-bringup.md) now locates the original registry and
validates its static bus/address/IRQ configuration. A native diagnostic verifies
ADSP shutdown and pin restoration, but refuses to clock low bus lines. Confirm
supplies and bus/pin mapping from a working stock runtime baseline before another
AP transfer; no chip identity or DMP pass is claimed.

1. Establish the hardware path from stock runtime evidence: chip identity/WHO_AM_I and revision, bus/address, supplies, reset, interrupt routing/polarity/latching, mounting matrix and ownership by the application processor or a sensor DSP. Resolve bus ownership before probing; do not access a bus concurrently with remote firmware. Verify that Linux's MPU6515 variant describes this silicon, including any significance of the M suffix. Record the exact source and firmware revisions used.
2. Capture a stock baseline for raw acceleration/angular rate and available DMP operation, including interrupt behavior during suspend. Identify the matching DMP firmware, configuration, packet formats and supported algorithms. Preserve extraction instructions, hashes and licensing/provenance; keep per-unit calibration private. Publish firmware only when redistribution rights permit it, otherwise provide a reproducible extraction/loading path from the device's preserved stock material.
3. Reuse and extend the maintained IIO `inv_mpu6050` family driver where appropriate. Qualify raw accelerometer, gyroscope and available temperature data first: axes/mounting, scale/range/rates, bias/calibration, timestamps, triggered buffers, FIFO overflow recovery and resume. Existing `invensense,mpu6515` matching is a starting point, not evidence that DMP access works.
4. Implement DMP firmware loading and execution for the verified part: bank/address handling, bounded uploads and verification where supported, entry point, reset/start/stop, error recovery and safe switching between raw and DMP modes. Decode the actual firmware's FIFO packets, timestamps and event status; handle partial packets, overflow, reset and firmware reload without stale events. Inventory and expose supported outputs/events such as fusion/quaternions, motion, gestures or step information without promising algorithms absent from this firmware. Supply a reproducible userspace example that enables the DMP and reads its output through a reviewed Linux ABI. Software fusion on the application processor or sensor DSP does not qualify as execution on the MPU's DMP.
5. Implement **DMP interrupt wake from system suspend**. Retain the IMU's required power, clock and DMP state; configure the verified interrupt pin and event masks and provide the firmware-described wake path. Manage IRQ wake arming/disarming and suspend/resume ordering without accessing a suspended bus. Preserve and identify the triggering DMP event, then drain retained events/FIFO after resume. Distinguish a DMP-generated event from ordinary data-ready, FIFO or raw wake-on-motion interrupts; qualifying one of those alone does not qualify DMP wake. If a sensor DSP mediates the path, demonstrate the complete DMP-to-DSP-to-application-processor wake chain.
6. Validate real system suspend rather than display blanking or runtime idle. Establish a safe RTC fallback, confirm suspend entry, generate a physical DMP event, and correlate IRQ/wakeup-source counters, suspend/resume logs and the retained event/timestamp. Record wake latency and use a masked-DMP negative control to establish causality. Complete at least 20 consecutive DMP-triggered suspend/wake cycles within the overall 50-cycle requirement. Test repeated arming/disarming, firmware retention/reload, recovery after reset and interaction with ordinary sensor buffers. Prevent stale interrupts, immediate resume loops and lost first events.
7. Measure armed-but-idle standby and event wake on battery, with USB unplugged or its wake contribution explicitly isolated. Include overnight standby, false-wake counts and energy use; USB-powered success cannot qualify standby drain. Demonstrate that disabling DMP wake restores the expected wake policy and that unrelated wake sources still work. Keep failures open until both event delivery and suspend behavior pass on the final image.
8. Integrate raw IIO sensors and supported DMP functions with current Nura userspace, including rotation through the appropriate sensor service. Separate board description, driver/ABI, DMP firmware handling, wake support and userspace packaging into reviewable changes. Validate against current upstream IIO and PM interfaces; do not copy historical Android sysfs interfaces or a vendor driver wholesale. Prepare driver, binding/ABI documentation, firmware provenance and reproducible functional/power evidence for the relevant upstream maintainers.

**Exit:** physical raw-sensor tests, actual DMP firmware execution/output, and DMP-event wake from verified system suspend all pass on the final Nura image. Missing firmware rights, unresolved routing or unsupported wake behavior remain explicit blockers; they do not reduce this requirement.

## Phase 7 Complete both cameras and media acceleration

1. Identify the exact front and rear sensors, EEPROM/OTP calibration, lens actuator/OIS, flash/torch, supplies, reset GPIOs, clocking, CSI wiring, and any image-processing dependencies. The [camera work record](camera-bringup.md) now pins confirmed stock IDs and production source wiring. Reconcile the matching private EEPROM captures, remaining capacity/other-bank/integrity checks and actual actuator/OIS identification before commands that can modify calibration.
2. Determine what current MSM8226 camera and media support can be reused. Separate sensor drivers, camera-interface/ISP work, and userspace integration into appropriate patch series. If essential SoC infrastructure is absent, track it as a substantial implementation workstream.
3. Qualify CCI/power sequencing with sensor IDs, then the MSM8226 camera IOMMU and sensor-independent CSID/VFE test pattern, before sensor streaming. Bring up each sensor and the media graph with test captures before the camera application. Preserve calibration and verify Bayer format, orientation, colors, exposure, and frame integrity.
4. Integrate libcamera and a current Nura camera application. Test front/rear selection, stills, autofocus where fitted, supported video capture, microphone synchronization, flash/torch, and suspend/reopen.
5. Inventory advertised hardware video encode/decode capabilities and implement exposed acceleration through the appropriate media interfaces. Validate actual acceleration and CPU load rather than counting software playback as hardware support.

**Exit:** both cameras and verified media hardware work through current userspace. Missing camera or codec support stays in scope even if the remainder of the handheld is usable.

## Phase 8 Complete modem and cellular operation

1. Preserve provisioning and calibration. Identify the modem remote processor, firmware authentication requirements, transports, control channels, SIM interface, network interfaces, audio transport, and any GNSS dependency.
2. Without a SIM, validate firmware startup, control requests, ModemManager discovery, missing-SIM reporting, radio power control, and absence of crash/restart loops. Disable unused radio activity during other power measurements.
3. Once a suitable SIM is available, verify SIM detection and supported PIN handling, network registration, APN configuration, mobile data, DNS, SMS send/receive, outgoing/incoming calls, earpiece/microphone/speaker/headset routing, and DTMF.
4. Verify wake for incoming calls/SMS, data reconnect after suspend, airplane mode, and coexistence with Wi-Fi, Bluetooth, audio, GNSS, and charging. Test VoLTE/IMS only where device/network capability supports it; document available network modes and limitations.
5. Separate driver defects from unavailable bands, retired network services, SIM restrictions, or carrier requirements. Use an appropriate supported network or controlled test facility for otherwise untestable paths. Do not make live emergency-service calls as a test.

**Exit:** full cellular evidence exists on a suitable network. No SIM means this phase remains open; successful modem enumeration is insufficient.

## Phase 9 Qualify installation updates and reliability

The following counts are initial project test targets, not claims about certification standards. Increase them if failures or intermittent behavior justify it.

1. Perform at least 20 cold boots and 20 warm reboots, with logs and no unexplained boot failures. Include power-off and recovery entry.
2. Perform at least 50 suspend/resume cycles across battery/USB power and important peripheral combinations, including at least 20 consecutive MPU-6515M DMP interrupt wakes with retained-event and wake-source evidence (section 6.1). Exercise incoming cellular events when a SIM is available.
3. Run a 24-hour mixed-use soak and an overnight unplugged standby test. Record crashes, watchdogs, thermal behavior, memory pressure, battery change, and peripheral recovery.
4. Exercise simultaneous workloads: charging plus camera, Wi-Fi plus Bluetooth audio, call plus screen blanking, GNSS plus suspend, and microSD I/O plus suspend. Investigate filesystem errors, firmware restarts, and excessive drain.
5. Rebuild and install from clean source manifests. Demonstrate stock-to-Nura installation and the section 2.1 minimum-partition layout, factory-stock rollback, and return to Nura with the documented procedure and retained recovery path. Run final reliability tests on that layout.
6. Upgrade userspace and kernel, confirm the running kernel version after reboot, and verify that the previous known-good installation can be recovered. Recheck current edge breakage reports before attributing startup failures to this board.
7. Repeat essential tests on current edge and the upstream submission bases. If pursuing Nura community categorization, satisfy its release testing and kernel-upgrade history requirements; category promotion is separate from project completion.

**Exit:** current stable acceptance passes, edge compatibility is recorded, updates/recovery are demonstrated, and all hardware matrix entries have current evidence.

## Phase 10 Prepare upstream submissions and handoff

1. Split working integration changes by upstream destination and subsystem. Remove debugging scaffolding and explain any remaining temporary packaging patch.
2. Rebase submission branches onto the appropriate current maintainer trees, preserving useful historical attribution and licensing.
3. Run the relevant build, static, schema, packaging, and physical tests listed in [upstream development](upstream-development.md). Save sanitized results keyed to exact commits.
4. Prepare versioned patch series, cover letters, recipients, dependency maps, and Nura/lk2nd merge-request descriptions. Record the supported unit revision and any variants requiring further testing.
5. Publish reviewed source commits to the intended public development repositories. Keep private backups, raw logs, firmware without redistribution rights, and credentials out of their history.
6. Leave ready-to-send kernel mail and ready-to-open merge-request material. Sending mail, posting comments, or opening submissions is a separate action requiring explicit instruction; this task's endpoint is submission readiness.
7. Record the final installed versions, complete acceptance matrix, source manifest, installation/recovery instructions, and maintenance owner/contact once established.

**Exit:** the physical installation satisfies the objective, all required changes have a public reviewable history, and each outstanding upstream series is ready to submit without further implementation or validation.

## Milestones and dependencies

| Milestone | Depends on | Required evidence |
| --- | --- | --- |
| M0 Recoverable development device | Phase 0 | Verified backups, host access, stock baseline, recovery path, Git setup |
| M1 Repeatable Linux execution | M0 and phase 1 | Correct DTB selection, shell, logs, repeated boots |
| M2 Current persistent Nura | M1 and phase 2 | Persistent root, maintained kernel, package management; section 2.1 storage migration tracked separately until complete |
| M2s Final internal storage | M2 and section 2.1 | Complete verified restoration coverage, demonstrated stock rollback, one large native root, minimum justified extra partitions, removable external SD |
| M3 Interactive handheld | M2 and phase 3 | DRM, acceleration, display, touch, buttons, usable UI |
| M4 Connected handheld | M3 and phases 4 to 6 | Wireless, audio, power, sensors and peripheral tests |
| M5 Full hardware functionality | M4 and phases 7 to 8 | Cameras/media and complete SIM-based cellular qualification |
| M6 Qualified current installation | M5, M2s and phase 9 | Clean install, updates, recovery, reliability evidence |
| M7 Upstream submission ready | M6 and phase 10 | Public commits, current submission bases, passing checks, prepared series |

Patch cleanup and submission preparation proceed as individual subsystems mature; they need not wait for M6. Assess camera, modem, and power infrastructure during phase 1 so their dependencies are understood before the interactive-handheld milestone.

## Risks and replanning

- **Host access:** device work cannot start until the execution host can use USB and the required privileges. Continue source and documentation work independently.
- **Boot access:** LAF and bootloader behavior must be verified on this unit. Stop dependent writes if recovery cannot be established.
- **Historical sources:** minimal old mainline work is not proof of full operation. Inventory each missing driver and recheck newer upstream work.
- **Power and panel revisions:** shared supplies and revision-specific sequencing can affect touch, display, and charging together. Confirm the actual revision before configuring them.
- **Camera and modem infrastructure:** missing SoC drivers or firmware interfaces could dominate effort. Produce an explicit gap report early; do not reduce the completion goal to hide them.
- **SIM and network:** full cellular qualification needs additional test access. Keep it pending while advancing all independent work.
- **Current software:** release and kernel choices move over time. Refresh versions at milestones and retain a reproducible known-good build while qualifying updates.

Plan in milestones rather than promise a fixed completion date. Recovery and first boot may take several sessions; complete camera, modem, and power support may require months if substantial infrastructure is missing. Re-estimate after M1 and after the camera/modem gap assessment.
