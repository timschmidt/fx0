# Corrected NFC family startup

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
No real r58 stage or boot has occurred at this checkpoint. A future entry still
requires immediate native/temperature/PMIC checks, a completed transfer and exact
readback, terminal transfer-controller success and no surviving transfer PID,
live observers and one BOOT. The USB staging defect remains unresolved.

The earlier source audits misreported an ELF string-table byte length as a
source-file count. Fresh comparisons verify all 21 changed files in each source
family and preserve both original reports and all linked artifact hashes.
See [the correction](../../evidence/2026-11-08-nfc-source-comparison-correction.json)
and [startup preparation evidence](../../evidence/2026-11-08-nfc-teardown-startup-preparation.json).
