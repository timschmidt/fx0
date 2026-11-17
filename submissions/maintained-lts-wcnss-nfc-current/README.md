# Maintained LTS WCNSS equivalence and NFC lifecycle/clock

Five NFC ports unregister outside the mode mutex, keep receive available through
the closing reset, drain the threaded IRQ before freeing NCI state, balance an
optional reference clock across modes, and describe the production PN547 on its
100 kHz bus. Preserve original authors, dates, source notices and disclosures.
Four ports retain exact added/removed source lines; the clock port carries the
feature while omitting newer-base cleanup already absent from LTS. The separate
typed-allocation conversion is inapplicable to the older API and is not imported.

Actual driver/NCI close/reset/response/receive callbacks reproduce nine wrong
baseline cases and none of ten after repair. Nine optional-clock/probe cases,
eight WCNSS selection cases with sixteen injected resource failures, and seven
RF-classification cases pass: 50 positive cases. Eleven regression variants fail
the intended contracts. WCNSS already has the memory/signaling descriptions, RF
match/data, PD regulator selector and WCN3660A wireless classification; the source
and modeled OF/classification checks preserve its distinction from WCN3680.

Sixty native ARM, ARM64 and ARM64 RT objects compile without W=1 diagnostics or
permissive CFI, including built-in/module and ACPI-off/on paths. ELF line tables
bind current C bytes. All nineteen family DTBs validate silently against the full
current schema, with eight focused NFC binding cases. Sixteen DTBs are identical;
the normal, CPR and suspend Madai variants add only NFC, its three pin states and
bus/pin configuration after resolving phandle renumbering. The seventy-five prior
DTC warnings match the baseline, with source positions normalized; no new warning
is introduced. Initial verifier omissions of the inherited CPR variant and mixed
phandle/phandle-array typing are retained and corrected without source changes or
restarting the completed builds. All five kernel patches pass strict checks with
no ignored types; human DCO and owner/security review remain pending.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is verified before extraction/execution. Seven source-only suites
regenerate all seventeen qualified fixture units, including fault controls.
Normal LSan and fail-fast ASan/UBSan stay enabled. Host-only unused-parameter,
signed-comparison and unused-fixture-helper diagnostics are scoped; native W=1
builds have none. Native/schema receipts and built public-source DTBs are archived
evidence, not rebuilt by the model replay. OF, locks, queues, bus, IRQ scheduling,
clocks and regulator services are modeled. Concurrent firmware, complete driver
core, physical NFC/radio/image behavior and the original r2 fault remain unproven.

The complete 147-origin inventory is preserved: 68 ports (45 exact, 23 reconciled),
48 scoped existing equivalents, three newer API-only changes inapplicable and
28 audits pending. Four additional local IOMMU repairs remain separate. All seven
original bringup requirements, current complete linking, trusted reproducible
normal APK/update/recovery and final hardware matrices remain open. Source and
review are local/unpublished. No private signing/device data, Wi-Fi scan, Replimat3
interaction, network change, phone action or maintainer contact is included.
