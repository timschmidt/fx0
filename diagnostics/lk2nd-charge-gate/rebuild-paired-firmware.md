# Rebuild the exact paired charging firmware

The managed charging source uses lk2nd commit
[`2ce757408f36`](https://github.com/timschmidt/fx0-lk2nd/commit/2ce757408f364ec6f1197b1d5d0be4128a309b1e).
Two independent empty builds and an additional run of the public helper produce
identical bytes for all 491 retained output files. The resulting 315,408-byte
`lk2nd.img` also matches the retained firmware from the earlier policy trial:

```text
20775e2f7ba7dee2b8cecf36e9c9aab22b38536fe3eb321f7cca7336759df482
```

This connects the fresh rebuild to the historical firmware artifact. The newer
Linux r6 package has no physical boot or combined charging qualification from
this result. The unchanged r2 repeat and its return gate remain separate.

## Reproduction

The helper was executed on Fedora with ARM GCC 15.2.0, ARM binutils 2.45,
host GCC 15.3.1, host binutils 2.45.1, Make 4.4.1, DTC 1.7.2, Python 3.14.8
and Bubblewrap 0.12.0. Exact executable hashes and versions are in
[the evidence](../../evidence/2026-11-14-paired-firmware-rebuild.json).
These are the tested tools, rather than a claim about current release versions.
The helper uses Fedora's `/usr` layout and the existing `ld.bfd` linker target.
User and network namespaces must be available.

Starting from this coordination checkout and a clean clone of the firmware:

```sh
git clone https://github.com/timschmidt/fx0-lk2nd firmware-source
git -C firmware-source checkout --detach 2ce757408f364ec6f1197b1d5d0be4128a309b1e
python3 diagnostics/lk2nd-charge-gate/build-paired-firmware.py firmware-source firmware-build-a
python3 diagnostics/lk2nd-charge-gate/build-paired-firmware.py firmware-source firmware-build-b
python3 diagnostics/lk2nd-charge-gate/check-linked-firmware.py firmware-build-a/build/build-lk2nd-msm8226
python3 diagnostics/lk2nd-charge-gate/check-linked-firmware.py firmware-build-b/build/build-lk2nd-msm8226
diff -qr firmware-build-a/build firmware-build-b/build
```

Each output path must be new and outside the source tree. The helper rejects
tracked changes, untracked files and ignored files in the source checkout. It
mounts source and host tools read-only, disables networking, creates fresh HOME
and temporary directories, hides the upstream test-signing directory and disables
image signing. No phone devices are exposed. It sets the original firmware
version, commit epoch and `LK2ND_FORCE_FASTBOOT=1` explicitly.

`APPSBOOTHEADER_DIR=/out` retains the auxiliary MBN outputs. Without that
override, this build system derives a path outside `BOOTLOADER_OUT`. The first
successful isolated pair preserved its main outputs but lost those auxiliary
files when the namespace ended. The qualified pair and public-helper run retain
them all. The earlier failure caused by a missing isolated host linker
alternative is preserved separately; it contributes no successful-build result.

## Verification and limits

The source audit matches 2,898 tracked bodies/link targets/executable modes to
Git. It excludes the body of the upstream `verity.pk8` test key. No production
credentials or signers are needed. Each build retains one existing RWX
LOAD-segment linker warning from the firmware's single-segment layout.

The independent checker walks the actual ELF hook table, validates both profile
and charge-gate function pointers and the battery-detection registration, checks
the version pointer, and reconstructs the raw binary from allocated ELF sections.
It then checks that the Android boot payload contains that binary and the built
Fx0 DTB, matches all packaged artifacts, and has the correct SHA-1 header digest.
Four controls reject a missing gate pointer, changed boot payload, raw-binary/ELF
divergence and a changed header digest. These controls run in memory only.

The firmware's earlier physical evidence remains tied to its original Linux
kernel. Current USB budget timing, PMIC bus timing, charging current, state of
charge, thermal boundaries, suspend and reliability remain open. This workflow
does not stage, boot or flash an image, and publishes no firmware binary.
