# Installed Linux 6.18.63-r1

The Fx0 now runs the persistent `6.18.63-fx0-vibrator-alpine` kernel from
`linux-postmarketos-qcom-msm8226-6.18.63-r1`. The owner confirms display and
touch on the new installed boot. Sxmo r7 and UPower r5 are retained.
The [installation manifest](../../manifests/kernel-native-6.18.63-installed.json)
and [evidence](../../evidence/2026-11-12-kernel-native-6.18.63-installed.json)
pin the package, boot image, controller and verification scope.

## Qualified transition

This is the guarded update from the captured r50 installation. Its native
controller verifies the original package/boot snapshot and supplemental
commit-hook state, installs the signed candidate with `--no-interactive`,
waits for owned package hooks, and verifies the resulting files and persistent
boot image. The lk2nd prefix remains unchanged; the OS image starts at offset
524288. The kernel's world checksum hold moves to the candidate identity.

Installation and postboot checks verify 545 candidate payload files, including
464 modules, and 243 initramfs entries. The other 774 package identities match
the original baseline. Modules come from persistent storage. Kernel notes match
the previously tested candidate, the RAM-trial marker and return timer are
absent, and the owner-confirmed boot has zero taint.

The original r50 file archive and raw boot backup remain verified on the phone.
The existing off-device recovery material remains preserved. Use fresh
snapshots and plans for subsequent updates on r1; this r50 transition plan is
bound to its original boot and package state.

## Large confirmed-plan transport

The first host launcher embedded the 178,175-byte confirmed JSON plan in an
SSH argument and failed with `E2BIG` before creating an SSH process. Native
inspection confirmed that no plan, installation status or service had been
created and all original hashes still matched.

[stage_confirmed_plan.py](stage_confirmed_plan.py) implements the corrected
transport. It sends the payload over an ordinary pinned SSH connection into
a private user file. A separate call through the existing root client checks
the exact current boot, unused installation unit, expected controller,
file ownership/mode, byte count and SHA-256 before creating the root-owned
plan with mode 0600. It removes the user staging file after verification.
The root client's authentication input and the JSON payload use separate
calls.

The helper accepts:

- A client exposing `OPTS` for the normal pinned SSH invocation and
  `run(command, root=True, timeout=...)` for normal root authentication.
- The local confirmed-plan path and a new private host state directory.
- The prepared root-owned native backup directory, target JSON basename and
  dedicated installation unit.

The native directory must be under `/var/lib/fx0-rollback`, owned by root
and mode 0700. The helper stages the plan; the qualified native controller
performs the full preflight and installation.

A separate native transport test copied and verified a 178,007-byte plan in
a disposable namespace. It checked root ownership, mode 0600 and exact bytes,
then removed both the user staging file and native fixture directory. It
did not invoke the installer.

The host records the transfer request before dispatch. After uncertain
acknowledgement, inspect that exact user path, native target and installation
unit before continuing. Existing host state and exclusive file creation
prevent blind replay.

## Reboot and verification

Observe the installer's `updated-and-verified` status, completed owned hooks
and the actual current-boot PID 1 success journal before requesting one normal
reboot. A collected unit's default status fields alone do not prove success.

Run the [read-only persistent verifier](verify_persistent_6_18_63.py) with
the expected new boot ID recorded by the host's reboot observer:

```sh
python3 -B verify_persistent_6_18_63.py --boot-id "$FX0_EXPECTED_BOOT_ID"
```

It checks the running release and kernel notes, package identities and world,
all candidate payloads, initramfs, raw boot contents and preserved prefix,
retained backups, signature configuration and services. It also checks four
online CPUs, display power controls, the gesture daemon's open touchscreen,
thermal bounds, the restored PMIC target and serious kernel warnings.

Module enforcement is active through `module.sig_enforce=1` and the runtime
`sig_enforce=Y` parameter. An actual ARM `finit_module` check rejected an
unsigned copy of the unused `camellia_generic` software module with
`EKEYREJECTED` (129), then admitted its exact signed copy. The module was
unloaded, RAM files removed and the loaded-module list restored. Taint stayed
zero. Decompression used the existing libzstd API; no package was added.

## Remaining qualification

This verifies the installation and its first persistent boot. Full hardware
acceptance, extended reboot/suspend reliability, CPR operating points,
NFC RF/concurrency, camera and charging qualification, current stable userspace
updates and clean reinstall coverage remain open. No audio testing was
performed.
