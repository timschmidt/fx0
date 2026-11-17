# Maintained-LTS CPU foundation

Local source and host evidence for Fx0 Linux 6.18.63. Base:
`136e614f365c855c3897e4a96ac3b2bdede9feda`; resulting source head:
`432cb11b41e9427d0d095fda2d09da9b7034983e`.

Two local commits add four exact calibration/planning headers and the missing
QFPROM raw-window size guard. Original Timothy Schmidt authors/dates and source
licenses/copyrights are preserved; Codex assistance is disclosed. The existing
SCM calibration API, wire macros, legacy transport functions and public API
prototype already match the current integration exactly. The QFPROM final
source matches apart from the preserved LTS mod_devicetable include. Its raw
binding semantics also match; ten unrelated newer SoC compatible entries were
not imported into this maintained tree.

The decoder passes 4,068 synthetic cases and 178,907 checks. Existing SCM wire
behavior passes 667 cases and 34,017 checks, plus 13 captured API contracts.
The QFPROM probe/read/keepout/sysfs model passes 18,393 assertion checks, with
one failing baseline check demonstrating a read beyond the final keepout on
an oversized synthetic resource. The reader's legacy `cases` receipt field
counts assertions, not separate scenarios. Twelve faulty variants are rejected
without sanitizer diagnostics. ASan, UBSan and normal LeakSanitizer are enabled.

Sixteen selected helper test methods pass with no skips. Their ctypes shared
oracle modules are unsanitized; the standalone synthetic fuse loader uses the
sanitizers. All rows, MMIO and firmware responses are synthetic. Production
function bodies are extracted unchanged. Synthetic NVMEM declarations and
captured registration assignments follow the LTS direct-callback API. The
initial fixture assumed the newer missing-callback error: four EOPNOTSUPP
expectations were corrected to the actual extracted LTS EINVAL behavior.
No SRCU lifetime or full kernel registration behavior is established.

QFPROM, NVMEM core and two SCM objects compile in ARM normal, ARM64 normal and
ARM64 RT: 12 driver objects, no diagnostics, W=1 and nonpermissive CFI verified
in actual configs. Three additional native object probes instantiate all four
helper headers against real LTS APIs. These are probes, not CPR consumer/kernel
links. ARM32 RT is unsupported and is not counted. The controller ran before
source commits; its source hashes match the committed bytes.

The existing binding passes 39 focused schema profiles and rejects all ten
malformed variants. These include the 38 LTS corrected-compatible profiles
and an unchanged cached board used as a raw-reader schema fixture. It is not
a newly built LTS board or proof of complete 64-bit raw-cell integration.
The processed schema includes the full LTS nvmem directory plus packaged core
schemas; validation selects QFPROM. The first single-YAML attempt lacked
referenced NVMEM schemas and failed. No diagnostic was suppressed. Ordinary
binding examples and full-board/all-binding validation were not rerun here.

Strict checkpatch reports zero errors, one warning and one check. Remaining:
MAINTAINERS coverage of new headers, to complete with the CPU metadata/consumer
port; and the original `bootstrap_mx_uV` field's voltage-unit spelling, flagged
as CamelCase. The complete check log is retained. No check type is ignored.
Human review/DCO and the complete remaining CPU consumer, rail/clock/suspend,
board, normal public-source package, update/recovery and hardware work remain
open. Across the LTS audit, eight source backports and seven existing equivalent
changes have focused qualification; another 132 current-source commits still
need audit. All seven original bringup requirements remain in scope.

Run the portable source models (Python 3, cc and clang-21 required) in an
environment supporting normal LeakSanitizer:

```sh
python3 replay.py --source /path/to/qualified/linux --output /new/private/output
```

The replay verifies every pinned source input, executes positives, baseline,
12 fault controls and the 16 helper methods, and records terminal cleanup.
It does not repeat native compilation or schema validation; those have separate
receipts. `build-native.py` is the exact workspace controller used with existing
qualified LTS configs. The first portable controller compared only the C program
hash for included-header mutations; it correctly stopped and was fixed to use
the actual included calibration-header hash. No source bug or failed mutation
was hidden by that correction.

There was no phone access, real fuse read/write, firmware invocation, audio/radio
execution, Wi-Fi scan, Replimat3 interaction, network configuration, publication
or maintainer contact. No compiled programs, boot images, firmware, credentials
or private keys are included. New verification code and helper headers retain
GPL-2.0-only notices; the QFPROM binding retains its original dual license.

Copied project test fixtures and vendor-array manifests under `harness/fixtures`
retain the project MIT license and Timothy Schmidt copyright in `LICENSE-MIT`.
Kernel-derived/new GPL verification code retains its SPDX notices; the GPL
license text is included separately. No source attribution was replaced.

Review log copies normalize trailing whitespace and the workspace path;
`sanitized-log-provenance.json` records transformations and original hashes.
Raw logs are preserved locally. Diagnostic lines and counts are retained.
