# Supported stable userspace update preparation

The current r50/Sxmo r7 database has 775 installed packages. Four supported
v26.06/Alpine v3.24 indexes have independently verified RSA signatures against
the native public trust keys. An altered index stream is rejected. The
[plan](plan.json) selects 30 upgrades, preserving all ten exact signed-control
holds and all eight Sxmo r7 packages. The [host solver](solver-context.json) is
apk3.0.9; the phone runs apk3.0.8. Native solver and hook execution remain open.

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

## Native activation remains open

Only openssh-server and libheif supply candidate package control hooks.
Their historical version branches are false for the installed versions in
[host comparisons](hook-condition-review.json). A conservative review of all
15 installed trigger rows matches only BusyBox for this selected file set;
all 319 destinations from the two installed BusyBox binaries are covered.
Native trigger dispatch, hook execution, service continuity and recovery of an
actual live transaction remain unqualified. Isolated restoration success does
not qualify that controller or authorize skipping its ownership checks.

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
