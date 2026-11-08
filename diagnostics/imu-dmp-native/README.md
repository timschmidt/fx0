# Native MPU6515 DMP candidate

This is staged development code in `worktrees/linux-dmp`, branch
`development/fx0-dmp-smd-wake`, based on integration commit
`4b800b920c7db82e8012a580a17cc2d8ff9d5e66`. A development kernel is installed, and the corrected driver captured 125
quaternion samples in five seconds. General ABI, accuracy, stability and wake
qualification remain incomplete; the exact-scale kernel fix has booted and passed three raw/DMP/raw cycles. Audio work/testing remains excluded.

The proposed ABI adds a buffered `IIO_ROT/IIO_MOD_QUATERNION` channel to the
MPU6515 IIO device. Its scan is four native-endian signed 32-bit Q30 values in
W, X, Y, Z order, followed, when timestamps are enabled, by eight padding bytes and a native-
endian signed 64-bit timestamp: 32 bytes total. IIO aligns the complete scan
to the repeated quaternion element's 16-byte storage size.
The scalar W is the nonnegative integer square root of `2^60-X²-Y²-Z²`, matching
the reference HAL's three-element quaternion convention. Values outside the
unit-vector domain invalidate the batch. This is six-axis fusion, with no
magnetic heading correction, in sensor coordinates; mounting/accuracy and
physical rotation still need qualification. The candidate exposes scale 2^-30
and fixed quaternion sampling frequency 25 Hz. The device-level legacy
`sampling_frequency` attribute continues to describe raw capture settings.

The quaternion scan is exclusive of raw accel/gyro/temperature scans. Existing
raw scan combinations remain available. MPU6515's timestamp scan index moves
to 8 so it remains last; clients must discover scan metadata rather than
hard-code indices. Quaternion index is 7. Other chip variants keep their channels.

Starting the buffer requests `invensense/mpu6515-dmp.bin` through the firmware
loader, validates 2943 bytes and reference CRC, read-verifies uploaded RAM,
configures the proven bounded-test outputs and starts FIFO plus DMP interrupts.
The driver restores/read-verifies saved raw registers on stop; previous volatile DMP RAM is not restored. Failed cleanup
keeps restoration pending. It rejects raw-rate and ordinary WoM changes during
DMP operation. Every start reloads firmware; no RAM-valid cache spans resets.

The FIFO path retains partial packets, validates each complete batch before
publication, resets on corrupt headers/quaternions, checks the overflow IRQ and
a 992-byte guard within the configured 1 KiB FIFO, and clears stale tails during
recovery. Timestamps are reconstructed at 25 Hz anchored to the host IRQ time;
they are **not hardware packet timestamps**. Physical accuracy, latency, lost-
IRQ behavior and reset/reload recovery remain unqualified.

System suspend currently returns busy while the DMP buffer is active or
restoration is pending. This temporary limitation prevents the raw-mode resume
path from silently configuring the wrong FIFO. It does not satisfy the DMP suspend-event wake qualification. Retention and IRQ wake now have a
positive pilots and controls. The r49 build now passes 20 consecutive
physical DMP wakes plus a matched-build masked-motion control. Battery and
broader qualification remain open.

## Reader (after candidate installation and hardware verification)

Extract the private reference image with `scripts/extract_mpu6515_dmp.py` and
install it under the firmware loader's path. Do not redistribute its bytes
without established rights. Stop conflicting sensor consumers, including
`iio-sensor-proxy`, for this development capture. The reader refuses an active
buffer and ordinary WoM, restores the original scan, trigger and buffer-length
settings, and emits CSV. Run under a sleep inhibitor until suspend is supported:

```sh
systemd-inhibit --what=sleep --mode=block --who=fx0-native-dmp \
  --why=Native-DMP-development python3 read_quaternion.py --seconds 5 \
  > /var/lib/fx0-diagnostics/native-quaternion.csv
```

Create that output directory privately first. Preserve results outside `/tmp`
and copy them off the phone before rebooting. The corrected 32-byte reader has captured native data. It now also requires
an exact nonzero Q30 scale, now physically verified on the corrected kernel.
The initial zero-scale kernel is superseded. A successful reader run will not
by itself qualify motion accuracy, raw/DMP switching, wake or stability.

Host model checks (no audio tests):

```sh
python3 -m unittest discover -s tests -p 'test_mpu_dmp*.py' -q
```

The C harness compiles the real transport, configuration, execution/cleanup and
FIFO code with a modeled regmap. It stubs firmware acquisition/loading for the
lifecycle test; a separate loader test uses the private pinned image and checks missing/invalid
firmware and injected errors. It skips if that image has not been extracted.
Real power/IRQ behavior and IIO buffer integration still need physical checks. Do not equate host models with physical support.

## Trial initramfs preparation

