# RMTFS packet-handler candidate

The handler candidate passes 25 synthetic packet cases on host Clang
ASan/UBSan/leak detection and static ARM/QEMU. The baseline fails 11 cases on
each runner, including four ARM segmentation faults. These tests use the real
dispatcher, QRTR/QMI codec, generated message descriptors and storage code.
The daemon remains uninstalled and unstarted on the phone.

Apply [the storage fix](rmtfs-storage-bounds.patch), then
[the handler patch](rmtfs-handler-errors.patch), to
[RMTFS b30a3eb](https://github.com/linux-msm/rmtfs/tree/b30a3eb38f9af283f18dbd3c7755653efc52c094).
Use [QRTR 29e36ae](https://github.com/linux-msm/qrtr/tree/29e36ae164389580a0f8ea7a7fdb728140ae978d)
unchanged. The baseline already includes the tested storage fix, isolating the
new handler failures. Attribution remains in [the upstream license](rmtfs-LICENSE).

The patch corrects the inverted GET_DEV_ERROR handle check: a live handle now
returns its status, while invalid, closed and foreign handles fail without
dereferencing NULL. Verbose CLOSE formats a numeric handle correctly and has
the correct number of format arguments. Sector multiplication widens before
multiplying by 512, preserving offsets beyond 4 GiB and at UINT32_MAX sectors
on ARM. The unsigned sector loop index matches the wire count type. Write
responses propagate storage sync failures and avoid syncing an absent handle.
Transaction variables start at zero when request decoding fails before assigning
them. Allocation address logging uses a matching 64-bit format on ARM.

The harness feeds encoded QMI through `handle_rmtfs()`. Responses must have
the expected message ID, result and transaction. Storage opens only two guarded
synthetic files with O_RDONLY; writes affect RAM shadows. Memory and transport
are mocked, real sockets and persistent writes fail, and all backing bytes must
remain unchanged. Positive reads/writes cover multiple sectors and shadow
round trips. Additional cases cover same-node handle reuse, foreign/closed
handles, global allocation before OPEN, oversized allocation, far-sector
offsets, sync errors, memory errors/short transfers, zero sectors, an unknown
request and an incorrect message type. Global allocation and nonzero direction
semantics are preserved; this work does not establish a new ownership policy.

The pinned generated OPEN descriptor is a variable-length string without a
DATA_LEN descriptor, and the pinned encoder rejects it. The harness constructs
that request's specified string TLV directly; other requests use the real
encoder. All requests and responses use the real decoder. Fixing the encoder
and qualifying malformed/truncated/missing-field decoding remain open.

```sh
patch --batch --fuzz=0 -p1 -d /private/rmtfs-candidate \
  -i "$PWD/diagnostics/modem-control/rmtfs-storage-bounds.patch"
patch --batch --fuzz=0 -p1 -d /private/rmtfs-candidate \
  -i "$PWD/diagnostics/modem-control/rmtfs-handler-errors.patch"
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/modem-control/check-rmtfs-protocol.py \
  --source /private/rmtfs-candidate --qrtr /private/qrtr \
  --harness tests/rmtfs-protocol-harness.c \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]' \
  --output local/rmtfs-packets-replay
```

Use a fresh output directory. The checker also accepts JSON compiler and runner
argv prefixes for cross compilation and isolated emulation. ARM runs mount
compiler/sysroot inputs read-only, use synthetic /dev and isolate networking;
no signing-key home or physical device is mounted. Core dumps are disabled.
Exact source/header/harness hashes and commands accompany each run. Initial
test development failures are retained: the OPEN encoder rejection, unavailable
LeakSanitizer under the tracing sandbox, and two corrected mock errors (pointer
arithmetic and ARM unsigned conversion of an error return). Final runs use the
same corrected 25-case harness on both architectures.

This is finite handler qualification, not a complete codec or daemon audit.
Shared-memory span/truncation checks, large-count resource limits, malformed
messages, client cleanup and service/remoteproc ownership still require work.
The [full-daemon libudev provenance gap](rmtfs-userspace.md) also remains open;
the current handler tests do not link libudev. No revised full-daemon binary is
promoted. No phone command, upload, reboot, RAM entry, package/module operation,
firmware/radio operation, provisioning write or recovery-disk write occurs in
this checkpoint. The current native display/touch gate remains pending.
See [evidence](../../evidence/2026-11-09-rmtfs-handler-candidate.json).
