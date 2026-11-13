# Stable userspace controller on the current r1 boot

The current phone runs the accepted Linux 6.18.63-r1, treescan 0.1-r1,
Sxmo r7 and UPower r5 installation. The owner confirmed display and touch
for its November 13 UTC boot. Package database, world, repositories and
boot bytes match the preceding accepted installation. No stable package
upgrade has been performed at this checkpoint.

A new dual-lock capture reads all 7,002 paths and 701 complete directory
memberships again. It verifies archived payloads, live nanosecond metadata,
254 hardlink aliases and 1,480 SELinux labels. Both FLOCK and POSIX locks
remain held; the lock file is hashed through its held descriptor. All five
private recovery files have independently verified phone and host copies.
Runtime private keys remain excluded. The prior backup is retained.

The first exact-controller qualification, on the preceding boot, failed
because its verifier expected Alpine's `/etc/issue` payload. APK actually
keeps three files owned by the unselected `postmarketos-release` package:
`/etc/issue`, `/etc/os-release` and `/usr/lib/os-release`. Its `replaces`
declaration takes precedence over `alpine-release`. The unchanged
`apk_pkg_replaces_file` function in both APK 3.0.8 and 3.0.9 confirms that
this decision occurs before protected-configuration processing. The failed
unit and its original source and receipts are retained.

The corrected controller derives these collisions from the captured APK
database and authenticated incoming package controls. These three paths
and their configuration sidecars are excluded from recovery writes. Their
original bytes, metadata and installed owner remain required invariants;
their owner's package identity must also remain unchanged. Unexpected
collisions or unsupported replacement dependencies cause refusal.

The version 3 scope permits recovery of 2,708 files and metadata on 133
directories, with seven incoming configuration paths and fourteen sidecars.
The complete capture remains guarded, including boot, kernel modules,
public trust keys, normal commit hooks, treescan and unrelated package
files. Twenty-six focused host tests pass. They include recovery with retained
distro files, refusal before writes when those files change, and rejection
of changed file ownership despite unchanged file bytes.

Fresh supported-repository indexes authenticate against the phone's existing
public keys. Their actual host APK simulation still selects the same thirty
versions and signed package identities as the qualified software packet,
preserving all custom holds. The official
[installation page](https://nura.eco/install/) still identifies v26.06 as the
latest stable release. The host OpenSSL attempt rejects APK's signature
digest format before index acceptance; the existing isolated Alpine OpenSSL
environment verifies all four indexes and rejects an altered stream without
changing host crypto policy.

Native qualification uses a new private fixture restored from this boot's
capture, with the live OS read-only, private networking, hidden block
devices and bounded resources. The public worker
`diagnostics/stable-update/qualify_stable_transaction.py` exercises the same
controller source for success, scoped recovery, an OpenSSH hook execution
failure before its body, and a controlled failure after commit. A retained
signed executor inserted by the harness is explicitly synthetic. A live
update requires actual successful unit completion, an empty owned cgroup,
independent postflight and a separate check in its real service environment.
Qualification results must come from current unit state and PID1's
current-boot journal; stored intent or unloaded-unit default fields do not
establish success.

Native controller qualification and live activation remain pending until
their actual results are recorded. Abrupt power loss and the stop-signal
matrix remain unqualified. Audio testing stays excluded. Full hardware,
edge compatibility, reliability and upstream readiness remain open.

The [checkpoint evidence](../evidence/2026-11-13-stable-controller-recovery.json)
and [source manifest](../manifests/stable-userspace-controller-recovery.json)
identify the actual running unit, verified backup and tested sources. The
new native fixture has completed successfully; controller qualification is
running and must be observed to its actual terminal result.


## Symlink timestamp correction and the second private rollback

The second exact-controller cohort commits all thirty packages and completes
normal hooks, then rejects `/usr/bin/ex` because it compares the symlink's
creation timestamp with the tar header. The original unit fails after the
controller restores and verifies all 7,002 captured paths, 701 memberships,
775 identities, hardlinks, labels and unit timestamps. Harvest the terminal
unit, empty cgroup and original failed status before resetting only this
owned test unit's failed systemd state. The failure remains preserved.

The exact APK 3.0.8 and 3.0.9 filesystem extractors explicitly preserve
archive timestamps only for non-symlinks. Revision 3 keeps exact archive
mtime checks on regular files. For the nine incoming symlinks, it requires
an exact signed link target, mode, owner and policy attributes, with mtime
inside the actual owned upgrade command's recorded start/end interval.
The interval includes owned descendants and is recorded even if APK returns
an error. A backwards wall-clock jump refuses forward verification.
Preserved protected configurations and the three retained distro files
continue to require their captured metadata.

Five additional focused tests cover a freshly created symlink, an out-of-window
timestamp, missing/reversed windows, a wrong target and a regular-file mtime
change. All twenty-six host tests pass. The independent verifier's actual
ownership parser also accepts the thirty pinned archive controls and derives
all three retained distro paths independently of the controller helper.

Revision 3 reuses the prior fixture only after checking the terminal recovery
receipts, empty old cgroup, complete saved private namespace and all retained
signed cache/input files. Its ordinary preflight still verifies the entire
capture before package changes. The success and two failure cohorts are
running in `fx0-stable-userspace-qualification-03.service`. This is a private
qualification, with no live update or reboot. See the
[current evidence](../evidence/2026-11-13-stable-symlink-timestamps.json) and
[revision 3 manifest](../manifests/stable-userspace-symlink-timestamps.json).
