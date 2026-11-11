# LG Fx0 hardware acceptance

## Status and evidence

All entries initially have status **unverified**. No physical test result is implied by source availability. Record two distinct results for each function: the stock baseline and the current Nura candidate. An implementation commit or device-node enumeration alone is not a functional pass.

Use these statuses: `unverified`, `identified`, `in progress`, `blocked`, `failed`, `passed`, and `absent`. `blocked` means the required test or implementation cannot currently proceed; it does not count as passed. Use `absent` only when physical or product-specific evidence shows the unit does not contain or expose the feature. Record stock hardware faults separately; an existing fault does not silently satisfy the all-hardware goal.

For each result record the exact image hash, source revisions, package manifest, unit revision, power source, battery condition, procedure, observations, log/artifact reference, and date. Keep identifiers and original logs privately; publish reviewed evidence under `evidence/` when available.

**Current phone state: restored r50, booted with zero taint.** Exact boot
readback, 300–787.2MHz limits, the programmed 1.15V APC target, raw IMU reads
and pre-trial zero L2 state are verified. The initial reboot after r51
installation reached Qualcomm9008; a later boot after reconnection passed
L2/S2 bootstrap checks. Its failing stage remains unknown, so r51 stays
quarantined. See [recovery evidence](../evidence/2026-11-07-r50-restored-after-r51.json).

Installed package: `6.18.59-fx0-dmp` (r50), adding read-only CPU calibration
interfaces with CPR and higher OPPs disabled. Native bounded raw reads and the
secure conditional selector read pass ([evidence](../evidence/2026-11-06-cpu-calibration-r50-native.json));
r50 clean post-pilot raw/quaternion/SMD retention and RTC baseline checks pass with zero taint and no MDP5 underruns. On r49, twenty consecutive physical
DMP wakes pass, with matched-build masked-motion control, recovered sensor
streams, no display underruns and zero taint. Owner confirms display and touch
after the run. The overall 50-cycle, battery/overnight and wider peripheral
gates remain open; hotspot installed Sxmo recovery passes two bounded cycles; broader qualification remains open. See [20-cycle
evidence](../evidence/2026-11-06-mpu6515-dmp-20-consecutive-wakes.json).
Audio testing remains excluded.

November 8 reconstructed-r50 RAM baseline: two boots return to installed r50
with an unchanged boot-partition hash, four CPUs online and taint zero. The
second captures the timed return and 22 USB HTTP status/log pairs; the owner
reports restored-r50 display/touch working. That return still had a pending
time-synchronization job despite no failed units; the later read-only runtime
candidate preflight reaches `running` startup with Sway and the original
hash/limits/zero taint. No controller or higher-OPP pass
is implied: the moduleless baseline reports an inherited 800 MHz CPU clock,
which needs a safe handoff before the current CPR candidate can attach.
See [RAM baseline evidence](../evidence/2026-11-08-r50-ram-baseline.json).

The 39-patch runtime CPU-clock candidate now has a complete linked ARM kernel,
464 verified signed modules and 114 passing host checks with no skips. Its
first moduleless ordinary-DTB RAM bootstrap/return passes: four CPUs, taint zero,
L2 master bound and APC's reported 1.15 V boot target. Twenty-two USB HTTP log
pairs and serial capture the timed return; installed r50 retains its hash,
limits, Sway and sensor proxy. The same return boot subsequently reaches running
systemd startup with no failed services or pending jobs; its physical UI check
remains pending. The original image reproduces an input-dependent lk2nd USB
stall; an equivalent gzip-level-1 encoding boots, while that transport defect
remains open. CPR, eligible higher OPPs, actual rails/feedback, fail-stop recovery
and wider hardware qualification remain open. See
[runtime source/build evidence](../evidence/2026-11-08-msm8926-runtime-clock-candidate.json)
and [native bootstrap evidence](../evidence/2026-11-08-l2-s2-ram-bootstrap.json).

The complete runtime candidate now also passes a distribution source-package
build with Alpine Clang 22.1.3. The actual community configuration, signed APK,
exact kernel/DTBs, embedded kernel trust certificate and all 464 module
signatures verify; corruption and wrong-certificate controls reject. This
Alpine artifact is unbooted and uninstalled, so the earlier Fedora-Clang RAM
result does not qualify it. The [source-package branch](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-cpu-runtime-package)
is published at `4f17b6905c75` after the owner authorized fx0 development pushes. See
[package evidence](../evidence/2026-11-08-runtime-kernel-source-package.json).

The first separate CPR qualification-DTB RAM trial reaches diagnostics but
fails its startup gate: provider probe returns -EINVAL, CPU stays at 800 MHz
and no CPUfreq policy appears. The timer returns at 181.623794 seconds to
unchanged installed r50; startup, services, original hash/rates and the owner's
display/touch check pass. Host network state is restored. Failure-stage
instrumentation passes 116 selected checks and its ARM object; the separate
kernel links and RAM-boots once. It identifies the reference-source check as
the failure. A read-only native APCS+0x64 word is 1, the stock AHB selection;
controlled XO ownership and verified selection remain to implement. Pstore
confirms a 181.601496-second timer return, with unchanged r50 and another owner
display/touch pass. No CPU/rail guard is bypassed and no CPR/DVFS
qualification is inferred. See
[trial evidence](../evidence/2026-11-08-cpr-bootstrap-first-ram.json) and
[diagnostic preparation](../evidence/2026-11-08-cpr-probe-diagnostics-preparation.json).

The subsequent stopped-controller XO handoff passes its moduleless startup
RAM gate: CPR initializes seven eligible OPPs, all four virtual CPU consumers
attach, the CPU mux reads 300 MHz, APC's reported 1.15 V boot target is retained,
and MX has an enabled bootstrap vote. LOOP_EN stays clear despite RESULT_0.BUSY
remaining set. All four CPUs are online with taint zero and five bound SPM
controllers; no module, CPUfreq policy or positive pstate is activated. A cached
1.08 V debugfs corner value is not the programmed APC target. The timer returns
at 181.782488 seconds to unchanged r50, with Sway/sensor proxy and restored host
network state. The owner confirms display/touch on this return. Time-sync
jobs remain pending. This closes startup only; runtime
DVFS/feedback, real rails, thermal/suspend and wider gates remain open. See
[startup evidence](../evidence/2026-11-08-cpr-disabled-reference.json).

The later observation kernel and its two matching signed CPU modules pass
registration under enforced signatures/userspace, retaining 300 MHz, the
unapplied 1.15 V APC target and disabled feedback. A separate limited trial
passes 300→384→300 MHz with applied 1.08 V targets at both fixed-corner points
and LOOP_EN clear. The timer returns at 181.756403 seconds to the original
r50 hash/policy; exact PMIC S2 reads confirm restoration to 1.15 V. Taint is
zero and Sway/sensor proxy run. The owner confirms display/touch and startup reaches running without failed
or pending jobs. These quiet holds do not qualify later feedback, analogue rails,
load/thermal/suspend or distribution/install behavior. See
[registration](../evidence/2026-11-08-cpr-voltage-observation.json) and
[first fixed-corner evidence](../evidence/2026-11-08-cpr-first-fixed-corner.json).

