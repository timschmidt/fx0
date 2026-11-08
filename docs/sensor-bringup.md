# Fx0 sensors, MPU-6515M and DMP

The required endpoint is native raw sensor access, actual MPU DMP execution and
DMP-event wake from verified system suspend. The [acceptance gates](bringup-plan.md#61-mpu-6515m-dmp-access-and-interrupt-wake)
remain open. Native WHO_AM_I `0x74` identifies the MPU-6515, and raw IIO
sensors are working. A pinned manufacturer DMP image now passes a physical
RAM upload/readback check; no DMP algorithm execution or interrupt wake has
yet been demonstrated. Earlier sections below retain their historical results.

## Preserved stock path

The original system image contains `/etc/sensor_def_qcomdev.conf`,
`/vendor/lib/hw/sensors.msm8226.so`, `libsensor1.so`, `libsensor_reg.so` and
`/bin/sensors.qcom`. The daemon names `/sns/cal/sns.reg`. Stock init mounts the
separate `sns` partition at `/sns`; its preserved `/cal/sns.reg` is 13,056 bytes.
The original persist image instead has only `sensors_settings` in that folder.
All extracted calibration, complete proprietary files and their private hashes
stay outside the public repository and have independent-filesystem copies.

Group 2690, using the pinned
[`sns-reg` map](https://gitlab.com/msm8996-mainline/sns-reg/-/tree/4d238e5f0baba3fb77456fe2bffbf8e8f18a71a0),
occupies 256 bytes at 0x1700. All 72 shared static keys match the stock defaults,
with signed defaults masked to their actual field widths. The comparison does
not qualify the other groups or make their calibration public.

| Configuration | Bus | Address | First interrupt GPIO | Identity evidence |
| --- | --- | --- | --- | --- |
| Accel/gyro | 2 | 0x68 | 69 | Defaults name MPU6500; owner identifies MPU-6515M. Actual WHO_AM_I remains unknown |
| Magnetometer | 2 | 0x0c | 66 | Defaults name HSCD008; runtime chip identification remains open |

The [topology inspector](../scripts/inspect_fx0_sensor_registry.py) outputs only
these wiring fields and comparison status. It rejects unresolved conditional
defaults and mismatches before interpreting topology. It never emits calibration,
driver UUIDs or a registry hash. Its 270 private-input/boundary/selector/output-
isolation cases pass. Reproduce with the private registry/defaults and the pinned
map:

```sh
python3 scripts/inspect_fx0_sensor_registry.py \
  --registry /private/sns.reg --defaults /private/sensor_def_qcomdev.conf \
  --map /path/to/sns-reg/map.c
python3 diagnostics/imu-read-id/check-registry.py \
  --registry /private/sns.reg --defaults /private/sensor_def_qcomdev.conf \
  --map /path/to/sns-reg/map.c
```

The [vendor source](https://github.com/peremen/android-kernel-lg-madai/tree/03aba4427a7666d57b5ae06d375e259ea337f351)
maps `/dev/smd_sns_adsp` to the `SENSOR` channel on SMD_APPS_QDSP. The daemon
names this node too. Its `sensors_adsp.c` driver provides timing/OCMEM support,
not a direct MPU driver. The preserved sensor DTS is empty. Stock init also
starts ADSP through `/sys/kernel/boot_adsp/boot`, whose loader calls
`subsystem_get("adsp")` when required.

The proposed [SMGR IIO series](https://lkml.iu.edu/hypermail/linux/kernel/2504.0/07239.html)
supports MSM8226-class platforms, but its QRTR service discovery must be qualified
against this older firmware and direct `SENSOR` transport. The inspected
[libssc revision](https://codeberg.org/DylanVanAssche/libssc/src/commit/033e2a32095c024d6dbdfb1d4ae1db4a94be32f1)
uses QMI_SERVICE_SSC with Protobuf payloads. It does not establish compatibility
with this old SMGR path. Software fusion through either interface alone cannot
qualify execution on the MPU's DMP.

## First direct identity trial

The native r4 inventory has no active remote processor. GPIO6/7/66/69 are
unclaimed; no AP sensor adapter is present. The candidate bus 2 mapping to
BLSP I2C2 uses GPIO6/7 from the MSM8226 pin description. Numeric bus naming and
physical connectivity still need runtime confirmation.

The [fixed ID diagnostic](../diagnostics/imu-read-id/README.md) passes 800 actual
helper cases under ASan/UBSan, an ARM LLVM22 W=1 build against canonical r4 and
37 import-CRC comparisons. Its physical read-only preflight passes. Capture
then successfully shuts down ADSP through PAS1 before acquiring GPIOs. Both
released lines read low, so it returns -EBUSY before adapter registration or any
I2C transaction. The original pin control/output values pass restoration checks.
No sensor supply, reset, configuration or DMP memory is written; IRQ69 is untouched.

The supervisor initially uses synchronous `Type=oneshot` startup, so the expected
module refusal makes the launch call return failure before it saves the result.
Its existing recovery path completes. The previous-boot journal recovers the exact
PAS success, idle-low refusal and restoration messages. Future supervision uses
[`--no-block`](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html#--no-block)
plus explicit job/result observation and pre-return log capture. That supervisor
revision has not been exercised in a second hardware trial.

A fresh installed r4/UPower r4 boot is verified with taint 0, native framebuffer,
normal services and all four display controls automatic. The diagnostic is
absent and bootloader/GPT readbacks match. This is not a chip-ID, raw sample,
DMP or suspend-wake pass. Low lines alone do not identify a missing supply or
prove that the proposed pin mapping is correct. See
[evidence](../evidence/2026-10-30-sensor-ownership-and-id.json).

## Native ADSP start

With the ADSP enabled (`6fb0c0cae80b`, RAM test), the stock ADSP firmware starts
on the native r6 kernel. It publishes the QMI **Sensor Manager** service (256,
instances 0 and 1) and further unidentified services (257, 263, 264, 269) over
QRTR. That makes the stock SMGR path testable natively, in addition to direct
AP access. Starting the ADSP may also take the sensor bus, which is relevant to
the earlier low-line refusal. No sensor data has been requested yet. See
[ADSP evidence](../evidence/2026-10-30-adsp-start.json).

On installed r8 (2026-10-31), with the ADSP running on every boot, QRTR lists
the Sensor Manager (256) on nodes 5 and 7, the SLIMbus control service (769)
and the unidentified 257, 263, 264 and 269. The ADSP has **not** taken the
sensor bus: TLMM GPIO6/7 stay function 0 (GPIO) inputs, reading low with no
pull, and GPIO66/69 are idle inputs with pull-down. So the earlier idle-low
lines were not caused by ADSP ownership. An unpowered sensor rail remains the
leading explanation. The stock path normally configures the Sensor Manager
from the AP daemon (`sensors.qcom`), which Nura does not run.

## Native direct access works (2026-10-31)

The sensors answer the application processor directly once their rails are
on. The vendor kernel never configured BLSP1 I2C2 (GPIO6/7) because the ADSP
owned it, so the rails were found by switching unclaimed candidates one at a
time and reading only ID registers:

- **LVS1** (1.8 V switch, no AP consumer in the vendor description) powers
  the sensor I/O and the bus pull-ups. With it on, the IMU returns WHO_AM_I
  **0x74**, confirming an **MPU-6515**.
- **L19** (2.85 V) powers the magnetometer, which returns WIA **0x49**: an
  **ALPS HSCDTD008A**, supported by mainline `ak8974`.
- L23 is not involved.
- LVS1 needs about 5 ms before the bus works (no delay: NACK; 2 ms: zeros;
  5 ms and longer: the ID). Both drivers talk sooner, so the DT gives LVS1 a
  10 ms enable delay.

With fx0-linux `integration/fx0-imu`, mainline `inv_mpu6050` probes at boot,
`ak8974` reads a steady field, and the PM8226 vibrator appears as a
force-feedback device. Running the vibrator at the vendor's 2.4 V raises the
accelerometer's in-plane noise from about 35 to 5,000–9,000 counts, and the
gyro responds as well. See [evidence](../evidence/2026-10-31-imu-vibrator.json).

Still open:
- **Accelerometer accuracy, resolved 2026-11-01.** A six-position test shows
  correct sensitivity on all axes (0.999–1.001). The 0.90 g screen-up reading
  is a +98 mg Z zero-g offset, not a scale error. It also uncovered two
  inv_mpu6050 bugs: the MPU-6500 accelerometer offset registers are three
  bytes apart, not two, and calibbias reads skipped the runtime resume. Fixes
  are on fx0-linux `integration/fx0-imu-calibbias`. The board DT gave LVS1
  only as `vddio`, so every autosuspend reset the chip's configuration and
  left gyro readings 8× too large; LVS1 is now also `vdd`. See the
  [evidence](../evidence/2026-11-01-imu-accuracy-and-offsets.json).
- IMU mounting matrix: measured and added (kernel r17). Magnetometer matrix
  measured with the owner and added (kernel r30,
  [evidence](../evidence/2026-11-02-camera-rotation-and-compass.json)); its
  large hard-iron offset needs userspace calibration.
- `CONFIG_AK8974` in the kernel package.
- Suspend and IRQ wake.
- The DMP: mainline `inv_mpu6050` neither loads nor runs DMP firmware. The
  DMP gates need either a DMP-capable driver or InvenSense firmware support.

## Next implementation steps

1. Capture a working stock sensor baseline in a bounded RAM environment. Verify
   the original system/modem sources and use read-only, unreplayed mounts. Copy
   `/sns/cal/sns.reg` and any mutable daemon state to RAM; do not let the daemon
   rewrite the original calibration partition. Preserve the current Nura boot
   artifacts and arm recovery before loading ADSP.
2. Observe the actual ADSP/SENSOR transport and raw sensor enumeration. Compare
   TLMM function/line state, physical bus numbering, IRQ routing and regulator
   votes before and after the stock sensor path starts. Identify the exact supply
   names, voltages and startup timing before enabling native votes. Do not scan
   alternative buses or raise rails speculatively because this trial read low.
3. Choose the native ownership path from that evidence. For direct AP access,
   provide explicit ADSP sensor exclusion and verified shared-supply votes, then
   re-run the fixed WHO_AM_I read before enabling a maintained IIO driver. If the
   DSP must mediate access, implement/qualify this firmware's real transport and
   retain access needed for on-chip DMP operation. Audio coexistence must pass.
4. Qualify native raw accelerometer/gyro/magnetometer/light/proximity data,
   mounting, rates/FIFO/timestamps, reset and PM. Confirm the actual MPU revision
   and significance of the M suffix. Match DMP firmware provenance, packet/event
   ABI and supported algorithms; keep proprietary firmware/calibration private
   unless redistribution rights are established.
5. Implement DMP upload/start/stop/recovery and actual event delivery, then the
   complete wake chain and power retention. Prove real system suspend, retained
   DMP event causality and masked-event negative controls, at least 20 consecutive
   DMP wakes within the global 50-cycle requirement, and battery standby/false-
   wake measurements. Keep each result tied to exact sources and firmware.

## Pinned DMP image and physical upload path (2026-11-06)

InvenSense's AOSP `6515` HAL at `d411d613f60e6305d48ade617c848262b62a582a`
contains a 2,943-byte `dmpMemory` image. Its Linux CRC32 (seed zero) is
`0xa7e2110d`, exactly the contract in the MPU-6515 manufacturer kernel driver
at `04a77e80d63a6b792970c8567447f70d76ac7be4`. Source, agreement and firmware
hashes are pinned by the new extractor; the binary and agreement stay in
ignored private local storage. This is a reference-image candidate, not a
claim about the stock Fx0 firmware's DMP use or the part's M suffix.

A diagnostic using the bound driver's debugfs access, runtime-power hold and
temporarily stopped sensor proxy first failed by assuming that separate
MEM_R_W reads preserve auto-increment. Restoration verification also failed
and that first trial's RAM snapshot was not separately preserved; exact
restoration to its original volatile RAM state remains unproven. The DMP
was never enabled, reserved/OTP regions were not written, and native raw
sensor access and ordinary service/power state remained available.

An explicitly indexed four-byte control passed and restored its scratch
region, isolating the transaction issue. After adding explicit addressing and
a private pre-write recovery file, the corrected full-image trial verified
all 2,943 uploaded bytes across RAM banks 0–11, then restored and verified
that retry's pre-write RAM. It took 66.73 seconds; power policy returned to
auto, the sensor proxy returned active/unmasked, and taint stayed zero.

The next implementation is a maintained IIO firmware loader/lifecycle using
bounded, addressed no-increment memory-port transfers, followed by actual
DMP execution/output, a reviewed ABI and DMP interrupt wake. Neither the RAM
diagnostic nor the driver's existing ordinary wake-on-motion meets those
gates. See the [reproducer](../diagnostics/imu-dmp-memory/README.md) and
[physical evidence](../evidence/2026-11-06-mpu6515-dmp-memory.json). Audio testing
remains excluded by the owner; no audio work was performed in these trials.


## Bounded DMP execution (2026-11-06)

The corrected `check_execution.py` diagnostic ran the pinned image for two
seconds with interrupts masked. It decoded 44 accelerometer packets and 44
six-axis quaternion packets (1,056 bytes), with a maximum observed FIFO count
of 192 bytes and no partial packet remaining. The run counter advanced to 421;
it stayed at zero before enabling and at 422 after disabling. Cleanup verified
all 3,040 writable RAM bytes and functional registers, restored power/service
state, and canonicalized the memory cursor. This is an execution/output pass,
not an accuracy, native IIO, stability or suspend-wake pass.

An earlier execution produced packets but failed its final cursor readback.
Independent controls established that reading MEM_START_ADDR advances it;
the corrected diagnostic verifies functional controls and sets the cursor
without reading it. The earlier trial remains an overall failure.

A later reboot cleared the private captures and recovery snapshots in `/tmp`
before archival. The execution result survives in diagnostic stdout only.
The prior journal ends without a shutdown explanation and pstore is empty;
the owner subsequently confirmed a manual reboot after an apparent black-screen
lockup. The lockup and any relationship to the diagnostic remain unverified.
Sensor proxy is active on the new boot.
See [execution evidence](../evidence/2026-11-06-mpu6515-dmp-execution.json).
Audio remains excluded. Native IIO firmware lifecycle, parsed channels/events,
and real DMP interrupt suspend wake remain required.


### Native DMP firmware-loader stage (2026-11-06)

The isolated DMP worktree now requests `invensense/mpu6515-dmp.bin`, validates
its manufacturer size/CRC contract before writing, verifies all uploaded RAM,
and writes/read-verifies entry point 0x0400. It requires stopped DMP/FIFO and
masked interrupts and never enables execution. Always reloading avoids a stale
RAM-valid cache after reset/power loss. Firmware bytes remain private.

The complete ARM IMU object build with W=1 passed without diagnostics, and
checkpatch reported zero issues on the new file. Eighteen targeted DMP tests
pass. A new host C harness compiles the actual transport and injects each of
1,472 transfer-operation failures, with bank-boundary, lost-cursor, corrupt-
readback, bounds, busy and wrong-device controls. This models transport only;
physical native bulk transfers and loader failure paths remain unqualified.
The initial sanitizer link failed because the host UBSan library is missing;
the passing host harness uses compiler warnings as errors without sanitizers.
The loader remains staged, with no userspace entry point or installation.
Native execution lifecycle, buffered channels, IRQ parsing and actual DMP
suspend wake remain open. No audio testing or host Wi-Fi changes were made.
See [loader evidence](../evidence/2026-11-06-mpu6515-native-loader-build.json).


### Native DMP configuration and decoding (2026-11-06)

Ported the physically exercised 25 Hz accel/six-axis quaternion configuration
into the native driver, with verified bounded RAM patches. Added a one-packet
wire decoder: signed accel XYZ and Q30 quaternion XYZ, partial-packet retry,
header flag extraction and explicit corruption failure without publishing
partial/stale output. Caller-side FIFO draining/tail retention, overflow/reset,
quaternion scalar conversion and timestamped IIO output remain to implement.
Neither helper starts execution or enables interrupts.

Nineteen targeted tests pass. The actual C configuration helper stops at each
of 184 injected operation failures; the actual decoder passes every packet
fragment length, signed extremes, header flags and unknown-header controls.
Transport's 1,472 fault controls still pass. ARM W=1 driver object compilation,
checkpatch and diff whitespace checks pass. This stage is not installed or a
physical native FIFO/ABI/wake qualification. Audio and host built-in Wi-Fi
remain untouched. See [evidence](../evidence/2026-11-06-mpu6515-native-config-decode.json).


## Awake native DMP significant motion (2026-11-06)

The driver now exposes an independent activity/still CHANGE/FALLING event,
with event-only DMP configuration, PM ownership, stale-status clearing and
automatic single-shot disarm. A ten-second no-event interval verified zero
IRQs and empty/disabled FIFO. One owner-assisted physical-motion test then
produced one IRQ and the expected IIO event; raw access and 74 quaternion
samples worked afterward, with unchanged boot ID and normal service state.
All 28 targeted host tests and ARM module/style checks pass.

That result was awake-only at the time. Subsequent r49 packaging, 20
consecutive physical DMP wakes and a matched-build masked-motion control pass;
battery, overnight, accuracy and broader qualification remain unfinished. Audio stays excluded; host built-in
Wi-Fi untouched. See [evidence](../evidence/2026-11-06-mpu6515-dmp-smd-awake.json)
and the [wake implementation notes](mpu6515-dmp-wake-design.md).

Current r49 result: all 20 consecutive DMP wakes pass with retained status and
IRQ attribution, plus a same-build masked-motion RTC control. Owner confirms
display/touch recovery, taint is zero and raw/quaternion access is restored.
See [consecutive-wake evidence](../evidence/2026-11-06-mpu6515-dmp-20-consecutive-wakes.json).
