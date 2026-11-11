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
