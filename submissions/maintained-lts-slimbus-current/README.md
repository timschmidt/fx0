# Maintained LTS SLIMbus/BAM source qualification

Eighteen reviewed source changes now preserve startup readiness and parent,
child, IRQ, TX, response and DMA software ownership on maintained Linux 6.18.
Fifteen ports carry exact added/removed lines; three reconcile older APIs.
The child-ownership port also balances the explicit LTS OF iteration reference.
Existing LTS channel-removal/reconfigure and socket interfaces are retained.

The series passes 3,221 exact-source synthetic cases and 117 independent fault
controls. Targeted intermediate baselines fail 4,071 assertions. The retained
LTS stream caller contributes 216 cases and three controls, including padded
remove/reconfigure packets, TID allocation, PM and DMA admission/error paths.
The TX ownership replay preserves all 41,147 packet-trace bytes. All 108 native
ARM, ARM64 and ARM64 RT component objects compile with W=1 and nonpermissive
CFI without diagnostics; ELF source checksums bind them to the candidate.
All eighteen port patches pass strict checkpatch with zero findings.

Run `python3 -B replay.py /absolute/new/output` with Python and clang-21.
The manifest is verified before any model compiles. The default replays all
six baseline/candidate models and the stream caller with its three controls,
checking exact generated source and receipts. Add `--all-controls` to rerun
all 117 independent controls. Normal LSan and fail-fast ASan/UBSan are required.
Some sandbox tracing layers cannot run LSan; use an ordinary isolated host
process without tracing. No network or private signing material is needed.

Kernel workqueues, waits, devices, IDR, PM, packets and DMA are synthetic here.
Native objects are compiled, never loaded. This does not establish physical
DMA stop, registered-QMI-endpoint recovery, audio, firmware lifetime, full
driver concurrency, full current-kernel link or final-image acceptance.
No phone, network changes, scans, firmware or audio operations ran.

This completes classification of the frozen 147-origin inventory: 90 ports
(62 exact, 28 reconciled), 54 scoped equivalents and three newer-API-only
changes inapplicable. Additional runtime/prerequisite/test changes remain
separate. All seven bringup requirements stay open. Final linked kernel,
trusted normal APK/update/recovery and hardware acceptance remain required.

Original authors, dates, source notices and assistance credits are retained.
The final original patch keeps its original AI co-author metadata; the LTS
changelog retains that credit as prose to meet kernel trailer conventions.
Codex prepared the adaptations/models. Human DCO, owner/security and subsystem
review remain pending. This branch and packet are local and unpublished.