A separate 300→600→300 MHz RAM trial passes fifty bounded feedback samples on
the same kernel/module family. The CPU clock reads 600 MHz, APC/cache remain
at this unit's 1.08 V floor within the 1.08–1.18 V limits, and one CPR interrupt
sets the IRQ-handler floor-response flag with LOOP_EN enabled. This qualifies
a handled floor clamp, not voltage adjustment or load/thermal/suspend. Return
to 300 MHz clears LOOP_EN. The 181.741527-second timer returns to r50 with its
original hash, PMIC 1.15 V target, zero taint and UI services; host network
cleanup passes. The owner confirms display/touch on this newest return; only
the existing time-sync jobs remain pending. Details are recorded in
[600 MHz feedback evidence](../evidence/2026-11-08-cpr-feedback-600.json).
Higher rates, repeated transitions, physical rails and broader gates remain open.

The same family subsequently passes five pre-load 300–600 MHz round trips and
a bounded four-core load at 600 MHz. Four affinity-verified 30-second workers
check 1,463 one-MiB SHA256 results with 113.737 total process CPU seconds. All
90 state checks pass, with reported temperatures 38–44°C and APC at 1.08 V;
feedback handles the floor without observed voltage adjustment. Workers stop
before the final verified 300 MHz return. The 181.714515-second timer restores
r50's hash, PMIC 1.15 V target, zero taint and UI services; host network cleanup
passes. Latest physical UI/startup status is in
[repeat/load evidence](../evidence/2026-11-08-cpr-load-600.json). This short run
does not qualify higher rates, long stress, whole RAM, thermal throttling,
physical rails, battery power, suspend or installed/distribution behavior.
The same native boot subsequently synchronizes NTP and reaches running startup
with no failed units/jobs and no configuration changes; earlier intermittent
DNS/startup delays remain a reliability gate. See the
[startup follow-up](../evidence/2026-11-08-r50-time-sync-followup.json).

A separate 787.2 MHz PLL/load RAM image is prepared with thirteen passing host
checks, explicit raw PLL/mux guards and the shared 600/787.2 MHz voltage bounds.
It is unbooted and unstaged while the preceding 600 MHz load return's newest
physical UI check remains pending. The actual stage entry rejects that pending
result before sending any phone command. This is preparation only, not a
787.2 MHz hardware pass. See
[preparation evidence](../evidence/2026-11-08-cpr-787-preparation.json).

The independent Alpine r55 source package now includes the 43-patch observation
source instead of r54's 39-patch candidate. Its full build, actual normalized
community config/CFI, exact kernel/DTBs/trust list, all 464 signed modules,
corruption/wrong-certificate checks and normal offline ARMv7 package simulation
pass. The distinct `-fx0-cpr-observe-alpine` release prevents ordinary module
path mixing. It is unbooted/uninstalled and inherits no Fedora RAM hardware
result. A read-only postflight confirms the phone remains on the same r50 boot,
original hash/1.15 V target, zero taint, running startup/NTP and UI services;
its latest physical UI result remains pending. See
[r55 package evidence](../evidence/2026-11-08-cpr-observation-source-package.json).

Its empty BusyBox module dependency metadata is now corrected in packaging
revision r57 using kmod. The original kernel/configuration/DTBs/certificate
and all 464 signed modules remain byte-identical. All 25,294 import CRCs and
567 dependency edges verify; binary-index loader dry-runs and isolated
usermode r55-to-r57 replacement also pass, including all 546 final payload
files. These checks do not test phone autoload, update hooks, boot or recovery.
See [r57 correction](../evidence/2026-11-08-cpr-package-dependencies.json).

The first independent Alpine startup/signed-registration RAM image is prepared
with the exact signed APK kernel/DTB and matching two-module family. It retains
the 180-second return and makes no explicit performance request. Three real-shell
tests cover 36 modes, including before/after bootstrap drift; ARM BusyBox syntax,
image layout and actual observer-command checks pass. Its stage entry rejects
the pending previous-return physical UI result before any phone command. This
remains preparation only, with no Alpine staging, boot or hardware pass. See
[Alpine RAM preparation](../evidence/2026-11-08-alpine-cpr-registration-preparation.json).

November 8 r50 regression: the owner confirms display and touch before testing.
Five USB-powered RTC controls retain DMP execution across traced s2idle and
recover 373 quaternion samples, with RTC IRQ +1 and IMU IRQ +0 per cycle, no
MDP5 underruns and taint 0. Sensor proxy and wake/alarm policy are restored.
These add RTC-control evidence; the r49 physical-motion results do not become
r50 motion-wake qualification. Post-test physical display/touch confirmation
and the overall reliability gates remain open. See [r50 regression](../evidence/2026-11-08-r50-rtc-regression.json).

The owner confirms display and touch after the restored-r50 boot, closing that
recovery check ([record](../evidence/2026-11-07-r50-restored-after-r51.json)).
CPU-series 25–27 now provide shared CPU/CPR filtering, retry-safe attachment
and a separate qualification DTB. Complete-source reconstruction now links both
r50 and the CPU candidate and verifies all 928 staged module signatures. The
109 source/DMP/preparation checks and three image-placement checks pass.
The phone still runs the same r50 boot with four rates. A checked r50 RAM
baseline image is prepared but has not booted; source packaging, RAM-only
controller/recovery and physical OPP/rail/thermal/suspend qualification remain
open. See [rebuild evidence](../evidence/2026-11-08-kernel-reconstruction.json).

## Acceptance matrix

