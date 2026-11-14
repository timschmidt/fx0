# Rebuilding the prepared passive-r1 image

This host-only workflow reproduces the prepared 6,785,024-byte diagnostic image,
SHA256 `428779913614a376bd40844bf80b10d004de0571d721b1bb29b85b68f31d4f53`.
It uses public source and explicit locked inputs; no ignored controller,
installed initramfs, stock DT dump, device record or credential client is needed.
The image leaves the modem disabled and initially leaves its worker idle.
Physical RFSA, USB serial and independent return remain unqualified.

The kernel input is the exact previously accepted r1 APK, SHA256
`73d28444c42edf3feba6fa0c91f45240ef0cd12a4ae401a18ae343508e4fabc4`.
This workflow does not rebuild that historical kernel APK, qualify r2/r4/r5,
or complete kernel installation/update/recovery. A same-version APK with
different bytes is rejected. Preserve the accepted archive separately from
old build directories.

## Inputs

Use Python 3.11 or later, Bubblewrap, Clang/LLD from the authenticated Alpine
roots, host CPP/DTC/patch, zstd and `qemu-arm-static`. Build the normal packages
and fresh `rmtfs-roots/{native,target}` using the
[public userspace bootstrap workflow](userspace-package-rebuild.md).
The helper launcher checks those roots' exact package databases and static
link inputs, then requires exact helper output hashes. This does not replace
the bootstrap's signed package/payload verification. It mounts the roots read
only, has no network namespace access and never mounts a signing key.

The [archive lock](../../manifests/passive-r1-materials.json) names eight APKs:

- `linux-postmarketos-qcom-msm8226-6.18.63-r1.apk`
- `busybox-static-1.37.0-r31.apk`
- `musl-1.2.6-r3.apk`
- `eudev-libs-3.2.14-r6.apk`
- `qrtr-libs-1.2-r2.apk` and `qrtr-doc-1.2-r2.apk`
- `rmtfs-1.3-r1.apk` and `rmtfs-doc-1.3-r1.apk`

Use the accepted local kernel archive, retained signed Alpine ARM packages and
the rebuilt distribution APKs. The lock binds the complete archive bytes whose
RSA signatures and data hashes were independently verified during qualification.
The material extractor repeats exact archive SHA256 and payload datahash checks;
it does not perform another RSA verification or grant new package trust.
It reads ten named regular members without extracting a package tree or running
install hooks. Zstd only decompresses the selected QRTR module.

Reference package bytes include the original local signature. Other developers
must use their own signing keys and separately qualify a new archive lock;
never distribute the reference private key. The selected image payload hashes
remain independently pinned by the [image lock](../../manifests/passive-r1-image.json).

The remaining three materials are the two public helper builds and the rebuilt
RFSA DTB. Obtain the public fx0-linux source at
`c69b017cd9af9c589aeb921f901987fb26c55a4d`. Its `include/` and
`arch/arm/boot/dts/` trees suffice for the DT step. The
[DT lock](../../manifests/passive-r1-dtb.json) checks the board source, patch and
both resulting DTBs; the checker confirms exactly the five reviewed RFSA
property differences and disabled MSS. It does not repeat the earlier stock
comparison, schema tests or full source inventory audit.

## Commands

Run from the fx0 checkout. All output directories must be new; preserve failed
attempts. Set these variables to explicit host paths containing only the
reviewed input cohorts:

```bash
BUILD_ROOT=/absolute/path/to/completed/userspace-build
KERNEL_SOURCE=/absolute/path/to/public/c69b017c/source
APK_INPUTS=/absolute/path/to/the/eight/locked/APKs
ATTEMPT="$PWD/local/passive-r1-rebuild-01"

mkdir -m 700 "$ATTEMPT"
python3 -B diagnostics/modem-control/build-passive-r1-helpers.py \
    --native-root "$BUILD_ROOT/rmtfs-roots/native" \
    --target-root "$BUILD_ROOT/rmtfs-roots/target" \
    --output-dir "$ATTEMPT/helpers"
python3 -B diagnostics/modem-control/build-passive-r1-dtb.py \
    --kernel-source "$KERNEL_SOURCE" --output-dir "$ATTEMPT/description"
python3 -B diagnostics/modem-control/prepare-passive-r1-materials.py \
    --apk-dir "$APK_INPUTS" --helpers "$ATTEMPT/helpers" \
    --passive-dtb "$ATTEMPT/description/candidate.dtb" \
    --output-dir "$ATTEMPT/materials"
python3 -B diagnostics/modem-control/build-passive-r1-image.py \
    --materials "$ATTEMPT/materials" --output-dir "$ATTEMPT/image-one"
python3 -B diagnostics/modem-control/build-passive-r1-image.py \
    --materials "$ATTEMPT/materials" --output-dir "$ATTEMPT/image-two"
cmp "$ATTEMPT/image-one/fx0-r1-rmtfs-passive.img" \
    "$ATTEMPT/image-two/fx0-r1-rmtfs-passive.img"
```

The helper launcher compiles both helpers twice and two fixture harnesses, checks
the complete seven-file static link cohort, and runs four ARM/QEMU controls.
Only the harness substitutes a return operation; the real helper is run with
invalid arguments so it cannot reboot. The observer's real CLI control likewise
exits before opening a QRTR socket. Every actual child has a bounded wait.
The [helper lock](../../manifests/passive-r1-helpers.json) pins source and output
identities. Compiler commands use canonical `/work/inputs` and `/target` paths.

The assembler accepts exactly 13 owned regular material files and five pinned
public sources. It constructs the same 34-entry canonical newc archive, including
the initial `/bin/sh` link, then requires the exact CPIO, compressed ramdisk and
final Android image hashes before creating output. It does not reuse a private
boot image as an assembly input. Compression/library changes that alter the
encoding cause failure. Image outputs use private directories and mode 0600.

All four launchers reject optimized Python. Input/source drift rejects; output
directories cannot be reused. These commands only prepare host artifacts.
Any physical run still follows the distinct
[private-plan/operator gates](passive-adapter.md) and
[passive trial procedure](rmtfs-passive-r1.md).
