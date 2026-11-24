# RMTFS storage candidate and ARM diagnostic builds

RMTFS remains uninstalled and unstarted on the phone. This checkpoint prepares
a storage-layer fix and local full-daemon binaries. It does not qualify QMI
dispatch, shared-memory transfers, remoteproc lifecycle or physical firmware.

The source bases are [RMTFS b30a3eb](https://github.com/linux-msm/rmtfs/tree/b30a3eb38f9af283f18dbd3c7755653efc52c094)
and [QRTR 29e36ae](https://github.com/linux-msm/qrtr/tree/29e36ae164389580a0f8ea7a7fdb728140ae978d).
Twenty-one used source/header/license/build files match their upstream Git blob
hashes. Two fetched files initially lost trailing bytes during text writing;
the integrity check rejected them and exact bytes were restored before building.
The rejected inputs and failed build attempts are retained privately.

## Reproduced storage defects

The exact upstream storage code fails 15 of 20 host sanitizer cases and 13 of
20 static ARM emulation cases. Three ARM cases terminate with a segmentation
fault, including a read beyond 2 GiB where a signed 64-bit subtraction narrows
to a positive 32-bit byte count. Other failures include closed/negative handles,
negative offsets, huge counts, truncated shadow snapshots, error suppression,
leaked failed-read buffers and negative `errno` values. A deliberately nonzero
allocator tail exposes uninitialized gaps after shadow growth.

The [storage-only patch](rmtfs-storage-bounds.patch) rejects invalid/closed handles
before access, checks ranges before narrowing/addition, preserves read errors,
zeroes grown shadow memory and reports positive error numbers. Initial snapshot
reads handle partial/EINTR results, reject premature EOF and free failed buffers.
The existing exclusive 16 MiB shadow-write boundary and valid read/write behavior
remain covered. No wire format, structure layout, service option or lifecycle
code changes. Upstream attribution/license is preserved in [rmtfs-LICENSE](rmtfs-LICENSE).

Both patched runs pass all 20 cases. The harness compiles the actual `storage.c`
and headers. Guarded open/read/pread/write/sync/realloc calls operate on synthetic
files; no real backup image or modem channel is used. Tests verify normal
shadow and partition-label modes, same-node reuse and foreign-node refusal,
four storage mappings and unchanged backing bytes. A separate read/write control
must modify the expected synthetic file, so zero writes in shadow mode is checked
against an observable control. Core dumps are disabled for failing baselines.

```sh
# Prepare private checkouts at the pinned commits, then apply only the patch:
patch --batch --fuzz=0 -p1 -d /private/rmtfs-candidate \
  -i "$PWD/diagnostics/modem-control/rmtfs-storage-bounds.patch"
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/modem-control/check-rmtfs-storage.py \
  --source /private/rmtfs-candidate --qrtr-includes /private/qrtr/include \
  --harness tests/rmtfs-storage-harness.c --compiler-json '["clang"]' \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]' \
  --output local/rmtfs-storage-replay
```

Use a fresh output path. For ARM, supply a JSON compiler argv prefix using the
cross compiler and target sysroot, static linking, and a runner prefix for an
isolated `qemu-arm-static`. The recorded builds mount only public compiler/library
directories read-only and the new workspace writable; key homes, real device
nodes and host networking are absent. This tests storage APIs, not packet dispatch.

## Full daemon build and dependency limits

Both complete daemons compile, including the generated QMI code, remoteproc and
shared-memory source, with only `storage.c` changed. The ARM output is a 6,303,972
byte ELF32 hard-float static PIE with no interpreter or shared-library dependency.
It is a local diagnostic output, not an installed package or RAM image payload.
An isolated ARM invalid-option invocation exits before memory-device/socket
access. No other full-daemon execution is claimed.

The cross compiler is Alpine GCC 15.2.0. Target development inputs include musl
1.2.6-r3, systemd/libudev 261-r0 and libucontext 1.5.1-r0. Static libudev needs
libucontext; its signed ARM development APK is verified against established
public keys and exact recipe `a141eb73d03406651da092ec035ebb2fe89abe9b`.
See the [official dependency package metadata](https://pkgs.alpinelinux.org/package/v3.24/main/armv7/libucontext).
Earlier incomplete-header, missing-sanitizer and static-link failures are retained;
final storage testing uses the installed Clang sanitizer runtime.

The retained target's systemd-dev/systemd-udevd metadata has commit `-dirty`.
The actual library archive is hashed, but its clean recipe/source identity is
not established by this checkpoint. Close that dependency provenance before
promoting the full daemon to a phone trial or redistribution. This limitation
does not replace the passing storage-only host/ARM tests, which do not link
libudev. The full server still needs packet/sector arithmetic, shared-memory
bounds, service/start-stop ownership and physical qualification.

For full builds, compile RMTFS `qmi_rmtfs.c`, `rmtfs.c`, `rproc.c`, `sharedmem.c`,
`storage.c` and `util.c`, plus QRTR `lib/qmi.c`, `lib/qrtr.c`, `lib/logging.c`.
Use QRTR's include directory, the target sysroot/CRT files and static
`-ludev -lucontext -lpthread` libraries. The legacy `qmi_tlv.c` is not part of
the upstream Makefile source list. Build commands, ELF metadata and hashed input
provenance are retained under `local/rmtfs-userspace-01`.

Fresh native checks preserve r50/r5, boot hash, services, taint, CPU/NFC/MSS and
APC/S5 state. All five provisioning sources and persistent phone snapshots still
match the private host manifest; host payload verification also passes. The
current native UI gate remains pending. No reboot, upload, installation, RMTFS
start, firmware/radio action or recovery-disk write occurs. See
[evidence](../../evidence/2026-11-09-rmtfs-storage-candidate.json) and
[submission draft](../../submissions/rmtfs/README.md).


## Later provider replacement checkpoint

A separate [clean provider/runtime candidate](rmtfs-libudev.md) now links signed
Alpine eudev and target GCC/musl inputs instead of the retained dirty-metadata
systemd library and cross-runtime files. It preserves this earlier candidate.
Five synthetic libudev API cases pass; full daemon startup remains unqualified.
Compiler-executable recipe identity and packaging are still open.


## Shared-memory follow-up

The [shared-memory candidate](rmtfs-shared-memory.md) adds common range validation for both backends and checks all IOVEC spans before transferring. Thirty-five memory cases and fifteen selected functional regressions pass on both host and ARM. Physical mapping, constructors, service lifecycle and modem operation remain unqualified. This preserves the earlier source/build evidence.


## Linux discovery follow-up

The [discovery candidate](rmtfs-discovery.md) fixes constructor ownership and validates Linux RFSA/UIO and DT metadata before mapping. Its 46 isolated discovery cases and 35 memory regressions pass on host and ARM. Actual driver mapping, service lifecycle and modem operation remain open.
