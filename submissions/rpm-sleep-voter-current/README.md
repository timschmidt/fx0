# Independent PM8226 CPU sleep protection

The regulator class can persist a normal SLEEP enable change before a later
voltage write fails. The PM core aborts entry and skips ordinary resume for a
device whose callback failed. This is persistent sleep configuration, not a
generic regulator-core rollback defect. A CPU constraint needs independent
ownership so Pronto's normal policy cannot remove its protection.

The PM8226 provider now combines normal/AO voters for ACTIVE and normal/SO for
SLEEP. SO never writes ACTIVE. Both contexts retain their own covering boot
hold until a corresponding enabled covering voter is acknowledged. Releasing
SO rearms the SLEEP ceiling, including uncertain failure followed by a normal
write. Cached MAX voltage, enable OR, saturated summed load and the existing
no-SO path are preserved. This follows the vendor logical voter split; firmware
KVP atomicity and the actual physical context handoff are not qualified.

CPR optionally acquires the independent sleep supplier after calibration and
clock validation and retains 1337500 uV. Managed cleanup disables before put;
one uncertain disable is retried and two failures are explicitly fatal. Only
the experimental CPU board names SO. Existing DTs retain prior behavior.
ACTIVE scaling can fall while SLEEP remains covering. No 750000 uV CPU sleep
request is installed by this change, and the deep-suspend guard remains.

The new source-bound model passes 1785 cases / 175489 checks and composes 35
actual functions, five operation tables and one catalogue. It includes all six
registration orders, inherited APC values, normal/CPU coexistence, managed probe
unwind, missing suppliers, partial class-suspend failure without resume, real
regulator resume, allocation/send/NACK/stale/boundary/timeout outcomes, applied
and unapplied timeouts, saturated load and independent voltage scaling. OF,
devres, reference counts, locks, registration, clock/register and RPMsg services
are synthetic. Cleanup panic policy is modeled with a caught logical fatal
path; no kernel panic, phone, firmware or radio is executed.

The retained boot suite passes 317 / 57600, paired suite 3726 / 202962 and legacy
suite 6310 / 77934. Together these are 12138 unique positive cases / 513985
checks; the integrated variant is not double-counted. All 1280 ACTIVE trace
bytes match the prior trace. Seventeen new and forty-one retained negative
controls fail intended assertions with normal LSan and fail-fast ASan/UBSan;
compiler errors, crashes and sanitizer failures do not count. A separate six
case before check shows the pinned parent rejects the new SO topology. It is
not a claim that the full new-feature suite runs on an unsupported parent.

ARM and ARM64 native regulator/CPR builds compile 32 objects with ARCH_QCOM,
COMPILE_TEST off, LLVM21 W=1 and strict callback diagnostics: zero diagnostics.
The complete development kernel and 459 modules build and pass CMS, ELF32 ARM,
release and dependency checks. All twenty DTBs pass unfiltered full-schema
validation; nineteen are byte-identical, with sixty inherited DTC warnings and
none new. Twenty-two invalid binding controls are rejected; compiled supplier
phandles and CPU/CPR OPPs are verified. Prior artifacts and module paths remain.
These incremental builds do not establish clean maintained-LTS reproducibility,
normal package update/recovery or physical acceptance.

Run `python3 -B replay.py /path/to/fresh-private-output` using clang-21 and patch
outside ptrace so normal LSan works. Replay verifies every input, checks the
unsupported before topology, applies four source and five runtime patches with
no offset or fuzz, runs both source compositions and all retained suites, and
rejects all 58 controls without Git or network. Compiler temporary files stay
inside the output. Source-before explicitly combines pinned regulator and CPR
parents with correlated RPM/core prerequisites. Native/kernel/DTB rebuilding
requires the complete pinned trees listed in dependencies.json.

Checkpatch diagnostics are unsuppressed. The only advisory is FILE_PATH_CHANGES
for the new header (also in its runtime copy); the existing MAINTAINERS cpr*.h
entry already covers it. Human review and DCO remain pending. No agent
Signed-off-by is added, and existing attribution is retained. The draft is
unsent; all new heads stay local and unpublished.

Full CPU/L2/SPM/SCM/RPM/MPM entry/abort/reentry remains incomplete. Lowering the
CPU sleep floor still requires CPR quiescence, verified voltage/clock state,
L2 sequencing and cache handoff, IRQ-safe RPM freeze/drain/context ownership,
and MPM wake topology. Keep the deep-suspend guard. All seven original bringup
requirements remain open as recorded, including original r2 display/IOMMU fault
resolution, nonaudio hardware/interactions, DMP/wake/soak/cold/warm acceptance,
maintained-LTS public-source packaging/update/recovery and attributed review.
Independent SLIMbus hardware-stop, PM rollback and endpoint recovery remain.
No phone, firmware, audio, radio, WiFi scan, Replimat3 interaction or network
configuration change occurred. Existing-connection public downloads remain
authorized, but no downloads are needed for this checkpoint.
