# QRTR QMI bounds and required fields — unsent draft

Base: [29e36ae](https://github.com/linux-msm/qrtr/tree/29e36ae164389580a0f8ea7a7fdb728140ae978d).
No issue, message or merge request has been sent.

Malformed packets can read beyond short headers/TLVs/count prefixes/scalar
arrays, skip an optional TLV beyond the packet, or decode incomplete arrays and
missing required fields successfully. RMTFS can consequently close a live
handle, allocate or transfer data for an incomplete request. The
[candidate patch](../../diagnostics/modem-control/qrtr-qmi-bounds.patch) validates
wire bounds and complete descriptor groups before reporting success. It also
allows string encoding without a preceding array-count descriptor. Preserve
the original BSD notice.

The [52-case codec harness](../../tests/rmtfs-qmi-harness.c) passes on host
Clang ASan/UBSan/leak detection and static ARM/QEMU; baseline failures are 35
and 24 respectively. The [32-case dispatcher harness](../../tests/rmtfs-protocol-harness.c)
passes on both with a separate RMTFS OPEN buffer correction. Six malformed
dispatcher cases fail against the unchanged codec. Positive cases include
unknown optional TLVs, reversed required fields, zero/maximum arrays and
empty/maximum strings. No physical channel or provisioning data is used.

The upstream default-branch head was rechecked on November 14 and remains
the base above. Before submission, split encoder/decoder concerns as
appropriate, integrate generic tests into the upstream build, and review
descriptor compatibility beyond the finite supplied tables. Resolve the RMTFS
string generator's terminator allocation separately. This is not a complete
codec security audit or hardware qualification. See
[procedure and limits](../../diagnostics/modem-control/rmtfs-qmi.md).

Normal signed distribution builds now use the complete QRTR 1.2 release;
its seven library/header/license blobs match this draft's base. The actual
signed ARM library passes the existing 52 codec cases. This closes the package
and source-replay prerequisite, with generic upstream test integration still
open. [Distribution evidence](../../evidence/2026-11-14-rmtfs-distribution-packages.json)
