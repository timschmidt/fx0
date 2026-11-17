# Maintained LTS IOMMU probe and removal lifetime

Two additional local repairs keep parent data and runtime PM available until
clients and context children are retired. Probe registers the LTS managed PM
cleanup before managed child population, including allocation-failure handling.
Removal unregisters clients, removes sysfs, explicitly releases managed children,
forces suspend and clears parent data. Automatic devres cleanup cannot remove the
already released children a second time. All other driver bytes are preserved.

The actual probe tail, parent/context remove and selected LTS PM/OF/driver cleanup
functions are extracted. Pre-tail allocation/resource getters, the devres list
container, device creation, client release, PM transitions and hardware are service
models. The real LTS reverse-release order and driver-data clearing order are
checked against their source. An unavailable parent read is intercepted before
NULL/UAF dereference and counted as a contract failure. The full kernel driver
core, locks, concurrent remove/IRQs and actual hardware are not executed; successful
force-suspend is modeled. This is scoped lifetime evidence, not physical acceptance.

The baseline has 24 wrong cases out of 30. The repaired source has zero out of 36,
covering the same 30 and six new PM cleanup-action allocation failures. Three
deliberately regressed orderings fail 15, nine and nine cases respectively.
Normal LeakSanitizer and fail-fast ASan/UBSan stay enabled. Native ARM, ARM64 and
ARM64 RT driver objects compile without diagnostics using nonpermissive CFI, with
ELF source checksums matching current source. Both patches pass strict checkpatch
without ignored types; human DCO/security/owner review is still pending.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is verified before re-extraction, and all five generated fixtures
must match the qualified bytes. No Git, network, phone or actual device is used.
Native receipts are archived evidence, not replayed native builds.

These repairs remain separate from the original 147-origin inventory: 57 ports,
41 scoped existing equivalents, one inapplicable API-only refactor and 48 audits
remaining. Four additional local IOMMU repairs now exist. The earlier domain/
resume and context-probe function bytes are unchanged. Board/schema inputs retain
their prior 19-board full-schema qualification. Current complete kernel linking,
normal trusted public-source APK/update/recovery, all seven bringup requirements
and final-image physical matrices remain open; the r2 fault is physically unproven.

This review is local and unpublished. No private key/boot/device data, phone action,
Wi-Fi scan, Replimat3 interaction, network change or maintainer contact is included.
