# Fx0 development log

## October 29 2026

### Device and host observations

The connected phone appears in host sysfs as LGE LGL25, USB `1004:6341`, at 480 Mbit/s. Initially its configuration exposed CDC ACM, a vendor interface, and mass storage. After the owner enabled debugging, interface class/subclass/protocol `ff/42/01` appeared, identifying an ADB interface.

The task's sandbox does not expose `/dev/bus/usb`; ADB, fastboot, and pmbootstrap are absent. Direct hostname resolution fails. The root `.git` directory is empty and read-only, so commits and repository setup remain pending. A request for host-level inspection was rejected by the session's approval policy. These are execution-environment constraints, not evidence that the phone is disconnected or defective. [Sanitized host probe](../evidence/2026-10-29-host-probe.json).

The owner was given the documented `/permissions` or desktop permission-control route to change host access. Debugging on the phone is enabled; host access still needs revalidation after that change.

### Implemented preparation

- Added `scripts/fx0_device.py` for sanitized host probing, private stock inventory, live partition discovery, binary partition reads, independent rereads, and offline SHA-256 verification. It requires explicit device selection and preserves failed/partial reads without a verified manifest. No flashing operation exists in this helper.
- Added 11 tests covering backup success and important failure modes, including all-byte binary data, disconnects, truncated reads, changed partitions, tampered images, existing backup protection, invalid partition paths, remote quoting, and old ADB exit-status behavior. [Test output](../evidence/2026-10-29-device-tool-tests.txt).
- Pinned upstream Linux MSM8226, lk2nd, and historical Fx0 source commits in [the source manifest](../manifests/sources.json). Retrieved 43 public source files/symlinks needed for DTB compilation and verified their Git blob hashes. The ignored cache is a source subset, not a complete Git checkout.
- Added reproducible source fetch/verification and DTB build scripts. Compiled DTC from the pinned kernel's own compiler sources.
- Restored the historical Fx0 UART/USB DTS and its DTB Makefile entry as a Linux development patch, preserving the original source attribution/license. Added the lk2nd filename-selection candidate using its documented prefix/suffix convention. [Patch scope](../patches/README.md).
- Checked both patches apply and compiled the resulting DTBs. The Linux candidate and unchanged SoC baseline each emit the same four DTC warnings; the lk2nd candidate emits none. [Build report and hashes](../evidence/2026-10-29-device-tree-build.json).

### Remaining validation for the candidates

No complete kernel or lk2nd image has been built. Schema checks, maintained-kernel integration, current submission-base validation, boot-image inspection, and all physical tests remain pending. The initial SoC reference is the pinned 6.16 development tree; it is not the required maintained-kernel endpoint. The Linux candidate enables only the inherited minimal UART/USB board configuration.

No phone partition has been read or modified by these tools. No backup or recovery capability is claimed. No commits, public repositories, pushes, or upstream submissions have been created.

### Next executable work

1. Revalidate host USB/network/Git access after the permission change. Install host tools and establish version control using the configured contributor identity.
2. Connect through ADB to the explicit Fx0 serial and collect the stock inventory privately. Determine root access and the actual partition/board/component details.
3. Back up the actual critical partitions, independently verify them, preserve a second off-device copy, and establish restoration before modifying LAF or boot.
4. Obtain repeatable fastboot access; build and inspect complete diagnostic images; qualify lk2nd and a headless Linux boot.
5. Continue all remaining phases of the bringup plan, including maintained-kernel rebasing, all peripherals, current Nura updates, SIM-based cellular qualification, and public submission-ready history.

The full goal remains active. Current evidence closes preparation tasks only; it does not close the recoverable-device, Linux-boot, current-Nura, full-hardware, or upstream-readiness milestones.

### Maintained kernel followup

Revalidated the execution environment: USB device nodes remain hidden, the host tools are still absent, and root Git metadata remains unavailable. The follow-up USB configuration no longer advertises the ADB interface previously observed; its cause is not established. [Follow-up probe](../evidence/2026-10-29-host-probe-followup.json).

Prepared a Linux 6.18.59 LTS source target at commit `1253a6aa5d104312bf0992afacc15220ae35bdf9`, with separate board-compatible and DTS patches. The default DTB build now selects this maintained target. All 62 cached source files/symlinks pass pinned Git blob verification. Both LTS baseline and Fx0 DTBs compile with the same four warnings; no additional Linux warnings appear, and lk2nd still compiles without warnings. The binding YAML parses and contains the expected three-element tuple. Full schema and image builds remain pending. [Maintained build evidence](../evidence/2026-10-29-maintained-device-tree-build.json).

