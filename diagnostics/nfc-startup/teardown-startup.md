# Corrected NFC family startup

One physical moduleless r58 startup and timed native return now pass. The owner
confirms working display and touch on return boot `98ab64c6-01c6-4c1e-91a2-433fc3afc4cf`.
See [physical evidence](../../evidence/2026-11-08-nfc-moduleless-startup.json) and
[the tested image](../../manifests/nfc-teardown-startup-xz3-ram.json).

`check-teardown-startup.sh` and [the r58 image manifest](../../manifests/nfc-teardown-startup-ram.json)
pin `6.18.59-fx0-nfc-teardown-alpine`, its linked kernel notes and the
`alpine-r58-moduleless-startup` marker. The separate r56 checker, tests and
prepared image retain their recorded bytes. The r58 checker rejects the older
release and marker; 30 fixture cases pass without fixture changes or module,
GPIO or I2C commands.

The image uses the exact kernel and DTB from the verified r58 APK, containing
neither modules nor firmware. Ten qualified init/BusyBox/USB/HTTP/timer entries
are unchanged. Its independent 180-second warm-return timer remains active
regardless of checker success. Header addresses, checksum, 14 CPIO entries and
kernel/BSS fit are independently checked; the exact ARM BusyBox parses its
scripts and executes compatible-string conversion under emulation.

The checker retains the r56 checks for signature-enforcement flag and command
line, zero taint, no loaded modules, four CPUs, two bounded temperatures,
absence of CPUfreq/CPR, RAM/pseudo-filesystems only, and one unbound QUP3 PN547
client. Candidate QUP3 is enabled: built-in controller probing can change
pinmux and clock state even without NFC modules. Clock/GPIO ownership and NCI,
RF, firmware and suspend/wake qualification remain separate work.

The owner confirms working native display and touch for boot
`28db1c68-3b08-4a53-8e5a-3397b8315813`. Read-only health checks confirm the
original r50 hash, zero taint, running systemd, Sway and sensor proxy. Instrumented
entry checks reject pending and mismatched-boot UI evidence before phone-client
imports; matching passed evidence reaches a controlled stop before import.
No real r58 stage or boot had occurred at that preparation checkpoint. A future entry still
requires immediate native/temperature/PMIC checks, a completed transfer and exact
readback, terminal transfer-controller success and no surviving transfer PID,
live observers and one BOOT. The USB staging defect remains unresolved.

The earlier source audits misreported an ELF string-table byte length as a
source-file count. Fresh comparisons verify all 21 changed files in each source
family and preserve both original reports and all linked artifact hashes.
See [the correction](../../evidence/2026-11-08-nfc-source-comparison-correction.json)
and [startup preparation evidence](../../evidence/2026-11-08-nfc-teardown-startup-preparation.json).

## Physical startup and native return

The original packed image times out before BOOT after 4,243,456 confirmed bytes.
Both transfer processes terminate before the identified USB transport is reset;
lk2nd identity is rechecked and one standard reboot restores native r50. The
owner confirms that intermediate native return. A 512 MiB retained eMMC pattern
also passes its changed-boot direct read before any r58 kernel runs.

An isolated encoding scratch tree reuses the original decompressor objects and
all EFI thin-archive members. Its original-payload link and assembler replay
each reproduce the original zImage exactly. Changing only XZ's LZMA2 preset to
3, retaining ARM BCJ, CRC32 and dictionary/alignment options, yields a different
packed image with the exact same decompressed runtime Image. Original source
build/ELF/APK/config/certificate/modules and prepared images remain unchanged.
The initial host control refused missing thin-archive members; its failure is
retained, and the complete-input controls pass.

The new 6,809,600-byte RAM image retains the exact ramdisk and command line.
It transfers and reads back exactly before one BOOT. The actual checker passes:
the 84-byte kernel notes match the published linked build, signatures are
enforced by flag/command line, four CPUs are online, modules remain absent,
and one unbound PN547 client appears as `1-0028`. There is no CPUfreq policy
or CPR provider. Its temperature and filesystem guards pass. Clocks/GPIOs are
snapshots, not ownership or electrical qualification. No module insertion or
controller/RF/firmware transaction occurs.

The timer message occurs at kernel time 181.610626 seconds. Serial collection
and 22 complete HTTP status/log pairs capture the run and detach. Native r50
retains its original boot hash, zero taint, four-rate schedutil policy, 1.15 V
programmed APC target, Sway and sensor proxy; temporary USB networking is removed
without host route/resolver changes. Display and touch pass. Native startup
still waits on time synchronization with no failed units; this reliability
issue and the USB transport defect remain open. Next qualify matching signed
modules, cold GPIO/clock ownership and cleanup, then NCI/controller, RF and PM.
