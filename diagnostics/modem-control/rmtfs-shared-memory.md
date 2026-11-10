# RMTFS shared-memory candidate

The candidate checks every shared-memory span before copying or issuing fd I/O.
The IOVEC handler checks all entries before its first storage or memory transfer.
This is a host-tested source candidate; RMTFS remains uninstalled and unstarted
on the phone.

Apply [the patch](rmtfs-shared-memory-bounds.patch) after the existing storage,
handler and OPEN corrections, with the regenerated QMI header described in
[qmic generation](qmic-generation.md). The source base remains RMTFS
`b30a3eb38f9af283f18dbd3c7755653efc52c094`, with corrected QRTR
`29e36ae164389580a0f8ea7a7fdb728140ae978d`. All callers rebuild together because
the private memory helper address parameter changes from `unsigned long` to
`uint64_t`.

The common validator uses subtraction after checking the region metadata and
lower bound, then checks the remaining capacity. It rejects empty or wrapping
regions, missing fd backing, mapped sizes unrepresentable by `size_t`, and fd
spans unrepresentable by signed 64-bit offsets. The implementation requires
64-bit `off_t` at compile time. The read/write helpers reject negative lengths
and nonempty null buffers, and return zero for a valid empty span without an
I/O call. Physical addresses remain 64-bit through offset calculation on ARM.

Global allocation retains its original ownership model and accepts a request
up to the region size. It now validates the backing and the signed return-value
representation. IOVEC validation multiplies sector counts in 64 bits and checks
all nonempty spans before transferring anything. A rejected span also prevents
write synchronization. Valid zero-sector and empty write requests retain their
flush behavior. The patch adds metadata/length checks before UIO and `/dev/mem`
mapping and validates a constructed region before returning it; these constructor
paths are compiled but are not exercised by this checkpoint's tests.

## Verification

Thirty-five isolated cases pass on host Clang ASan/UBSan and static ARM/QEMU.
The harness includes the actual patched `sharedmem.c` and `rmtfs.c`, generated
RMTFS descriptors and corrected QRTR codec. RAM, fd transfers, storage and reply
transport are synthetic; wrappers reject device open, mmap and socket creation.
Tests cover both backends, first/last-sector roundtrips, physical addresses above
4 GiB on ARM, empty transfers, allocation bounds, invalid spans and metadata,
64-bit fd limits, and mapped-size representability. Two-entry read/write tests
check exact effects. A later invalid entry must leave both entries untouched,
without fd/storage transfers or synchronization. Empty write requests still sync.
These are checks of the corrected candidate; no unpatched failure reproduction
is run.

Fifteen selected existing protocol/storage regressions also pass on both
platforms, using the updated 64-bit memory mock and preflight validator. Its
`--cases-json` option allows the selected subset to be recorded explicitly.
The old harness and checker bytes are retained with earlier evidence.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/modem-control/check-rmtfs-memory.py \
  --source /private/rmtfs-candidate --qrtr /private/qrtr-candidate \
  --provider /private/verified-eudev-provider \
  --harness tests/rmtfs-memory-harness.c --output local/rmtfs-memory-replay \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]'
```

Use a fresh output directory. ARM checks accept JSON compiler and runner argv
prefixes with static linking, the target musl sysroot and isolated QEMU. The
recorded runs mount compiler/sysroot directories read-only and only the new
workspace writable; physical devices, key homes and networking are absent.

The complete candidate is a 785,876-byte ARM hard-float static PIE, SHA256
`951f3b325e3180c65ae3cdcf4f322592c4aca7a7fe24c38a94f8c926639ba1e4`.
All eleven persistent linker inputs match the previously authenticated clean
recipe package members described in [the provider checkpoint](rmtfs-libudev.md).
Only the daemon's early unsupported-option exit executes under isolated QEMU;
it performs no device opens or socket calls. Existing unrelated compiler
warnings remain. The cross compiler executable's recipe identity is still
unqualified.

## Remaining acceptance

The tests do not establish real mapping, fd driver behavior, full metadata
parsing, constructor cleanup, service/remoteproc lifecycle, modem operation,
request scheduling limits or physical provisioning safety. A valid transfer
may still fail partway through; preflight is not transactional storage. There
is no new global work budget or ownership model. General nested-string codec
limits, reproducible packaging and static relink materials remain open.

No phone command, upload, package installation, reboot, RAM entry, firmware or
radio action, provisioning write or recovery-disk write occurs. The latest
native display/touch gate remains pending. Full fx0 bringup remains active.
See [manifest](../../manifests/rmtfs-memory-candidate.json) and
[evidence](../../evidence/2026-11-10-rmtfs-memory-candidate.json).
