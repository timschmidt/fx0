# Rebuilding the modem userspace packages

This host-only workflow builds the normal qmic, QRTR and RMTFS distribution
packages. It uses rootless Podman to establish the subordinate UID/GID map,
Bubblewrap for isolation and normal `abuild` for compilation and signing.
It needs no pre-existing Alpine root or container image. It neither accesses
the phone nor qualifies modem/GNSS operation.

The locked recipe objects are qmic
`ddba0e12b7667a29df359e68d37ebdf222f501ef` and QRTR/RMTFS
`3b2f30decd987cbb6ad14259e64189ef2092dc1c` in the fx0-pmaports repository.
Their branch `development/fx0-rmtfs-userspace-01` is currently local and awaits
publication approval. Obtain those objects before running the commands below.
The launcher reads `git archive` at the locked commit and checks every recipe
file; it does not use the checkout's working files or index.

## Inputs and trust

Use an x86_64 Linux host with Python 3.11 or later, Git, OpenSSL, Bubblewrap and
rootless Podman configured with subordinate UID/GID ranges. Allow sufficient
space for three fresh native/ARM root pairs and separate build outputs.
Every output directory must be new. Preserve failed attempts and dispatched
source snapshots; do not modify a root after its bootstrap audit.

[The lock](../../manifests/modem-userspace-build.json) records the exact package
versions, full source commits, root database/configuration digests, release
archive SHA-512 digests and public verification keys. The bootstrap first
authenticates Alpine's `apk.static` with its detached RSA/SHA-256 signature.
Normal APK signature verification then authenticates the root packages and
optional extras. The resulting identities and package-owned payloads are
checked, including symlink targets. Native account setup is reconciled against
three exact configuration digests. Credential bodies are excluded from audits;
no credential-bearing root is copied.

The reference signatures use the original local APK signer. Set `APK_SIGNER`
to that key's existing path for the authorized local replay. The launcher's
only private-key operation is a file-presence check; normal abuild/OpenSSL
signing reads it through a read-only mount in place. The adjacent `.pub` file
must match the lock. Public key fixtures grant no phone trust and contain no
private keys. Another developer needs their own signer and a separately
qualified lock: signed APK bytes and the qmic/QRTR extra-package and resulting
root database hashes will then differ. Never distribute the reference private
key to reproduce its signatures.

Download the following public inputs with the exact basenames shown:

- `apk-tools-static-3.0.9-r0.apk` from
  `https://cdn.alpinelinux.org/alpine/v3.24/main/x86_64/`.
- `pigz-2.8-r1.apk` from that same directory.
- `qmic-1.0.tar.gz` from
  `https://github.com/andersson/qmic/archive/v1.0/qmic-1.0.tar.gz`.
- `qrtr-v1.2.tar.gz` from
  `https://github.com/linux-msm/qrtr/archive/v1.2/qrtr-v1.2.tar.gz`.
- `rmtfs-v1.3.tar.gz` from
  `https://github.com/linux-msm/rmtfs/archive/v1.3/rmtfs-v1.3.tar.gz`.

Use normal signed APK caches for both x86_64 and armv7, including their signed
`APKINDEX.*.tar.gz` files. The complete original archive identities are in the
[package evidence](../../evidence/2026-11-14-rmtfs-distribution-packages.json).
Caches contain public packages/indexes only. The qualified run used `--offline`;
all namespaces then have network disabled. For an online bootstrap, omit
`--offline` and cache arguments; the helper uses the lock's repository URLs and
the host CA bundle. Package/source identity drift causes failure. Repository
URLs are not immutable snapshots, so retain the signed caches for later replay.
Compilation always has networking disabled.

## Commands

Run from the fx0 checkout. Set the input paths to the prepared public files,
caches and recipe repository; do not use an installed phone root as an input.

