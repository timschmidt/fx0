# First NFC kernel RAM startup

`check-startup.sh` checks the first moduleless boot of the independently built
`6.18.59-fx0-nfc-alpine` kernel. The prepared image contains no modules, firmware
or CPU registration scripts. Its kernel and DTB are exact bytes from the
verified r56 signed APK. The qualified BusyBox, init, USB/HTTP diagnostics and
180-second warm-return timer are retained unchanged. The command line retains
`module.sig_enforce=1` and selects the conservative family's `schedutil` default.
No CPUfreq driver module is included and no explicit performance request occurs.

The script reads proc/sysfs only. It requires the correct trial marker, release
and SHA256 of the linked kernel's 84-byte `.notes` section, signature-enforcement
parameter `Y`, zero taint and no loaded modules. It also requires four CPUs,
two temperatures from −40°C inclusive to 60°C exclusive, no CPUfreq policy/CPR provider or
unexpected filesystem mount, and one unbound I2C client at QUP3 address 0x28 with
the exact PN547/transport compatible list. It snapshots clocks, regulators,
GPIO ownership, deferred probes and interrupts without requesting GPIOs or
sending controller commands. The test-root override is for host fixtures;
the RAM observer uses the default real proc/sysfs paths.

The runtime checker is invoked once through the USB serial observer. Its exit
status is framed as `__NFC_STARTUP_EXIT__`; the observer then reads kernel notes,
the original boot partition hash and kmsg. The independent init timer continues
even if the checker fails or serial collection is unavailable. The image has
not been staged or booted, so real startup/return, exported note bytes, client
binding, signature enforcement and all other runtime expectations remain unproven.

Two host tests execute the actual shell script in 28 fixture modes, covering
success and 27 faults. Every fixture remains unchanged, and instrumented module,
GPIO and I2C commands are never called. The exact ARM BusyBox parses init, the
HTTP server and checker under emulation, and executes the NUL-separated
compatible-string conversion. A regression uses an actual zero-size, nonempty procfs file: the initial
unpublished checker incorrectly trusted file size, while the corrected checker
reads module-list contents and rejects it. The original image is retained and
was never staged. A second regression rejects a block filesystem whose source
uses a UUID alias by allowing only the expected RAM/pseudo-filesystem types.
These checks do not execute an ARM kernel.

The staging entry requires the passed display/touch result for the exact latest
native boot before any phone-client import, reboot or transfer. Both the real
pending-UI process and instrumented pending/wrong-boot paths reject without
phone commands or physical staging state. Host preparation does not satisfy the exact-boot UI gate. The normal
verified-transfer/readback and single-BOOT safeguards remain required, including
waiting for terminal USB I/O before any recovery or retry. The content-dependent
USB transport defect remains open.

See [the image manifest](../../manifests/nfc-startup-ram.json) and
[preparation evidence](../../evidence/2026-11-08-nfc-startup-preparation.json).
After startup and native recovery are qualified, separate bounded trials must
verify signed module registration, cold clock/GPIO ownership and cleanup,
NCI reset/init, tag/RF/userspace and suspend/wake. This image cannot qualify
those stages because it contains no NFC modules.
