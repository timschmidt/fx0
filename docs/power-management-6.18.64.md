# Power management on the maintained 6.18.64 source

The installed phone retains `6.18.64-fx0-lts-alpine`. Its ordinary four-rate
CPU frequency policy and per-core WFI/power-collapse idle states already work.
The new qualification profile builds the existing CPU/CPR, MPM, system entry,
ADC and guarded charging paths into a distinct `6.18.64-fx0-power-alpine`
kernel. This preparation does not establish closed-loop voltage, full-system
sleep or managed charging acceptance.

The [manifest](../manifests/power-management-6.18.64.json) pins the source,
recipe, signed kernel and matching reader. Two empty offline abuild/Kbuild
workspaces produce identical signed packages, repository indexes and all 567
compared linked outputs. All 91,291 source paths match the pinned Git tree in
each build. The 465 signed modules pass signature, vermagic, imported CRC and
dependency checks. CFI, full DWARF5, runtime trust, exact DTBs and the normal
community configuration check pass. Altered payload/signature/ABI controls
are rejected. Existing signers are consumed in place by normal signing tools
on read-only mounts; audit tools do not read, copy or hash their private bodies.

A workstation tool-server restart loses the original two outer build handles.
The exact containers survive; independent `podman wait` monitors capture actual
zero exit codes. Original controller records are retained, and their missing
outer completion is not invented. Separate completion evidence records the
container results. The matching reader also reproduces in two fresh builds.

## Installed software-clock ordering correction

Both clock packages are now `0.3.0-r1`, from the already-reviewed clock recipe.
The boot unit wants `local-fs-pre.target` and precedes that target and root fsck.
Its clock scripts retain their original bodies. The raw RTC's epoch-like value
is expected: the saved software offset restores wall time; it was not treated
as evidence that the hardware counter needed resetting.

The live preflight checks all 1,930 guarded paths, signed local inputs and the
exact two-package solver proposal. After the real upgrade, APK reorders the
unchanged complete world selection. A strict byte guard rejects acceptance;
automatic rollback stops at the same guard. Both failure records are retained.
An additional native read-only preflight verifies the exact captured permutation,
every other guarded path and all package records before a narrow continuation
restores the original world bytes. It then normalizes owned labels and verifies
the candidate without rerunning APK, clock scripts or package hooks.

PID1's real graph is reconciled only after unit completion and empty-cgroup
proof. Reload and enqueue-marked each complete once with no pending markers.
All 774 unselected complete package records, boot files, saved offset, original
clock invocation and core process IDs remain unchanged during installation.
The corrected clock unit subsequently executes successfully on an installed
boot. Cold retention, unplugged wake and absolute RTC accuracy remain separate.

## CPU target result and isolation

The first CPU/CPR target transfers with exact readback and receives one RAM
BOOT. It returns before candidate userspace is reachable. Retained progress
ends at 2.035301 seconds during L3 regulator constraint initialization, with
no panic report in that console. The reset cause is not established. Installed
boot files and the complete package database match after return, with taint
zero and signature enforcement enabled. All owned transfer/observer children
are terminal and reaped; this is a failed trial.

That first preparation also omits an explicit userspace default and governor
preload, allowing later schedutil selection. This is a distinct defect, not
an established explanation for the earlier pre-userspace reset. A controlled replacement is prepared to preload the exact signed userspace
governor before any cpufreq-dt load, reject an already-loaded driver, pin the
default and retain both automatic return paths. Its original host checks pass,
but the stronger archive-layout guard described below later rejects it.

The first controlled ordinary-board image fails in the prefix because its
appended governor file lacks the `/usr/libexec` parent directory. After arming
the helper, the prefix requests a clean reboot. This result does not demonstrate
a kernel configuration failure. Earlier image audits created parent directories
while constructing a syntax-test root and therefore missed the unpacking defect.
A [portable append-parent guard](../diagnostics/kernel-maintenance/initramfs_append.py)
and [six tests](../tests/test_initramfs_append_parents.py) now reject that actual failed
archive and accept the corrected image, which uses the existing `/usr/bin`.
The earlier unbooted controlled CPU image shares this preparation defect and
is rejected by the added guard; its initial host pass is not sufficient.

The corrected ordinary-board control reaches running systemd, Sway, gestures
and all four CPUs with userspace, the original four rates and an observed
787.2 MHz rate. All 479 candidate module files match on tmpfs, with enforced
signatures and taint zero. USB remains online with a 500 mA limit and charging
inhibited. VADC reports about 4.33 V for the battery; IADC returns computed
current samples. Neither sensor accuracy/sign nor the separate BMS discrepancy
is qualified. The six-minute automatic return completes, and an independent
audit checks all 482 installed module files on ext4, boot/package/world/repository
hashes, schedutil, services and desktop processes. The candidate journal contains
no critical kernel fault. No physical display/touch acceptance is claimed.

The separate `6.18.64-fx0-power-trace-alpine` diagnostic adds requested L3
vote/acknowledgement logging without changing vote construction, ordering or
error propagation. Its first build is interrupted externally, then the exact
fingerprinted tree completes through the real abuild build/package/index phases.
This is one interrupted-and-resumed diagnostic build, with a verified zero
container exit; it is not a clean reproducibility pair. Source, configuration,
all 465 signed modules, imported CRCs, trust, CFI, DWARF5 and packaged DTBs pass
the full host audit. The actual core/boot and sleep-voter models pass 317 and
1,785 cases under ASan/UBSan/LSan. Earlier failures remain recorded.