`prepare_initramfs.py RELEASE_FILE NEW_OUTPUT_DIRECTORY` is an on-phone
preparation helper for a completed candidate with matching modules already
staged under `/lib/modules/RELEASE`. It generates files only below
`/var/lib/fx0-diagnostics`, uses a private mount namespace to substitute the candidate release metadata
and replace boot-deploy with an archive-copy-only shim. mkinitfs 2.11.0 deletes
its temporary archive when `-no-bootdeploy` is used, so simply disabling that
step cannot retain the output. The real boot-deploy is never invoked. The
installed kernel metadata is checked unchanged afterward. It does not install
a kernel or write the boot partition. Private mount namespace creation has
been verified on the installed phone; candidate initramfs generation and unchanged installed metadata have passed.
The initial pre-deployment boot-partition readback matched the preserved rollback image.
The current phone runs the later scale-fixed development image; that original
backup remains the rollback target, rather than the current live image.

## Known initial-candidate defects and current fixes

The first native FIFO trial panicked: its 24-byte local sample omitted IIO's
final alignment to a 16-byte repeated quaternion element. A timestamped scan
is 32 bytes, with timestamp at byte 24. The current driver allocates 32 zeroed
bytes and uses `iio_push_to_buffers_with_ts()` with an explicit size check.
The C harness now models that layout. Corrected driver capture passed, with
raw acceleration and sensor proxy restored and no reboot during that trial.
See [physical evidence](../../evidence/2026-11-06-mpu6515-native-capture.json).

The generic IIO formatter rounded 2^-30 to zero at nine decimal places. The
companion tiny-log2-scale patch preserves exact decimal power-of-two fractions
that would otherwise round to zero. Twenty-seven targeted tests pass, including
exact Decimal comparisons. Its kernel build and physical scale validation pass: three captures of 75
samples each, with raw reads before/after and normal service/power cleanup. The driver patch and companion formatter patch form the
[current series](../../patches/linux-integration/mpu6515-series.txt).

Current physical results and remaining gates: [stream and scale evidence](../../evidence/2026-11-06-mpu6515-native-stream-and-scale.json).
At that stage the development boot/module installation still needed package integration;
the later r47 packaged trial is recorded below.

## Significant motion while awake

The development driver now exposes
`events/in_activity_still_change_falling_en`. It arms the firmware's native
significant-motion algorithm separately from the quaternion buffer, owns a
runtime-power reference and automatically disarms after one attributed SMD
event. Re-enable explicitly for another event. Ordinary raw capture/WoM and
DMP streaming are exclusive with this event-only mode. Armed SMD can suspend when the I2C device wakeup policy is enabled. Its
retention/IRQ wake path has passed one physical pilot and a masked control;
full cycle and standby qualification remain open.

With conflicting sensor consumers stopped and debugfs mounted, the bounded
helper opens the IIO event descriptor, arms, observes, disables in cleanup and
checks subsequent quaternion capture. The output directory must be new/private:

```sh
systemd-inhibit --what=sleep --mode=block --who=fx0-smd \
  --why=Awake-significant-motion-check python3 probe_smd.py \
  /var/lib/fx0-diagnostics/smd-motion-new --seconds 60 --announce-motion
```

Wait for `ARMED` before moving the phone for about 15 seconds with USB retained.
The helper records event code, IRQ delta, arming/register readback and cleanup.
A no-event interval does not establish controlled stationarity; a recorded
event does not by itself qualify suspend wake. One owner-assisted awake event
has passed with automatic disarm and raw/quaternion recovery. Twenty-eight
targeted host tests pass. See [awake event evidence](../../evidence/2026-11-06-mpu6515-dmp-smd-awake.json).

## Real-suspend development checks

`probe_smd_suspend.py NEW_OUTPUT --seconds 12` arms SMD, uses an RTC alarm,
enters real s2idle and checks retained DMP execution with its run counter. It
restores wake policy, RTC/UDC settings and dynamic debug, and captures a private
power/IRQ trace instance. `--motion --seconds 45` expects an attributed DMP wake
before RTC; `--masked-motion --seconds 30` expects RTC wake with no IMU event.
Operator movement is required for the latter two. Run with conflicting sensor
consumers stopped. The helper uses direct kernel suspend; idle/sleep policy
inhibitors can protect it from unrelated desktop suspend requests.

A traced RTC control retained DMP execution, one physical wake pilot retained
status 0x04 with one IMU IRQ and no RTC IRQ, and a masked-motion control remained
asleep until RTC with zero IMU IRQs. Owner confirms display and touch recovered
after the positive pilot. MDP5 still logs 0x04000000 during resume; long-run
display behavior remains tracked.

`run_wake_cycles.py NEW_OUTPUT --cycles 20` performs the consecutive
qualification run. It checks each trace, single SMD event, IMU/RTC deltas,
event-only hardware registers, retained status and recovered quaternion scans,
and stops on the first failure. Each pass and the active observer/child PID
are saved durably. The operator must remain available for motion. The r49 20-cycle run now
passes, with all downloaded records independently reverified. Thirty-two targeted host tests currently pass; added KUnit
vectors remain unexecuted. See the RTC, pilot and masked-control evidence files.

## Kernel package integration

The DMP recipe is prepared separately in `worktrees/pmaports-dmp`, based on the
CPU-idle integration before the later audio experiment recipes. It applies the
four current DMP patches and uses fixed kernel release `6.18.59-fx0-dmp` with
package revision r47. Ordered patch application reproduces all nine changed
source files exactly. Proprietary DMP firmware is not packaged.

