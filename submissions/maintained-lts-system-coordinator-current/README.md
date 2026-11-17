# Maintained-LTS MSM8226 system coordinator

This local, unpublished packet ports ten system-sleep changes onto maintained
Linux 6.18.63. Exact base/head and original authors/dates are recorded in
`source-current.json`. Eight ports retain their original added/removed source
lines. Two preserve LTS integration: register the extra DTB within its complete
board list, and include the generic Linux cacheflush wrapper. The wrapper's
compiled instruction and relocation streams match the original ARM include.
Original source notices and full original patches are retained; no human DCO
certification or agent sign-off was added.

The series adds the coordinator binding, retained A7PLL context, verified CPU
SAW readiness, owned CPR voltage/clock preparation, MPM image/wake handoff,
RPM transport lifetime and receive-IRQ handoff, secondary-core collapse and a
separate Madai suspend qualification target. Providers must be built in. The
feature is disabled by default and requires an explicit coordinator device.
Normal Madai and CPR targets remain unchanged. Final promotion into the normal
board and package path remains required; this alternate target is intermediate.

Synchronous voltage and clock preparation occurs in ordered device late/early
callbacks. RPM remains able to acknowledge device noirq requests. The platform
callback then freezes admission before masking receive delivery, prepares MPM,
and admits CPU/L2 entry only after all readiness checks and secondary-collapse
status agree. Wake disarms CPU/L2 before notifier exit, restores MPM and receive
delivery before device noirq requests, then restores voltage/clock state before
CPR resumes. Failing preparation owns its rollback. The independent sleep-only
MX floor remains 1337500 uV; this series does not authorize a lower floor.

## Host qualification

Thirteen explicitly selected source models pass 5,009 cases, plus four retained
PLL/mux/CPR/startup subruns. Eighty-five deliberately faulty variants are rejected
by intended assertions, with compiler crashes and sanitizer failures excluded.
The models execute the actual maintained function bodies and relevant tables:
CPU SPM/probe/idle/readiness, PLL context, CPR transaction/API, coordinator and
SMP/GIC entry, MPM, RPM transport/lifecycle, provider lifetime, clock probe and
existing channel/probe cleanup. Locks, IRQs, CCF, regulators, device services,
MMIO and firmware responses are synthetic. ASan, failfast UBSan and normal
LeakSanitizer remain enabled. No actual suspend, hardware, firmware, radio,
audio or device operation occurs.

The first run stopped at a synthetic declaration that exposed only the newer
allocation macro. Its LTS `kzalloc(size, GFP_KERNEL)` now uses the same faulted,
zeroed model allocation. The copied retained-test paths were moved together to
preserve imports. Production function bodies were not rewritten for models.
Earlier receipts are preserved and not counted as clean behavioral controls.

Seven supported native profiles compile 175 selected objects: ARM with CPU
support and coordinator enabled, ARM with CPU support enabled but coordinator
disabled, ARM with both disabled, and ARM64 normal/RT with CPU support enabled
and disabled. CPU idle, coordinator and Qualcomm ARM SMP code are ARM-only.
All profiles verify EXPERT, COMPILE_TEST off, actual RT state and nonpermissive
CFI. ARM32 RT is unsupported and is not counted as an RT build.

The first native controller's owning execution ended with status 143 after
four profiles completed. Their completed object/config receipts were retained,
and the remaining three profiles ran separately. The interrupted controller's
internal cleanup is not certified as a clean exit. A parallel Kbuild invocation
compiled one ARM hotplug target twice and reported an existing mcount section.
All three ARM hotplug objects were rebuilt serially, without diagnostics. The
recipe now separates that target. The generic-cacheflush correction rebuilt
the coordinator object and preserved every instruction and relocation. Final
source, configuration and object hashes were reverified. Original warning and
interruption evidence remains available locally.

A complete integration build links `vmlinux` and 447 raw unsigned modules, and
an incremental relink verifies the final include correction. Module verification
and the existing lockdown policy remain enabled. Automatic signing is disabled,
and only the already-reviewed public verification certificate is supplied. No
private key is accessed or generated. Modules are verified unsigned; nothing is
installed. The integration build retains its precommit development release
string, so this is not release-specific APK or normal signed-image acceptance.

