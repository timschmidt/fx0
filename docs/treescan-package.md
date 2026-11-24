# Treescan time64 package candidate

The normal signed ARM package `treescan-0.1-r1.apk` corrects the unstable
modification timestamps found during APK recovery qualification. It is built
from Alpine's checksum-pinned 0.1 source with the single `PRIdMAX`/`intmax_t`
format correction. The original build and installation functions are retained;
strict format checking and focused Python regression checks are added.

The recipe and tests are published in the owner's
[fx0-pmaports development repository](https://github.com/timschmidt/fx0-pmaports/commit/e58c455e3c0d88f443f449fabcea3eed57b75a93).
No upstream message or merge request was sent.

Pmbootstrap/abuild built and tested the package in the ordinary ARM QEMU-only
environment. The stored Alpine roots were reused read-only, with fresh build
homes and writable overlays in container RAM. Their original channel/init
metadata was retained. The outdated-chroot warning remains in the build log;
this is not a claim of a freshly bootstrapped toolchain. The signing key was
mounted read-only and used through normal signing tools; only public keys,
signed artifacts and explicitly selected software sources were exported.

Independent RSA verification, the signed control/payload hash chain, ordinary
APK verification and two valid-tar corruption controls passed. The signer was
already in the phone's trust store. The package has one executable, no embedded
package scripts, and only the verified native musl runtime dependency. Its
source identity is embedded before signing. The candidate archive SHA-256 is
`24f63c20f7197468a005b08c023242e70c491edb40c965372c540d70736ddf11`.

The exact packaged executable then passed actual phone execution against
Python metadata for 545 systemd entries and nine synthetic entries. Tests
cover negative timestamps, the 2038 boundary, 2100, recursion, symlinks and
missing-directory failure, with three repeated scans. The original installed
executable still reports incorrect timestamps; the candidate remains uninstalled.

A signed one-package local repository preserves the candidate APK bytes.
Its RSA signature, control checksum and a corrupted-index negative control were
verified independently. Native APK 3.0.8 accepted it in a normal simulated
`upgrade treescan`, selecting only 0.1-r0 → 0.1-r1. Using `upgrade` preserves
the existing world selection. Database, world and raw boot hashes remained
unchanged. Earlier orchestration/observer failures are retained separately
and are not presented as successful qualification.

The host candidate and repository are under `local/treescan-package-01/`;
the private phone copy is under `/var/lib/fx0-rollback/treescan-package-01/`.
The authenticated exact 0.1-r0 rollback archive remains available. Actual
installation, normal live hooks, downgrade recovery, all-architecture testing
and a clean-toolchain rebuild remain open. Install after the prepared kernel
transition, using a fresh backup and a fresh simulation for that state.
Replacing the installed helper now would invalidate the prepared kernel
controller's captured inputs.

The phone remains on r50 with Sxmo r7 and UPower r5. Its returned-boot physical
display/touch confirmation is pending. The revision-02 kernel installer is
prepared and already approved; the old revision-01 launcher stays superseded.
The complete bringup goal remains active, with audio testing excluded.