```bash
APORTS=/path/to/fx0-pmaports
INPUTS=/path/to/public-release-archives
NATIVE_CACHE=/path/to/signed-apk-cache/x86_64
TARGET_CACHE=/path/to/signed-apk-cache/armv7
APK_SIGNER=/path/to/existing/pmos@local-6ae3f5f3.rsa
BUILD_ROOT="$PWD/local/modem-package-replay-01"
PODMAN_ROOT="$PWD/local/modem-package-storage"
PODMAN_RUNROOT="$PWD/local/modem-package-run"

bootstrap() {
    python3 -B diagnostics/modem-control/bootstrap-userspace-roots.py \
        --lock manifests/modem-userspace-build.json \
        --public-keys configs/modem-build-keys \
        --apk-static-package "$INPUTS/apk-tools-static-3.0.9-r0.apk" \
        --native-cache "$NATIVE_CACHE" --target-cache "$TARGET_CACHE" \
        --offline --podman-root "$PODMAN_ROOT" \
        --podman-runroot "$PODMAN_RUNROOT" "$@"
}

build_package() {
    python3 -B diagnostics/modem-control/build-userspace-package.py \
        --lock manifests/modem-userspace-build.json --aports "$APORTS" \
        --public-keys configs/modem-build-keys --signing-key "$APK_SIGNER" \
        --podman-root "$PODMAN_ROOT" --podman-runroot "$PODMAN_RUNROOT" "$@"
}

# The 75-package native base and 28-package ARM development sysroot.
bootstrap --output "$BUILD_ROOT/base"
build_package --package qrtr --native-root "$BUILD_ROOT/base/native" \
    --target-root "$BUILD_ROOT/base/target" \
    --archive "$INPUTS/qrtr-v1.2.tar.gz" --output "$BUILD_ROOT/qrtr"

# qmic's historical reference used pigz for APK compression. Without pigz,
# the uncompressed data tar is identical but its compressed hash differs.
bootstrap --native-pigz-apk "$INPUTS/pigz-2.8-r1.apk" \
    --output "$BUILD_ROOT/qmic-roots"
build_package --package qmic --native-root "$BUILD_ROOT/qmic-roots/native" \
    --archive "$INPUTS/qmic-1.0.tar.gz" --output "$BUILD_ROOT/qmic"

# New roots: install the rebuilt generator and ARM development libraries.
# Do not add packages to the preceding frozen roots.
bootstrap \
    --qmic-apk "$BUILD_ROOT/qmic/pmos-home/packages/pmos/x86_64/qmic-1.0-r2.apk" \
    --qrtr-dev-apk "$BUILD_ROOT/qrtr/pmos-home/packages/pmos/armv7/qrtr-dev-1.2-r2.apk" \
    --qrtr-libs-apk "$BUILD_ROOT/qrtr/pmos-home/packages/pmos/armv7/qrtr-libs-1.2-r2.apk" \
    --output "$BUILD_ROOT/rmtfs-roots"
build_package --package rmtfs --native-root "$BUILD_ROOT/rmtfs-roots/native" \
    --target-root "$BUILD_ROOT/rmtfs-roots/target" \
    --archive "$INPUTS/rmtfs-v1.3.tar.gz" --output "$BUILD_ROOT/rmtfs"
```

Each bootstrap/build writes its immutable source snapshot, exact inputs, logs
and actual child return code in its fresh output directory. A successful
bootstrap additionally writes `root-verification.json`. Retain those records
privately; build plans contain local paths. Signed package files and indexes
are under `pmos-home/packages/pmos/{x86_64,armv7}`. Compare their SHA-256 digests
with the [clean-bootstrap evidence](../../evidence/2026-11-14-modem-clean-bootstrap.json).

The ARM profile uses Clang/LLD 22.1.3 and clean signed target GCC runtime
objects. Clang ignores the inherited GCC options `-fstack-clash-protection` and
`-fno-plt`; this workflow does not claim those protections. Its standard RMTFS
service requests remoteproc management with `-s`. Building these packages does
not authorize starting that service or changing the phone.
