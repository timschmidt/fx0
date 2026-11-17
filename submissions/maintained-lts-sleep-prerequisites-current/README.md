# Maintained-LTS sleep prerequisites

This local, unpublished packet qualifies seventeen prerequisites against Linux
6.18.63, following the initial CPU stack. See `source-current.json` for the
exact base/head and the attributed per-commit mapping. Sixteen ports preserve
the original added/removed source lines; one retains zeroed allocation through
`devm_kzalloc(dev, sizeof(*pair), GFP_KERNEL)`, supported by the LTS API.
Unrelated LTS platform support and allocation calls remain intact.

The changes fix the SDM660 silver L2 AVS value and zero-offset sequence copying;
add explicit RPM sleep callbacks, paired normal/active-only MX votes and an
independent sleep-only vote; protect live APC during boot handoff; retain a
covering optional CPR sleep vote; install the 84-byte public vendor L2 programs;
bound CPU-SPM writes and propagate errors through CPU idle; and provide owned
RPM request admission/drain APIs. The ordinary Madai DTB is unchanged. These
changes update the alternate CPR qualification target only; normal-target
promotion and the production system-entry coordinator remain pending.

Original authors/dates, licenses and human attribution tags are retained.
Original patches preserve the pre-backport messages, including historical Fixes
references. Current dependency references point to the corresponding maintained
commits. Codex prepared the reconciliation and verification; no agent sign-off
or human DCO certification was added. Message-only revisions are archived,
with each source tree verified identical. Nothing was published or sent to
maintainers.

## Qualification and limits

Nine synthetic source models execute 14,924 cases, with zero failed checks.
They cover normal, active-only and sleep-only request aggregation, all six
valid topology orders, boot constraints before the first consumer, regulator
core callbacks, CPR sleep-vote cleanup and uncertainty, exact CPU-SPM and
CPU-idle paths, L2 setup/arm/disarm/publication, RPM send/ACK/admission, and the
actual maintained `suspend_enter` ordering with six dispatch wrappers. The
shared-platform SPM checks reuse the 1,198-case SPM suite with explicit AVS
and zero-sequence-offset assertions. These reused cases are not added again
to the nine-model total. All four vendor programs and their END padding match
the public-source provenance, totaling 84 bytes.

A further 44 retained CPU regression methods pass without discovery or skips.
An audited compiler wrapper instruments 25 standalone executables with ASan,
UBSan and normal LeakSanitizer; seven ctypes numerical oracles are explicitly
unsanitized. The obsolete setup-only L2 method is replaced by the stronger
1,259-case sequencer/publication suite. Synthetic declarations now represent
the new RPM fields, pair dispatch and optional absent sleep supply. The old
unpaired recovery model asserts that pair dispatch is unreachable; complete
paired and sleep-client paths are covered separately. The first six fixture
compile failures are retained and are not counted as clean behavioral controls.

There are 113 rejected fault controls: 107 rail/SPM/L2/admission controls, four
PM-order controls and two shared-platform regressions. Rejection requires the
intended assertion, not a compile error or sanitizer crash. RPM admission also
passes 40 real host pthread drain runs, with synthetic IRQ and transport state.
This does not qualify kernel concurrency, firmware KVP atomicity or hardware.

The pre-boot-guard provider fails 2,180 checks on the 317-case boot model and
passes afterward. The pre-sleep-only factory fails the six valid-topology
contracts and passes afterward; this is an unsupported new feature, not a
generic-core vulnerability. An earlier copied baseline had mutually exclusive
assertions; it is excluded from the packet and from qualification. The old
unbounded SPM write is escaped by a model watchdog after 101 writes and 100
reads/relaxes; the old function itself did not return. The legacy ACTIVE trace
is byte-identical before and after (1,280 bytes). Failures of new sleep-policy
expectations on the old parent are not claimed as legacy ACTIVE defects.

Six native profiles compile 122 selected objects: ARM normal, ARM64 normal and
ARM64 RT, each with the MSM8926 feature enabled and disabled. CPU-idle is ARM
only. Configs verify EXPERT, COMPILE_TEST off, actual RT state and nonpermissive
CFI. W=1 produces no diagnostics. ARM32 RT is unsupported and not counted.
The first unsupported allocation-macro build is retained. All final source,
config and object hashes were reverified after commits; objects were built
before source commits. No full link or release-specific APK is qualified.

All seventeen MSM8226-family DTBs build. The ordinary Madai and fifteen other
boards are byte-identical to the previous CPU checkpoint; only the alternate
CPR target changes. Six binding example/lint/meta-schema gates pass and 119
selected DTB/schema checks are silent. The 68 DTC warning lines, including
multiplicity, match the prior build. The initial controller incorrectly
expected the ordinary DTB to change and then compared parallel warning order;
the successful native builds are retained and qualified by their hashes and
warning multiset. This is not a new global, unfiltered schema acceptance claim.

Strict full-patch checkpatch reports two errors and five warnings, with no
check types ignored. Both errors and four warnings misparse unchanged YAML
context `regulator-state-standby: false` as an attribution/email trailer. The
last warning is the new-file reminder; existing `cpr*.h` MAINTAINERS coverage
includes the new helper. Evidence records the exact context and hashes. The
checkpatch gate remains failed; human review is required. The sign-off check is
disabled explicitly because human DCO has not been certified. Historical failed
receipts and unchanged source trees remain preserved locally.

## Replay

With clang-21, a C compiler, Python and the exact maintained source available:

```
python3 -B run-qualified.py --source /path/to/linux --output /private/new-output
```

The runner verifies the packet manifest and 60 pinned source inputs before
executing nineteen explicitly selected host-only jobs. It owns, times out and
reaps its subprocesses. It does not perform test discovery, native kernel builds,
DTB/schema checks, signing, installation, real suspend or any device action.
Native/schema controllers and build scripts are separate workspace-bound
evidence. No root audio/SLIMbus test is invoked. Model services are synthetic;
no phone, fuse, firmware, audio, radio or network execution occurs.

The full LTS ledger now has 38 source ports (32 exact deltas, six reconciled),
seven existing equivalents with focused qualification and one allocation-only
refactor inapplicable to LTS. Another 101 commits remain to audit. A complete
system sleep coordinator, final normal target, normal public-source APK and
update/recovery, all nonaudio hardware, final boot/motion/standby/soak acceptance,
and the independent SLIMbus recovery gaps remain open. The original r2 fault
is not physically proven fixed. All seven original bringup requirements remain.

There was no phone access, Wi-Fi scan, Replimat3 interaction, network change,
publication or maintainer contact. Compiled programs, objects, DTBs, boot images,
private keys, credentials and firmware are excluded. Project fixtures retain
the MIT license; kernel-derived/new verification retains its GPL SPDX notices.
Patch license notices remain intact. Review log copies normalize only workspace
prefixes and trailing whitespace, with original/transformed hashes recorded.
The exact historical `.diff` fixture retains its original context bytes through
one narrowly scoped literal-whitespace attribute, matching prior review packets.
