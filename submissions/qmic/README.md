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

The current upstream default-branch head was rechecked on November 14 and
remains the base above. A two-patch series now separates the correction from
generic upstream `make check` integration:

1. [String terminators and optional flags](0001-kernel-string-terminators-and-optional-flags.patch).
2. [Generated output contracts](0002-tests-generated-kernel-string-contracts.patch).

The six fixture/golden inputs exactly match the qualified distribution
package inputs. The upstream target passes in the authenticated Alpine
native root. The unchanged-generator control, first and last output mismatches,
and failed generator all reject; temporary directories are cleaned afterward.
The default build target and BSD license are preserved. See
[contract-test evidence](../../evidence/2026-11-14-qmic-upstream-contract-tests.json).
The exported series replays to the exact reviewed tree. Git's mail-patch
application reports three blank-at-EOF warnings: the Makefile and the two
golden C files retain a final blank line. The golden bytes match the qualified
generator contracts exactly.

The series remains local and unsent. Human authorship/DCO and submission review
remain pending. A 256-byte nested string remains outside the legacy one-byte
length prefix's range; resolving that codec/wire issue is separate work.
No comprehensive generator audit or physical modem acceptance is claimed.
See [procedure, evidence and limits](../../diagnostics/modem-control/qmic-generation.md).
