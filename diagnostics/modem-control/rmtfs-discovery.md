# RMTFS Linux shared-memory discovery

This candidate fixes fd ownership and error handling during Linux shared-memory
initialization. Apply the [discovery patch](rmtfs-device-discovery.patch) after
the [shared-memory bounds patch](rmtfs-shared-memory-bounds.patch). Only
`sharedmem.c` changes; the source bases, generated QMI code and corrected QRTR
are unchanged.

RFSA and UIO share one discovery routine. Each acquired fd, libudev context and
libudev device has one owner. Discovery transfers the fd and mapping to the
memory object only after it succeeds. Failed stat, metadata or mapping cleanup
leaves no partial object. Opening a non-character path is rejected. Hexadecimal
sysfs values must contain a number with no sign, overflow or trailing text;
leading and trailing whitespace are accepted. Empty, wrapping or unrepresentable
regions are rejected before mapping or transfer.

The legacy Linux order remains RFSA, UIO, then `/dev/mem`. Only an `ENOENT` from
opening a device path permits fallback; a present device with failed stat,
metadata or mapping stops discovery. DT fallback reads the reserved-memory
parent's address and size cell counts, supports one or two cells for each, and
requires a single complete `reg` tuple in a unique matching node. It handles
short reads and `EINTR`, closes directory fds through their owning streams, and
validates the physical span before opening `/dev/mem`. Zero-address mappings
are released and rejected because a null pointer denotes fd-backed memory in
the existing object. Returned errors survive cleanup.

## Verification

The actual Linux constructors and teardown pass 46 cases under host Clang
ASan/UBSan and 46 under static ARM/QEMU. Test doubles bind to calls from
`sharedmem.c`; libudev, DT properties, fd handles and mapping results are
synthetic. The harness checks exact open order, errors, fd and reference
ownership, mapping size/offset, and release. It tests successful RFSA/UIO/DT
initialization, absent paths, failed metadata and directory operations, partial
property reads, duplicate nodes, 32-bit mapping width and 64-bit DT offsets.
The earlier link-time fixture missed musl's time64 `fstat` redirect and could
intercept libc's cleanup; its failed run is retained. The final fixture binds
only the source calls. No unpatched failure reproduction is run.

The prior 35 actual-helper/IOVEC memory cases still pass on both platforms. The
`dt-ok` and `rfsa-ok` fixtures use the offline fx0 DTB region `0xfd80000` plus
`0x180000`; independent `fdtget` checks verify one address cell, one size cell
and client ID 1. The DTB is unchanged and unbooted.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/modem-control/check-rmtfs-discovery.py \
  --source /private/rmtfs-candidate --qrtr /private/qrtr-candidate \
  --provider /private/verified-eudev-provider \
  --harness tests/rmtfs-discovery-harness.c --output local/rmtfs-discovery-replay \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]'
```

Use a fresh output directory. For ARM, the checker accepts JSON compiler and
runner argv prefixes, with static linking, the target musl sysroot and isolated
QEMU. Actual compiler and runtime mounts are read-only, and physical devices,
networking and signing homes are absent from the ARM sandbox.

The complete ARM hard-float static PIE is 790,340 bytes, SHA256
`9c9ab067d08246d06e51a2de6ae52459cd5ae9187078e5aa212f26ec3deea870`.
Its eleven persistent link inputs match the previously authenticated package
members. Only the early unsupported-option exit executes, with no device open
or socket syscalls. This test does not run the full daemon or link the constructor
fixture to real libudev; the [separate provider checks](rmtfs-libudev.md) cover the
five libudev APIs using synthetic sysfs.

Android-specific discovery, actual driver mapping, service and remoteproc
lifecycle, physical modem operation, compiler source identity and reproducible
packaging remain open. No phone operation, installation, RAM entry, reboot,
firmware or radio action, provisioning write or recovery-disk write occurred.
The latest native display/touch gate is still pending and full bringup remains
active. See [manifest](../../manifests/rmtfs-discovery-candidate.json) and
[evidence](../../evidence/2026-11-10-rmtfs-discovery-candidate.json).
