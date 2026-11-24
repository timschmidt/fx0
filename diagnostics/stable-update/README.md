# Supported stable userspace update preparation

The current r50/Sxmo r7 database has 775 installed packages. Four supported
v26.06/Alpine v3.24 indexes have independently verified RSA signatures against
the native public trust keys. An altered index stream is rejected. The
[plan](plan.json) selects 30 upgrades, preserving all ten exact signed-control
holds and all eight Sxmo r7 packages. The [host solver](solver-context.json) is
apk3.0.9; the phone runs apk3.0.8. Its exact ARM solver now passes under QEMU
and on the phone kernel in a private chroot. Live-OS transaction, service
continuity and rollback acceptance remain open.

All [30 candidate APKs](verified-packages.json), totaling 15,903,143 bytes,
match authenticated index control checksums. Independent RSA, signed payload
SHA256 and ordinary APK verification pass; altered control and payload cases
reject. [Twenty-one exact original APKs](verified-rollback-packages.json) are
also verified. Nine originals remain unavailable: alpine-release and eight
OpenSSH packages. File-backed recovery below uses captured original bytes;
it does not substitute or fabricate those nine package archives.

## Complete file backup and isolated recovery

The [coherent capture](backup-capture.json) covers 5,784 paths: the complete
existing 2,595-path boot/module/kernel/APK/world backup plus selected old/new
package files, configuration sidecars, public trust keys, BusyBox destinations
and parent metadata. Full original-tree membership is checked before and
after capture. Types, file bytes, ownership, modes, nanosecond mtimes, symlink
targets, 254 hard-link aliases, all 939 SELinux labels and 39 absent paths are
captured privately. Runtime private keys are not read, hashed or exported.

The 19,228,951-byte delta supplements the verified complete 147,347,436-byte
original archive and 32 MiB raw boot backup; none of their scope is dropped.
[Persistent host and phone copies](backup-copies.json) are verified after
rechecking every captured live path, its metadata and all attributes. Private
archives, full manifests, configuration data and individual configuration hashes
are excluded from publication; aggregate backup identities are public.

The [actual offline host rehearsal](rollback-rehearsal.json) upgrades five
packages, restores the original state, then upgrades all 30 selected packages.
Both recover the exact original 775 package versions and signed control
identities. The complete update retains the world, ten holds and eight Sxmo
packages. Native hooks are disabled. Corrupted files, detached hard links,
incorrect modes, symlink targets and unexpected user attributes recover.
An injected interruption after 930 completed path operations resumes cleanly.
Parent symlink escapes are rejected; unknown descendants are preserved and
restoration refuses to erase them. Boot-tail recovery is tested on an ordinary
RAM file, preserving the first 512 KiB. No block device is written.

The [private native-directory rehearsal](native-file-rehearsal.json) runs the
same [restore helper](file_rollback.py) on the phone filesystem under a systemd
unit limited to 400 MiB, no swap, 50% of one CPU and 900 seconds. It restores and
verifies all 5,784 paths, including all 939 SELinux labels and 254 hard-link
aliases, then verifies recovery after the same injected interruption. The
private fixture is removed and the actual systemd unit exits successfully.
The live database, world and raw boot remain unchanged. Host and native tests
use isolated directories; the helper explicitly refuses `/` as a restore root.
Power loss and a crash during an individual write are not qualified.

## Exact phone APK solver under ARM emulation

The [runtime closure](native-apk-runtime.json) contains the exact phone APK
3.0.8, libapk, musl loader, OpenSSL and zlib: six ARM32 hard-float ELF files and
two symlinks. Every file matches the payload of its exact, signature-verified
installed package. All interpreter and NEEDED entries resolve inside the
fixture. Package archive names are normalized through the captured usrmerge
aliases before byte comparison. Only whitelisted software is read from the
phone; private runtime keys are excluded.

The [ARM rehearsal](native-apk-rehearsal.json) explicitly invokes QEMU10.1.5
inside an offline, read-only container with a 1 GiB RAM work filesystem. The
phone's ARM APK3.0.8 performs actual five-package and full 30-package updates.
Each updates APK itself to ARM3.0.9; file-backed recovery returns it to ARM3.0.8
and restores all original 775 package versions and signed control identities.
The world, ten holds and eight Sxmo packages are preserved by the complete
update. The same 5,784-path, hard-link, metadata, interruption and path-safety
checks pass. A missing libapk loader control fails as expected. No host binfmt
registration is changed.

