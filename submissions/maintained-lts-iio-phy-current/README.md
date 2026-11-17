# Maintained LTS IIO, PHY and deterministic header qualification

The maintained LTS buffer helper placed a quaternion timestamp at byte 24;
the documented 32-byte scan requires byte 16. Two attributed upstream changes
cache and use the pre-padding offset while retaining the LTS byte-count API.
The disabled-timestamp path initializes the cache; the HID rotation driver's
existing dual-slot compatibility remains byte-identical. The actual scan
descriptors, compute/cache/push fragments reproduce one wrong baseline case
and none of fourteen candidate cases. Full buffer registration is not modeled.

Two original feature ports reconcile counted PHY storage and missing DMP ABI,
maintainer coverage, six precise formatter vectors and opaque scan storage.
LTS already handles offset-zero sequences and malformed lengths: both baseline
and candidate pass, with the baseline's extra separate-allocation OOM case.
Three SoC tuning sequences are unchanged. Existing signed IADC, MPU offset/PM,
raw-channel configuration, DMP/SMD guards and tiny formatter are preserved.
The ABI's original KernelVersion proposal metadata is retained for attribution.
The normal package must update its reader together with the new kernel; the
review example's decoder alone runs against nine synthetic records. The installed
r1 reader and the phone remain untouched. Raw FIFO timestamp transition/estimation
dependencies require a separate audit before final combined-kernel acceptance.

Numeric, offset/PM, scan, PHY and decoder checks pass 19529 finite cases.
Five fresh DMP models pass 876382 assertions. The loader source is byte-bound
to its prior accepted private proof; no fresh loader run or private firmware
read is claimed. Sixteen behavioral regressions fail as intended. The actual
LTS header generator gives one header for five seeds and four usage arrays;
an unsorted control diverges, giving seventeen regression variants overall.
Sixty-nine native ARM, ARM64 and ARM64 RT objects pass W=1 and nonpermissive
CFI with ELF source checksums verified, built-in/module and ACPI-off/on paths.
Three formatter objects were rebuilt after a blank-line cleanup; the other
sixty-six remain unchanged. Seven real UML formatter KUnit tests pass again.
The four source patches pass strict checkpatch with zero errors/warnings/checks
and no ignored types; genuine upstream trailers are provenance, not new DCO
for the adaptation. Original authors, dates, notices and assistance disclosures
are retained, including the underlying eight-commit IIO feature series.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is verified before execution. Twenty-nine portable tasks regenerate
twenty-seven pinned C fixture units, all behavioral controls, the actual header
generator and the pure decoder. Normal LSan and fail-fast ASan/UBSan remain on.
The replay does not rebuild native objects or UML, rerun the private loader,
or execute capture/main/restore from the public example. Resource, regmap, PM,
IRQ, scheduling, allocation, resolver and sink services are synthetic; integer
sqrt is modeled. Host shim annotations do not test counted-by instrumentation.
No full driver-core, concurrency, real firmware, sensor accuracy, motion wake,
USB electrical or physical behavior is qualified. No DTS/schema bytes change;
the preceding full nineteen-board schema proof is reused without rebuilding.

The 147-origin inventory now has 70 ports (45 exact, 25 reconciled), 49 scoped
existing equivalents, three newer API-only changes inapplicable and 25 audits
pending. Four additional local IOMMU repairs and these two upstream backports
remain separate. Full current linking, trusted reproducible normal APK/update/
recovery, original r2 fault and all seven original requirements remain open.
Human DCO and owner/security review are pending. Everything remains local and
unpublished: no phone/SSH, Wi-Fi scan, Replimat3 interaction, network change,
maintainer contact or private boot/signing/device data is included. Four read-only
public GitHub source/metadata fetches used the existing connection this phase.
