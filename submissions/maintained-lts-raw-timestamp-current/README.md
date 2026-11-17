# Maintained LTS raw FIFO timestamp dependency sequence

Integrate five upstream timestamp changes as a complete sequence: watermark
batch alignment, a longer measurement interval, an estimated-period cap,
monotonic transitions/reset history, and suppressing estimation during a
pending rate change. Two comment/type prerequisites remain separate from
runtime repairs. Only the timestamp module portion of the broader spelling
cleanup is included. Preserve original authors, dates, notices and genuine
upstream trailers; local Fixes references point at the actual backports.
The downloaded official endpoint is 0d695709ed380f1bc9303a91f57525d33766a07e.
Current source matches it except documentation for the new init field and
a redundant blank line removed. The original 147-origin inventory is unchanged.

The complete pure module and inline API pass 504 synthetic cases and 83780
checks, versus 344 failed checks in the baseline. Seven source-bound behavioral
regressions fail as intended. The arithmetic shim preserves Linux signed-division
argument types; no kernel service, real clock or device executes. MPU's 1 kHz
and ICM's 8 kHz internal clock profiles are bound to actual source constants.
All direct consumers are enumerated and stay byte-identical. Full MPU/ICM FIFO
callbacks, their latency, concurrency and physical data accuracy are not replayed.
The separate DMP and quaternion timestamp ABI are unchanged.

A separate limitation is deliberately retained: the upstream estimator cannot
fit its minimum 980000 ns period into a 500000 ns IRQ budget. Both the exact
downloaded official source and the candidate produce a timestamp 480000 ns later
than that IRQ. This reproducer is evidence of an open timing constraint, not a
physical observation or a claim of complete timestamp accuracy. Final IRQ latency,
buffering, frequency transitions and sensor timing acceptance remain open.

Ninety native objects across ARM, ARM64 and ARM64 RT cover generic IIO, the
timestamp helper, all MPU components and both ICM transports. W=1 has no new
diagnostics, CFI stays nonpermissive, built-in/module and ACPI-off/on paths pass,
and ELF checksums bind the exact C source. ARM32 RT is unsupported and excluded.
All seven patches pass strict checkpatch with zero errors, warnings or checks,
without ignored types. No DTS/schema bytes change; the existing full nineteen-
board schema proof is reused without rebuilding. Formatter UML and previous
DMP/PHY qualification are retained evidence, not new runs in this phase.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is verified before execution. Ten portable tasks regenerate ten
pinned C fixture units for baseline, candidate, official source and seven controls.
Normal LSan and fail-fast ASan/UBSan remain enabled, with strict host diagnostics.
Native objects and full-schema evidence are not rebuilt by this portable replay.

The original inventory remains 70 ports (45 exact, 25 reconciled), 49 scoped
existing equivalents, three newer API-only changes inapplicable and 25 audits
pending. Additional changes now comprise four local IOMMU repairs, seven upstream
runtime changes and two upstream comment/type prerequisites. Complete current
linking, the paired reader/kernel package update, trusted reproducible normal
APK/update/recovery, original r2 fault and all seven original requirements remain
open. Human DCO and owner/security review are pending. Everything is local and
unpublished. No phone/SSH, firmware/radio/audio/LED/NFC execution, Wi-Fi scan,
Replimat3 interaction, network change, private boot/signing/device data or
maintainer contact is included. Twelve read-only official public GitHub source,
metadata and history fetches used the existing connection during this phase.