The CPU-enabled trace trial returns before userspace and retains no paired-vote
markers. Disabling only the CPR provider retains the original boot-APC guard
and L3 constraints, but still fails early: its final recorded event is a SLEEP
request for 1,337,500 microvolts with no acknowledgement recorded. A further
control changes only the active/sleep voter maximum properties to 1,287,500
microvolts. CPR remains disabled. It reaches running systemd, Sway and gestures;
all 479 module files match on tmpfs, signatures are enforced and taint is zero.
All ten recorded L3 requests receive successful acknowledgements. The automatic
return and independent audit verify all 482 installed module files, protected
boot/package/world/repository hashes, schedutil, services and desktop processes.

This establishes a voltage-dependent difference on this phone; it does not
prove the electrical reset mechanism or a universal PM8226 voltage limit.
The cap control deliberately has no CPR CPU frequency policy. A separate
per-unit diagnostic retains that cap and changes the CPR sleep/runtime guard
from the global maximum to the complete validated voltage-plan ceiling.
Uncovered calibration or boot-voltage plans still fail closed. Seven planner
tests pass, including all synthetic bin/rule combinations against the cap.
A further model runs the actual provider/core/sleep callbacks through 528 cases
and 89,136 checks: all six voter orders, every synthetic inherited APC point,
above-cap rejection before any RPM request and managed sleep-vote release.
ASan/UBSan/LSan pass. An unused-fixture compile failure is retained separately.
One clean signed diagnostic build completes with independently verified exit
zero and passes the full source/module/signature/configuration/trust audit.
Sixty-three DTBs are unchanged; the CPR DTB and its including suspend DTB each
differ only in the two cap properties. The first comparison omitted that
include effect and is retained as a failed audit, followed by the complete
semantic check. The prepared RAM image selects the CPR target only.
The capped CPR image subsequently reaches userspace with a registered userspace
CPU policy and seven advertised rates, initially at 300 MHz. All 479 module
files match, signatures remain enforced and taint is zero. The first automatic
installed return passes the complete module/hash/service audit. A prepared CPU
exercise declines to start near that return deadline, before any rate request.

