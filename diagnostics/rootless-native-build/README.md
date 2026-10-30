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
