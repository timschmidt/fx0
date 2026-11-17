# Maintained-LTS initial CPU stack

Local, unpublished host qualification for Fx0 Linux 6.18.63. Base:
`432cb11b41e9427d0d095fda2d09da9b7034983e`; source head:
`8d8cb579e4ba340a4bd943daca58dffa47aa2559`.

Thirteen attributed source changes port the CPU binding/metadata, permanent L2
owner, fixed-range APC transaction, per-request RPM correlation, retained MX
helper, PLL/mux verification, calibrated domain, filtered CPUfreq attachment,
raw map locks, legacy map ownership and the board qualification target.
Original authors/dates and source copyrights/licenses remain preserved. The
original messages and complete source IDs are recorded separately. Codex
assisted the port, context reconciliation and verification; no agent sign-off
or human DCO certification was added. Initial message-only revisions remain
preserved in archive refs with every source tree unchanged.

Changes are reconciled against their exact original-parent files. LTS Kconfig
and root-node/allowlist APIs and unrelated SoC support are retained. The older
fork rail wrapper is retained; its separate fuse allocation is reconciled into
the incoming checked flexible-array allocation. The typed-allocation-only
refactor from Kees Cook is inapplicable to the 6.18 API: supported zeroed,
size-checked allocations are retained. No newer SoC support was imported merely
to resolve context. The two style-only code corrections preserve token streams
and were recompiled on every native profile.

Forty-five explicitly selected CPU source test methods pass, without discovery
or skips. An audited compiler wrapper instruments 26 standalone executables
with ASan, UBSan and normal LeakSanitizer. Seven ctypes numerical-oracle builds
are deliberately unsanitized. The initial run was unsanitized and had fixture
compile/missing-input errors; its receipt is explicitly corrected and retained.
Synthetic debug/regmap/OF declarations and a missing historical negative-provider
source input were corrected without transforming production function bodies.
The first instrumented run found a synthetic successful NULL/zero memcpy call;
it now uses a valid dummy byte. That UBSan report is preserved locally and is
not counted as a clean behavioral control.

Focused tests execute the actual source: SAW map acquisition passes 47 cases and
407 checks; LTS regmap selection/callbacks including all three maps pass 20 cases
and 149 checks. A well-formed RPM model fails ten checks on the baseline and
passes all 18 afterward. Eight deliberately faulty variants are rejected
without sanitizer diagnostics. Core locks, scheduling, regulators, clocks and
MMIO are modeled; real firmware, SMP concurrency and physical RT lockdep remain
unqualified.

Twenty selected driver/core objects compile in each of ARM, ARM64 and ARM64 RT,
with the feature enabled and disabled: 120 objects. All configs verify EXPERT,
COMPILE_TEST off, actual RT state and nonpermissive CFI. W=1 produces no compiler
diagnostics. Twelve objects were recompiled after whitespace corrections; the
final effective controller verifies all current bytes/artifacts. Three additional
actual regmap core objects also compile. ARM32 RT is unsupported and is not
counted. The first native attempt requested the wrong PMIC Kconfig symbol and
failed its assertion before object compilation; the corrected actual symbol is
MFD_SPMI_PMIC. No failed attempt is reported as a passing profile.

All five CPU-related ordinary binding examples/lint/meta-schema checks pass.
The processed schema has 5,257 entries and is generated from the entire LTS
binding tree. Six schemas are selected for direct board validation: 102 checks
across 17 candidate DTBs are silent. Sixteen baseline and 17 candidate complete
family DTBs build, including ordinary and additional CPU Madai targets. Every
other one of the 15 board binaries remains byte-identical. The inherited DTC
warning count is 65 before and 68 after. Independent named-board rebuilds prove
that the additional CPU target repeats exactly the same three existing Madai
warnings, with no new distinct warning and identical rebuilt bytes. This does
not qualify full unfiltered board/schema acceptance.

The ordinary board includes the shared APC setup and complete eight-byte CPU
raw row. Its ordinary rates and absent calibrated consumer are preserved; the
separate CPU target explicitly links the calibrated domain and canonical rates.
This intermediate target does not satisfy final normal-target promotion or
physical acceptance. Boot MX guards, sleep voters, bounded SPM entry, full
system sleep and the remaining current fixes still require integration and
qualification before any package/image can be accepted for the phone.

Per-commit strict checkpatch reports zero errors, six warnings and eight checks.
All findings are retained: five file-add ownership reminders, the per-device
mutable regulator_ops warning, seven existing microvolt field spellings and
one udelay preference check. CPU helper/shared-API MAINTAINERS metadata is now
added. The operations copy is adjusted before publication; FTS2 runs in a
synchronous CPU0 IPI and requires a non-sleeping delay. These are documented
review contexts, not ignored check types. Human review/DCO remains pending.

Run the portable selected models in a normal LeakSanitizer-capable environment:

```sh
python3 run-models.py --source /path/to/qualified/linux --output /new/private/output
```

Requires Python 3 and clang-21. Modified source inputs are checked against the
receipt. Model temporary files and compiler mode logs stay in the new output.
The source-only packet contains the exact runner, fixtures and focused harnesses;
native and schema controllers are separate workspace-bound evidence. Native
compilation, schema validation and board builds are not repeated by this command.

Across the full LTS audit, 21 source changes are backported, seven existing
changes have focused equivalence qualification, and one newer allocation API
refactor is inapplicable. Another 118 current-source commits remain to audit.
Normal public-source APK/update/recovery, complete hardware and final boot,
motion-wake, standby/soak acceptance remain open. All seven original bringup
requirements are preserved; the original r2 fault is not physically proven fixed.

There was no phone, real fuse read/write, firmware/radio/audio execution, Wi-Fi
scan, Replimat3 interaction, network change, publication or maintainer contact.
No compiled objects/programs/DTBs, private keys, boot images, credentials or
firmware are included. Copied project tests/manifests retain the MIT license;
new/kernel-derived verification retains its GPL SPDX notices. Source patches
retain their original kernel, dual-binding and BSD board licenses.

Review log copies normalize workspace prefixes and trailing whitespace.
`sanitized-log-provenance.json` records exact original/transformed hashes.
Raw logs remain preserved locally. The packet replay passes all 45 selected
methods with the pinned modified-source checks and audited compiler modes.

The historical negative-provider `.diff` retains every original context byte.
The review repository already treats unified-patch marker whitespace as literal
data; its existing exact regression-fixture attribute is extended only to this
new copy. Production source/checkpatch checks are unchanged.

Native object checks ran before source commits. Final source hashes and all
selected artifacts are reverified, including the two formatting rebuilds.
A full link and release-specific kernel package remain unqualified.
