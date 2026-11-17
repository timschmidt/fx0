# Maintained-LTS binding dependencies and torch shutdown

Local, unpublished qualification for Linux 6.18.63. Exact base/head and original
authors/dates appear in `source-current.json`. Three source changes are ported;
two existing PON/torch descriptions receive focused equivalence qualification.
Original patches and assistance credits are preserved. Human review and DCO
remain pending; no agent sign-off or human certification was added.

The existing normal board, PM8226 PON label, disabled common torch node,
CAMSS binding, WCN3660A enum and driver build entries are retained. The complete
incoming normal board is already present, with the maintained tree's additional
APC/SAW blocks and eight-byte CPU calibration cell. These are preserved, along
with CPU/suspend targets and the full LTS board list. No DTS or DTC input changes.
The IOMMU dependency is reconciled against its exact original parent. Only the
LED choice changes in the MFD parent; unrelated PMIC/child support is unchanged.
The existing modern LED binding remains byte-identical, with disjoint compatible
fallbacks proving the added choice does not reject its existing valid nodes.

The old torch driver aborts shutdown after an early register error and clears
supply ownership even when regulator disable fails. The port attempts all off
paths, retains the first error and keeps ownership after failed disable. The
entire driver otherwise matches the original current-source implementation;
only its shutdown function changes in the existing LTS driver. Attribution to
Timothy Schmidt and the original Claude assistance remains in the source series.

The exact LTS baseline fails all five shutdown fault scenarios. The corrected
source passes all five, eight startup fault scenarios, one combined cleanup
fault, 32 healthy brightness/supply cases and 400 host-thread callback
transactions. Two deliberately faulty variants are rejected by the intended
assertions, not by compiler or sanitizer failures. Production function bodies
are extracted unchanged. Regmap, regulators and delay services are synthetic;
POSIX mutexes provide the host-thread exclusion. ASan, failfast UBSan and normal
LeakSanitizer are explicit, with compiler temporaries in owned output directories.
Earlier runs without the explicit failfast settings are retained locally and
are superseded by the named before-03/after-02 receipts.

Three actual driver objects compile on ARM, ARM64 and ARM64 RT with W=1,
COMPILE_TEST off and nonpermissive CFI, without diagnostics. This phase does not
relink the complete kernel. The full kernel/447 unsigned module integration
link at the prior coordinator head remains historical evidence. Normal signed
APK, release-specific updates/recovery and current combined hardware remain open.

Fourteen binding lint/meta/example gates pass. Full, unfiltered schema
validation is silent for all nineteen tested DTBs: every one of the eighteen
registered maintained-tree PM8226 boards and the unaffected S3VE3G control.
This includes normal, CPR and suspend Madai, so their former torch-parent schema
rejection is resolved. The eighteen prior family DTB hashes are reverified;
the additional existing Falcon target is built natively. The newer Titan and
Eagle targets are absent from LTS and are not imported or counted. The source
inventory follows registered DTS include graphs rather than filename prefixes.
Seven malformed LED examples are rejected, and PM8941-only, minimum-current and
nonmultiple-current forms pass. Existing board, PON, reserved memory, normal APC
and CPU cell source bytes remain unchanged. This is current LTS family schema
acceptance; it does not erase the earlier experimental 66-board global failure.

Strict full-patch checkpatch reports zero errors, one new-file reminder and no
checks. The following exact metadata port supplies the binding owner. No check
types are ignored. The sign-off check is disabled explicitly because human DCO
has not been certified; the strict style gate remains unpassed. A message-only
wrap correction preserves its source tree and retains the first style receipt.

With Python and clang-21, run:

```
python3 -B run-qualified.py --source /path/to/linux --output /private/new-output
```

The runner verifies packet and all twelve selected source hashes before three
explicit jobs: baseline, corrected behavior and regression controls. It owns
and reaps children and performs no discovery, native build, schema check, real
LED operation or network access. Build/schema controllers are separate
workspace-bound evidence. No ELF, module, DTB, boot image, private key, device
capture, credential or firmware is included. Source and fixture licenses are
retained. Review log copies normalize only workspace prefixes and trailing
whitespace, with original/transformed hashes recorded.

The maintained ledger now has 51 ports (41 exact, ten reconciled), nine focused
existing equivalents and one inapplicable allocation-only API change. Another
86 commits remain to audit. Final normal CPU/system-sleep promotion, all other
hardware/source dependencies, public-source APK/update/recovery, physical
current and bus uncertainty, strobe/boost, the original r2 fault, final boot,
motion-wake, standby and soak acceptance remain open. The original seven
bringup requirements are preserved. No phone, Wi-Fi scan, Replimat3, network
configuration, publication or maintainer contact occurred during this phase.