| Function | Required identification and functional evidence | Initial status |
| --- | --- | --- |
| Boot and recovery | Stock and lk2nd entry; correct Fx0 DTB; cold/warm boot; recovery and original-boot restoration procedure | Partial: production lk2nd (no extlinux, no forced fastboot) installed; unattended warm and cold (power key) boots to Nura from the boot-deploy raw image; Volume Down cold entry and (with kernel r8 and the PON-aware lk2nd) `systemctl reboot --reboot-argument=bootloader` reach lk2nd fastboot; stock fastboot (Volume Up + USB) and full factory-stock restoration rehearsed with a verified whole-eMMC return; 20 warm reboots on the final layout pass (69–72 s each, all checks); 20 cold boots and final-layout recovery pending |
| CPU and memory | All four cores; expected usable RAM after reservations; stable stress run; frequency scaling and idle | Partial: r49 bounded four-core test passes 30 s with one pinned SHA256 worker per CPU (3063 verified one-MiB hashes, ~29.5–29.9 CPU s each), peak reported CPU temperature 47°C, recovery downscales to 300 MHz, unchanged schedutil/limits and taint=0 ([evidence](../evidence/2026-11-06-cpu-thermal-bounded-r49.json)). The r50 filtered raw interface and secure conditional selector read now pass natively with unchanged conservative limits; full calibration, CPR/rail lifecycle and OPP integration remain open ([native evidence](../evidence/2026-11-06-cpu-calibration-r50-native.json)). Higher OPPs explicitly need speed-bin support; full CPU/RAM stress and performance/power qualification remain open |
| Firmware handoff | Correct memory reservations, firmware ownership and remote-processor startup; no corruption or restart loops | Partial: RAM WCNSS starts stock-matching firmware from the reserved 10 MiB region; after the DXE trigger fix, a stop/restart re-registers Wi-Fi. Modem/ADSP startup and restart-loop/soak qualification pending |
| eMMC | Correct layout/capacity; sustained reads/writes in the test filesystem; persistence and clean shutdown | Final layout applied 2026-10-31: native ext4 root on p35 (14.92 GB filesystem, initially 12.67 GB free), firmware partitions intact and found by label, unattended boot and kernel updates pass. Consolidated-layout stock rollback and byte-identical r13 return pass on November 1 ([rollback](../evidence/2026-11-01-stock-rollback-from-final-layout.json)). On r50 November 8, four 512 MiB temporary-file rounds pass 2 GiB written/directly read with per-sector tags, fsync, host-expected checksums, matching block accounting and zero filesystem/new kernel storage errors; 512 temperature samples are 39–45°C ([integrity evidence](../evidence/2026-11-08-emmc-native-integrity.json)). Same native boot/hash/policy/services retained. A later warm-native-boot direct read verifies all 512 MiB and the expected hash; the exact temporary files are subsequently archived/removed ([persistence evidence](../evidence/2026-11-08-emmc-cross-boot-persistence.json)). Long soak, power-loss/clean-shutdown retention and final-candidate regression remain open |
| microSD | Card detect, read/write, filesystem integrity, suspend behavior, safe removal where supported | Partly verified (RAM boot with the new SDHC2 DT): 8 GB SDHC detected at 50 MHz high-speed 4-bit, formatted FAT32, 64 MiB written and verified, user-writable, clean unmount, hot removal and reinsertion detected with data intact ([evidence](../evidence/2026-10-31-microsd.json)); in the installed kernel since r9; eMMC numbering pinned in r10; suspend behaviour pending: r49 microSD trials on 2026-11-06 fail before actual sleep because GPIO37 card-detect/mmc1 wake events abort the freezer. Both 64 MiB initial write/read hashes pass; cleanup and read-only FAT checks pass. A separate 16 MiB direct read succeeds without new CD IRQs; a later 4 MiB phase probe reproduces 22675 GPIO37 CD IRQs during ~0.29 s fsync, with none during read/idle and a clean final FAT check ([phase evidence](../evidence/2026-11-06-microsd-writeback-cd-irqs.json)). Electrical root cause and SD suspend remain open ([evidence](../evidence/2026-11-06-microsd-r49-suspend-abort.json)) |
| USB device mode | Reliable enumeration, debug networking, reconnect, supported user-facing profiles, charging interaction | Partial: NCM/ACM configured, HTTP and root serial shell verified; full reconnect/power qualification pending |
| USB host or OTG | Establish product support, then peripheral enumeration, power/role switching, disconnect and resume | Unverified |
| Display | Actual panel/revision; DRM ownership; correct colors/timings; blank/unblank; orientation; no retained-logo false pass | Installed r3: native console/SSH/Wayland, taint 0, all four display controls auto after temporary initial holds. Earlier native r1 RAM RGB/off-on physically confirmed. Initial enable error04000000 persists. Since r15 (2026-11-01) startup needs no workaround: 20 unattended boots start Sxmo with msm DRM, owner-confirmed visible with touch ([evidence](../evidence/2026-11-01-display-startup-fix.json)); suspend remains open. Native Wayland terminal/keyboard is physically visible with Pixman. See [installed evidence](../evidence/2026-10-29-native-r1-installed-boot.json). 2026-11-01: sway now turns the panel back on at the first `power on` after `power off` (wlroots gamma-reset fix, 5 of 5 vs 0 of 5 unpatched; [evidence](../evidence/2026-11-01-sway-power-on-gamma.json)) |
| Backlight | Correct controller; useful brightness range; off state; dimming and resume without flicker or stuck output | Partial stock baseline: visible at half brightness; mainline backlight lit with hardware fault status zero. Full range/off/resume unqualified |
| Touchscreen | Actual controller/revision; full-area coordinates, multitouch, edge behavior, orientation and suspend/wake | Installed r1: requested gestures record 2,468 events, 23 matched starts/releases, max 2 contacts, X19–719/Y0–1278, no SYN_DROPPED or contacts left active. Both board-DT axis inversions physically pass on an installed r2 boot with compositor identity; r3 retains them and passes its combined installed physical test. Full edge/rotation/power/noise acceptance remains open |
| Physical buttons | Power, volume up/down, home, long presses, recovery combinations and wake where supported | RAM d80: Home102, VolumeDown114 and VolumeUp115 each3 matched presses/releases, no drops/stuck keys. Signed r3 installed/booted with matching DTB; installed physical retest passes with one matched pair per key; long presses, UI actions and wake remain open |
| Graphics acceleration | Actual Freedreno renderer; rendering correctness, compositor stability, load and memory-pressure behavior | Partial, installed signed r7: A305B 3.0.5.18 through a new GPU IOMMU; freedreno FD305 GLES 3.0; kmscube 60 fps vsync-locked (RAM test), no faults; devfreq simple_ondemand 19–450 MHz. Owner confirms the GLES2 Sxmo session displays normally with responsive touch and keyboard. Devfreq downscaling, long-session memory, stability and power pending |
| Wi-Fi | Supported bands; scan, authentication, DHCP/DNS, sustained transfer, stable MAC, reconnect and resume | Partial, installed signed r6, taint 0: WCN v2.0/Iris TSMC 3.0 firmware from the device's partitions. WPA2 association on 5 GHz ch36 (270 Mbit/s link), DHCPv4/IPv6, DNS via wlan0, 20/20 gateway pings, 48–62 Mbit/s down, 57 Mbit/s up, 250 MB sustained, 5/5 reconnects, radio off/on, and 10/10 reconnect/scan cycles after the cfg80211 scan-block fix. Forced 2.4 GHz ch11: association, DHCP, 40.6 Mbit/s, 30/30 pings. Resume, overnight soak, early 2.4 GHz loss and factory-MAC policy pending |
| Wi-Fi hotspot | Confirm firmware capability; client association, forwarding, stability and power behavior | Partial, installed r44 (2026-11-06): default-PMF AP startup failure reproduced and fixed with a wcn36xx-specific NetworkManager default. WPA2-CCMP on 2.4 GHz ch6: independent RTL8188CUS USB client associates and receives DHCP; 10/10 baseline pings; a verified 16 MiB direct transfer and 16 MiB Wi-Fi-to-USB forwarded transfer; five client reconnect cycles each pass 3/3 pings and a verified 16 MiB forwarded transfer. Host default route/DNS unchanged. The signed device-lg-madai-1-r2 APK is now installed; its regenerated boot image matches readback, and post-upgrade warm boot/default-hotspot startup pass ([package evidence](../evidence/2026-11-06-hotspot-package-installed.json)). No PMF/BIP support added. On r49, two simultaneous USB clients pass DHCP, 5/5 pings each and concurrent 16 MiB transfers in four baselines; direct-kernel resume loses AP stations/data, and ordinary system suspend deactivates the non-autoconnect test AP. An explicit AP teardown/restore coordinator candidate passes two RTC suspend cycles with both clients automatically recovering, 5/5 pings each and verified 16 MiB transfers; the installed Sxmo 1.18.1-r6 path subsequently passes two bounded cycles with both clients, 96 MiB verified total including baseline, and unchanged r49 boot readback ([installed evidence](../evidence/2026-11-06-sxmo-hotspot-installed.json)). Full UI/autosuspend-loop and longer AP qualification remain open ([coordinator evidence](../evidence/2026-11-06-hotspot-coordinated-suspend.json)). Baseline failure details: ([r49 evidence](../evidence/2026-11-06-hotspot-r49-two-clients-and-suspend.json)). External DNS/Internet, power and long soak remain unqualified ([evidence](../evidence/2026-11-06-hotspot-default-and-client.json)). |
| Bluetooth | Controller/firmware; discovery, pairing, transfer, HID, supported audio profiles, reconnect and resume | Partial, installed r6: Qualcomm HCI v6 controller over btqcomsmd. Discovery and outgoing ACL (l2ping 10/10) work. Phone-initiated SSP pairing with the host bonds, and the passkeys match. With an independent Broadcom USB peer, phone-initiated SSP pairing bonds; three bonded RFCOMM connections each deliver 4 MiB with matching SHA-256 at about 1.2 Mbit/s, with WLAN on 5 GHz. Earlier PC-adapter failures were peer-acceptance and harness artifacts. HID, audio, address source and resume pending |
| Wireless coexistence | Wi-Fi plus Bluetooth audio/data, suspend, modem activity and charging without persistent disruption | Unverified: an earlier WLAN-state correlation was confounded by host-side behaviour and is withdrawn. Iris rails switch off with the WLAN radio off; the effect on Bluetooth is unproven |
| GNSS | Outdoor cold/warm fix; position/time sanity; acquisition logs; assisted and standalone behavior as exposed | Unverified: MSS is disabled and no location service has been exercised. Generic GNSS class-node absence does not establish product absence. See [modem/GNSS dependencies](modem-bringup.md) |
| NFC | Actual controller and antenna path; tag reading and supported transfer modes; suspend/restart | Partial: production PN547/QUP3/GPIO/rising-IRQ/CXO_D1_PIN wiring is audited. A matching r58 moduleless RAM boot and timer return pass. Same-ELF unsigned/altered-signature controls are rejected; matching signed modules complete four cold probe/remove cycles, with released pins/IRQ, zero clock votes and zero taint ([cold evidence](../evidence/2026-11-08-nfc-cold-lifecycle.json)). These cycles do not exercise NCI communication or pending IRQ/open unregister. A later source fix retains receive through the closing reset; the matching r59 kernel/APK and all 468 modules pass host crypto/ABI/dependency checks. The XZ3 and XZ4 transfers time out after 512 KiB and 656 KiB respectively, before readback or BOOT. Both return to r50/r5. r59 startup remains untested. [XZ4 attempt](../evidence/2026-11-10-nfc-r59-xz4-transfer-timeout.json). Installed r50 still has QUP3 disabled and no NFC modules. Controller/tag/RF/userspace/PM, real open teardown and installed update/recovery remain open ([NFC work](nfc-bringup.md)) |
| FM radio | Establish product exposure first; if present, tune/receive, antenna/audio routing and resume | Unverified |
| Battery sensing | Battery type, voltage, current, temperature, capacity trends and low-battery reporting | Signed r4 IADC arithmetic and stock baseline pass. Experimental BMS lookup/calibration/lifetime and discharge response pass; 37 getter cases include temperature. RAM thermistor readings agree around 32.6–32.7°C; independent accuracy is open. RAM firmware now selects the stock profile and passes all 155 OCV points/design attributes to r4. No current capacity or usable UPower battery interface is qualified. USB-idle current/counter and first-probe behavior remain unresolved. Raw BATFET IRQ guard is rejected after ~6799 IRQ/s. No promotion; see [battery work](battery-bringup.md) |
| Charging | Correct input/charge limits; plug/unplug, termination, temperature response, power-off charging as supported | In progress: RAM firmware gate and Linux managed policy now validate runtime profile/sensors, user inhibition and supplier loss while USB HTTP stays available. Forced supplier rebind needs explicit drivers_probe. Model/fault/quiesce/ABI tests and ARM builds pass; actual thermal boundaries, system suspend, watchdog timing, USB negotiation, current accuracy, termination and powered-off charging remain open. BTC stays conservative; the policy remains RAM-only and installed r50 is unchanged. See [native policy evidence](../evidence/2026-10-30-smbb-native-policy.json) |
| Thermal management | Sensors and trip behavior; sustained CPU/GPU/media loads; throttling and recovery | Partial observation only: r49 reports two CPU zones with passive 75°C/critical 110°C trips; bounded 30 s four-core load peaks at reported 47°C and recovers without changing policy. Sensor accuracy, sustained mixed loads and actual throttling remain unqualified ([evidence](../evidence/2026-11-06-cpu-thermal-bounded-r49.json)) |
| Suspend and wake | Verified sleep state; measured unplugged consumption; buttons, RTC and required MPU-6515M DMP interrupt wake, plus other supported event wake sources | In progress (r19, 2026-11-01): s2idle works. 20 of 20 RTC-woken 20 s suspend/resume cycles pass with touch, display, Wi-Fi, ADSP/WCNSS and sound back each time; owner confirms Sxmo and touch after resume, and the power key wakes it (owner-tested). Fixed on the way: the in-cell touchscreen now follows the panel (it hung the I2C bus once the display went off) and MDP5 hwpipe state after resume. No cpuidle states yet, so no measured savings; Sxmo lock/screen-off states and current draw remain ([evidence](../evidence/2026-11-01-s2idle-touch-mdp5.json)). 2026-11-02: CPU idle standalone power collapse works on all four cores (local-timer-stop broadcast fix, kernel r44); about 90% of idle time collapsed, s2idle still succeeds ([evidence](../evidence/2026-11-02-cpuidle-spc.json)) |
| Clock and RTC | Correct timekeeping, time synchronization, suspend continuity and alarm behavior as supported | Unverified |
| Power-off and restart | Clean shutdown, restart, low-battery handling and repeatable subsequent boot | Unverified |
| Speaker | Playback, volume, amplifier behavior, supported rates, no persistent distortion and suspend recovery | In progress (audio probe kernel): mainline QDSP6 + SLIMbus + new WCD9306 component play to the speaker: worked on installed r14 (owner-confirmed), but since then the speaker is silent on most boots with every software indicator normal; under investigation ([regression evidence](../evidence/2026-11-01-speaker-regression-open.json)); volume range, rates and suspend pending ([evidence](../evidence/2026-11-01-speaker-installed.json)) ([evidence](../evidence/2026-10-31-first-speaker-playback.json)) |
| Earpiece | Playback and telephone routing, volume, proximity interaction and call transitions | Unverified |
| Microphones | Every installed mic; recording, route selection, simultaneous playback/record and supported processing | Unverified |
| Headset jack | Insert/remove detection, headphone playback, headset microphone/buttons where exposed and route transitions | Unverified |
| Bluetooth audio | Supported playback/call profiles, route switching, reconnect, recording and suspend behavior | Partial, installed r7: A2DP playback to JLab Studio headphones (48 kHz stereo); owner heard correct left/right tones; AVRCP play/pause events work. The session now starts PipeWire/WirePlumber automatically (verified after a clean reboot); HFP calls, microphone, reconnect and suspend pending |
| Audio policy | Correct ALSA UCM/PipeWire routing across media, calls, speakerphone, headset and Bluetooth | Unverified |
| Accelerometer | Owner-reported MPU-6515M: confirm silicon/wiring; axes/mounting, movement, buffered data, screen rotation and resume | Partly verified (installed kernel r9/r10): WHO_AM_I 0x74 confirms MPU-6515 on BLSP1 I2C2 (I/O rail LVS1); mainline `inv_mpu6050` probes at boot and responds to vibration; magnitude reads 0.91 g at rest; axes/mounting, rotation and resume pending ([evidence](../evidence/2026-10-31-imu-vibrator.json)) |
| Gyroscope | Owner-reported MPU-6515M: confirm silicon/wiring; angular-rate response, axes, buffered data, calibration and resume | Partly verified: same MPU-6515 via `inv_mpu6050`; angular-rate channels respond to vibration; axes, calibration and resume pending ([evidence](../evidence/2026-10-31-imu-vibrator.json)) |
| MPU-6515M DMP access | Matching firmware provenance/loading/execution; decoded FIFO outputs/events through a documented Linux ABI; raw/DMP switching, overflow/reset/reload recovery and userspace example | In progress (2026-11-06): pinned 2,943-byte manufacturer MPU6515 image matches the reference driver CRC; private extraction/provenance recipe and seven targeted tests pass. Corrected on-device RAM upload verifies every byte and restores/verifies the pre-retry snapshot. Initial sequential-read trial failed image/restoration verification and its first pre-test RAM restoration remains unproven. Corrected two-second execution decoded 44 accelerometer and 44 six-axis quaternion packets with RAM/configuration restoration; native ABI, stability and wake remain unqualified ([execution evidence](../evidence/2026-11-06-mpu6515-dmp-execution.json)). Owner later rebooted after an apparent black-screen lockup; cause/relationship unverified. Native quaternion IIO code has booted; initial FIFO trial exposed a scan-size stack overflow, now corrected. Updated modules captured 125 samples in five seconds and restored raw access/service. Exact scale now reports correctly; three further raw/DMP/raw cycles each captured 75 samples. Full recovery/accuracy, packaging and wake remain open; 32 host tests pass ([current evidence](../evidence/2026-11-06-mpu6515-native-stream-and-scale.json)) ([candidate](../evidence/2026-11-06-mpu6515-native-iio-candidate.json)) ([evidence](../evidence/2026-11-06-mpu6515-dmp-memory.json)); native raw support alone remains insufficient. |
| MPU-6515M DMP interrupt wake | Real system suspend; physical DMP event wakes AP through verified routing; retained event and IRQ/wake-source evidence, masked-event control, at least 20 consecutive cycles, no storms and measured battery standby | Native SMD wake pilot passed: 32.21 s traced s2idle, retained status 0x04, one IMU IRQ and no RTC IRQ. Masked motion slept until RTC with no IMU IRQ/event. Owner confirms display/touch recovery. The later r49 trial passes all 20 consecutive DMP cycles and a same-build masked-motion control; the total 50-cycle gate and battery qualification remain open ([awake evidence](../evidence/2026-11-06-mpu6515-dmp-smd-awake.json)). Ordinary data-ready or raw motion wake alone is insufficient; see [plan section 6.1](bringup-plan.md#61-mpu-6515m-dmp-access-and-interrupt-wake) |
| Magnetometer | Establish presence; heading response, axes, calibration and resume | Partly verified: ALPS HSCDTD008A (WIA 0x49) at 0x0c, VDD L19; mainline `ak8974` reads a steady field; in the installed kernel since r9; heading, axes, calibration and resume pending ([evidence](../evidence/2026-10-31-imu-vibrator.json)) 2026-11-02: mounting matrix measured with the owner (six poses, up-minus-down) and in the DT since r30 ([evidence](../evidence/2026-11-02-camera-rotation-and-compass.json)); hard-iron calibration is left to userspace. |
| Ambient light | Raw sensor response, brightness integration, sensible transitions and resume | Unverified |
| Proximity | Near/far response; screen behavior during calls; wake and resume as supported | Unverified |
| Other sensors | Inventory every additional sensor; define raw-data and user-facing tests before closure | Unverified |
| Vibration | Correct actuator, duration/intensity as exposed, notifications and resume | Installed r50: measured PM8226 code 21 (2.1 V target) at strength 39168; profile and new-session inheritance pass. Normal/muted/re-enabled Sxmo notifications reach Dunst once each, with bounded 300 ms pulses or no enabled samples when muted. The source range correction remains unbooted. Tactile quality, lock/suspend and resume remain open. [Native notification evidence](../evidence/2026-11-10-sxmo-notification-haptics.json) |
| LEDs and button lighting | Identify each channel; brightness/color, notifications, off state and resume | Unverified |
| Rear camera | Identify sensor/calibration; correct media graph, stills, exposure, orientation/color, reopen and resume | Stock ID0x8179 confirmed; static library geometry decoded. New IMX179 driver identifies the sensor (0x8179) and captures a recognisable RAW10 image through CSIPHY0/CSID/ISPIF/VFE RDI and the VFE IOMMU on a RAM boot (needed MMCC M/N, IOMMU stream-ID, RDI frame-geometry and DMA-segment fixes); every 3280×2464 frame complete with no IOMMU faults; in the installed kernel since r13 (AXI clock raised while streaming); libcamera captures full-resolution RGB through its GPU software ISP (about 1 fps); gain control needs a libcamera IMX179 helper; no processing, front camera pending. 2026-11-01: libcamera IMX179 sensor helper, crop rectangles, rear location and a 2×2 binned 1640×1232 mode at 30 fps (kernel r27); AGC settles in about 4 s on the binned preview ([evidence](../evidence/2026-11-01-rear-camera-binned-preview.json)). Real-scene colour, orientation, reopen and resume still unqualified 2026-11-02: image rotation 270 (both cameras, owner-checked scene), no mirroring ([evidence](../evidence/2026-11-02-camera-rotation-and-compass.json)). Real-scene check 2026-11-02: correct orientation, black level 64 verified; low-light quality limited by the libcamera soft ISP ([evidence](../evidence/2026-11-02-camera-real-scene.json)). |
| Front camera | Identify sensor/calibration; stills, orientation/color, switching, reopen and resume | Stock ID0x0132 confirmed; static library geometry decoded; stock capture and maintained driver/capture pipeline unverified. 2026-11-01: new IMX132 driver and board wiring (kernel r28): ID 0x0132, one-lane RAW10 at 14.37 fps as computed, colour-bar test pattern correct (RGGB), real image through libcamera with an IMX132 helper ([evidence](../evidence/2026-11-01-front-camera-imx132.json)). Orientation, reopen and resume still unqualified 2026-11-02: rotation 270, no mirroring, owner-checked ([evidence](../evidence/2026-11-02-camera-rotation-and-compass.json)). Real-scene check 2026-11-02: correct orientation, black level 64 verified; low-light quality limited by the libcamera soft ISP ([evidence](../evidence/2026-11-02-camera-real-scene.json)). |
| Lens control | Establish actuator and capabilities; autofocus/manual controls where fitted; repeatability | Source candidate only; actual part/control/calibration unverified |
| Optical stabilization | Establish actual OIS module; preserve coefficients, qualify stabilization/control/resume where fitted | EEPROM maker0x01 selects old LGIT path; three matching bank0 reads backed up privately; capacity/other banks, coefficient validity and physical controller/functionality unverified |
| Camera flash and torch | Verify supported hardware modes, control, exposure synchronization, limits and off state | Torch works in the installed kernel (r11) with a new mainline-style driver: `white:torch`, 16 steps to 200 mA, toggled by Sxmo's flashlight action; the rear camera sees the light (mean 67 → 366); enabling the module pauses USB charging; flash strobe, 5 V boost and limits pending ([evidence](../evidence/2026-10-31-kernel-r9-r10-and-torch.json)) |
| Video capture | Supported front/rear modes, sustained capture, frame integrity, audio synchronization and playback | Unverified |
| Video codec hardware | Identify exposed encode/decode blocks; supported formats, actual acceleration, load and stability | Unverified |
| SIM interface | Detection, insertion/removal behavior supported by the hardware, PIN handling and missing-SIM state | Blocked for SIM-based tests |
| Modem control | Firmware/remoteproc, control transport, ModemManager integration, radio power and no restart loops | Identified: r50 MSS node is disabled; only ADSP/WCNSS run and active ModemManager has no objects. Stock firmware names resolve through the configured loader path. A stock-derived MSM8926 supply/descriptor candidate passes host checks with modem and S5 disabled; no firmware start, QMI or RF pass. See [modem work](modem-bringup.md) |
| Cellular data | Supported network registration, APN, IP/DNS, transfer, reconnect, tethering as exposed and resume | Blocked without SIM/network |
| SMS | Send/receive, notifications, encoding and wake from suspend | Blocked without SIM/network |
| Voice calls | Incoming/outgoing, DTMF, earpiece/mic, speakerphone, headset, Bluetooth, proximity, suspend wake | Blocked without SIM/network |
| Network modes | Bands and modes supported by this device/network; airplane mode; VoLTE/IMS only if supported | Blocked for network qualification |
| UI integration | Keyboard, rotation, lock/unlock, notifications, camera/audio selection and console recovery | Native Wayland/Sxmo terminal and keyboard physically work using Pixman; installed r2 orientation passes. A physical-trace-driven gesture profile passes synthetic replay on installed r3; physical close/open retest passes; remaining integration tests pending |
| Updates | Current packages; kernel actually changes after update; DTB/initramfs deployment; recovery to known-good image | Partial: repository refresh/upgrade audited earlier; native r3 replacement and subsequent boot pass; saved native16 fallback fails startup acceptance. Frozen-r3 rescue/menu repair pass across the kernel r4 upgrade. UPower r4 installation, native CLI/services and regenerated artifacts pass; the later sensor diagnostic returns to a fresh r4/UPower r4 boot. UPower r5 is now installed on r50 with matching daemon, native startup/CLI checks and byte-identical boot readback after normal hooks. No whole-system currency claim. Live package/root rollback and final-layout update tests remain pending. See [UPower evidence](../evidence/2026-10-30-upower-telemetry-r4.json) and [return boot](../evidence/2026-10-30-sensor-ownership-and-id.json) |
| Final storage layout | Full restoration coverage/rehearsal before repartition; one maximum-capacity native root and minimum justified extra partitions; external SD removable | In progress: host-only 14.30 GiB ext4/GPT preview and offset-aware updater source checks pass; factory-stock rehearsal, minimum retained-partition audit and all physical migration/update/recovery tests remain open |

## Reliability qualification

Initial project targets are 20 cold boots, 20 warm reboots, 50 suspend/resume cycles (including at least 20 consecutive DMP interrupt wakes), a 24-hour mixed-use soak, and overnight unplugged standby with DMP wake armed. Record counts and failures, not just a final boolean. Re-run affected tests after changes to shared regulators, memory reservations, firmware, USB, audio, or power management.

Measure idle memory, available storage, suspend power, thermal behavior, and representative interactive latency. Establish numerical power and performance targets after stock and early Nura measurements; do not invent battery-life claims from the nominal capacity.

Include charging plus camera, Wi-Fi plus Bluetooth audio, cellular call plus proximity/blanking, GNSS plus suspend, and microSD I/O plus suspend. Fresh installation, userspace upgrades, and kernel updates require their own passing evidence.

## Final closure

Every physically present feature needs a passing result on the final current stable image, with the source manifest attached. Tests blocked by missing equipment, SIM, network access, or implementation remain open. Stock defects require repair or an explicit change to the agreed goal; they are not an automatic exception.

Maintain an issue for each failed or blocked row with the next diagnostic step, dependencies, upstream destination, and evidence. Add discovered components to the matrix rather than limiting scope to this initial list.

## Latest native UI confirmation and r58 NFC preparation

The owner confirms working display and touch on native r50 boot
`28db1c68-3b08-4a53-8e5a-3397b8315813`; its original boot hash, zero taint,
running systemd, Sway and sensor proxy are rechecked. The corrected r58
NFC family now has a separate moduleless RAM image and checker, passing 30
fixture cases including rejection of the older r56 release and marker.
Kernel/DTB bytes match the signed r58 APK; qualified init/USB/HTTP/BusyBox
and the independent 180-second return timer remain unchanged. The image
is unstaged and unbooted at this checkpoint. See [r58 startup details](../diagnostics/nfc-startup/teardown-startup.md)
and [preparation evidence](../evidence/2026-11-08-nfc-teardown-startup-preparation.json).

Fresh byte comparisons also correct an earlier audit count: each r56/r58
build has 21 changed source files matching its published commit. The old
field reported ELF symbol-string-table bytes. Original reports and all
linked artifact hashes are preserved; [the erratum](../evidence/2026-11-08-nfc-source-comparison-correction.json)
adds no runtime or hardware qualification.

## Physical r58 startup and eMMC warm-reboot persistence

The corrected r58 family passes one moduleless RAM startup and timed return to
installed r50. Its original packed image first times out before BOOT; after
terminal transfer recovery and an owner-confirmed native boot, isolated XZ
preset-3 encoding preserves the exact runtime Image/ELF/notes/certificate/ABI.
The new image reads back exactly, the actual startup checker passes, and its
84-byte notes match the linked r58 build. Four CPUs, no modules and one unbound
PN547 client at QUP3 `1-0028` are observed. The timer returns at 181.610626 s,
with serial and 22 complete HTTP pairs. Original r50 hash, zero taint, 1.15 V
PMIC target, policy and UI services are restored; owner confirms display/touch
on boot `98ab64c6-01c6-4c1e-91a2-433fc3afc4cf`. See
[startup evidence](../evidence/2026-11-08-nfc-moduleless-startup.json).

The preceding intermediate native reboot also verifies the retained 512 MiB
eMMC pattern with direct reads, full pattern and hash checks, and no ext4
errors. Its exact synthetic files are archived/removed after the later RAM
return. This is warm-reboot persistence, with power-loss/endurance qualification
still open. See [storage evidence](../evidence/2026-11-08-emmc-cross-boot-persistence.json).

Signed module runtime checks, NFC GPIO/clock ownership/teardown, controller/RF/PM
and wider bringup remain open. Original build/package/image artifacts and the
protected root index are unchanged. The USB transport fault remains unresolved;
native systemd currently waits on time synchronization with no failed units.

## NFC signature and cold lifecycle qualification

A matching r58 RAM image rejects same-ELF unsigned and altered-CMS rfkill
controls with key errors/status 129, then loads all five signed modules in
dependency order. Four cold probe/removal cycles include three explicit
unbind/rebind rounds and final ordinary reverse module unload. Twelve
snapshots verify VEN/FIRM low, IRQ21 input/pull-down, pinmux ownership and its
release, NFC/rfkill parentage and zero reference-clock votes. All NFC IRQ
counters are zero; 48 temperature samples are 38–39°C. The final state has
no modules, class/rfkill child, IRQ handler or pin owner. The independent timer
returns at 181.622714 seconds to original r50 with zero taint, programmed
1.15 V APC target, running systemd, synchronized time and UI services. Latest
owner display/touch status is recorded separately in
[the evidence](../evidence/2026-11-08-nfc-cold-lifecycle.json).

The checker passes 43 host modes, detects three isolated weakened guards and
preserves the qualified kernel/DTB/command line plus all fourteen original
CPIO entries. See [procedure and limits](../diagnostics/nfc-startup/cold-lifecycle.md).
NCI reset/init, tag/RF/userspace/PM, open-device or pending-IRQ teardown and
firmware concurrency remain unqualified. The candidate is RAM-only; installed
update/recovery, intermittent USB/time-sync faults and broader bringup remain open.

## NCI startup remains physically pending

A separate r58 RAM image is prepared for one NCI up/down pair. It retains the
qualified kernel/DTB/command line, fourteen base CPIO entries and 180-second
init timer, with the same five signed modules plus a static ARM get/up/down
helper. The helper validates kernel sender, sequence, family, attributes, ACK
and fresh powered state; failed/short/interrupted mutations are not resent.
The shell requires reset/init/mapping response traces and identity fields,
active/cold GPIO and clock votes, then cold module cleanup. No polling, RF
discovery, vendor, secure-element or firmware request is exposed.

Thirteen host tests cover 105 cases and detect five weakened guards. Host
sanitizers and ARM emulation each pass 16,384 packet byte/length variants;
all 79 helper cases match under ARM emulation. Independent image and exact
ARM BusyBox checks pass. These are preparation/model results, with real NCI
controller communication still unqualified. See [procedure](../diagnostics/nfc-startup/controller-startup.md)
and [preparation evidence](../evidence/2026-11-08-nfc-controller-preparation.json).

The image is unstaged/unbooted. Its actual entry refuses the pending physical
UI result before importing the phone client. Native r50 boot
`2e6126b9-498e-4d89-b23e-f08fe6ccc361` retains the original hash, zero taint,
running synchronized services, low VEN/FIRM, released NFC pins and zero
reference-clock votes. New native pre/postflight also checks those pin/clock
conditions. Current exact-boot display/touch confirmation remains pending.

## November 8: open NFC teardown source correction

The new [source evidence](../evidence/2026-11-08-nfc-open-teardown-source.json)
shows that r58 open unregister loses its closing reset response because the
IRQ was already released, while kernel close still returns success. The fix
keeps receive available through unregister, then drains it outside the mode
mutex before freeing state. Five host tests / ten cases, five broken variants
and the r58 baseline control verify the modeled behavior; three ARM objects
compile with W=1 and CFI. This is source verification, with no new kernel,
package, RAM boot or hardware acceptance. A fresh matching module family is
required because the private operations type changed. Existing r58 cold
qualification remains intact; open/pending IRQ timing, controller/RF/PM and
firmware concurrency remain unqualified. Exact latest-native display/touch
confirmation remains pending; the older moduleless return was already passed.

## November 8: matching open-teardown NFC build verified on host

A separate r59 kernel/module/APK build completes with a new certificate and
unchanged CFI/signing/full-DWARF policy. All 22 changed source files, 468 module
signatures, 25,562 imported CRCs and 468 binary-index loader requests verify.
The changed private operations ABI is observed in nxp_nci_probe; the new I2C
module rejects the r58 export map. APK signature controls and isolated
r58-to-r59 usermode replacement pass, with 549 final files matching the APK
and install hooks disabled. See [evidence](../evidence/2026-11-08-nfc-open-teardown-package.json).
These results establish host build/package integrity. No r59 RAM image, boot,
physical signature enforcement, NCI communication, open/pending IRQ teardown
or installed update/recovery is qualified. Original r58 evidence remains
unchanged; the current exact-boot UI check remains pending.

## November 8: matching r59 moduleless RAM preparation

A new [prepared image](../manifests/nfc-open-teardown-startup-ram.json) contains
no modules/firmware and retains the qualified independent return timer and
eleven original r58 CPIO payloads/modes. The runtime kernel is byte-identical
to the built r59 Image after lossless re-encoding. The new read-only checker
records RAM boot identity and requires released NFC pins, original moduleless
GPIO states and zero clock votes. Fifty host and exact ARM BusyBox fixture
cases, three weakened-guard controls and independent image checks pass.
The actual entry stops at the pending exact-native UI result; no phone reboot,
transfer or BOOT occurs. Separate native read-only preflight passes on the
same r50 boot with original hash, zero taint, services and programmed 1.15 V
target. These are preparation results; r59 startup, signature enforcement,
NCI communication/teardown and installed recovery remain unqualified. See
[evidence](../evidence/2026-11-08-nfc-r59-startup-preparation.json).

## November 9: battery interface inventory and userspace validity gaps

Read-only native r50 inventory confirms unchanged boot and UPower r4 binaries,
zero taint and running services. SMBB exposes no remaining-charge/capacity or
voltage/current/temperature measurement attributes. VADC/IADC are bound, but
the new processed battery channels, BMS consumer and firmware profile handoff
are absent. USB online, 500 mA input setting/descriptor and Good/Discharging
are reported states, with battery current, negotiation and SOC still unqualified.

Unchanged UPower 1.91.5 and 1.91.0-backport builds each fail eleven new validity
contracts while five controls pass under isolated UMockdev/D-Bus. False empty
critical states, infinite-capacity reporting, failed-refresh handling and
later-availability recovery require correction; the backport NaN case instead
aborts under fatal diagnostics. Genuine zero-charge protection still passes.
This is reproduction evidence, with no native fault injection, production C
change, package update, charging/radio/audio operation or reboot. GNSS/radio
class-node absence is only an inventory observation. See
[evidence](../evidence/2026-11-09-battery-telemetry-validity.json).

## November 9: UPower numeric validity correction tested on host

The source correction passes 131 current-tree and 122 backport tests, including
28 validity/lifecycle cases each, genuine-empty and existing critical-action
controls. Failed reads retain the last good report, and ignored supplies can
register when valid telemetry appears. Existing overfull behavior remains
covered; NaN alone no longer fabricates an empty system battery. Fixture event
pacing and elapsed-time corrections are distinguished from production changes.

This is host UMockdev/private D-Bus qualification. Native installed r50 and
UPower r4 remain unchanged; ARM package/deployment and physical gauge, power,
charging, stale-data policy and final hardware acceptance are pending. The latest
native return's exact display/touch answer is still pending; older confirmations
are not reused. See [evidence](../evidence/2026-11-09-battery-telemetry-fix.json).

## November 9: ARM UPower r5 candidate, deployment pending

Six native-trusted candidate APKs now build from the validated r5 recipe. Actual
ARM source fingerprints, same-target repeat-build byte identity, all signatures,
signed-metadata tamper rejection and offline actual-r50 database resolution pass.
Five ARM dummy-backend/core bodies execute under QEMU; two system-bus-dependent
bodies do not. Temporary native eager-loader/read-only CLI and daemon-help
checks pass, leaving installed r4, its PID, the database and original boot hash
unchanged. The updated daemon service and its telemetry logic have not run on
the phone. Probe files are removed. No installation, reboot or physical
power/radio/audio operation occurs. Rollback/deployment, native daemon/gauge and
final hardware acceptance remain open. See
[manifest](../manifests/upower-telemetry-r5.json) and
[evidence](../evidence/2026-11-09-upower-r5-arm-candidate.json).

## November 9: installed UPower r5, kernel r50 retained

The exact r5 daemon is now installed/running after explicit owner approval,
two-persistent-filesystem current backups and a successful isolated r5-to-r4
file/database rehearsal. Native CLI and real charger-only rejection pass;
unknown/absent display battery remains finite with no warning for more than
30 seconds after the temporary inhibitor is released. Services are active,
Sway keeps its PID and all display power controls are auto. Owned mask,
inhibitor, transaction unit and temporary transfers are cleaned up.

Normal APK hooks write the existing r50 boot image, preserving its 524,288-byte
prefix. Independent readback proves the complete raw partition, both GPTs,
all 99 boot paths/bytes, 478 module paths/bytes and 243 initramfs payloads/modes
match the backup. The 19 initramfs module payloads match installed r50. This is
same-boot software integration, without a new boot, physical UI test, live
rollback, native malformed-telemetry fault or physical gauge/power qualification.
See [evidence](../evidence/2026-11-09-upower-r5-native-install.json).

## November 9: r59 transfer timeout, r50/r5 return verified

A fresh explicit display/touch answer passes for r50 boot
`2e6126b9-498e-4d89-b23e-f08fe6ccc361` after UPower r5 installation. The
older cold-trial UI ledger stays unchanged. A new entry directory checks that
exact question, answer, software checkpoint and boot; six altered UI controls
fail before phone-client import. Fresh native preflight verifies r50/r5,
original boot hash, running services, 1.15 V programmed APC target, 40–41 C
temperatures, released NFC pins and zero reference-clock votes.

The unchanged 6,809,600-byte r59 image download times out after 524,288
completed bytes. No complete readback, BOOT, RAM startup checker or NFC action
occurs. Both transfer and stage terminate with status 1 and their PIDs are gone
before recovery. Reset only the identified USB transport, verify lk2nd, and
send one standard reboot to installed r50. Do not retry the RAM entry. The
intermittent USB fault remains unresolved; lossless XZ encoding does not cure it.

Native boot `c3ac8f04-888e-493c-bb5d-a1729a275f7d` returns with the original
raw boot hash, zero taint, 1.15 V programmed target, low VEN/FIRM, released NFC
pins and zero clock votes. UPower r5 starts automatically; all three package
records, installed ELF hashes and running daemon hash match. Three samples
keep absent/unknown battery state, finite unknown percentage 0, no warning and
OnBattery false. This is not measured zero charge. Final systemd state is
running with no jobs; Sway and sensor proxy are active, temperatures are 41 C,
and initramfs/kernel/package database/world hashes are unchanged. Host routes,
resolver and protected index match; no temporary USB network was started.

A local return-helper filename collision initially stops at an assertion before
probing the phone. A separate waiter state filename fixes it; the successful
read-only postflight and the failed wrapper records are both retained. No
additional reboot or device action follows from that correction.

A fresh native read and owner confirmation now verify display and touch on this
exact r50 return. The read-only preflight also rechecks the original boot hash,
UPower r5 and the idle NFC pins. r59 startup, NCI communication/open teardown
and RF/PM/firmware behavior remain unqualified.
[Timeout evidence](../evidence/2026-11-09-nfc-r59-transfer-timeout.json) ·
[Fresh native check](../evidence/2026-11-10-smbb-usb-budget-ram.json)


## November 10 microSD observation and bias comparison

Native r50 passes a bounded 4 MiB direct-read control with the expected read sectors, 18 SDHCI completions, zero GPIO37 interrupts and zero written sectors. A stock-matched bias candidate is prepared with a matching pull-up control, exact retained r50 kernel and the independent RAM return timer. The vendor bias difference is a hypothesis for the fsync-associated interrupt burst. Card insertion/removal, writeback and suspend still need physical comparison. [Procedure and evidence](../diagnostics/microsd/README.md)

## November 10 native camera switching and USB coexistence

Installed r50 and libcamera `99990.7.1-r2` pass alternating front/rear raw capture and reopen. Five sessions, including full-resolution rear, deliver 120 contiguous RAW10 frames with 88 validated hardware color-bar frames. Both sensors runtime-suspend after close. High-speed USB stays configured, Sway stays active, and the battery reports discharging. The final boot and package hashes match. This adds capture, reopen and USB coexistence evidence. System suspend, sustained video, active charging and lens/flash qualification remain open. [Native evidence](../evidence/2026-11-10-camera-r50-reopen.json)

## November 10 native vibrator integration

The Sxmo profile now resolves the PM8226 event path and supplies a usable strength. Three short pulses have measured enable intervals, a 2.1 V programmed target and an accelerometer response. The normal Sxmo environment-loader invocation works as the graphical user and leaves the actuator off. The candidate driver fixes have host and ARM evidence, with physical testing pending. Tactile quality, notifications and system suspend remain open. The next native boot verifies that Sway inherits both profile settings. The corrected signed RAM image remains unbooted after its download times out at 1,392,640 bytes; original r50 hashes, zero taint and idle haptics are verified after recovery. [Transfer evidence](../evidence/2026-11-10-vibrator-ram-transfer-timeout.json) The stock LED GPIO conflicts with the panel negative-enable pin and needs separate wiring verification. [Evidence](../evidence/2026-11-10-vibrator-r50-integration.json)


## November 10 native notification haptics

The installed notification monitor loses a partial record in a real-inotify control. A local backed-up correction watches completed writes and atomic moves; strict release and pinned-upstream fixtures pass seven deliveries each. The real notification daemon then passes normal/muted/re-enabled cases with one Dunst bus call per notification, two bounded 300 ms pulses at code 21 and no enabled samples while muted. The actuator returns off, all test notification files/history are removed and the mute flag is restored. Sway keeps its PID, with original r50 boot/module/package hashes and zero taint. This qualifies the awake notification path; physical visual/tactile acceptance and lock/suspend remain open. The script correction and user hook are local overrides pending package integration. [Evidence](../evidence/2026-11-10-sxmo-notification-haptics.json)


## November 10 Sxmo r7 packaging candidate

Fourteen signed ARM/noarch APKs reproduce byte for byte, preserve r6 hotspot payloads and pass current-trust/tamper, source and ABI checks. A temporary native probe of the exact package loader/profile/hook/helper passes the installed-loader control and normal/muted/re-enabled notification cases. Both real daemons retain their PIDs; original r50 boot, package database/world and idle hardware match postflight. This adds candidate packaging and native payload evidence. The installed package remains r6; package transaction/rollback, override retirement, subsequent-session input/visual checks and lock/suspend remain open. [Evidence](../evidence/2026-11-10-sxmo-r7-arm-candidate.json)


## November 10 Sxmo r7 deployment preparation

Current phone/host backups and an isolated exact r7-to-r6 restoration rehearsal
pass, including all 331 package paths, two overrides and APK database/world
bytes. The rehearsal excludes native hooks and ARM execution. Native preflight
verifies all 16 candidate/rollback signatures, unchanged boot/payload and the
same eight-package simulation. The controller is staged, but automatic approval
review requires explicit Sxmo installation approval. No installation or service
restart occurs; installed r6 and r50 remain. USB bulk upload stalls again;
pinned-identity Wi-Fi completes exact-prefix resume and backup transfer on the
same boot. Native deployment, later-session UI, lock/suspend and USB reliability
remain open. [Evidence](../evidence/2026-11-10-sxmo-r7-deployment-preparation.json)
