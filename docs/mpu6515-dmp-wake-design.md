# MPU6515 DMP wake implementation notes

Status: native significant-motion events now work while awake, including one
owner-assisted physical-motion test. Suspend retention and IRQ wake are implemented, with an RTC retention control,
one physical wake pilot and a masked-motion control passing. Full qualification
is incomplete; streaming-mode suspend remains rejected.
Continuous DMP output IRQs are not evidence of the required algorithm-event
wake. Ordinary raw WoM is a separate path.

## Reference significant-motion event

The pinned manufacturer kernel at
[`04a77e80d63a6b792970c8567447f70d76ac7be4`](https://android.googlesource.com/kernel/msm/+/04a77e80d63a6b792970c8567447f70d76ac7be4/drivers/iio/imu/inv_mpu6515/)
provides an actual DMP significant-motion detector (SMD). Files are preserved
privately under `downloads/dmp-reference`; the firmware provenance is recorded
in the [memory evidence](../evidence/2026-11-06-mpu6515-dmp-memory.json).

| Contract | Source and verified interpretation |
| --- | --- |
| Enable | `inv_mpu_core.c`, ATTR_DMP_SMD_ENABLE: big-endian 16-bit Boolean at RAM 288 (`KEY_SMD_ENABLE`) |
| Threshold | RAM 344, big-endian 32-bit `value << 16`; reference range 0..32767, default 1500. Physical units still require verification. |
| First delay | RAM 340, big-endian 32-bit `seconds * 200`; reference default 3 seconds |
| Second delay | RAM 348, big-endian 32-bit `seconds * 200`; reference default 1 second |
| Execution state | RAM 352, 16 bits; debug observation only |
| Delay counter | RAM 336, 32 bits; debug observation only |
| Event status | Register 0x39 (`REG_DMP_INT_STATUS`), SMD bit 0x04; `inv_process_dmp_interrupt()` reports SMD and marks its software enable false |
| Distinct step event | Status bit 0x08 is pedometer, not SMD |

Addresses come from `dmpDefaultMPU6050.c` key mapping. Delay frequency comes
from `MPU_DEFAULT_DMP_FREQ=200` in `inv_mpu_iio.h`. These contracts need actual
firmware execution tests; their presence in source does not prove an event on
this physical sensor. The reference debug test-point patches are artificial
controls and cannot qualify a physical-motion wake.

An existing Linux IIO ABI precedent is
`drivers/iio/common/cros_ec_sensors/cros_ec_activity.c` in the maintained kernel:
significant motion uses `IIO_ACTIVITY/IIO_MOD_STILL`, CHANGE/FALLING, with an
enable control. This is a candidate for review, distinct from the MPU raw
ACCEL/ROC event. Do not invent physical threshold units or expose tunable
threshold/delay attributes before validating their semantics.

## Required native behavior and physical proof

First validate the IRQ/status event while awake, with continuous data/FIFO
interrupts disabled and actual physical motion. Establish one-shot/rearm
semantics, negative controls, retained status and stale-status clearing. Do not
infer the event from a FIFO packet, an IRQ counter alone or a forced test point.

Integrate an event-only lifecycle independent of a buffered quaternion client:
retain accelerometer/DMP power and required clocks, mask non-event producers,
keep raw-mode snapshots, and reject incompatible raw/ordinary-WoM use. During
suspend, arm IRQ wake without bus accesses after bus suspend; prevent the
threaded handler from touching a suspended adapter. On resume, identify status
0x39 bit 0x04 before clearing/rearming, emit a timestamped IIO event and restore
normal FIFO state without replaying stale packets. Handle aborts, IRQ-wake
errors, disable/rearm races, reset and missing firmware explicitly.

Use an RTC fallback and prove real system suspend entry. Require at least 20
consecutive physical SMD wake cycles, masked-SMD negative controls, IRQ and
wakeup-source deltas, retained event status, latency and no immediate-resume
storm. Then qualify battery-powered armed standby, false wakes and overnight
energy use. USB must be disconnected or its wake/power contribution isolated.
These remain part of the full [acceptance gates](hardware-acceptance.md).

Audio and audio coexistence testing remain deferred by the owner. The host's
built-in Wi-Fi must remain untouched.

## Awake implementation result (2026-11-06)

The native event-only path uses the standard activity/still CHANGE/FALLING
event and independent runtime-PM vote. It disables continuous FIFO producers,
pedometer and pedometer IRQ, clears stale algorithm status before starting and
automatically stops/disarms after observing 0x39 bit 0x04. Raw buffers/direct
access and ordinary WoM are excluded while armed. Device teardown releases the
event PM vote. Host models cover 280 startup-operation failures, stale and
pedometer status, one-shot/rearm, status errors and PM balance; ARM module
build/style checks pass.

An awake ten-second interval produced no IRQ/event, with DMP enabled, FIFO
disabled/empty and INT_ENABLE=0x02 verified physically. The owner then confirmed
readiness and was instructed to move the phone after the armed marker. One
IRQ produced activity/still CHANGE/FALLING and automatic disarm. Raw reads and
a subsequent 74-sample quaternion capture worked, with boot ID unchanged,
proxy active and taint zero. Captures were archived off-phone. This does not
prove system suspend, wake routing, physical masked-event controls or standby
energy. See [evidence](../evidence/2026-11-06-mpu6515-dmp-smd-awake.json).

## Initial real suspend evidence (2026-11-06)

The driver disables/synchronizes the IRQ outside its mutex before suspend,
retains DMP power/clock/RAM, arms IRQ wake, and defers all bus accesses until
the parent adapter resumes. A defensive suspended-state guard blocks event
reads in the IRQ path. Resume identifies retained status before re-enabling
normal IRQ handling; event timestamps represent resume attribution time.
Models cover wake-enable/disable failures, early events, aborted/RTC resumes
and status read failures. ARM build/style checks pass.

A 12.39-second traced s2idle RTC control retained DMP execution (counter delta
3679 across the 18.35-second whole call), with zero IMU IRQs and still-armed
SMD. An owner-assisted wake pilot spent 32.21 seconds in s2idle, retained
status 0x04, produced one IMU IRQ and no RTC IRQ, and resumed with 12 seconds
remaining on the fallback alarm. The masked-motion control slept 30.01 seconds
until RTC despite requested movement, with no IMU IRQ/event. Raw and quaternion
reads recover. Owner confirms normal display/touch after the positive test; an
MDP5 0x04000000 warning remains recorded and needs follow-up.

These are pilots/controls, not the 20 consecutive DMP wake cycles, 50-cycle
overall gate or unplugged standby qualification. See
[RTC retention](../evidence/2026-11-06-mpu6515-dmp-suspend-rtc-control.json),
[positive pilot](../evidence/2026-11-06-mpu6515-dmp-wake-pilot.json) and
[masked control](../evidence/2026-11-06-mpu6515-dmp-wake-masked-control.json).

The later r47 Clang/CFI package is now installed with normal boot-update hooks
and matching `6.18.59-fx0-dmp` metadata. Raw/quaternion checks, awake arming and
one 12.17-second RTC-retention cycle pass on that build with taint zero. The
owner-assisted positive pilot and masked control above remain evidence for
the earlier GCC image; r47 still needs physical motion-wake qualification.
See [r47 installation evidence](../evidence/2026-11-06-mpu6515-dmp-r47-installed.json).

The current r49 display trial keeps r47 DMP code and changes only the MSM
video startup sequence. Three RTC retention controls pass with no display
underruns and taint zero, but do not establish physical DMP wake support on
this build. The prepared 20-cycle wrapper now checks both the expected loaded
MSM build ID and r49 package ownership before arming.

## r49 consecutive qualification

All 20 consecutive owner-assisted r49 cycles pass, with one IMU IRQ and no RTC
IRQ per cycle, retained SMD status 0x04, exactly one correct IIO event, automatic
disarm and recovered streams. The downloaded artifacts were independently
reverified. Sleep intervals span 2.64–14.24 seconds; event timestamps remain
resume attribution. Proxy, wake policy, alarm and event/buffer state are clean,
taint is zero and no display underruns appear. Owner confirms display and touch.
A same-build movement control with SMD disabled sleeps 29.86 seconds until RTC
with no IMU IRQ/event. This closes the 20-consecutive gate; 50-cycle/peripheral,
overnight/battery and false-wake/accuracy gates remain open. See [positive
run](../evidence/2026-11-06-mpu6515-dmp-20-consecutive-wakes.json) and [negative
control](../evidence/2026-11-06-mpu6515-dmp-r49-masked-control.json).