The full host Clang/CFI build and signed local binary APK now pass. All 464
modules match release `6.18.59-fx0-dmp`, and all 545 APK payload files match
the staged SHA256 manifest. APK signature verification passes. The host tools
differ from Alpine's exact versions; this is a wrapper of the host-built payload,
not an Alpine source-build reproduction. The signed r47 binary-wrapper APK
is now installed through normal APK hooks; the phone runs `6.18.59-fx0-dmp`
and its kernel metadata matches. Normal initramfs/boot-image regeneration and
boot-partition readback passed. The new Clang/CFI build passed bounded raw,
quaternion, awake arming and RTC-retention checks; motion-wake and broader
qualification remain open. See [installed evidence](../../evidence/2026-11-06-mpu6515-dmp-r47-installed.json). See [package preparation evidence](../../evidence/2026-11-06-mpu6515-dmp-package-preparation.json).
The initramfs preparation helper accepts both the fixed package release and
the earlier candidate release, and requires matching staged module metadata.

Five consecutive RTC-retention checks passed on the earlier GCC trial: each
entered real s2idle for 12.20–12.43 seconds, retained DMP execution and recovered
the quaternion stream, with RTC IRQ +1 and IMU IRQ +0. Each resume still logged
one display underrun. These results do not count as physical motion wakes.
See [RTC-series evidence](../../evidence/2026-11-06-mpu6515-dmp-rtc-series.json).

The helper also accepts `--module-tree PRIVATE_RELEASE_DIRECTORY`, constrained
to a matching release below `/var/lib/fx0-diagnostics`. It bind-mounts that
private module parent over the module search directory only inside the private
namespace. No candidate module directory needs to be installed first.

The r47 package preview passes on the phone: generated initramfs is 11,945,465
bytes, has only release `6.18.59-fx0-dmp`, and all 19 included module files
match the verified APK payload. Full before/after hashes of `/boot`, installed
modules, kernel metadata and the APK database match, as does the boot partition.
This preview intercepts boot-deploy; real boot-image generation, installation
and boot qualification remain separate. See [preview evidence](../../evidence/2026-11-06-mpu6515-dmp-initramfs-preview.json).

The next native boot-deploy preview also passes: private candidate `/boot`,
explicit no-op flash functions, Android v0 image 17,549,312 bytes, used load
addresses and command line matching the working image. Embedded kernel/DTB
and ramdisk match the verified inputs on both phone and host. The live boot
partition and installation remain unchanged. This verifies image generation,
not installation or the new kernel's physical operation. See [image preview
evidence](../../evidence/2026-11-06-mpu6515-dmp-boot-image-preview.json).

## Current packaged trial

r49 retains the r47 `6.18.59-fx0-dmp` kernel and DMP modules, with only an
experimental in-tree MSM module that flushes video state before enabling the
timing engine. Its loaded build ID is verified. Startup and three traced RTC
suspends have zero MDP5 underruns and taint zero; five quaternion captures
contain 74–75 valid samples. Final DRM/proxy state is active, with event/buffer
disabled and wake/alarm policy restored. See [r49 evidence](../../evidence/2026-11-06-mdp5-prefill-r49-trial.json).

Owner confirms display and touch after 20 consecutive r49 DMP wakes. A
matched-build disabled-SMD movement control stayed asleep until its RTC alarm.
Earlier GCC pilots remain specific to their image. Missing
interconnect support, longer/battery testing and wider MDP5 regression review
remain open. The first r48 module was incorrectly built as an external module
and tainted the kernel; it is retired. Complete r47 rollback copies remain on
phone and host. No audio testing or host built-in Wi-Fi changes.

## Consecutive motion-wake qualification (r49)

The owner-assisted run passes all 20 consecutive cycles, independently verified
from the downloaded traces, IRQ counts, retained status, event and scans. Each
cycle has one IMU IRQ, no RTC IRQ, retained SMD status 0x04 and automatic disarm.
The RTC alarm was still pending at every wake. Actual s2idle intervals were
2.64–14.24 seconds and post-wake streams total 1,498 quaternion samples. No
MDP5 underruns or kernel taint appeared; proxy and wake/alarm/event/buffer state
are restored. Owner confirms normal display and touch after the run.

A same-build masked control, repeating movement with SMD disabled, remained
asleep for 29.86 seconds until RTC (RTC IRQ +1, IMU +0, no event), then recovered
74 quaternion samples. The first positive attempt missed the owner's cue and
expired to RTC; it is not counted. See [20-cycle evidence](../../evidence/2026-11-06-mpu6515-dmp-20-consecutive-wakes.json)
and [matched control](../../evidence/2026-11-06-mpu6515-dmp-r49-masked-control.json).
This closes the 20-consecutive-DMP gate, not the overall 50-cycle, overnight,
battery, false-wake-rate or calibrated-motion-accuracy gates. Event timestamps
remain resume-attribution timestamps rather than hardware event time.
