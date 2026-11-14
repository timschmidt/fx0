# Native software-clock transaction and recovery checkpoint

These are the exact controller bytes used by the expanded four-case native
qualification in [the evidence](../../evidence/2026-11-14-swclock-native-transaction-qualification.json).
The tested candidate is the signed main/systemd 0.3.0-r1 package pair. The phone
still has 0.3.0-r0. This is a device-bound reference implementation requiring
its matching private capture and plan; it is not a general installer.

The controller changes exactly eleven files and nine directory metadata rows,
protects 1,929 paths and 64 memberships, verifies all 775 original package
records, and preserves the existing APK lock inode and 22 trusted public keys.
It permits only the selected signed clock payloads, source-defined state files
and three exact authorized trigger executors. It never uses package removal
for recovery: the original main package removal hook deletes the saved offset.
The fixed initially absent inventory `.new` file has a bounded, owned recovery
rule. A separate killed synthetic writer exercised that rule; the test did
not kill an APK transaction. The expanded guard revision retains that exact
method and adds five immutable production service symlinks.

Native execution requires a fresh private PID1 namespace, isolated network,
IPC, devices and `/run`, read-only source/backup inputs, and the constrained
mount/capability policy. Package children permanently lose namespace setup,
capability-setting and label authority. The trusted parent retains only the
authority needed for captured metadata recovery. The live clock offset,
boot image, raw boot device, kernel/modules and trust keys are protected.
Private manifests, file archives, hook logs and complete launch adapters stay
outside this public reference. Their matching hashes are required by the plan;
changing dispatched inputs requires a new revision and native qualification.

A successful unit requires actual current-boot PID1 completion records,
MainPID zero and an empty cgroup. Default properties of an unloaded unit do
not prove execution. The external driver verifies disk state independently
after the package worker and before changing the host manager. Hiding `/run`
means the normal package trigger cannot reach the host PID1.

The manager reconciliation policy requires unchanged boot, exact package
cohort and guards, original world/keys/boot/offset, stable display/sensor/UI
process IDs and the original clock invocation. No loaded unit may have a
pending marker. It then issues one `daemon-reload`, verifies the graph and
absence of markers, issues one `enqueue-marked`, and repeats all checks.
The candidate clock unit must want `local-fs-pre.target` and order before it
and `systemd-fsck-root.service`. An uncertain acknowledgement is inspected
through the same operation's evidence; it is not automatically retried.

A manager failure after a terminal installer has a prepared file-backed
recovery entry. That wrapper calls the unchanged qualified `rollback()` and
`verify_rollback()` methods under the transaction lock. Its launcher must first
prove the installer and all hooks are terminal. After verified file recovery,
PID1 must be reconciled against the original dependency graph with the same
checks. The new entry wrapper is staged but has not been executed; native
proof covers the exact restoration methods, not this new orchestration entry.

Portable component checks need no private backup or device:

```sh
python3 -B -m unittest discover -s diagnostics/native-swclock-update -p 'test_*.py' -v
```

The original native qualification additionally used the complete captured
package database and private snapshot fixture. The portable tests exercise
record and policy rejection behavior without claiming full-device coverage.
Fixed-unit boot, wall restoration before NTP, cold/long-term RTC retention,
remaining hardware and complete bringup acceptance remain open.
