# NXP NCI reference-clock review drafts

These two unsigned patches add an optional reference clock to the binding and
I2C transport. They target the advertised NFC `for-next` base
`fd73f4a6659897191fa0d40695fe370925dd3780`; the
[source branch](https://github.com/timschmidt/fx0-linux/tree/submit/nxp-nci-ref-clock-v1)
is published at `8616767b2b9e01846b1a61af2055ab7965a2f245`.
The removal locking and receive-lifetime fixes remain a
[separate series](../nxp-nci-remove/README.md).

The binding accepts one clock named `ref`, requires `clocks` and `clock-names`
together, and preserves clockless boards. The driver propagates provider errors
before claiming GPIOs, prepares the clock before raising enable, retains one vote
across active modes, and releases it after entering cold mode. A failed open
keeps the software mode cold so it can retry. Existing DT/ACPI trigger handling,
firmware GPIO optionality and failed-IRQ unwind remain intact.

## Checks

[Actual C checks](host-controls.json) pass nine mode/open/close/probe cases under
ASan and UBSan with leak detection enabled. Five independent modified-body
controls compile and fail at runtime for ignored enable failure, duplicate votes,
missing clock release, ignored open failure and ignored provider defer.
[Strict style checking](style-checks.json) has zero findings on both patches,
with only the DCO sign-off check disabled. Both
[exported prefix trees replay exactly](prefix-replay.json).

The [binding checks](binding-checks.json) pass document validation and assemble
schemas from the complete receiving-tree binding set in bounded RAM. All five
compiled-DTB tests pass, including missing/wrong/duplicate clock controls and
legacy boards. These tests use the previously compiled development Madai DTB
and its r50 baseline; they do not build a receiving-tree Madai board. That board
file is absent from this tree and needs a broader board-support series.

[ARM object builds](ARM-object-checks.json) pass on the unmodified base and the
clock tip: six actual objects, `W=1`, zero compiler diagnostics, unchanged
[normalized configuration](../../configs/linux-7.3-rc3-nxp-nci-remove.armv7),
KCFI and full zlib-compressed DWARF5. Complete pinned Git archives are extracted
into bounded 4 GiB RAM scratch; each build verifies all 95,942 inventoried source
paths against Git blobs and modes, excluding 93 private-named/PEM source paths.
The binding-only prefix has byte-identical compiler inputs to the base and uses
that build proof; its schema is checked separately. The
[ELF inspection](object-inspection.json) verifies 18 actual callback type words,
matching across both cohorts, and actual compressed DWARF5 sections.

## Full normal kernel and module qualification

[Complete base and clock builds](full-build-comparison.json) now pass normal ARM
`zImage modules` plus full module installation staging in bounded RAM. Each
verifies all 457 signed modules, complete dependencies, actual embedded kernel
certificate, nonpermissive KCFI and compressed DWARF5. The base checks 24,811
imported CRCs; the clock tip checks 24,817. The six extra I2C imports are existing
clock/error APIs. Exported CRCs remain identical, unlike the separate removal
series whose transport operations layout changes.

Both full builds contain the same 233 warning lines, with none added or removed.
Actual wrong-build certificate pairs reject; correct pairs pass. See the
[base](full-build-base.json), [clock](full-build-clock.json),
[signatures](full-module-signatures.json), [ABI](full-module-ABI.json) and
[dependencies](full-module-dependencies.json) receipts. These remain standalone
host builds, without distro packaging or a receiving-tree Madai boot.

[Signed-payload comparison](module-payload-observation.json) finds 454 unchanged
module payloads; the two NFC modules and MSM differ. A
[generator probe](msm-generator-observation.json) reproduces hash-seed-dependent
MSM header ordering with identical C tokens/macros. The original MSM payloads
were not exported, so exact section attribution remains unproven. Byte
reproducibility is not claimed; matching-cohort signature/ABI qualification passes.

## Remaining qualification

The earlier object artifacts are not loadable modules; the later full builds
qualify the normal matching module cohorts. Broader configurations, GCC, physical
clock/open/firmware/RF/PM and reliability remain open. Earlier 6.18 cold-start results do not qualify this receiving-tree
feature. Separate removal-series `allmodconfig` attempts under GCC and Clang
failed in unchanged upstream code; their receipts do not qualify this branch.

The pinned tree requires `Assisted-by: LLM`; both drafts retain it. No AI-added
DCO certification is present. OpenAI Codex assisted adaptation, analysis, tests
and documentation. Human review and certification are required before any
human-controlled upstream submission. No upstream email or PR was sent.