An unchanged-image repeat triggers the exercise promptly on readiness. Clock
readbacks match 300, 384 and 600 MHz, then a further twenty cycles pass all sixty
rate requests/readbacks. Both PID1 services exit zero with empty cgroups and
restore 300 MHz. At initial 300 MHz the driver correctly reports its corner as
not yet applied and preserves the 1.15 V APC target. After the first transition,
it reports the applied plan, feedback enabled and a 1.08 V APC target; one CPR
interrupt is observed. That is a programmed target and armed feedback path,
not an analogue voltage measurement or proven adaptive feedback response.
Reported CPU temperatures stay about 40–44 degrees C. Higher advertised rates,
long load/standby reliability and physical UI checks remain unqualified.
The repeat returns automatically to the installed kernel. Its independent final
audit verifies all 482 installed module files on ext4, protected boot/package/
world/repository hashes, schedutil, clock startup, services and desktop processes.
The saved candidate kernel journal contains no critical fault and records 57 L3
requests with 57 successful acknowledgements, all at or below the cap. A further
live audit was attempted as automatic return began and produced no receipt; the
completed first candidate audit and final installed/journal audit are kept as
distinct checks. The diagnostic source is published on
[`diagnostic/fx0-power-cap-6.18.64-01`](https://github.com/timschmidt/fx0-linux/tree/diagnostic/fx0-power-cap-6.18.64-01).
The installed phone retains its accepted kernel and guarded charging policy.

## RTC alarms while awake

A bounded PID1 service tests twenty relative RTC alarms while the phone stays
awake. Every cycle delivers one IRQ, for twenty new interrupts total. The RTC
advances 80 seconds over 79.952 monotonic seconds; this short observation does
not establish absolute accuracy. The service exits successfully with an empty
cgroup, clears its alarm and leaves the saved software offset unchanged. It has
no suspend or hardware-clock-setting capability. This qualifies the awake alarm
path only; it does not establish alarm wake from system sleep or cold retention.

### RTC wake from s2idle

Both RAM trials reused the installed signed kernel and ordinary Madai DTB.
The images disabled WLAN and checked the installed module hashes before
userspace. The suspend gate allowed the two pending time-sync jobs after
verifying that both return paths were active and no other startup jobs or
failed units remained.

The installed kernel omits `pm_wakeup_irq` from sysfs. The probe therefore
uses a tracefs instance to record the kernel wake IRQ inside `machine_suspend`.
The first trial stopped before arming an alarm because Python's append mode
tried to seek in `kprobe_events`. The direct-write correction passed the
workstation checks and the next handset trial. [RTC s2idle probe](../diagnostics/rtc-s2idle/probe.py)
[Linux kernel event tracing](https://docs.kernel.org/6.18/trace/kprobetrace.html)

The corrected trial completed one s2idle cycle without a suspend failure.
The inactive-clock difference was 13.967 seconds. The kernel recorded IRQ 33
as the only wake IRQ in the interval, and the PM8xxx RTC alarm counter
increased by one. The probe cleared its alarm and exited successfully.
After automatic return, an independent USB audit verified all seven protected
hashes and recovered the candidate's suspend-entry, suspend-exit and service
completion records from the journal. [Handset evidence](../evidence/2026-11-18-rtc-s2idle-handset.json)
[Workstation checks](../evidence/2026-11-18-rtc-s2idle-workstation.json)

A repeat on the signed kernel with WLAN disabled completed eight consecutive
RTC-triggered cycles. Inactive-clock differences ranged from 13.691 to 14.631
seconds. Each trace identified RTC IRQ 33 as the only wake IRQ, the alarm
counter increased by one, and the alarm cleared. The kernel logged eight
suspend entries and eight exits. After the last cycle, an independent check
verified trace cleanup, an empty test cgroup, all four CPUs online, and the
desktop and gesture processes running. Deep suspend and battery standby
remain open. [Eight-cycle handset evidence](../evidence/2026-11-18-rtc-s2idle-series.json)

### Capped deep-suspend boot

The signed capped kernel booted the Madai suspend DTB with WLAN disabled.
The MSM8226 suspend coordinator and MPM driver both bound. The live tree
routed the PMIC interrupt through MPM pin 62. Linux exposed `[s2idle] deep`
with s2idle selected, and both suspend counters stayed at zero during the
boot-only trial. [Linux system sleep states](https://docs.kernel.org/6.18/admin-guide/pm/sleep-states.html)

All ten logged startup MX requests received successful acknowledgments, with
a maximum request of 1,287,500 µV. All four CPUs were online. After automatic
return, an independent audit matched all 482 installed module files and the
protected boot and package hashes. Entry into deep suspend and wake through
MPM still require testing. [Capped boot evidence](../evidence/2026-11-18-rtc-deep-cap-boot.json)

### Platform-only suspend tests

The PM debug build uses the same capped DTB. It enables the 30-second device
PM watchdog and leaves suspend-on-boot disabled. The image audit verified all
465 module signatures and 25,511 imported-symbol CRCs. The test selects the
kernel's `platform` mode, which stops before secondary CPU shutdown.
[Linux PM test modes](https://docs.kernel.org/6.18/power/basic-pm-debugging.html#testing-suspend-to-ram-str)

The first test applied the CPR corner with a bounded CPU frequency transition
and restored 300 MHz before the suspend request. The kernel reported
`-ETIMEDOUT` in CPR late suspend. Python's buffered writer flushed again
while closing and the second request returned `-EBUSY`. A workstation
fixture reproduced that sequence. The kernel resumed its device handling and
the probe restored the suspend controls.

The single-write repeat stopped while registering the CPR tracepoint.
The retained journal identifies `cpr_suspend_prepare` as unavailable to
kprobes and records zero suspend entries for that boot. Both trials returned
to installed 6.18.64. Independent audits matched the protected hashes and all
482 installed module files. The current probe uses one unbuffered write,
keeps the regular power trace if an optional CPR probe is unavailable, and
records the failed registration. It passed four workstation regression tests.
[Platform test evidence](../evidence/2026-11-18-msm8226-platform-test.json)
[Platform probe](../diagnostics/msm8226-pm/platform-test.py)

The corrected test issued one platform request. The retained journal records
one late-suspend timeout. The trace reached the CPR late-prepare function
before timing out and recorded zero calls to the CPU rate check. In the tested
source the CPR result register's busy poll is the only path to this error
before the rate check. It waited up to 1 ms for the bit to clear. No CPU entered
the platform's suspend routine. [Tested CPR driver](https://github.com/timschmidt/fx0-linux/blob/4cb942677a07683bc8c7341829a96ad004704630/drivers/pmdomain/qcom/cpr.c#L2278)

The kernel completed the early resume callbacks. The live audit confirmed
all four CPUs online, `pm_test` restored to `none`, `s2idle` selected and the
temporary trace instance removed. After the automatic return, an independent
audit matched all 482 installed module files and the protected boot and
package hashes. Physical deep entry and wake remain open.
[Corrected platform test evidence](../evidence/2026-11-18-msm8226-platform-cpr-followup.json)

The timing build logged the CPR feedback loop as already disabled before the
suspend callback wrote to its control register. The result busy bit was set
before and after that write and throughout the longer poll. The 10 ms poll
timed out after 10,030 µs. Five read-only samples after early resume again
found the loop disabled and the busy bit set. These observations show that
the longer wait did not clear the outward busy indication on this boot.
[Timing diagnostic source](https://github.com/timschmidt/fx0-linux/commit/108d6d1068476ba9c70c3bc08fbb72022d28446d)

The platform test again unwound before the clock and rail checks. The
separate reads after resume also found the CPR timer enabled and an interrupt
status bit set. The test leaves open whether the result bit reflects active
measurement or latched status while the loop is disabled.
[CPR timing evidence](../evidence/2026-11-18-msm8226-platform-cpr-timing.json)

The same signed RAM image ran a comparison at 600 MHz, where the feedback
loop was active. The result busy bit was clear immediately before the
driver's disable sequence and set immediately afterward. It stayed set
through the poll, which timed out after 10,008 µs. The callback aborted
before the CPU rate check. The probe restored 300 MHz, and all four CPUs
were online after early resume. The comparison places the busy transition
within the disable sequence in this run.
[Feedback-active comparison](../evidence/2026-11-18-msm8226-platform-cpr-active-control.json)

The per-write diagnostic sampled CPR at the same 600 MHz point. Busy was
clear through interrupt masking, disabling automatic acknowledgement,
timer adjustment, interrupt clear and the explicit ACK. The first busy
sample followed the explicit NACK. The bit stayed set after loop disable
and through a 10,027 µs poll. The ordinary disable sequence and all rail
and clock guards were retained in this test. [Per-write diagnostic source](https://github.com/timschmidt/fx0-linux/commit/cb31884d1f7e0c8ca2cca130c8e20ae33f28b91b)
[CPR disable sequence evidence](../evidence/2026-11-18-msm8226-platform-cpr-quiesce.json)

In the matched control, the driver skipped NACK after observing a clear busy
bit at the ACK sample. The bit became set by the next sample even though
that interval contained no NACK write. The same poll timed out after
10,049 µs, and the callback again aborted before the CPU rate check.
The brief interval after ACK leaves open whether its effect arrived after
the first read or a previously scheduled measurement started then.
[NACK omission control](../evidence/2026-11-18-msm8226-platform-cpr-idle-nack.json)

The idle-ACK comparison omitted both commands. The retained panic record
shows Busy clear at all eight samples and the 10 ms poll passing on its
first read. The kernel continued into the CPR clock and voltage preparation,
then panicked in the ceiling-restoration path with `-EINVAL`. The record
shows successful RPM acknowledgements at the 1,287,500 µV MX ceiling
immediately before the panic. CPU collapse did not run.
[Idle-ACK diagnostic source](https://github.com/timschmidt/fx0-linux/commit/622fa1449de547879fe6975bb1c2d1e15f64687d)

The tested code uses the MX ceiling as an exact APC target. The PM8226
fixed-range SAW provider has no 1,287,500 µV APC selector in either range.
The phone returned to installed 6.18.64 after the diagnostic panic. The
installed audit matched all 482 module files and the protected boot and
package hashes. [Idle-ACK result and retained panic](../evidence/2026-11-18-msm8226-platform-cpr-idle-ack.json)

The selector correction retains the highest validated APC point separately
from the rounded MX ceiling. It checks provider support for the exact APC
point before acquiring the suspend clock lease. Eight voltage planner
tests passed. The synthetic suspend fixtures used the two fixed APC
selector ranges with the same 1,287,500 µV MX ceiling and passed 3,702 cases.
[APC selector correction](https://github.com/timschmidt/fx0-linux/commit/96f8b4dda84fbd3d72808cfeaff011efeb14b0eb)

On the handset the corrected image passed the CPR busy poll and called
the CPU rate check. The later CPR callback returned `-EBUSY` and unwound
without a panic. The live audit confirmed 18 successful MX acknowledgements,
all four CPUs online, 300 MHz restored and `s2idle` selected. After the
unwind, the CPU mux ran from GPLL0 and the A7 PLL had zero enable references
and one prepare reference. That snapshot is consistent with the PLL
readiness gate in the source. It does not identify the exact return site.
The installed return matched all 482 module files and protected hashes.
[APC selector handset result](../evidence/2026-11-18-msm8226-platform-apc-selector.json)

An exact kernel, DTB and initramfs comparison enabled clock event tracing
through boot arguments. The A7 PLL's first recorded prepare ran under
`qcom_apcs_msm8916_clk_probe` while CCF registered the critical CPU mux.
The early trace retained every buffered event through the preflight.
The platform request reproduced `-EBUSY` and restored all four CPUs.
The general return-probe capture hit its output limit. The retained
kernel journal confirms the callback error.
[Clock-owner trace](../evidence/2026-11-18-msm8226-clock-owner-first.json)

The counted trace identified the lingering A7 PLL reference. APCS clock
registration brought the prepare count to one. The generic syscon lookup
in `cpr_msm8926_init` brought it to two. When startup switched the CPU
mux to GPLL0, CCF released the mux's reference and the PLL count fell
back to one. The retained journal showed zero suspend entries on that boot
after the test dispatch failed. The phone returned to installed 6.18.64
and matched all protected hashes and 482 module files.
[Prepare-count trace](../evidence/2026-11-18-msm8226-clock-prepare-balance.json)

The correction obtains the APCS mailbox driver's register map and creates
a managed device link for the supplier lifetime. The generic path
attaches the first DT clock to the map, which prepares the A7 PLL on
MSM8226. Seven workstation cases exercise the provider lookup, deferral,
map and device-link failures, and balanced device references.
[APCS register-map correction](https://github.com/timschmidt/fx0-linux/commit/3651953cbe1e033d67d510f2b55194c520e2fbc5)

With the shared APCS map, the complete startup trace shows the A7 PLL
prepare count rise to one and fall to zero when the CPU mux moves to
GPLL0. The platform test completed late and noirq suspend and the
matching resume callbacks exactly once. It recorded one success and
zero failures. The live audit verified the APCS supplier link, all
18 MX acknowledgements, 300 MHz, all four CPUs online and `s2idle`
selected afterward. The platform test stops before secondary CPUs
are offlined. [Platform result with the shared APCS map](../evidence/2026-11-18-msm8226-apcs-platform-pass.json)

### Secondary CPU suspend test

The processor test used the same signed kernel, device tree, and boot
arguments. Only the PM probe changed in the initramfs. Linux's
`processors` mode takes secondary CPUs offline and returns before
`syscore_suspend()` and the machine suspend callback.
[Kernel ordering](https://github.com/timschmidt/fx0-linux/blob/3651953cbe1e033d67d510f2b55194c520e2fbc5/kernel/power/suspend.c#L438)

The kernel passed the CPR checks and reached the five-second test wait
after offlining the secondaries. CPUs 1–3 then timed out coming online
with `-EIO`. Ramoops records all three later returning from
`smp_ops.cpu_die()`, entering the idle path and faulting in
`tick_nohz_get_sleep_length`. The kernel panicked and the phone returned
to installed 6.18.64. The probe receipt was unavailable over USB.
The independent audit matched all 482 installed module files and protected
hashes. Secondary CPU restart and physical deep suspend remain open.
[Processor test and reset evidence](../evidence/2026-11-18-msm8226-processor-test.json)

The first late `cpu_die()` return occurred 6.27 seconds after the last
secondary CPU online timeout. The ARM bringup code clears its shared
secondary boot data at the end of each timed attempt. Qualcomm's
downstream hotplug path publishes a per-CPU startup vector and uses the
firmware's dedicated hotplug-collapse argument. The tested kernel uses
the idle context-resume vector and the ordinary L2-on collapse argument.

### CPU3 warm-vector probe

The diagnostic uses the firmware's hotplug-collapse argument `0x10` on
CPU3. It records entry to the ARM warm vector in an aligned memory word
and parks the core until reboot. The other cores can still run userspace
and the automatic return. Ordinary idle resumes use `cpu_resume_arm`.
Keeping CPU3 at the vector avoids relying on the timed-out ARM startup
request or its cleared boot data. The diagnostic runs only when its boot
parameter is supplied. [Kernel source](https://github.com/timschmidt/fx0-linux/commit/a37af0becb9c29e4b6da131fa7ded3fd5ca72ac7)

The worker issues one offline request and checks that CPU3 is armed and
the other cores are online before issuing one online request. Linux can report an online timeout
while the core is parked. The worker measures warm-vector arrival
separately and verifies that the system suspend counters stay fixed.
The RAM boot uses the capped DTB, enforces module signatures and disables
WLAN. The host verifies exact USB readback before boot. [Probe worker](../diagnostics/msm8226-pm/cpu3-warm-probe.py)

The ARM controls run the compiled dispatcher at two link addresses. They
substitute a synthetic MPIDR value, skip privileged interrupt masking and inspect the state at
the WFI boundary. Twenty-four cases cover normal idle, CPU identity and
probe state. The ARM SMP and cpuidle objects also compile with the MSM8226
coordinator disabled. [ARM controls](../diagnostics/msm8226-pm/warm-entry-controls.py)

The first RAM boot skipped the probe because the host checker lacked a
Python import. The repaired checker passed on the same boot before the
automatic return. The repeat used the same image and took CPU3 offline
with CPUs 0–2 still online. Linux returned `EIO` after the wake request on
SGI 0. The probe word still read `armed` at 353.4 seconds after boot. The
journal recorded two distinct online timeouts. A host reproduction showed
that Python's buffered file close retries the failed write. The worker now
uses unbuffered sysfs writes, and a regression test exercises the rejected
write. The return audit matched all 482 installed module files and protected
boot and package hashes. [CPU3 evidence](../evidence/2026-11-18-msm8226-cpu3-warm-probe.json)

Qualcomm's downstream wake uses hardware SGI 1. The same capped DTB and
boot arguments with SGI 1 and a single unbuffered online write produced
one kernel timeout. CPU3 stayed armed through the last sample at 353.6
seconds. The installed kernel passed the independent return audit.
[SGI 1 source](https://github.com/timschmidt/fx0-linux/commit/85ae3cf7bc5016ccea2ef33cc78b3fe464dca081)

ARM disables the per-CPU IPIs during CPU teardown. GICv2 leaves the
effect of SGI enable changes up to the implementation. The control
read CPU3's banked enable bit immediately before collapse and restored
it. It kept the SGI 1 trigger, device tree, boot arguments, and unbuffered
worker. [Arm architecture specification](https://documentation-service.arm.com/static/5f8ff196f86e16515cdbf969)
[Wake-enable source](https://github.com/timschmidt/fx0-linux/commit/4b44caace62baa968b0c43ea84e4225bfabe499f)

The banked SGI enable bit was clear after teardown and set after the
write. CPU3 reached the firmware vector 1.009 seconds after the worker
started the wake request. The diagnostic parks CPU3 at the vector, so
the online request still timed out as expected. The suspend counters
stayed fixed. This qualifies wake delivery to the firmware vector.
The phone returned to installed 6.18.64 with all four CPUs online.
The independent audit matched all 482 module files and the protected
boot and package hashes.
The restart test below checks the additional steps needed to return
CPU3 to the scheduler. [CPU3 evidence](../evidence/2026-11-18-msm8226-cpu3-warm-probe.json)

### Restarting secondary CPUs after power collapse

The restart candidate re-enables the banked SGI before collapsing a
secondary, then restores its saved ARM suspend context on wake. The
firmware receives the hotplug collapse argument `0x10`. In coherent
kernel code the secondary must atomically claim a current online request
before it can enter ARM secondary initialization. On timeout the
controller can withdraw an unclaimed request. If the core has already
claimed it, ARM retains the startup state for up to five more seconds.
The diagnostic stops the kernel if that committed startup stalls, since
ordinary timeout cleanup would allow hotplug to unwind while the core
is still entering Linux.

The host harness compiles the actual platform transition functions and
ARM startup wait. It exercises a stale wake after cancellation, a failed
SGI send, a request accepted as the timer expires, and a committed startup
that never finishes. The RAM worker tests CPU3 twice, then CPUs 1 and 2
in isolation. It requires a checksum task to run on the restarted CPU
before issuing the next offline request.

All four isolated restarts completed in 26–72 ms, and the checksum
tasks ran on the intended CPUs. The following `processors` PM test
completed in 6.191 seconds. Its trace recorded all four late and noirq
device callback pairs and one offline and online pair for each secondary.
The independent kernel journal recorded seven restores of the saved
context across both tests. The PM success counter rose from zero to
one, the failure counter stayed at zero, and all four CPUs returned.
Two optional CPR probes could not register. The required power trace
and independent journal were available. [Restart evidence](../evidence/2026-11-18-msm8226-secondary-restart.json)
[Kernel source](https://github.com/timschmidt/fx0-linux/commit/3743831132900a49258df9378563a634ae62a87a)

A separate RAM boot repeated the exact image for `pm_test=core`. Its
trace recorded one complete `syscore_suspend` and `syscore_resume` pair
and another complete offline and online cycle for CPUs 1–3. All CPUs
returned and the PM test controls were restored. The kernel stopped
before the machine-suspend callback. The independent postflight found
three saved-context restores and matched all 482 installed modules and
the protected boot and package hashes after return. [System-core evidence](../evidence/2026-11-18-msm8226-secondary-restart.json)

The installed Fx0 has a registered APSS watchdog. The existing driver
stops the active watchdog in its late suspend callback. The diagnostic
kept it armed and captured its tick counter on resume. It counted
165,857 ticks at 32,768 Hz during the bounded system-core test. The
next test woke from 13.99 seconds of `s2idle` via the RTC and recorded
only 584 watchdog ticks. The driver read the enable bit as set on both
resumes. The two samples leave continuous watchdog coverage during
sleep unverified. The phone returned normally, and the installed
module and protected hashes matched. [APSS watchdog evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)
[Diagnostic source](https://github.com/timschmidt/fx0-linux/commit/2fd22a05dd05ded4ed35806bd2f1a7051effcc90)

A matched-profile control kept the same signed image and 25-second watchdog
timeout, then disabled standalone collapse on all four CPUs. The kernel
recorded one s2idle entry and exit, one successful suspend increment and
one matching RTC wake interrupt over 14.811 seconds. The regular and
dedicated s2idle counters for standalone collapse stayed unchanged. All idle
settings were restored and the alarm cleared. Monotonic time kept advancing
with the WFI fallback, so the earlier stopped-clock classifier did not
recognize this successful freeze.

The independent installed-kernel audit matched the candidate's watchdog
resume record. The counter advanced 1,215 ticks at 32,768 Hz, about 37 ms,
while the watchdog remained enabled. Standalone CPU collapse is unnecessary
for reproducing the shortfall. The mechanism and recovery from physical
deep suspend remain unresolved. The first setup attempt used a 60-second
timeout that the watchdog ioctl rejected before suspend.
[WFI watchdog evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

A further RTC-woken s2idle control traced 11 sites in Linux's APSS
watchdog driver and core. The trace saw the late-suspend callback return,
then early resume begin 13.998 seconds later. No probed watchdog operation
occurred within that window. The trace includes starts and a stop outside
it and reports zero lost entries. An independent installed-kernel audit
confirmed one s2idle entry and exit and the resume count of 577 ticks at
32,768 Hz. Linux driver activity at the probed sites does not explain the
shortfall. The hardware counter and firmware activity during the interval
remain unobserved.
[Driver trace evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

The first counter-sampling kernel read 17,223 ticks during late suspend
and 592 before the early-resume restart. The RTC woke the phone after
14.145 seconds. The late callback completed in under one millisecond,
leaving the effect of its ping unobserved before the first read. This
comparison cannot separate a pending ping from a loss of the counter
during sleep. The host observer was interrupted after the phone accepted
the normal return request. A separate audit verified the installed return
and both raw status records.

The next image required the counter to drop after the ping before it
collected a starting count. The journal shows 22,197 before the ping and
3 when the drop was observed. The counter reached 2,525 in about 250 ms,
short of the 4,096-tick target. The driver aborted late suspend. The
independent audit confirmed zero successful suspends for the control,
a cleared RTC alarm, all three journal samples and the signed installed
return.

The completed comparison used a 2,048-tick starting target within the same
bounded poll interval. The counter fell from 19,869 ticks to 3 after the
ping, then reached 2,052 before s2idle. It read 2,634 at early resume. The
582-tick increase accounts for about 18 ms at 32,768 Hz across a 13.616-second
callback interval. The RTC woke the phone. The driver reported the watchdog
still enabled, and the probes recorded zero watchdog calls inside the
interval and zero lost trace entries. These observations support counter
retention with little advance during s2idle. The hardware mechanism and
coverage during physical deep suspend remain open. After the normal
return, the installed audit matched all four counter samples in the journal,
all 482 module files and the protected hashes.
[Counter sampling evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

The PM8226 power-on controller offers another watchdog path. Qualcomm's
downstream driver uses the same watchdog enable register offset as the
Linux PM8916 driver. The Fx0's RAM inventory read only the selected
registers through the bound PON driver. Two reads agreed on revision
`0x01`, type and subtype `0x01`, timer bytes `0x11` and `0x01`, reset
type byte `0x0e`, and control byte `0x80`. Bit 7 was already set. The
inventory issued zero PMIC register writes. Configuration ownership,
expiration behavior, and independent recovery during deep suspend
remain to be established. [PMIC watchdog inventory](../evidence/2026-11-18-fx0-watchdog-recovery.json)

A 45-second trace on the installed kernel captured four RTC read requests
and zero Linux SPMI write requests overlapping the PM8226 watchdog registers
0x854 through 0x858. The trace reported zero lost entries. The observation
covers Linux traffic during this window. Watchdog ownership across boot
firmware, secure-world code and remote processors remains unresolved.

[Passive trace evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)
[Inventory source](https://github.com/timschmidt/fx0-linux/commit/0d081b757956382cf328fadbf346e356dbfdfdb6)
[Qualcomm PON source](https://android.googlesource.com/kernel/msm/%2B/75b24301009d38deab0f93cd10095b9b33dba545/drivers/input/misc/qpnp-power-on.c)
[Related Linux watchdog driver](https://android.googlesource.com/kernel/common/%2B/refs/tags/android15-6.6-2025-03_r8/drivers/watchdog/pm8916_wdt.c)
This difference defines the next hardware comparison. Its effect on
the delayed wake remains unverified.
[ARM bringup timeout](https://github.com/timschmidt/fx0-linux/blob/3651953cbe1e033d67d510f2b55194c520e2fbc5/arch/arm/kernel/smp.c#L143)
[Qualcomm downstream power collapse](https://android.googlesource.com/kernel/msm/%2B/android-msm-seed-3.10-marshmallow/drivers/power/qcom/msm-pm.c)

## Combined early charging firmware: host qualification

A separate firmware branch combines the existing battery/profile and charge-gate
work with the installed PON/raw-boot base. Seven changed file bodies match the
attributed policy source, and the installed boot-path files remain exact.
Host fixtures pass 307 gate cases, 2,048 SPMI cases, 41 profile cases and 128
battery cases, including 155 vendor OCV points. Both hook orders produce the
same critical policy/battery properties on the maintained kernel's actual DTB.

The first equal firmware images are rejected because an incorrect board filter
produces an empty DTB table. Two corrected fresh builds reproduce all outputs;
their Android/QCDT segments contain exactly the intended Madai DTB. One existing
RWX load-segment linker warning remains in each build. No new firmware is booted
or flashed, and no physical charge-handoff, temperature, protection or calibration
acceptance is inferred from the host checks.

## Installed CPU load and capped suspend follow-up

The installed 6.18.64 kernel passed three 18-second load intervals with one
checksum worker pinned to each core. A repeat verified all 5,282 one-MiB blocks
against a known SHA-256 result. The existing `schedutil` policy reported its
787.2 MHz maximum under load and all four advertised rates across the run. All
cores entered standalone power-collapse idle again. CPU sensors peaked at
49 °C in both runs. The installed boot, package and configuration hashes
passed the independent postflight audit.

USB stayed online with its input limit at 500 mA. The battery driver reported
`Not charging`, `Good` health and `inhibit-charge`. The driver exposed no
current, voltage, state of charge or battery temperature in this measurement.
USB draw and battery charge behavior still require electrical measurements.

The [replay](../diagnostics/cpr-suspend-cap/replay.py) extracts the actual
CPR helpers from the pinned 6.18.64 cap diagnostic and checks the packaged
suspend DTB. Its two MX maxima are 1,287,500 µV. The prior synthetic regulator
fixture runs at that ceiling with 1,344 transactions and 136,547 invariant
checks. All four controls detect the intended failure, covering APC voltage
synchronization, live PLL references, clock exclusivity and the matching sleep
vote. AddressSanitizer, UndefinedBehaviorSanitizer and LeakSanitizer pass.
The initial sandbox run could not start LeakSanitizer process inspection and
its output is retained locally.

The packaged IRQ description maps motion GPIO 69 to MPM pin 33. Home and
volume use MPM pins 36–38. The RTC alarm and power key share the PMIC arbiter
route to MPM pin 62. The installed awake IRQ inventory agrees on the device
interrupt identifiers. The installed boot exposes only `s2idle` and its
suspend success and failure counters were both zero at inspection. Physical
testing remains necessary for wake arming, wake delivery and display recovery.

Replay requires Python 3, Git, `fdtget`, clang-21 and an environment that
allows LeakSanitizer to inspect its process. Pass the kernel checkout containing
the diagnostic commit, the exact packaged suspend DTB and a new output directory.

```sh
python3 -B diagnostics/cpr-suspend-cap/replay.py /path/to/linux \
    /path/to/qcom-msm8926-lg-madai-suspend.dtb /path/to/results
```

[Follow-up evidence](../evidence/2026-11-18-power-qualification-followup.json)

## Installed battery ADC observations

The installed signed 6.18.64 kernel exposes the battery sense voltage and
ratiometric thermistor voltage through IIO. Four raw and processed samples
reported 4,228.884–4,229.178 mV on VBAT and 653 mV on the thermistor input.
The USB supply reported online with its 500 mA input limit. The battery
power-supply device reported `Good` health and `Not charging`.

The installed battery power-supply interface still lacks temperature,
current and state-of-charge data. Electrical accuracy, conversion from
thermistor voltage to temperature and actual USB current remain unmeasured.
[Installed ADC evidence](../evidence/2026-11-18-power-qualification-followup.json)

The 6.18.64 development branch adds read-only `voltage_now` to `smbb-bif`
when the board supplies the optional `battery-voltage` IIO input. The
Madai DTB points that input at the existing VBAT sense channel 6. The
driver requests a fresh processed sample in microvolts. It propagates ADC
read failures and returns no data if the pack is absent or disappears
during the read. The new input does not depend on identifying the pack or
starting the charging policy. A device tree that supplies this input
requires the VADC provider for the charger to finish probing.

Host sanitizer tests exercised the SMBB setup and voltage callbacks,
including missing or wrong-type channels, deferred probe, read failures and
pack removal. The existing provider test passed all 84 unit and scaling
cases. The ARM SMBB object built with and without IIO. The baseline and
candidate DTBs passed the targeted binding check, and the candidate
matched the baseline after removing the two new properties. Three existing
DTC warnings persisted in both builds. Handset validation and independent
electrical measurement remain open. The installed supply still lacks the
new property.
[Kernel source](https://github.com/timschmidt/fx0-linux/commit/0f2c00771fd1fa728c5775a4b8a69d440d31d527)
[SMBB callback replay](../diagnostics/vadc-battery-units/check-smbb-voltage.py)
[Host build and DTB evidence](../evidence/2026-11-18-power-qualification-followup.json)

## PM8226 hardware key reset

An opt-in read-only diagnostic sampled the PM8226 S3 source and debounce
registers twice. Both reads returned `0x03` and `0x04`. The Madai vendor
driver's field definitions decode those values as combined KPDPWR and
RESIN with a 16-second timer. The vendor device tree maps RESIN to
Volume Down. Its stock configuration requests a longer debounce interval.
The source of the currently observed setting is unresolved.
[Vendor PON driver](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/platform/msm/qpnp-power-on.c#L1187-L1231)
[Vendor board configuration](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm-pm8226.dtsi#L30-L53)

The RAM image kept the prior verified DTB, initramfs and command line.
The probe issued zero PMIC writes and the journal recorded zero suspend
entries. The installed return passed the complete 482-module and
protected-hash audit. Testing the reset itself would require a physical
key press or an independent actuator. Reset behavior, recovery from
deep suspend and unattended recovery remain open.
[Diagnostic source](https://github.com/timschmidt/fx0-linux/commit/e239ca303c5dcbc5a70452851cd3ad6edfc5ef7b)
[Device evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

### PM8226 reset-reason inventory

The opt-in Madai PON inventory now exposes `reset_reason_inventory`. It
returns five hexadecimal bytes in register order. The first is the
power-on reason at `0x808`. The remaining bytes are the two warm-reset
reasons and two power-off reasons at `0x80a` through `0x80d`.
Capture the raw bytes with the boot ID after a known reset. Qualcomm's
Gen1 PON driver describes the power-off reason bits for PMIC watchdog,
PS_HOLD and stage-3 reset. Attribution to a specific event also requires
the preceding boot and a comparison with the earlier register values.
[Qualcomm Gen1 reason definitions](https://android.googlesource.com/kernel/msm/%2B/20f6203c302caa77d7de6e662c0062da58850c65/drivers/input/misc/qpnp-power-on.c#262)

The ARM kernel builds with the existing diagnostic configuration. All
11,740 built-in export CRCs and the public module certificate match the
previous S3 image. The DTB, initramfs and command line are byte-identical.
A host test exercises every byte value in each position and both read
failures. The handler issues two read transactions and returns no partial
record on error.

After an ordinary software reboot into fastboot and one RAM boot, two
reads on the handset returned `91 02 00 a0 00`. The `0x00a0` power-off
mask has both the combined-key and long-power-key bits set in the Gen1
definitions. The PMIC watchdog and stage-3 bits are clear. Those reads
provide a baseline for later comparison. They cannot attribute the
reported desktop freeze to a reset source, and the watchdog's ability
to recover the phone from deep sleep remains unverified. The watchdog
and S3 configuration bytes matched the earlier handset inventory.

The controller could not confirm the early return request over USB. It
observed a new installed boot, and the independent USB audit matched all
482 installed module files and the protected hashes. The candidate's
journal recorded no suspend, watchdog expiry or critical kernel fault.
[Diagnostic source](https://github.com/timschmidt/fx0-linux/commit/eb2e1d27f6eaa10591d809c5dc1212b0c28aa5b2)
[Qualification evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

The installed 6.18.64 build can now supply the same five reason bytes
without a reboot. The reader verifies the running kernel and PM8226
regmap layout, then reads only the five reasons and four watchdog
configuration registers. The process-scoped SPMI trace confirmed all
18 one-byte reads across two snapshots, with zero writes and zero lost
events. Both snapshots returned reasons `91 02 00 a0 00` and watchdog
configuration `11 01 0e 80`, matching the earlier RAM capture. The
operating system identified the PMIC arbiter as v1 (`0x20000002`),
with execution environment and channel zero. These observations give a
baseline for a future independently identified reset. The observed reason
bits supply no additional attribution for the reported desktop freeze.
[Installed reader](../diagnostics/pm8226-reset-reasons/read-installed.py)
[Qualification evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

An installed capture before and after a guarded RAM test returned the
same reason and watchdog configuration bytes. The controller recorded
its request to reboot into Fastboot, the acknowledged RAM boot and the
request to return to the installed kernel. The retained journal showed
the expected three boot IDs in order. It had no kernel restart message
independently identifying either reset. On the returned boot, the
reader again verified 18 reads and zero writes. The unchanged reason
bytes do not distinguish the two observed boot transitions.
[Qualification evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

After the later reported desktop freeze and reboot, the same installed
reader again returned `91 02 00 a0 00` and `11 01 0e 80` in two snapshots.
It verified 18 SPMI reads and zero writes. The captured journal shows an
orderly shutdown from the preceding RAM boot. The return request was
also acknowledged, so the journal and the PMIC bytes cannot uniquely
identify the owner's reboot or attribute the freeze to a reset source.
The retained boots show no suspend entry or matching display, touchscreen
or IOMMU failure. Pstore contains no new crash dump.

The LG kernel release's only direct caller of `qpnp_pon_wd_config()`
disables the PMIC watchdog when preparing emergency download mode. The
published MSM8226 lk2nd source likewise clears `0x857` when preparing a
download mode. Its ordinary Fastboot reboot branch leaves that register
alone. The source inspection identifies these boot paths without
establishing who owns the watchdog during normal operation.
[LG restart source](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/mach-msm/restart.c#L110)
[MSM8226 lk2nd restart source](https://github.com/timschmidt/fx0-lk2nd/blob/8fbf21a4fd2dd6bd682edc24e83c22a04cb3b927/target/msm8226/init.c#L391)
[Qualification evidence](../evidence/2026-11-18-fx0-watchdog-recovery.json)

### Installed Sxmo idle policy

The current Sway session loaded the Madai profile and was in the unlocked
state. Both `sxmo.noidle` and `sxmo.nosuspend` exist under
`$XDG_CACHE_HOME/sxmo/`, as retained in earlier bring-up. An earlier probe
looked in the parent directory and missed both flags. The corrected USB
audit verified the paths from the active session. Neither idle job was
registered, and no `swayidle` process was running. Five installed hooks
matched the workstation package byte for byte.

The workstation replay exercised all four flag combinations in both
locations, using 32 invocations of the packaged hooks and mock display and
suspend commands. With only `sxmo.nosuspend` set in the effective
subdirectory, the lock and unlock hooks queue the idle timer while the
suspend blocker still waits. Existing settings were kept on the handset.
This accounts for the lack of automatic screen blanking and suspend under
the current policy. The reported freeze remains unresolved.
[Packaged hook replay](../diagnostics/sxmo-fx0-profile/check-idle-hooks.py)
[Power management evidence](../evidence/2026-11-17-power-management-6.18.64.json)

## Remaining physical scope

The installed firmware lacks the verified early charge-inhibition marker.
The policy rejects that handoff; no gate is forged or bypassed. The owner's
observation that the current USB connection maintains charge is preserved as
an observation, without inferring gauge calibration or fault protection.

The L3 reset mechanism, higher-rate and sustained CPU/feedback qualification,
full-system wake and supplier recovery, battery telemetry accuracy, firmware
handoff, charge completion, thermal/source-loss behavior and standby/reliability
remain open. Manual display/touch, USB removal and wall-charger checks are
unavailable during this autonomous pass. No Wi-Fi scan, interaction with the excluded workstation network,
network reconfiguration, audio test or maintainer contact is performed.

[Sanitized evidence](../evidence/2026-11-17-power-management-6.18.64.json)
