# LG Fx0 hardware acceptance

## Status and evidence

All entries initially have status **unverified**. No physical test result is implied by source availability. Record two distinct results for each function: the stock baseline and the current Nura candidate. An implementation commit or device-node enumeration alone is not a functional pass.

Use these statuses: `unverified`, `identified`, `in progress`, `blocked`, `failed`, `passed`, and `absent`. `blocked` means the required test or implementation cannot currently proceed; it does not count as passed. Use `absent` only when physical or product-specific evidence shows the unit does not contain or expose the feature. Record stock hardware faults separately; an existing fault does not silently satisfy the all-hardware goal.

For each result record the exact image hash, source revisions, package manifest, unit revision, power source, battery condition, procedure, observations, log/artifact reference, and date. Keep identifiers and original logs privately; publish reviewed evidence under `evidence/` when available.

## Acceptance matrix

| Function | Required identification and functional evidence | Initial status |
| --- | --- | --- |
| Boot and recovery | Stock and lk2nd entry; correct Fx0 DTB; cold/warm boot; recovery and original-boot restoration procedure | Partial: stock fastboot/RAM boot, installed lk2nd warm reset, and stock-root restore write/read verified; automatic Nura warm boot verified; cold/key/final recovery qualification pending |
| CPU and memory | All four cores; expected usable RAM after reservations; stable stress run; frequency scaling and idle | Partial: four CPUs online, initial scaling at 300–787.2 MHz and thermal readings; complete frequency/idle/stress qualification pending |
| Firmware handoff | Correct memory reservations, firmware ownership and remote-processor startup; no corruption or restart loops | Unverified |
| eMMC | Correct layout/capacity; sustained reads/writes in the test filesystem; persistence and clean shutdown | Partial: all 39 partitions and two matching 1 GiB reads; regulator-load fix permits fresh 32 MiB random-data write/cache-cleared readback hash without MMC errors; fresh 8 MiB root-filesystem pattern survives automatic reboot; full soak pending |
| microSD | Card detect, read/write, filesystem integrity, suspend behavior, safe removal where supported | Unverified |
| USB device mode | Reliable enumeration, debug networking, reconnect, supported user-facing profiles, charging interaction | Partial: NCM/ACM configured, HTTP and root serial shell verified; full reconnect/power qualification pending |
| USB host or OTG | Establish product support, then peripheral enumeration, power/role switching, disconnect and resume | Unverified |
| Display | Actual panel/revision; DRM ownership; correct colors/timings; blank/unblank; orientation; no retained-logo false pass | Stock RAM baseline: owner confirms RGB bars after full powerdown/unblank. Mainline kernel 35: native DRM with temporary runtime-power workaround, valid panel replies, physical pixels unqualified |
| Backlight | Correct controller; useful brightness range; off state; dimming and resume without flicker or stuck output | Partial stock baseline: visible at half brightness; mainline backlight lit with hardware fault status zero. Full range/off/resume unqualified |
| Touchscreen | Actual controller/revision; full-area coordinates, multitouch, edge behavior, orientation and suspend/wake | Stock RAM baseline: 4,179 input events during owner gestures. Mainline: PLG430 probes, earlier gestures yielded no events/IRQs; kernel 35 startup-delay/NOSLEEP retest pending |
| Physical buttons | Power, volume up/down, home, long presses, recovery combinations and wake where supported | Unverified |
| Graphics acceleration | Actual Freedreno renderer; rendering correctness, compositor stability, load and memory-pressure behavior | Unverified |
| Wi-Fi | Supported bands; scan, authentication, DHCP/DNS, sustained transfer, stable MAC, reconnect and resume | Unverified |
| Wi-Fi hotspot | Confirm firmware capability; client association, forwarding, stability and power behavior | Unverified |
| Bluetooth | Controller/firmware; discovery, pairing, transfer, HID, supported audio profiles, reconnect and resume | Unverified |
| Wireless coexistence | Wi-Fi plus Bluetooth audio/data, suspend, modem activity and charging without persistent disruption | Unverified |
| GNSS | Outdoor cold/warm fix; position/time sanity; acquisition logs; assisted and standalone behavior as exposed | Unverified |
| NFC | Actual controller and antenna path; tag reading and supported transfer modes; suspend/restart | Unverified |
| FM radio | Establish product exposure first; if present, tune/receive, antenna/audio routing and resume | Unverified |
| Battery sensing | Battery type, voltage, current, temperature, capacity trends and low-battery reporting | Unverified |
| Charging | Correct input/charge limits; plug/unplug, termination, temperature response, power-off charging as supported | Unverified |
| Thermal management | Sensors and trip behavior; sustained CPU/GPU/media loads; throttling and recovery | Unverified |
| Suspend and wake | Verified sleep state; measured unplugged consumption; buttons, RTC and supported event wake sources | Unverified |
| Clock and RTC | Correct timekeeping, time synchronization, suspend continuity and alarm behavior as supported | Unverified |
| Power-off and restart | Clean shutdown, restart, low-battery handling and repeatable subsequent boot | Unverified |
| Speaker | Playback, volume, amplifier behavior, supported rates, no persistent distortion and suspend recovery | Unverified |
| Earpiece | Playback and telephone routing, volume, proximity interaction and call transitions | Unverified |
| Microphones | Every installed mic; recording, route selection, simultaneous playback/record and supported processing | Unverified |
| Headset jack | Insert/remove detection, headphone playback, headset microphone/buttons where exposed and route transitions | Unverified |
| Bluetooth audio | Supported playback/call profiles, route switching, reconnect, recording and suspend behavior | Unverified |
| Audio policy | Correct ALSA UCM/PipeWire routing across media, calls, speakerphone, headset and Bluetooth | Unverified |
| Accelerometer | Identify sensor; axes/mounting, movement, screen rotation and resume | Unverified |
| Gyroscope | Establish presence; angular-rate response, axes, calibration and resume | Unverified |
| Magnetometer | Establish presence; heading response, axes, calibration and resume | Unverified |
| Ambient light | Raw sensor response, brightness integration, sensible transitions and resume | Unverified |
| Proximity | Near/far response; screen behavior during calls; wake and resume as supported | Unverified |
| Other sensors | Inventory every additional sensor; define raw-data and user-facing tests before closure | Unverified |
| Vibration | Correct actuator, duration/intensity as exposed, notifications and resume | Unverified |
| LEDs and button lighting | Identify each channel; brightness/color, notifications, off state and resume | Unverified |
| Rear camera | Identify sensor/calibration; correct media graph, stills, exposure, orientation/color, reopen and resume | Unverified |
| Front camera | Identify sensor/calibration; stills, orientation/color, switching, reopen and resume | Unverified |
| Lens control | Establish actuator and capabilities; autofocus/manual controls where fitted; repeatability | Unverified |
| Camera flash and torch | Verify supported hardware modes, control, exposure synchronization, limits and off state | Unverified |
| Video capture | Supported front/rear modes, sustained capture, frame integrity, audio synchronization and playback | Unverified |
| Video codec hardware | Identify exposed encode/decode blocks; supported formats, actual acceleration, load and stability | Unverified |
| SIM interface | Detection, insertion/removal behavior supported by the hardware, PIN handling and missing-SIM state | Blocked for SIM-based tests |
| Modem control | Firmware/remoteproc, control transport, ModemManager integration, radio power and no restart loops | Unverified |
| Cellular data | Supported network registration, APN, IP/DNS, transfer, reconnect, tethering as exposed and resume | Blocked without SIM/network |
| SMS | Send/receive, notifications, encoding and wake from suspend | Blocked without SIM/network |
| Voice calls | Incoming/outgoing, DTMF, earpiece/mic, speakerphone, headset, Bluetooth, proximity, suspend wake | Blocked without SIM/network |
| Network modes | Bands and modes supported by this device/network; airplane mode; VoLTE/IMS only if supported | Blocked for network qualification |
| UI integration | Keyboard, rotation, lock/unlock, notifications, camera/audio selection and console recovery | Unverified |
| Updates | Current packages; kernel actually changes after update; DTB/initramfs deployment; recovery to known-good image | Partial: repository refresh and upgrade check current, initramfs/boot-file regeneration and subsequent boot pass; kernel replacement/recovery/final-layout update tests pending |
| Final storage layout | Full restoration coverage/rehearsal before repartition; one maximum-capacity native root and minimum justified extra partitions; external SD removable | In progress: host-only 14.30 GiB ext4/GPT preview and offset-aware updater source checks pass; factory-stock rehearsal, minimum retained-partition audit and all physical migration/update/recovery tests remain open |

## Reliability qualification

Initial project targets are 20 cold boots, 20 warm reboots, 50 suspend/resume cycles, a 24-hour mixed-use soak, and overnight unplugged standby. Record counts and failures, not just a final boolean. Re-run affected tests after changes to shared regulators, memory reservations, firmware, USB, audio, or power management.

Measure idle memory, available storage, suspend power, thermal behavior, and representative interactive latency. Establish numerical power and performance targets after stock and early Nura measurements; do not invent battery-life claims from the nominal capacity.

Include charging plus camera, Wi-Fi plus Bluetooth audio, cellular call plus proximity/blanking, GNSS plus suspend, and microSD I/O plus suspend. Fresh installation, userspace upgrades, and kernel updates require their own passing evidence.

## Final closure

Every physically present feature needs a passing result on the final current stable image, with the source manifest attached. Tests blocked by missing equipment, SIM, network access, or implementation remain open. Stock defects require repair or an explicit change to the agreed goal; they are not an automatic exception.

Maintain an issue for each failed or blocked row with the next diagnostic step, dependencies, upstream destination, and evidence. Add discovered components to the matrix rather than limiting scope to this initial list.
