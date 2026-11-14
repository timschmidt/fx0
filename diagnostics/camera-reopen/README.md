# Native camera reopen and USB coexistence

This check runs the installed r50 and libcamera `99990.7.1-r2` capture path.
It opens and closes the IMX132 and IMX179 cameras in front, rear, front, rear
order. The front uses 1976×1200 RAW10 and the rear uses 1640×1232 RAW10.
Identify each camera by its libcamera location and DT path, since indices can
change. Leave normal USB networking, WirePlumber and Sway running.

Run as root on the identified phone with both sensors idle and no camera
application in use. Pass the native boot UUID from the host preflight.

```sh
python3 native-test.py --boot-id "$fx0_native_boot_id"
```

Each session requests 24 contiguous frames and checks the V4L2 sequence and
byte count. After capture starts and the sensor is runtime-active, it enables
the sensor’s V4L2 color bars. It checks at least 12 consecutive patterned
frames per session. The RAW10 decoder tests the eight bars on the four RGGB
sites at three row positions, using contrast to allow startup pedestal changes.
It records USB gadget state and battery status during capture.

A preset rear `test_pattern=2` read back as disabled after libcamera opened
the pipeline. Both rear resolutions delivered normal-sized frames in that
control run. Reapplying the V4L2 control during streaming produced a stable
pattern. This is consistent with libcamera initializing supported sensor test
patterns to off. [libcamera v0.7.1 sensor initialization](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/sensor/camera_sensor_legacy.cpp#L277)

Capture files stay on the phone in a temporary tmpfs directory. The worker
restores the pattern control, verifies both sensors have runtime-suspended,
and checks the kernel journal for new CAMSS, IOMMU and display faults. The
read-only postflight checks the installed boot and package hashes and confirms
that all temporary frame files were removed. The same capture function was
also run at the rear sensor's full 3280×2464 resolution and verified 16
consecutive patterned frames. These captures establish switching and reopen
with configured high-speed USB while the battery was discharging. Charging
and system suspend remain separate physical gates.
[Native evidence](../../evidence/2026-11-10-camera-r50-reopen.json)

## November 14 installed r1 regression

The new `current-test.py` pins installed Linux `6.18.63-fx0-vibrator-alpine`,
its linked notes and the accepted 775-package database. Sensor discovery checks
the driver/model, address and firmware node rather than requiring I2C bus 3;
this boot enumerates both sensors on bus 2. The actual discovery function passes
three renumbered inventories and rejects seven mismatches, including from a
two-file export:

```sh
python3 diagnostics/camera-reopen/check-current-discovery.py
```

The physical worker ran in one owned service with a 90-second runtime limit,
a separate stop deadline and a 512 MiB memory limit. It completed front, binned
rear, front, binned rear and full-resolution rear sessions: 24 delivered buffers
per session, 120 total. The 88 consecutive patterned frames pass the existing
four-RGGB-site/eight-bar check at three rows per frame. This samples the pattern;
it does not validate every pixel.

**The clean regression gate failed.** The independent full launch window found
`qcom-camss fda0ac00.camss: Missing ready buf 1 4!`. The old worker's text matcher
missed this diagnostic, so its `passed` field only describes its narrower checks.
Do not use that field as complete camera acceptance. The new independent
classifier rejects this actual window and also retains unfamiliar camera
diagnostics when their severity is absent or above informational level:

```sh
python3 diagnostics/camera-reopen/check-kernel-window.py --self-test
python3 diagnostics/camera-reopen/check-kernel-window.py /private/postflight.json
```

The second command intentionally exits 1 for this run. In the unchanged r1/r6
source, state 4 is `VFE_OUTPUT_IDLE`; the ISR reports ready-buffer index 1 absent
and returns before assigning a timestamp, sequence or completion. Queue draining
and a late interrupt are a hypothesis, not an established explanation. Contiguous
delivered-buffer sequences do not rule out hardware drops because this driver
increments its sequence only when a ready buffer exists. Per-session monotonic
timing and retained `cam` stdout are required to locate the warning relative to
start, capture and stop before changing the driver or accepting it as harmless.

Both sensors runtime-suspended after every close and both pattern controls
returned to zero. USB remained configured at high speed in every capture sample;
Sway and the gesture process remained unchanged. The service exited 0 and was
stopped, all owned frame directories were removed, taint remained zero, and the
independent postflight matches the accepted boot-file/package/world/repository
hashes. Raw frames stayed in temporary phone RAM and were not transferred.

The battery reported discharging, so active charging is unqualified. System
suspend, sustained capture, complete pixel integrity, scene quality, lens/flash
functions and final-image acceptance remain open. No reboot, package, firmware
or boot write occurred. The separate r2 repeat and r6 physical gates are unchanged.
[Current r1 observations and unresolved diagnostic](../../evidence/2026-11-14-camera-current-r1-reopen.json)

The subsequent [six-case timing comparison](queue-timing.md) retains capture
stdout and completion timestamps while alternating frame-file output and discard.
All 144 buffers arrive, but writing is associated with longer completion gaps.
The missing-ready warning does not repeat and remains unresolved. The comparison
adds timing evidence without closing the original clean-regression gate.

The [owned-client pause experiment](owned-pause.md) then delivers another 144
buffers across three 250 ms pauses and three unpaused controls. Four buffers
complete during each stop, followed by a new completion 60–64 ms after resume.
No kernel diagnostic recurs; neither the original warning nor the approximately
one-second file-output gaps are explained. Existing vb2 trace events expose
queue counters for the next diagnostic, but tracing has not been changed.

The [full-thread follow-up](owned-group-stop.md) strengthens the first
leader-state acknowledgement to a kernel group-stop notification plus checks of
every live thread. Its matched native repeat observes both `cam` threads stopped
and resumed in all three paused cases; all 144 buffers arrive with no new kernel
messages. The original queue warning remains open.
