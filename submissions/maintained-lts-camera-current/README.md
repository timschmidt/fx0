# Maintained LTS camera sensors and CAMSS

Six scoped reconciliations restore proposed sensor maintainer entries and stream
guards, validate contiguous mapped DMA coverage, and validate RDI geometry before
buffer ownership while propagating the VFE4.1 height limit. The LTS sensor API,
register/power data, alignment, board data and binding bytes stay intact. Proposed
maintainer ownership and human DCO remain pending. Author/date and source notices
are retained, including the original Timothy Schmidt and Claude Opus 5.5 credits;
Codex prepared the current LTS reconciliation and qualification.

The sensor models reproduce nine failures across 378 cases, DMA five across 46,
and partial geometry 241 across 6433. Repaired code has zero failures. Existing
saved-completion code passes 84 cases. Twenty-two deliberately regressed variants
fail their contracts. Normal LSan and fail-fast ASan/UBSan remain enabled. Selected
host-only unused-parameter and unchanged signed-comparison diagnostics are scoped;
all 78 native ARM, ARM64 and ARM64 RT objects compile without W=1 diagnostics or
permissive CFI, and ELF line-table source checksums match. Three source-only partial
CAMSS links are additional evidence, not final Kbuild module/kernel links.

The newer PHY timing helper fix is inapplicable: this LTS CAMSS has no caller.
An exploratory select and its 81-object/Kconfig results are excluded from current
qualification; the select was removed before source acceptance. Four actual full
LTS Kconfig profiles retain CAMSS y/m on ARM/ARM64 with that helper absent. Three
original camera changes are scoped existing equivalents: ARM IOMMU backend,
MSM8226 resources/clock match, and saved-completion dispatch. Newer bulk regulator
representation and unrelated RT clock/platform changes are not imported.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is checked before extraction/execution. Twenty-one individual model
runs and one completion generator reproduce 33 qualified fixture units from the
included source, baseline and fault controls. Native/Kconfig receipts are archived
evidence and are not rebuilt by replay. No Git, network, phone or real device is
used. Core services, locks, MMIO, bus/power services and IOVA allocation are modeled;
physical image integrity, V4L2 ioctl/compliance and the full driver core are open.

Current source has 63 original ports (41 exact, 22 reconciled), 44 scoped existing
equivalents, two newer API-only changes inapplicable and 38 original audits pending.
Four additional local IOMMU repairs remain separate. The prior maintained 19-board
full-schema evidence is reused for unchanged DTS/schema inputs, without a new DT
build. Current full kernel link, normal public-source reproducible APK/trusted
update/recovery, all seven bringup requirements and final physical matrices remain
open. The original r2 fault is physically unproven. This packet remains local and
unpublished, without private signing/device data, Wi-Fi scanning, Replimat3/network
interaction, phone changes or maintainer contact.
