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
| Firmware handoff | Correct memory reservations, firmware ownership and remote-processor startup; no corruption or restart loops | Partial: RAM WCNSS starts stock-matching firmware from the reserved 10 MiB region; after the DXE trigger fix, a stop/restart re-registers Wi-Fi. Modem/ADSP startup and restart-loop/soak qualification pending |
| eMMC | Correct layout/capacity; sustained reads/writes in the test filesystem; persistence and clean shutdown | Partial: all 39 partitions and two matching 1 GiB reads; regulator-load fix permits fresh 32 MiB random-data write/cache-cleared readback hash without MMC errors; fresh 8 MiB root-filesystem pattern survives automatic reboot; full soak pending |
| microSD | Card detect, read/write, filesystem integrity, suspend behavior, safe removal where supported | Unverified |
| USB device mode | Reliable enumeration, debug networking, reconnect, supported user-facing profiles, charging interaction | Partial: NCM/ACM configured, HTTP and root serial shell verified; full reconnect/power qualification pending |
| USB host or OTG | Establish product support, then peripheral enumeration, power/role switching, disconnect and resume | Unverified |
| Display | Actual panel/revision; DRM ownership; correct colors/timings; blank/unblank; orientation; no retained-logo false pass | Installed r3: native console/SSH/Wayland, taint 0, all four display controls auto after temporary initial holds. Earlier native r1 RAM RGB/off-on physically confirmed. Initial enable error04000000 persists; startup without workaround, suspend and full UI remain open. Native Wayland terminal/keyboard is physically visible with Pixman. See [installed evidence](../evidence/2026-10-29-native-r1-installed-boot.json) |
| Backlight | Correct controller; useful brightness range; off state; dimming and resume without flicker or stuck output | Partial stock baseline: visible at half brightness; mainline backlight lit with hardware fault status zero. Full range/off/resume unqualified |
| Touchscreen | Actual controller/revision; full-area coordinates, multitouch, edge behavior, orientation and suspend/wake | Installed r1: requested gestures record 2,468 events, 23 matched starts/releases, max 2 contacts, X19–719/Y0–1278, no SYN_DROPPED or contacts left active. Both board-DT axis inversions physically pass on an installed r2 boot with compositor identity; r3 retains them and passes its combined installed physical test. Full edge/rotation/power/noise acceptance remains open |
| Physical buttons | Power, volume up/down, home, long presses, recovery combinations and wake where supported | RAM d80: Home102, VolumeDown114 and VolumeUp115 each3 matched presses/releases, no drops/stuck keys. Signed r3 installed/booted with matching DTB; installed physical retest passes with one matched pair per key; long presses, UI actions and wake remain open |
| Graphics acceleration | Actual Freedreno renderer; rendering correctness, compositor stability, load and memory-pressure behavior | Unverified |
| Wi-Fi | Supported bands; scan, authentication, DHCP/DNS, sustained transfer, stable MAC, reconnect and resume | Partial, installed signed r6, taint 0: WCN v2.0/Iris TSMC 3.0 firmware from the device's partitions. WPA2 association on 5 GHz ch36 (270 Mbit/s link), DHCPv4/IPv6, DNS via wlan0, 20/20 gateway pings, 48–62 Mbit/s down, 57 Mbit/s up, 250 MB sustained, 5/5 reconnects, radio off/on, and 10/10 reconnect/scan cycles after the cfg80211 scan-block fix. Forced 2.4 GHz ch11: association, DHCP, 40.6 Mbit/s, 30/30 pings. Resume, overnight soak, early 2.4 GHz loss and factory-MAC policy pending |
| Wi-Fi hotspot | Confirm firmware capability; client association, forwarding, stability and power behavior | Unverified |
| Bluetooth | Controller/firmware; discovery, pairing, transfer, HID, supported audio profiles, reconnect and resume | Partial, installed r6: Qualcomm HCI v6 controller over btqcomsmd, powered, discovery finds devices. Address source, pairing, transfer, HID, audio and resume pending |
| Wireless coexistence | Wi-Fi plus Bluetooth audio/data, suspend, modem activity and charging without persistent disruption | Unverified |
| GNSS | Outdoor cold/warm fix; position/time sanity; acquisition logs; assisted and standalone behavior as exposed | Unverified |
| NFC | Actual controller and antenna path; tag reading and supported transfer modes; suspend/restart | Unverified |
| FM radio | Establish product exposure first; if present, tune/receive, antenna/audio routing and resume | Unverified |
| Battery sensing | Battery type, voltage, current, temperature, capacity trends and low-battery reporting | Signed r4 IADC arithmetic and stock baseline pass. Experimental BMS lookup/calibration/lifetime and discharge response pass; 37 getter cases include temperature. RAM thermistor readings agree around 32.6–32.7°C; independent accuracy is open. RAM firmware now selects the stock profile and passes all 155 OCV points/design attributes to r4. No current capacity or usable UPower battery interface is qualified. USB-idle current/counter and first-probe behavior remain unresolved. Raw BATFET IRQ guard is rejected after ~6799 IRQ/s. No promotion; see [battery work](battery-bringup.md) |
| Charging | Correct input/charge limits; plug/unplug, termination, temperature response, power-off charging as supported | In progress: RAM firmware gate and Linux managed policy now validate runtime profile/sensors, user inhibition and supplier loss while USB HTTP stays available. Forced supplier rebind needs explicit drivers_probe. Model/fault/quiesce/ABI tests and ARM builds pass; actual thermal boundaries, system suspend, watchdog timing, USB negotiation, current accuracy, termination and powered-off charging remain open. BTC stays conservative; installed r4 is unchanged. See [native policy evidence](../evidence/2026-10-30-smbb-native-policy.json) |
| Thermal management | Sensors and trip behavior; sustained CPU/GPU/media loads; throttling and recovery | Unverified |
| Suspend and wake | Verified sleep state; measured unplugged consumption; buttons, RTC and required MPU-6515M DMP interrupt wake, plus other supported event wake sources | Unverified |
| Clock and RTC | Correct timekeeping, time synchronization, suspend continuity and alarm behavior as supported | Unverified |
| Power-off and restart | Clean shutdown, restart, low-battery handling and repeatable subsequent boot | Unverified |
| Speaker | Playback, volume, amplifier behavior, supported rates, no persistent distortion and suspend recovery | Unverified |
| Earpiece | Playback and telephone routing, volume, proximity interaction and call transitions | Unverified |
| Microphones | Every installed mic; recording, route selection, simultaneous playback/record and supported processing | Unverified |
| Headset jack | Insert/remove detection, headphone playback, headset microphone/buttons where exposed and route transitions | Unverified |
| Bluetooth audio | Supported playback/call profiles, route switching, reconnect, recording and suspend behavior | Unverified |
| Audio policy | Correct ALSA UCM/PipeWire routing across media, calls, speakerphone, headset and Bluetooth | Unverified |
| Accelerometer | Owner-reported MPU-6515M: confirm silicon/wiring; axes/mounting, movement, buffered data, screen rotation and resume | Registry topology validated; ADSP shutdown passes, but low bus lines stop the first native ID trial before any transfer. Actual chip/raw data remain unverified; see [sensor work](sensor-bringup.md) |
| Gyroscope | Owner-reported MPU-6515M: confirm silicon/wiring; angular-rate response, axes, buffered data, calibration and resume | Shares the validated stock bus/address/IRQ selection with accel; physical ID/raw data remain unverified |
| MPU-6515M DMP access | Matching firmware provenance/loading/execution; decoded FIFO outputs/events through a documented Linux ABI; raw/DMP switching, overflow/reset/reload recovery and userspace example | Required, unverified; upstream MPU6515 raw support does not establish DMP support |
| MPU-6515M DMP interrupt wake | Real system suspend; physical DMP event wakes AP through verified routing; retained event and IRQ/wake-source evidence, masked-event control, at least 20 consecutive cycles, no storms and measured battery standby | Required, unverified; ordinary data-ready or raw motion wake alone is insufficient; see [plan section 6.1](bringup-plan.md#61-mpu-6515m-dmp-access-and-interrupt-wake) |
| Magnetometer | Establish presence; heading response, axes, calibration and resume | Unverified |
| Ambient light | Raw sensor response, brightness integration, sensible transitions and resume | Unverified |
| Proximity | Near/far response; screen behavior during calls; wake and resume as supported | Unverified |
| Other sensors | Inventory every additional sensor; define raw-data and user-facing tests before closure | Unverified |
| Vibration | Correct actuator, duration/intensity as exposed, notifications and resume | Unverified |
| LEDs and button lighting | Identify each channel; brightness/color, notifications, off state and resume | Unverified |
| Rear camera | Identify sensor/calibration; correct media graph, stills, exposure, orientation/color, reopen and resume | Stock ID0x8179 confirmed; static library geometry decoded; stock capture and maintained driver/capture pipeline unverified |
| Front camera | Identify sensor/calibration; stills, orientation/color, switching, reopen and resume | Stock ID0x0132 confirmed; static library geometry decoded; stock capture and maintained driver/capture pipeline unverified |
| Lens control | Establish actuator and capabilities; autofocus/manual controls where fitted; repeatability | Source candidate only; actual part/control/calibration unverified |
| Optical stabilization | Establish actual OIS module; preserve coefficients, qualify stabilization/control/resume where fitted | EEPROM maker0x01 selects old LGIT path; three matching bank0 reads backed up privately; capacity/other banks, coefficient validity and physical controller/functionality unverified |
| Camera flash and torch | Verify supported hardware modes, control, exposure synchronization, limits and off state | Unverified |
| Video capture | Supported front/rear modes, sustained capture, frame integrity, audio synchronization and playback | Unverified |
| Video codec hardware | Identify exposed encode/decode blocks; supported formats, actual acceleration, load and stability | Unverified |
| SIM interface | Detection, insertion/removal behavior supported by the hardware, PIN handling and missing-SIM state | Blocked for SIM-based tests |
| Modem control | Firmware/remoteproc, control transport, ModemManager integration, radio power and no restart loops | Unverified |
| Cellular data | Supported network registration, APN, IP/DNS, transfer, reconnect, tethering as exposed and resume | Blocked without SIM/network |
| SMS | Send/receive, notifications, encoding and wake from suspend | Blocked without SIM/network |
| Voice calls | Incoming/outgoing, DTMF, earpiece/mic, speakerphone, headset, Bluetooth, proximity, suspend wake | Blocked without SIM/network |
| Network modes | Bands and modes supported by this device/network; airplane mode; VoLTE/IMS only if supported | Blocked for network qualification |
| UI integration | Keyboard, rotation, lock/unlock, notifications, camera/audio selection and console recovery | Native Wayland/Sxmo terminal and keyboard physically work using Pixman; installed r2 orientation passes. A physical-trace-driven gesture profile passes synthetic replay on installed r3; physical close/open retest passes; remaining integration tests pending |
| Updates | Current packages; kernel actually changes after update; DTB/initramfs deployment; recovery to known-good image | Partial: repository refresh/upgrade audited earlier; native r3 replacement and subsequent boot pass; saved native16 fallback fails startup acceptance. Frozen-r3 rescue/menu repair pass across the kernel r4 upgrade. UPower r4 installation, native CLI/services and regenerated artifacts pass; the later sensor diagnostic returns to a fresh r4/UPower r4 boot. No whole-system currency claim. Package/root rollback and final-layout update tests remain pending. See [UPower evidence](../evidence/2026-10-30-upower-telemetry-r4.json) and [return boot](../evidence/2026-10-30-sensor-ownership-and-id.json) |
| Final storage layout | Full restoration coverage/rehearsal before repartition; one maximum-capacity native root and minimum justified extra partitions; external SD removable | In progress: host-only 14.30 GiB ext4/GPT preview and offset-aware updater source checks pass; factory-stock rehearsal, minimum retained-partition audit and all physical migration/update/recovery tests remain open |

## Reliability qualification

Initial project targets are 20 cold boots, 20 warm reboots, 50 suspend/resume cycles (including at least 20 consecutive DMP interrupt wakes), a 24-hour mixed-use soak, and overnight unplugged standby with DMP wake armed. Record counts and failures, not just a final boolean. Re-run affected tests after changes to shared regulators, memory reservations, firmware, USB, audio, or power management.

Measure idle memory, available storage, suspend power, thermal behavior, and representative interactive latency. Establish numerical power and performance targets after stock and early Nura measurements; do not invent battery-life claims from the nominal capacity.

Include charging plus camera, Wi-Fi plus Bluetooth audio, cellular call plus proximity/blanking, GNSS plus suspend, and microSD I/O plus suspend. Fresh installation, userspace upgrades, and kernel updates require their own passing evidence.

## Final closure

Every physically present feature needs a passing result on the final current stable image, with the source manifest attached. Tests blocked by missing equipment, SIM, network access, or implementation remain open. Stock defects require repair or an explicit change to the agreed goal; they are not an automatic exception.

Maintain an issue for each failed or blocked row with the next diagnostic step, dependencies, upstream destination, and evidence. Add discovered components to the matrix rather than limiting scope to this initial list.
