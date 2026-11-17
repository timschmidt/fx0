# Maintained LTS charging, USB budget and VADC audit

The maintained 6.18.63 tree already carries eight original source changes.
Two local commits restore only the proposed charging-policy maintainer entry
and its header coverage, retaining original authors and dates. Runtime source,
normal/CPU/suspend board data and all existing LTS APIs remain unchanged.

Seven focused host suites pass: 8,846 control/policy cases, 27 lifetime cases,
21,496 vendor-model comparisons, 59 USB actuator cases, 59 gadget budget cases
and 84 VADC scaling cases. Three deliberately faulty lifetime variants fail
their intended assertions. All 94 channel records are checked; the other 92
records and both battery raw interfaces are preserved. Normal LeakSanitizer
and fail-fast ASan/UBSan are enabled. These are extracted callbacks with mocked
hardware, work queues and driver-core operations, not hardware acceptance.

Twenty native objects compile without diagnostics in ARM, ARM64, ARM64 RT and
legacy modular-charger profiles, with nonpermissive CFI. ELF source checksums
match every current source body. Managed policy requires a built-in charger
and IIO; the initial invalid modular-managed configuration is preserved locally
and excluded. Three ordinary binding gates and 27 schema contract cases pass.
Runtime firmware identity/handoff in schema tests is simulated. The prior
19-board full-schema result remains applicable to unchanged DTS/schema inputs.

Reverse application of several historical patches fails because successor
changes alter their context. Exact feature/source comparisons, not those
reverse checks, establish equivalence. Initial checkpatch could not resolve
experimental origin IDs; with their object store exposed read-only both patches
pass strict checks without ignored warning types. Human owner review and DCO
remain pending. This packet is local and unpublished.

Run `python3 -B replay.py --output /absolute/new/private/output` for the selected
portable host suites. It verifies the entire manifest before running; no Git
repository, network, phone, radio, charger or USB device is accessed. Native
build logs and ELF receipts are evidence, not portable compiler reproduction.

Combined live provider integration, physical current/thermal/source-loss and
sensor accuracy, USB timing, complete maintained link, normal signed APK and
all seven original bringup requirements remain open. The original r2 fault has
not been proven fixed on the phone. No Wi-Fi scans, Replimat3 interaction,
network changes, phone action, publication or maintainer contact occurred.

Six archived source/diagnostic paths retain existing whitespace byte for byte.
The review attributes exempt those exact paths from Git whitespace checks;
new metadata patches pass strict checkpatch with origin objects available.
