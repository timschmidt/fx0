# QMI kernel string fields — unsent draft

Base: [4574736](https://github.com/linux-msm/qmic/tree/4574736afce75aa5eec1e1069a19563410167c9f).
No upstream issue, message or merge request has been sent.

Kernel output declares 256-byte string buffers while its descriptors allow
256 wire bytes and decoding adds a NUL. It also omits the validity member and
OPT_FLAG for optional strings. The [patch](../../diagnostics/modem-control/qmic-string-fields.patch)
allocates the terminator byte and emits optional string markers. Only kernel.c
changes; accessor output is unchanged. Preserve the BSD license.

The real RMTFS Makefile regeneration rule produces the corrected OPEN header;
the generated descriptor C file remains byte-identical to upstream. Sixteen
normal cases pass with regenerated output on host sanitizers and static ARM:
whole-message independent wire bytes, round trips, top-level maxima, nested
strings through 255 bytes, optional presence and both regenerated RMTFS count
fields. Exact patch replay and repeated source generation pass.

Refresh the upstream base and integrate tests before submission. A 256-byte
nested string remains outside the legacy one-byte length prefix's range;
resolving that codec/wire issue and distribution packaging is separate work.
No comprehensive generator audit or physical modem acceptance is claimed.
See [procedure, evidence and limits](../../diagnostics/modem-control/qmic-generation.md).
