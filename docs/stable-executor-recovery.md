# Native APK executor and commit-state recovery

The phone remains on installed r50 (`6.18.59-fx0-dmp`), Sxmo r7 and UPower r5.
No live package transaction or boot-partition write occurred in this phase.
The Linux 6.18.63 RAM display/touch answer applies to that earlier RAM boot;
the returned r50 boot still needs its own physical display/touch confirmation.
Full bringup remains active and audio testing remains excluded.

The expanded, coherent backup preserves all earlier file rows and covers 6,351
paths, 1,479 SELinux label attributes and 40 complete directory memberships.
It includes APK configuration, executor metadata, systemd unit inputs and the
generated systemd inventory. An initial capture that inadvertently released a
POSIX lock was rejected and retained. The accepted capture verifies both real
FLOCK and POSIX locks before and after reading, hashing the lock through its
held descriptor. The original large archives and raw boot backup are reused.

A bounded private chroot ran the actual ARM APK 3.0.8 with ordinary package
hooks, the actual systemd commit hook, the native interactive marker and an
explicit noninteractive option. One `execve` EIO was injected before the
OpenSSH post-upgrade body. APK returned 1 but completed all 30 package changes,
including its own executable. After every owned descendant exited, recovery
restored all 775 package identities, APK 3.0.8, the captured files, metadata,
hardlinks, labels, directory contents and the original inventory. The private
namespace returned from 6,379 entries after failure to its original 6,372 entries,
with no unexplained missing or generated entries. Fixture repository/cache
paths are explicit harness state. A retained executor artifact was deliberately
injected to exercise cleanup; it was not falsely attributed to APK. The private
root was removed and current-boot PID 1 journal success was verified.

Two failed native attempts remain recorded: an incomplete fixture runtime and
an overly strict generated-inventory comparison. Coreutils and its full ELF
dependency closure now match signed original package payloads. The existing
postmarketos systemd commit-hook payload is authenticated through the trusted
repository index, exact installed control checksum and control/payload hash
chain. Its historical archive signer is absent from the native trust store;
individual archive RSA verification was not claimed and no trust key was added.
That archive is not proposed for installation.

The inventory comparison revealed a real `treescan` 0.1 bug: `%zd` is used for
64-bit `time_t` on 32-bit ARM. Three scans produced different incorrect values
without file changes. Strict ARM compilation rejects the original format and
accepts the attached `PRIdMAX`/`intmax_t` correction. The corrected ELF passed
actual phone execution against Python metadata for all 545 systemd entries and
nine synthetic entries, including negative and post-2038 timestamps, across
three repeats. Missing-directory failure also passed. The corrected executable
was tested privately and remains uninstalled. The correction is based on
[the upstream v0.1 source](https://github.com/kaniini/treescan/blob/v0.1/treescan.c).
Until it is packaged, the kernel guard validates inventory paths/types and
checks captured unit timestamps independently through Python; it does not
treat the original helper's timestamp output as reliable.

`install_native_v2.py` explicitly disables APK interaction and extends the
kernel rollback guard to the commit inventory and executor directory. It
recognizes exact captured original script bodies, preserves unknown artifacts,
and refuses cleanup while hooks remain active. Four host cases passed with
three actual APK transactions: candidate verification, forced full rollback,
pending physical confirmation and changed bootloader-prefix refusal. Hardware,
boot generation and hooks are explicitly modeled in those host cases. The
unmodified revised controller passed read-only preflight on the phone. A
separate bounded native probe verified all 582 supplemental paths and 38
memberships, actual label restoration, inventory/executor recovery, and refusal
with active hooks or unknown artifacts. The unchanged cgroup and hook-waiting
methods retain the earlier actual native scope qualification.

Use the prepared controller in `local/kernel-native-6.18.63-controller-02`,
after recording the exact returned r50 boot's physical confirmation. The old
controller 01 launch instruction is superseded. No further update approval is
needed: phone updates and fx0 GitHub pushes already have standing approval.
The new launcher refuses before phone commands if that physical check is
missing, and requires actual current-boot journal success for completion.

These results cover an execution failure before one hook body, not an arbitrary
hook-body failure, power loss, a mid-write crash, a complete live-OS namespace,
service continuity during a live update, or a successful installed r1 boot.
Kernel installation, normal live boot hooks, reboot, module-signature
enforcement and fresh UI acceptance remain outstanding. Stable userspace
acceptance needs a fresh baseline after that kernel transition. Raw backup
payloads, configuration, namespace inventories and traces remain private.