Forty-four earlier CPU regression methods also pass without discovery or skips.
The compiler wrapper instruments 25 standalone programs with ASan, UBSan and
normal LeakSanitizer; seven ctypes numerical oracles are deliberately unsanitized.
Synthetic structures now declare the new suspend/context fields, with the
coordinator absent in legacy fixtures; the new branches are tested separately.
The lost-L-write fault targets its register rather than an operation index that
shifted after verified disable. The first fixture declaration/constant failures
are retained; no production function body was transformed.

The full W=1 build succeeds with 222 warning lines and zero errors. Of these,
219 occur in thirteen files byte-identical to official 6.18.63; three occur in
the RMI driver, unchanged from the pre-series Fx0 baseline. This is source-byte
provenance, not a fresh reproduction of all warnings on an upstream checkout.
The complete warning log remains; the full build is not diagnostic-free. The
final incremental relink emits no diagnostics. Dedicated selected-object checks
are clean after the serial rebuild.

Twenty-one actual Kconfig contracts pass. ARM system sleep forces CPU hotplug,
ARM suspend/idle forces CPU_PM, and the architecture/SPM selectors force SCM
built in; impossible requests are recorded as forced positives. To test a real
SPM-off/module prerequisite, the CPU-idle selector is also disabled. These are
not counted as unsupported native RT profiles. Earlier failed test expectations
and their configurations remain preserved.

All eighteen family DTBs build, with seventeen prior binaries identical. Nine
binding lint/meta/example gates and 180 selected DTB/schema checks pass silently.
Twelve malformed coordinator/MPM/RPM binding controls are rejected. Compiled
wiring verifies CPU SAW/ACC providers, RPM/MPM ownership, SRAM/mailbox dimensions,
GPIO/SPMI/MDSS/TSENS wake routes and public vendor GIC-hwirq to SPI translation.
The added target repeats three existing DTC diagnostics, taking warning lines
from 68 to 71; it adds no new distinct diagnostic.

Unfiltered full-schema validation remains failed. Normal, CPR and suspend Madai
targets produce the same three PM8226 torch-child errors (six nonempty diagnostic
lines). A separate torch binding/driver port remains pending. This is not claimed
to be inherited from upstream, and passing selected schemas does not erase it.
The earlier experimental 66-board global-schema failure also remains open.

Strict full-patch checkpatch reports zero errors, six new-file reminders and two
checks on established uV member spellings. No check types are ignored. The
sign-off check is explicitly disabled because human DCO has not been certified.
The strict style gate remains unpassed. Message-only revisions preserve source
trees; original full messages and initial style findings remain recorded.

## Replay and remaining scope

With Python and clang-21, using the exact maintained source:

```
python3 -B run-qualified.py --source /path/to/linux --output /private/new-output
```

The runner verifies packet hashes and 78 source inputs, then owns and reaps
sixteen explicit model/control jobs. It performs no discovery, native kernel
build, signing, schema check, device or network action. Native, Kconfig, DT and
full-build controllers are separate workspace-bound evidence. Private output
ELFs, modules, DTBs, boot data, credentials and firmware are excluded. Public
source fixtures and license notices remain intact. Log copies normalize only
workspace prefixes and trailing whitespace, with original/transformed hashes.

The maintained ledger now has 48 ports (40 exact, eight reconciled), seven
already-present equivalents with focused qualification and one allocation-only
API refactor inapplicable to LTS. Another 91 commits remain to audit. Normal
public-source APK/update/recovery, final normal-target promotion, all combined
hardware and reliability gates, DMP ABI/accuracy and final boot, motion-wake,
standby/false-wake/soak acceptance remain open. Physical CPU/APC/cache/SCM/RPM/MPM
collapse and wake behavior is unqualified. Independent SLIMbus hardware-stop,
PM rollback and endpoint/TID recovery gaps remain open. The original r2 fault
is not physically proven fixed. All seven original bringup requirements remain.

There was no phone access, Wi-Fi scan, Replimat3 interaction, network change,
public source download, publication or maintainer contact during this phase.