The early source gap assessment identifies WCNSS definitions in the SoC development branch that are absent from the LTS tree, and a missing explicit MSM8226 CAMSS match. Those require further integration/investigation before full wireless and camera support can be claimed. [Kernel gaps](kernel-gaps.md).

### Host access blocker audit

At 07:00 UTC, the third consecutive goal turn confirmed the same execution restriction: the LGL25 is visible in host USB metadata, but USB device nodes are hidden, ADB/fastboot/pmbootstrap and the ARM GCC toolchain are unavailable, direct DNS fails, and the root folder is not a usable Git worktree. The latest USB configuration does not advertise ADB. The earlier host-inspection escalation was rejected by the configured approval policy.

There are no verified device backup manifests. Existing evidence covers source checks and DTB compilation only. Further board configuration requires stock inventory; destructive device changes require verified backups and recovery; complete image builds and public Git development require the missing host capabilities. The project remains incomplete and requires an execution-environment change to proceed meaningfully.

Resume by enabling host access through the task's permission control, then recheck USB and ADB. If ADB remains absent, re-enable debugging on the phone and inspect its actual USB configuration before connecting. Begin with inventory and backups; do not skip directly to flashing the unqualified candidates.

### Host access restored and physical inventory

After the permission update, USB nodes, network access and Git metadata became available. Installed host ADB/fastboot, pmbootstrap, ARM bare-metal GCC/binutils, dtc and build dependencies. Source checkouts are ignored independent repositories. The host contributor identity is configured; upstream certification/sign-offs have not been invented.

Stock ADB required a compatibility fix: `exec-out` is unsupported, the shell lacks `printf`, and the root interface accepts `su 0 sh -c`. Text commands now use explicit echo-based exit markers and legacy CRLF normalization. Partition bytes use the ADB sync service with root adbd. All 12 helper tests pass.

Physical inventory identifies MSM8926 revision 1.1, a 720×1280 framebuffer, Synaptics S3320 touch, WCD9302 Tapan audio, IMX179 rear and IMX132 front cameras. These are stock observations, not Nura functional passes. The actual layout has 39 named partitions; boot, recovery and LAF are each 32 MiB. Original Android v0 image headers use 2048-byte pages and a QCDT table.

Backed up 29 critical partitions (359,137,280 bytes) with independently matching rereads and verified manifests. Preserved primary/backup GPT metadata. Verified another recovery copy after a round trip through `/sdcard/fx0-recovery/stock-critical-01`. Disk B holds a separately verified host copy. Raw dumps, NV/calibration and serials stay ignored/private.

Built the Fx0-only lk2nd image with the DTB basename filter `LK2ND_DTBS=msm8926-lg-madai.dtb` and forced fastboot for initial testing. The QCDT table contains exactly one Fx0 entry. An earlier incorrectly filtered build must not be used. The correct image is 286,736 bytes, SHA-256 `a3d4ac8860051209796268504e4f266293ea864493ffda5b4c2fd81cd4d349c0`.

Linux 6.18.59 LTS has separate binding and initial UART/USB DTS commits. Its full LLVM ARM kernel/module build is running with a diagnostic USB gadget configuration. No physical Linux boot is established yet. Nura v26.06 rootfs preparation is underway. The stock `adb reboot bootloader` request returned to stock Firefox OS without a fastboot interface.

The owner selected `/run/media/tim/Disk B/fx0` for persistent large files. Its space-free bind mount `/tmp/fx0-storage` is active and required again after host reboot. Do not move an active kernel output directory during a build.

### LAF restore-path qualification

Confirmed the live LAF mapping and size against the backup manifest. Read back the phone's own original LAF copy and verified its SHA-256. Wrote that original image back to LAF, independently pulled the block device, and confirmed the original hash. Then cleared exactly the verified 32 MiB LAF partition, independently pulled it, and checked the hash of 32 MiB of zeros. The partition map is unchanged. Original boot/recovery and the primary boot chain remain intact. The owner has been asked to enter the documented Volume Up plus USB path. Fastboot entry and diagnostic image boot remain unverified.
