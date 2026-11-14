# Maintained r1 passive RMTFS RAM trial

This prepared trial uses the exact accepted installed kernel
`6.18.63-fx0-vibrator-alpine`, source
`c69b017cd9af9c589aeb921f901987fb26c55a4d`. It tests the Linux RFSA memory
device and local QRTR publication before modem firmware or remoteproc startup.
It does not qualify the reproducible r2/r4 kernels or complete modem/GNSS support.

The accepted kernel APK is pinned by SHA256
`73d28444c42edf3feba6fa0c91f45240ef0cd12a4ae401a18ae343508e4fabc4` and
control checksum `Q1zTO1mlgs1wilduzQdkNU/kbwGNI=`. Use its retained copy in
`local/edge-baseline-archives-01/custom-packages/`; the same-version archive in
the old build-output directory differs and was rejected before extraction.
The linked kernel notes, full public trust certificate and standalone QRTR
module are authenticated independently. All 119 QRTR imports match the exact
kernel, its CMS signature verifies against that kernel's complete trust list,
and it has no transport module dependencies.

The RFSA-only DT change reproduces the stock 1.5 MiB region at `0x0fd80000`,
client 1, while preserving the previous 4 MiB reserved union. Exactly five
properties change from the accepted DTB; MSS remains disabled. All 9,954
selected source paths match the accepted Git commit before and after the
unchanged description/schema verifier and its negative controls.

The minimal RAM filesystem contains the signed normal RMTFS 1.3-r1 and QRTR
1.2-r2 payloads and their complete musl/libudev closure. BusyBox 1.37.0-r31 is
verified from its signed stable ARM APK and source recipe. The unchanged local
observer and dedicated return helper are rebuilt twice with the verified
Clang ARM toolchain and clean target runtime objects. Both pairs match, and
their existing return/classifier controls pass under ARM/QEMU.

The [maintained worker](rmtfs-passive-r1.sh) requires its own trial token, linked
kernel notes, exact live DT/payload hashes, RAM-only mounts, disabled module
autoload, no remoteproc/rpmsg devices and a live independently armed return
helper. It permits one attempt before 120 seconds uptime. Only QRTR core is
loaded. The daemon uses `-r -o` with empty RAM storage; it never receives `-s`.
The observer sends local name-service lookups only. Acceptance requires absent,
present, the live RFSA descriptor, clean daemon exit, withdrawal and QRTR unload.

The [RAM init](rmtfs-passive-r1-init-v2.sh) arms an absolute 180-second BOOTTIME
return before USB setup. PID1 also watches helper failure. USB exposes one ACM
console, and the worker initially stays idle. The serial controller checks a
new boot ID, exact kernel notes and the dedicated token before its single
worker command. Short writes or missing acknowledgements do not cause retries.
After BOOT it observes the independent return and checks the installed boot,
packages, world, repositories, initramfs and complete module tree. Fresh owner
display/touch confirmation is required after return.

The prepared image is
`local/rmtfs-passive-r1-image-02/one/fx0-r1-rmtfs-passive.img`, 6,785,024 bytes,
SHA256 `428779913614a376bd40844bf80b10d004de0571d721b1bb29b85b68f31d4f53`.
Two independent assemblies match. Separate parsing and GNU cpio verify all 34
entries, initial script interpreters, links, ownership and contents. Android
header/digest/load bounds and the complete dynamic library closure pass; six
checks run from the actual extracted image under ARM/QEMU. The first assembly
omitted the initial shell link and remains retained, unstaged and rejected.

The image entry roster contains no credentials, firmware, calibration or native
initramfs data. Images remain ignored local files. Seven maintained-worker,
nine serial-protocol and seven one-BOOT-flow tests pass against synthetic
state. Physical RFSA, USB console, automatic return and modem/GNSS remain open.

The controller is prepared in `local/rmtfs-passive-r1-trial-01/`. It requires its
distinct current availability/UI receipt and repeats the exact read-only native
preflight before any reboot. An r2-repeat availability answer or publication
approval does not authorize this trial's operator window. Nothing has been
staged or booted. See [preparation evidence](../../evidence/2026-11-14-rmtfs-passive-r1-preparation.json).

The [public locked rebuild workflow](passive-r1-image-rebuild.md) now rebuilds
the return/observer helpers, the five-property RFSA DTB and the complete image
from exact APK materials. The [public adapter](passive-adapter.md) uses a
separately reviewed private plan. The original private controller and its
snapshots remain retained; the fresh public-plan attempt is undispatched and
still requires its own current operator availability/UI response.
