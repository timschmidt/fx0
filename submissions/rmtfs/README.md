# RMTFS storage correction draft

Destination: [linux-msm/rmtfs](https://github.com/linux-msm/rmtfs), based on
`b30a3eb38f9af283f18dbd3c7755653efc52c094`. Nothing has been sent upstream.

Proposed subject: `storage: validate handles and ranges before copying snapshots`

The storage API can turn large offsets into out-of-bounds copies on 32-bit ARM,
reuse a closed handle and accept an incomplete read as a complete read-only
shadow. Invalid caller IDs and signed/count errors also reach invalid memory,
while failed snapshot reads leak buffers. Growing shadows can expose uninitialized
gaps and backing pread errors can be reported as successful reads.

The [candidate patch](../../diagnostics/modem-control/rmtfs-storage-bounds.patch)
checks live handles and representable ranges before access, retains errors,
zero-fills growth and completes snapshot reads or fails without publishing a
partial buffer. It changes only `storage.c`; there is no ABI, QMI format or
remoteproc lifecycle change. Preserve upstream's BSD notice.

Validation uses [the actual storage API harness](../../tests/rmtfs-storage-harness.c)
and [runner](../../diagnostics/modem-control/check-rmtfs-storage.py). The upstream
baseline fails 15/20 host sanitizer cases and 13/20 static ARM emulation cases;
the candidate passes 20/20 in both. It includes a positive persistent-write
control and verifies no backing writes in shadow mode. Full host and static ARM
daemons build; only early invalid-option rejection is executed for the daemon.

This remains draft material. Integrate the generic harness into the upstream
test/build workflow and refresh the submission base before sending. Full daemon
dependency provenance includes a retained libudev provider with `-dirty` recipe
metadata, so hardware trial/promotion is not justified by this build. QMI/sector
and shared-memory/lifecycle tests remain separate. No firmware or physical
modem acceptance is claimed. See [scope and evidence](../../diagnostics/modem-control/rmtfs-userspace.md).


## OPEN buffer and dependency decoder follow-up

The [OPEN C buffer patch](../../diagnostics/modem-control/rmtfs-open-path-terminator.patch)
retains the descriptor's 256-byte wire maximum and adds room for the NUL
terminator. Integrate this allocation rule into `qmic` generation before
regeneration/package promotion. The separate
[QRTR QMI candidate](../qrtr/README.md) validates bounds and required fields;
52 codec and 32 dispatcher cases pass per host/ARM runner. The dispatcher now
rejects malformed requests before close/allocation/memory/sync effects. See
[procedure and limits](../../diagnostics/modem-control/rmtfs-qmi.md).


## Reproducible source generation checkpoint

The [pinned qmic patch](../qmic/README.md) now reproduces the corrected OPEN
capacity through RMTFS's real Makefile target. The generated descriptor source
is byte-identical to upstream; the current generator emits two count fields as
uint32_t. Sixteen normal cases verify generated wire bytes and round trips on
host/ARM. Distribution recipe integration and full daemon qualification remain
open. See [generation procedure](../../diagnostics/modem-control/qmic-generation.md).


## Provider qualification follow-up

The [new provider/runtime candidate](../../diagnostics/modem-control/rmtfs-libudev.md)
uses signed eudev and clean target GCC/musl runtime package members. Five real
libudev API cases pass in synthetic sysfs, and the full ARM diagnostic link has
no runtime shared dependencies. Earlier dirty-metadata builds remain separate.
Compiler-executable provenance, packaging and physical startup remain open.


## Shared-memory candidate follow-up

The [incremental memory patch](../../diagnostics/modem-control/rmtfs-shared-memory-bounds.patch) adds subtraction-based range checks shared by mapped/fd transfers, 64-bit physical parameters, allocation representation checks and IOVEC preflight before the first transfer. Valid empty-write flush semantics remain. Thirty-five memory tests and fifteen selected functional regressions pass on host sanitizers and ARM/QEMU; public patch replay matches the full candidate. Metadata/mapping guards in constructors are compiled but not exercised. Full daemon lifecycle, physical operation, compiler recipe identity and packaging remain open. See [scope and replay instructions](../../diagnostics/modem-control/rmtfs-shared-memory.md). This remains a draft; no upstream submission or phone startup occurs.


## Linux discovery candidate follow-up

The [discovery patch](../../diagnostics/modem-control/rmtfs-device-discovery.patch) gives fd, mapping and libudev resources explicit owners, limits fallback to absent device paths, and validates a unique DT region with declared cell counts before mapping. Forty-six synthetic constructor cases and thirty-five memory regressions pass on host sanitizers and ARM/QEMU. See [scope and replay instructions](../../diagnostics/modem-control/rmtfs-discovery.md). Android-specific code, live driver mappings and remoteproc/service lifecycle remain open. This remains a draft.


## Daemon lifecycle follow-up

Serialize optional remoteproc start and stop in one worker, keep its power reference independent of QRTR reconnection, and service requests while state writes finish. Correct socket and remoteproc descriptor cleanup and report startup failures to the caller. Nineteen synthetic lifecycle cases and fifty selected regressions pass on both host and ARM. Live remoteproc and firmware behavior remain open. [Lifecycle patch and verification](../../diagnostics/modem-control/rmtfs-lifecycle.md)
