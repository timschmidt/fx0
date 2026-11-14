# Checked recipe identity for rootless native builds

The tested host supports rootless Podman5.8.8 and user namespaces. A private
Alpine3.24 container builds the armv7 UPower package through pmbootstrap's
qemu-only backend, and the armv7 kernel through LLVM cross-native compilation.
The original root-owned pmbootstrap work and keys are untouched.

Use a separate work directory on Disk B and a disposable complete pmaports clone.
Mount the pinned pmbootstrap source read-only at `/pmbootstrap`, the recipe clone
at `/pmaports`, and only the new work/export directories needed for the build.
The container owns a private mount namespace. Rootless `mknod` is unavailable on
this host, so the tested setup bind-mounts the container's existing `/dev` into
the native and armv7 buildroot device directories. `--lax` skips strict zapping
of these device fixtures; start from an empty work directory and record reuse.
Use explicit `--arch armv7`: autodetection builds an `arch=all` package for the
host. pmbootstrap registers its emulation within this environment.

Some rootless container mounts retain locked sysfs submounts. In the r55
observation-package build, pmbootstrap's ordinary `mount --bind /sys` fails
before compilation (mount exit 32; a disposable BusyBox control reports
`Invalid argument`). `mount --rbind /sys` succeeds and retains those submounts.
Prebind `/sys` recursively into each private buildroot alongside `/dev` before
running pmbootstrap; its mount detector then leaves that existing mount alone.
The comparison uses only disposable container targets and changes no host
mount/network configuration. The failed build process must be terminal before
retry, and its logs must be retained. This fixture change does not alter kernel
source, configuration or hardware qualification.

For the reproducible Fx0 kernel recipe, the optional
`FX0_KERNEL_MODULE_SIGNING_KEY` environment variable names an absolute path
inside the build chroot. The provenance wrapper forwards that path to the
actual abuild environment. Mount the retained signing key and certificate
read-only at that path; the ordinary Kbuild signer consumes them. The wrapper
does not open key bodies. Leave the variable unset to use the recipe's normal
automatically generated development key. Repeated signed builds require the
same retained module signer, package signer, recipe commit/epoch, source archive,
configuration and toolchain.

Do not use a vanished temporary-directory alias as evidence that a signer has
been lost. Reconcile the original mounted build location using public key
fingerprints and private-file metadata. Use the existing trusted signer in
place through the normal signing tool. Export public keys and signed artifacts;
keep private keys on their retained storage. A change in compressed source
archive bytes requires checking the server archive against Git and pinning its
actual checksum in a new recipe revision.

The normal copied-APKBUILD layout produces `commit = -dirty`: abuild's path-based
Git lookup cannot identify the copied root-level APKBUILD at its original tracked
path. The wrapper here verifies the expected repository HEAD and a clean tree,
then supplies that snapshot and its timestamp to abuild before signing. It does
not rewrite signed artifacts or claim a last-change revision for another path.
The actual kernel r3 APK embeds0a7b0e9fa85fc1c4c32b112a5bcc562f516a23bb;
its DTB matches the physically tested candidate byte-for-byte. Earlier r1/r2 and
UPower APK metadata retains its recorded limitation.

Inside the prepared container, invoke the wrapper as:

```sh
python3 /pmb-repro EXPECTED_RECIPE_COMMIT --as-root \
  -c /pmb-config -w /pmb/work -p /pmaports \
  build --arch armv7 --lax --force linux-postmarketos-qcom-msm8226
```

Here `/pmb-repro` is a read-only mount of the Python wrapper. Match the disposable
clone's ownership to abuild's UID12345 during the build and restore ownership on
exit. Verify the source archive against the recipe checksum before use. Export
only the signed APKs, manifests and public signing keys; keep the package key private. Generated module keys stay in the private build
tree and may be cleaned with it; do not assume a later diagnostic module can be
signed with a retained matching key. Inspect package version/architecture,
recipe metadata, expected DTB, native kernel release and module contents after
export. Verify direct signatures and a normal package dry run before installation.

The kernel and UPower builds completed without another host sudo step. This
workflow is a tested development setup, not upstream pmbootstrap user-namespace
support or a guarantee of identical bytes with different signing inputs. Source,
recipe and artifact hashes plus actual device tests remain required.

A new clone also needs the official upstream remote URL and the pinned
`origin/main` reference used to read `channels.cfg` (plus the selected stable
channel reference). A local clone of a development clone does not automatically
preserve those remote-tracking refs. Copy verified refs/objects or fetch them
explicitly; do not substitute the development branch for upstream main.
Use a private network namespace as in the tested default Podman/pasta setup.
Host-network mode prevents the ordinary `/sys` bind in this user-namespace
configuration. The wrapper propagates pmbootstrap's return status, so setup
failures stop before export rather than falling through to package inspection.

The optional-path forwarding check in `check-provenance-wrapper.py` runs in a
networkless disposable container with the real pinned `/pmbootstrap` source and
clean `/pmaports` checkout. Mount the wrapper at `/test-inputs/wrapper.py` and an
empty writable result directory at `/results`, then set `EXPECTED_RECIPE` to the
checkout's exact HEAD and run the check with Python. It covers the absent
option, a quoted absolute path containing spaces, rejected relative/newline
paths, non-abuild call preservation and return-status propagation. Its final
pmbootstrap main/chroot calls are captured; it does not build or read keys.

`audit-native-toolchain.py --native-root /path/to/native --report /new/report.json`
checks package-owned file bodies and symlink targets against the retained APK
database. It resolves absolute links within the native root, excludes credential
and private-key paths, refuses an existing report, and returns nonzero for any
unreconciled difference. It reads no signer keys and does not modify the root.
Its database checksum is an input identity; it does not independently establish
package signatures or trust a new build signer.

For the pinned 103-package toolchain, 6,236 paths are checked. The 6,233 unchanged
bodies or links include the compiler, linker, signer and packaging tools. The
three differences are the exact build-account setup in passwd/group and the
standard abuild template plus the declared JOBS and cleanup assignments. Compare
those complete changes with their verified source APKs and setup sources;
blanket configuration exceptions are not accepted. The reusable auditor retains
these differences and returns nonzero so a caller cannot mistake setup changes
for an unqualified checksum pass.