The [ARM verify controls](native-apk-controls.json), run in a separate 128 MiB
RAM fixture, accept the signed musl archive and reject both a valid-gzip altered
control with BAD signature and a valid-tar altered payload with an integrity
error. This pairs the rejections with an accepted archive using the same
ARM3.0.8 command and runtime. The [fresh phone postflight](native-apk-postflight.json)
retains r50 boot747e87fe, original boot/database/world/repositories, healthy
Sway and gestures, systemd running and taint0. This phase writes no phone files.

This emulation cohort executes exact ARM userspace binaries on the host
kernel. It does not execute the phone kernel or native hooks. The following
cohort supplies private phone-kernel hook evidence; live-OS service and
transaction acceptance still require separate qualification.

## Normal hooks on the phone kernel in a private chroot

The [native boundary probes](native-hook-isolation.json) verify read-only OS,
kernel-tunable and cgroup mounts, an owned writable backup subtree, no visible
boot block device, loopback-only networking and NoNewPrivileges. A second
probe exercises ownership, setuid mode and SELinux/user attributes, then actual
native chroot, shell, APK3.0.8 and strace execution. The
[BusyBox interpreter proof](native-hook-runtime.json) matches both binaries and
the installed trigger body to exact signed packages; their dependencies are
covered by the verified musl runtime.

The [native transaction](native-hook-rehearsal.json) runs all 30 upgrades on
Linux6.18.59-fx0-dmp without QEMU or --no-scripts, inside the private chroot.
The [execve proof](native-hook-execution.json) verifies the OpenSSH and libheif
post-upgrade arguments, the BusyBox trigger directories and both BusyBox
installers. All eight observed processes exit0. The actual version comparisons
are greater-than, and no service-restart command executes. All children have been
reaped and the actual unit cgroup contains only the controller before recovery.

The update preserves the world, ten holds and eight Sxmo packages, and reaches
ARM APK3.0.9. Recovery restores the original 775 package identities, ARM
APK3.0.8 and all 5,784 captured paths, including 939 SELinux labels and 254
hard-link aliases. The private root is removed. The unit uses 400 MiB maximum
memory, no swap, 50% of one CPU and a 25-minute deadline; its successful
termination is verified in the current-boot systemd journal, independently of
unloaded-unit default exit fields. The [outside-unit postflight](native-hook-postflight.json)
retains the original live boot/database/world/repositories, healthy Sway and
gestures, systemd running and taint0. Only private test inputs and logs remain.

The trace identifies the APK executor directory at /usr/lib/apk/exec. Its live
state is an empty root-owned 0755 directory. The [next backup requirements](native-hook-next-backup.json)
add its metadata and complete membership to the fresh post-r1 snapshot. An
optional whole-private-tree membership sample was correctly refused after
cleanup; no full generated-state inventory is claimed. Normal-hook failure
recovery, power loss, mid-write crashes, live service continuity and live-OS
transaction rollback remain unqualified. This successful isolated transaction
does not replace those acceptance steps.

## Native activation remains open

Only openssh-server and libheif supply candidate package control hooks.
Their historical version branches are false for the installed versions in
[host comparisons](hook-condition-review.json). A conservative review of all
15 installed trigger rows matches only BusyBox for this selected file set;
all 319 destinations from the two installed BusyBox binaries are covered.
Private native hook and trigger execution now pass for this exact version
set. Live service continuity, failure recovery and the live transaction
controller remain unqualified; its ownership checks remain required.

The [postflight](backup-postflight.json) confirms the same r50 boot747e87fe,
original boot/database/world/repositories, systemd running, taint0, Sway and
gestures. Only private recovery files were added to the phone. The earlier
owner reply confirms the Linux6.18.63 RAM candidate, not this native return;
the current-return physical display/touch check is still pending. The approved
persistent kernel r1 update and a refreshed boot-specific backup baseline must
precede userspace activation. This r50 snapshot must not be reused as an r1
transaction baseline without fresh qualification. Phone updates and GitHub
publication already have standing approval. Audio testing stays excluded and
full Fx0 bringup remains active.
