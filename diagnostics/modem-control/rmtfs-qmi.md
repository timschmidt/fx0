# QMI boundary and required-field candidate

The candidate passes 52 codec cases and 32 actual RMTFS dispatcher cases on
each of host Clang ASan/UBSan/leak detection and static ARM/QEMU. The unchanged
codec fails 35/52 host cases and 24/52 ARM cases; six malformed dispatcher cases
fail on both. All data, memory and transport are synthetic. Nothing is uploaded,
installed or started on the phone.

The baseline already contains the [storage](rmtfs-storage-bounds.patch) and
[handler](rmtfs-handler-errors.patch) corrections. The new
[QRTR patch](qrtr-qmi-bounds.patch) applies to
[29e36ae](https://github.com/linux-msm/qrtr/tree/29e36ae164389580a0f8ea7a7fdb728140ae978d).
The [OPEN buffer patch](rmtfs-open-path-terminator.patch) applies to
[RMTFS b30a3eb](https://github.com/linux-msm/rmtfs/tree/b30a3eb38f9af283f18dbd3c7755653efc52c094).
Both replay exactly without fuzz. Only QRTR `lib/qmi.c` and the RMTFS OPEN
request's C buffer declaration change in this checkpoint. Preserve the
[QRTR QMI notice](qrtr-qmi-LICENSE) and [RMTFS notice](rmtfs-LICENSE).

The decoder now checks complete headers and matching message lengths before
reading fields, complete TLV headers and payload bounds before use or optional
skipping, count-prefix and scalar-array sizes before copying, and all declared
structure members and array entries. Nested strings check their prefix and
payload together. Known TLVs must consume their declared length. All required
top-level descriptor groups must appear; groups starting with OPT_FLAG may be
absent. Valid unknown optional TLVs and reordered required fields remain accepted.
Decoded output may be partially written on failure and must not be used then.

The baseline dispatcher demonstrates why failure handling matters: an empty
CLOSE closes caller zero, missing allocation size invokes allocation, missing
IOVEC direction transfers data as a read, and an array claiming two entries
with only one encoded entry still performs a write/sync. The candidate returns
MALFORMED_MSG before those effects, preserving the live handle and leaving
allocation, storage sync and memory transfer counters at zero. A short header
is rejected without a response. Guarded synthetic backing files remain unchanged.

OPEN's descriptor permits 256 wire bytes. The C buffer now has 257 bytes to
hold those bytes plus the terminating NUL; the wire maximum is unchanged.
The encoder now lets the string encoder determine its length instead of
requiring a preceding array count. Empty, ordinary and maximum-size OPEN
encoding/decoding pass. Existing dispatcher fixtures still construct OPEN's
string TLV directly so the same inputs can test the unchanged baseline.

The direct codec harness uses exact-size heap input buffers. Cases cover header
lengths zero through six, NULL inputs, length disagreements, truncated TLV
headers, oversized TLVs, unknown optional overrun, missing required fields,
short/extra scalar payloads, missing array counts/members/entries, zero and
maximum arrays, reversed required fields, string lengths 0/255/256/257, and
nested strings with one- and two-byte prefixes. The ARM emulator does not detect
every out-of-bounds access found by host sanitizers; its baseline pass count
does not prove those inputs safe.

```sh
# First prepare RMTFS with both earlier storage/handler patches.
patch --batch --fuzz=0 -p1 -d /private/rmtfs-candidate \
  -i "$PWD/diagnostics/modem-control/rmtfs-open-path-terminator.patch"
patch --batch --fuzz=0 -p1 -d /private/qrtr-candidate \
  -i "$PWD/diagnostics/modem-control/qrtr-qmi-bounds.patch"
python3 diagnostics/modem-control/check-rmtfs-qmi.py \
  --rmtfs /private/rmtfs-candidate --qrtr /private/qrtr-candidate \
  --harness tests/rmtfs-qmi-harness.c \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]' \
  --output local/rmtfs-qmi-replay
python3 diagnostics/modem-control/check-rmtfs-protocol.py \
  --source /private/rmtfs-candidate --qrtr /private/qrtr-candidate \
  --harness tests/rmtfs-protocol-harness.c \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]' \
  --output local/rmtfs-qmi-dispatch-replay
```

Use fresh output paths. Both checkers accept JSON compiler/runner prefixes for
static ARM cross compilation and isolated QEMU. Compiler/sysroot mounts are
read-only; networking and real device nodes are absent. Core dumps are disabled.
Build logs, exact source/header/harness hashes, binary hashes, per-case results,
and patch replays are retained under `local/rmtfs-qmi-01`.

This is finite qualification with trusted descriptor tables, not a complete
generic codec audit or physical modem test. The generated OPEN header fix needs
matching generator integration before regeneration/package promotion; the pinned
Makefile can invoke `qmic -k`. Shared-memory spans/address truncation, large-count
resource use, ownership/lifecycle and clean libudev recipe provenance remain
open. No revised full-daemon build is promoted. The latest phone UI check is
still pending. See [evidence](../../evidence/2026-11-09-rmtfs-qmi-candidate.json)
and the unsent [QRTR draft](../../submissions/qrtr/README.md).
