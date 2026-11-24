# Native treescan activation on the persistent r1 baseline

The treescan 0.1-r1 package fixes the incorrect ARM timestamps used by the
systemd APK inventory hook. Its candidate APK, signed one-package repository
and exact r0 rollback APK retain their earlier verified identities. The
controller uses the phone's existing public trust keys and native APK
3.0.8; it adds no trust keys and keeps normal package hooks enabled.

This controller is specific to the accepted Linux 6.18.63-r1 boot and the
fresh 7,002-path backup described in `post-r1-userspace.md`. Its source pins
the boot, backup manifest, backup archive and package identities. Completed
plans are single use. Another boot or package baseline requires fresh
qualification.

`diagnostics/stable-update/treescan_transaction.py` implements a separate
live transaction controller. The generic file rollback helper continues to
refuse the live root. File-backed recovery can replace only these six files:

- `/usr/bin/treescan`
- `/usr/lib/apk/db/installed`
- `/usr/lib/apk/db/scripts.tar.gz`
- `/usr/lib/apk/db/triggers`
- `/etc/apk/world`
- `/var/lib/systemd-apk/installed.units`

It can restore captured metadata on five related directories:
`/usr/bin`, `/usr/lib/apk/db`, `/etc/apk`, `/var/lib/systemd-apk` and
`/usr/lib/apk/exec`. It verifies all other captured rows, hardlinks, labels
and complete directory memberships before recovery writes. It also records
and checks the executable directory's complete child namespace.

Both FLOCK and POSIX locks must be present on the actual APK lock inode
during verification and file recovery. Lock contents are read through the
held descriptor. Recovery never replaces that inode. The controller
releases its APK locks while ordinary APK transactions run, and retains a
separate coordinator lock across the operation.

Every package process has a retained process handle and remains in the
owned service cgroup. A returned package parent does not establish that
hooks have finished: verification and recovery wait for the descendants.
Unknown executor files are preserved and cause refusal. A known retained
BusyBox trigger is accepted only after its type, ownership, link count,
size and exact captured script body match. All entries are checked before
deletion starts.

The live procedure first checks the exact qualified controller in its real
service environment with `--check`. That separate service performs native
signature verification, a one-package simulation and full baseline checks.
Its actual current-boot PID1 success journal and empty cgroup are verified
before the already approved `--install-live` operation starts.

The service makes the system read-only except for the normal APK and
BusyBox transaction paths and its private diagnostics directory. Public
trust keys, commit hooks, repositories, kernel modules and boot artifacts
remain read-only. The boot device is allowed for reading. There is no boot
write or automatic reboot operation. An installation stop request waits for
owned commands before recovery; the live service has no automatic runtime
kill deadline.

The first live check stopped because the service's module protection hid
the real module directory behind an inaccessible mount. No package was
installed and the live baseline hashes remained unchanged. That failed
result was harvested before its unit was reset. The revised service
exposes the real directory read-only and drops the module-loading
capability, allowing the exact metadata checks to run. The qualified
controller source is unchanged.

The forward operation is `apk upgrade treescan` through the signed local
repository. World remains byte-for-byte unchanged, including the r1 kernel
hold, and the other 774 package identities must match the post-kernel
baseline. The installed executable must match the signed ELF payload,
timestamp, ownership and captured policy label.

APK's pre-commit hook still runs r0 before replacement. The controller
therefore explicitly invokes the unchanged existing inventory hook after
the upgrade, while holding the APK locks. All 545 unit identities, types
and timestamps must match independently collected filesystem metadata.

Recovery first attempts the exact signed r0 APK with normal hooks. The
normal downgrade can add treescan to world and generates a different
inventory. After all hooks exit, the controller checks unrelated identities
and world entries, then restores the six captured files and five directory
metadata records. A failed normal rollback command does not authorize
unguarded writes: the same ownership and immutable-state checks must pass
before file-backed recovery. Final verification covers all 7,002 paths,
701 memberships, 254 hardlink aliases, 1,480 labelled paths and original
775 package identities.

Qualification uses the same controller source for native private success,
normal recovery with a deliberately retained signed executor, and failure
injected after an actual package commit and inventory refresh. The retained
executor is explicitly synthetic. The private fixture records its actual
initial namespace, including the APK log created during index loading;
generated cache files must match the signed package or index inputs.

The independent post-activation verifier checks the kernel payload,
modules, initramfs, bootloader prefix, raw boot, persistent signature
enforcement and core services. It allows only the kernel and treescan
identity changes relative to the older pre-kernel backup, and independently
checks the new treescan executable and all 545 unit timestamps. The
installed executable also runs the public negative/2038/2100 timestamp,
recursion, symlink and missing-directory checks.

The manifest and dated evidence report the actual completion state and
source hashes. Qualification of this controlled post-commit failure does
not establish recovery from abrupt power loss. Remaining stable userspace
updates, complete hardware acceptance and reliability work remain open.
Audio testing is excluded.
