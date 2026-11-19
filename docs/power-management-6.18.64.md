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

### USB wake routing

Both the installed r2 board DTB and the booted experimental suspend DTB
describe the USB controller with GIC SPI 134 alone. The LG kernel
describes a second interrupt, SPI 140, for asynchronous USB wake, and
the suspend DTB maps that SPI to MPM pin 47. The USB controller has no
reference to that pin in either current DTB. The PM8226 `usb-valid`
interrupt is a separate cable-power signal. Its parent SPMI arbiter uses
MPM pin 62 in the suspend DTB. The installed wake inventory reported
`usb-valid` disabled while awake. [LG USB interrupt description](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226.dtsi#L270-L274)
[LG USB wake handling](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/usb/otg/msm_otg.c#L1102-L1117)

Four s2idle cycles on the signed r2 kernel used the RTC as a fallback.
The USB controller's wake setting alternated between disabled and
enabled. In every cycle, only the RTC interrupt was recorded as a wake
source. The host could not reach the pinned USB link at either scheduled
send time, so both packet bursts were withheld. The host USB port was
in its ordinary active policy. ChipIdea's gadget suspend path can
disconnect the gadget when the host bus has not suspended. A separate
host bus suspend and resume test remains open. [USB wake comparison](../evidence/2026-11-19-fx0-rtc-usb-wake.json)

The RAM worker restored the USB wake setting, cleared the alarm and
removed its trace instance and probe. The return audit verified the
installed boot and all 482 modules.

The kernel candidate assigns USB SPI 134 to the core and routes the
separate PHY interrupt through MPM pin 47 in the experimental suspend
DTB. With USB wake enabled, the driver programs the line-state detector
for a connected gadget after the host has suspended its bus. It enables
the asynchronous interrupt output once the PHY enters low-power mode
and restores the saved register bits on resume. [Kernel candidate](https://github.com/timschmidt/fx0-linux/tree/1cd3353191f28d1bf4cbea6d7f1b96b619751feb)

Two ARM compilations produced identical objects. The build reproduced
the earlier suspend DTB byte for byte before changing the four USB
properties. The binding accepted both DTBs and rejected missing or
reversed interrupt names on the new variant. A host fixture exercised
1,024 combinations of USB role, bus and wake state, including a PHY
transition timeout and register restoration.
[Build and replay evidence](../evidence/2026-11-19-msm8226-usb-async-wake.json)

The RAM image uses a complete kernel relink with one changed built-in
ChipIdea object. Its 11,740 exported symbol CRCs match the parent kernel.
The image keeps the parent ramdisk, including its 465 signed modules
and both return timers. It starts with s2idle selected and WLAN disabled.
The handset bound the additional USB IRQ to MPM pin 47 and retained its
main controller IRQ.

The matched RAM comparison recorded no calls to set the dedicated IRQ's
wake flag with USB wake disabled. With USB wake enabled, Linux called
the arm and disarm paths once each. The RTC woke the handset in both
cycles. The worker restored the wake setting and cleared its alarm and
trace state. The installed return audit matched the 482 module files and
protected hashes. Host-driven USB bus resume and wake from deep suspend
remain unverified. [Handset and relink evidence](../evidence/2026-11-19-msm8226-usb-wake-runtime.json)

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

The linked RAM candidate uses the installed configuration and Alpine
Clang 22.1.3. The kernel embeds the installed public module certificate.
All 11,718 built-in export records match the installed kernel. The host
verified all 468 module signatures, 25,592 imported symbol CRCs, and 482
module file hashes. The link required only the public certificate.

The candidate includes `qcom-spmi-vadc` and its `qcom-vadc-common`
dependency from the same signed module set. The initramfs requests these
modules before USB configuration. The overlay checks installed module
hashes before and after copying them into RAM. The image preserves the existing
360-second normal and 420-second early return paths, requires module
signatures and blacklists `wcn36xx`. An independent parser verified its
boot header, load bounds, exact DTB properties and initramfs contents.
[Linked RAM candidate evidence](../evidence/2026-11-18-power-qualification-followup.json)

The handset booted the exact readback image and reported `voltage_now`
as read-only. Twelve paired conversions returned 4,193,040–4,193,922 µV
through the battery supply, within 882 µV of the IIO readings. USB power
stayed online and the input limit reported 500 mA. The two interfaces read
the same ADC. Electrical calibration and actual USB draw remain open.

The main observer waited for systemd to finish starting. A separate
same-boot check verified that only time synchronization was pending and
both automatic returns were armed. Its first read rejected the IIO
decimal precision. The corrected check accepted all 12 pairs. The main
observer stopped on an assertion while returning. The independent audit
verified the installed boot, all 482 module files and the protected boot
and package hashes. The retained trial journal recorded a successful
normal return service, an orderly shutdown, and zero suspend entries or
charger and ADC failures. On the installed boot, Sway replied and the
touchscreen was enumerated. Physical touch was outside this test.

The separate package recipes use the cached 6.18.64 release archive and
the exact patch that reconstructs the three tested kernel files. The Fx0
device recipe requests `qcom-spmi-vadc` in its early module list. The
archive and recipe checksums pass.

The signed kernel `6.18.64-r2`, device `1-r3` and DMP reader
`6.18.64-r2` passed offline package verification. The installed device
package was already `1-r2`. Its wcn36xx PMF configuration is preserved
byte for byte, and the early module list is the sole changed device
payload entry. The reader package retains its exact kernel-version
dependency and has identical payload bytes. Its host tests passed all
17 cases.

The packaged kernel has the installed configuration, public module
certificate and complete `Module.symvers`. All 468 module signatures
and 25,592 import CRCs passed verification. All three Madai DTBs changed,
and the normal Madai DTB matches the one from the earlier RAM trial.

A second guarded RAM trial loaded the exact zImage, normal Madai DTB
and 21 early signed modules from the APK. The diagnostic CPIO used the
device package's early VADC entry. The live tmpfs module tree matched
all 482 package files. The twelve paired readings agreed within
588 µV. Sway reported one active output and Linux enumerated the
touchscreen. Physical interaction was outside this unattended test.
The scheduled return service completed. An independent USB audit
matched all 482 installed module files and the protected boot and
package files, and found zero suspend entries, kernel faults or SMBB
and ADC errors in the retained trial journal.

An isolated APK transaction used the phone's captured package database
and verified the original and replacement signatures. Both simulations
and both transactions passed. The three packages were the only database
records changed during upgrade. Rollback restored the original database
and world files byte for byte, and both directions verified 562 payload
files.

The installed handset's `mkinitfs` generated an inventory matching its
current 243-entry initramfs. Two candidate runs produced identical
247-entry inventories, including 21 exact signed modules and 14 module
metadata files. The VADC driver and its dependency account for the new
module files. All non-module entries matched the baseline. The runs used
a private mount and network namespace with deployment intercepted. The
live boot and package files matched the preflight hashes afterwards.

The Fx0 now holds a private recovery copy of the 32 MiB boot partition,
783 archive entries and the package commit state. The archive verifier
checked 563 package-owned paths against the exact installed APKs. Native
APK verified all six forward and rollback packages and selected exactly
the intended three upgrades in a read-only simulation.

In an isolated workstation rehearsal, a partial candidate boot write
caused the transaction to roll back. The recovery restored the original
APK database, world file, 563 package paths and complete modeled boot
partition. It preserved the 512 KiB lk2nd prefix. A second recovery
performed zero writes.

The handset's `mkbootimg-osm0sis` reproduced the installed boot image
byte for byte. It also generated the candidate image using the
qualified native initramfs. An independent encoder produced identical
bytes and the candidate retained the installed command line. The live
boot partition matched its original hash after this preparation.

Two isolated runs on the Fx0 then performed the actual native APK
upgrade and rollback. Both ran the BusyBox, kmod, postmarketOS base and
`mkinitfs` triggers. The systemd APK commit hook regenerated the unit
inventory. The captured upgrade initramfs matched the staged candidate
byte for byte, and rollback regenerated the installed archive byte for
byte. The audited run restored all 776 package records and 563
package-owned paths. APK reordered the world file, so the rehearsal
checked its constraints before restoring the original byte order. The
only additional effective file change beyond the package, boot and
commit state and the rehearsal shim was the APK log. The live system hashes matched after both
runs. A private mount, process and network namespace kept the boot
device and live service sockets outside the rehearsal.

The owner approved the persistent install and reboot. Native APK
installed kernel `6.18.64-r2`, device `1-r3` and DMP reader
`6.18.64-r2`. The installer verified all 563 package-owned paths and
the complete boot partition against the staged image before rebooting.
The running kernel then matched the candidate build notes and verified
all 482 module files on ext4 with signature enforcement enabled. The
owner confirmed the Sxmo desktop displays normally and responds to
touch on the newly installed boot.

On the installed kernel, twelve battery-voltage readings agreed with the
IIO interface within 588 µV. Both interfaces read the same ADC. UPower
is active and enumerated zero battery objects, so the result currently
exposes kernel voltage without a desktop battery reading. Calibrated
charging and hardware wake qualification remain open.

The installed UPower daemon and library match the signed r5 manifest.
Its charge-data check requires usable capacity, a recognized capacity
level, or a valid remaining-charge or energy measurement with a full or
design value. The installed SMBB supply exposes voltage and none of
those charge values. Both current IIO channels returned samples, with
the external channel using the driver's default sense resistance.
Those samples lack independent current or polarity qualification.

During twelve samples, the thermistor channel stayed at 665 mV while the
charger health changed from Good to Overheat. A later scoped SPMI trace
verified eight reads and zero writes. Both live temperature-status reads
reported HOT while the comparator retained its conservative configuration.
The installed firmware supplied neither the charge-inhibited handoff
marker nor the stock-pack profile. The software charging policy was
unbound.

Source review found a separate cache error. After a hot interrupt, a
later cold reading could retain the previous HOT flag. The correction
updates both temperature flags after a successful read and preserves
them on an I/O error. The original handler fails the hot-to-cold
fixture. The correction passes 1,026 status cases and four read-error
cases, and the ARM charger object builds with warnings enabled.
The patch is published for review. The installed hardware HOT reading
remains a separate qualification issue.
[Handset and package recipe evidence](../evidence/2026-11-18-power-qualification-followup.json)
[Package recipes](https://github.com/timschmidt/fx0-pmaports/commit/a8174d382680372082827ae97b7b6f93a86f7d7a)
[Temperature-cache correction](https://github.com/timschmidt/fx0-linux/commit/6d7f378fc071fc88dbfdc9ee37c66cad27a13843)

## PM8226 fuel-gauge diagnostic

A read-only capture on the installed r2 boot confirmed the BMS and its
companion IADC identities. The SPMI trace recorded 78 reads and zero
writes. The counter output was read without a hardware hold, so these
bytes cannot establish a coherent counter value or charge estimate.

The experimental PM8226 non-VM driver and the IADC reference and
calibration changes are ported to the installed kernel's 6.18.64 source
base. The driver source matches the earlier experimental version. The
port adds `qcom-msm8926-lg-madai-bms.dtb` for diagnostic use. Its four
IIO channels select external current, gain, offset and battery voltage.
The normal Fx0 device tree and default kernel configuration retain their
existing gauge behavior.

Host fixtures passed for gauge arithmetic, snapshot and restart handling,
property getters, and IADC calibration and reference reads. Both unsigned
ARM modules linked using the installed build's symbol table and matched
all 86 imported symbol CRCs. The binding and targeted device tree passed
schema validation. Comparing the two compiled trees verified that all
143 existing phandle targets survived compiler renumbering.

No module was loaded on the phone. The diagnostic still needs a guarded
first probe and measurements against a known current reference. Current
direction and scale, usable remaining charge, pack identity and charging
policy remain open. The earlier diagnostic reported a discrepancy between
live and background current, so the relative counter cannot yet serve as
desktop charge telemetry.
[Diagnostic kernel source](https://github.com/timschmidt/fx0-linux/commit/9833a659ee487887893e47bca12db38886f1ef88)
[Read-only capture and build checks](../evidence/2026-11-18-power-qualification-followup.json)

The first-probe follow-up checks for an active output hold or counter clear
before calibration and again before resetting the counter. Both companion
IADC sense fields must read back correctly before reset. The driver attempts
to restore the original fields on probe unwind, unbind and shutdown, and
warns if verification fails. If configuration is retried after a rollback
failure, it uses the original values for recovery. Property reads stop
sampling when teardown begins. The installed baseline captured idle control
bits and zero selections in both companion sense fields twice.

Host fault injection covers busy controls, ignored register writes, late
rollback and blocked sampling during teardown. Both ARM modules linked with
all 87 imported symbol CRCs matching the installed build. This validates the
driver's control flow and module ABI. A hardware probe must still capture
the initial current disagreement before any reprobe, verify the companion
fields after unbind, and compare measurements with a known current reference.
The counter reset and provider trim commits are outside the sense-field
rollback. The phone remains on installed r2.
[First-probe and teardown correction](https://github.com/timschmidt/fx0-linux/commit/f9e46d93ede4c7115180352886830cd0bf7b63be)

A private RAM image now pairs the exact signed r2 kernel with the diagnostic
DTB. Independent parsing verified the same initramfs, command line, WLAN
blacklist and early and systemd return guards as the previously tested
package RAM image. The image uses the original early modules and the same
checksum-verified module overlay. The two experimental payloads are kept
separate for controlled activation after the return guards are confirmed.

Alpine Clang 22.1.3 reproduced the normal DTB byte for byte and built both
modules with the installed kernel's CFI settings. The sole configuration
addition selects the diagnostic BMS as a module. Both module signatures
verify against the certificate embedded in the installed kernel, and all
87 imported symbol CRCs match. The locally prepared image and modules passed
offline verification.

The diagnostic DTB booted on the handset with both return guards active
and WLAN unavailable. The kernel exposed the expected DT properties while
the experimental module remained unloaded. A process-scoped SPMI trace
recorded 22 reads and zero writes. Both snapshots showed idle counter
controls and zero selections in the companion IADC. All 482 module files
matched the signed r2 package manifest in the RAM overlay.

The normal return service rebooted to installed r2. An independent audit
matched the boot files, package state and all 482 installed module files.
It found one active Sway output and one touchscreen input. The trial
journal had zero suspend entries, kernel faults or lockups.

A second RAM boot activated the signed IADC and BMS pair once. The
process-scoped bind trace verified the two sense writes, the counter
clear and release, and the first output hold and release in order. It
recorded 109 writes in the VADC, IADC and gauge blocks. The unbind trace
recorded two writes, both restoring companion sense fields. Both field
readbacks matched the pre-probe values, and the original IADC provider
rebound. The USB input limit read 500 mA before and after the run.

Twelve samples spanned 13 seconds beginning after probe. The supply
reported Not charging and Good throughout. Live current read 0 mA and
the background reading ranged from 0 to −2.584 mA. The relative counter
changed by −7 µAh. This window did not reproduce the much larger earlier
disagreement under the hardware Overheat condition. Current accuracy,
the charging-to-idle transition and usable remaining charge remain open.

The upload was retried on the same boot after the unprivileged receiver
failed to read the root-only timer marker. The privileged observer
rechecked the timers and confirmed the gauge was still unloaded before
the single activation. An independent journal check verified automatic
return to the installed kernel and matching boot, package and module
hashes. The active trace covers the gauge bind and unbind processes.

### HOT-condition control and gauge comparison

The first attempt returned to installed r2 before the gauge test. Its
saved console recorded the early helper arming, then stopped at 5.75
seconds without an overlay-ready marker or a panic message. An independent
18-read, zero-write PM8226 capture matched earlier reset and watchdog
register values. The early return source remains unresolved.

On one exact-image repeat, three voltage-only conversions left the raw
comparator at Good. Three thermistor conversions at 663 mV were followed
by hardware HOT. The snapshots before and after each set recorded no
SPMI writes. The BTC setting remained `0x81` and the USB input limit stayed
at 500 mA. This ordered control reproduces the thermistor-associated status
transition under the existing settings. The fixed order leaves time and
ordering effects unisolated.

The signed gauge activated once while the comparator reported HOT. All
12 samples reported Discharging and Overheat. Live current read 0 mA,
the background reading ranged from 0 to +3.615 mA, and the relative
counter increased by 11 µAh over 13.018 seconds. Unbind restored both
companion settings and the original IADC provider. Hardware HOT persisted
after unbind. The historical idle discrepancy of about 212 mA did not
reproduce in this window. Actual charging-stop behavior and independent
current calibration remain open.

The repeat returned through the normal timer. Independent journal and
file checks verified installed r2, the same boot and package hashes and
all 482 installed module files. [HOT-condition evidence](../evidence/2026-11-18-power-qualification-followup.json)

## Installed pack identity and charging-policy handoff

The installed r2 boot exposes neither the stock battery-ID argument nor a
battery-ID IIO channel. The firmware supplied no selected profile, monitored
battery reference, or charge-inhibited handoff marker. The managed policy
driver is unbound. The preserved stock evidence identifies the TOCAD Madai
selection, and the current boot still lacks live pack identification.

The PM8226 reported Good immediately before three 665 mV thermistor reads
and HOT immediately after them. Both sysfs health and the hardware status
changed. Separate four-register snapshots confirmed BTC stayed at `0x81`
and USB input remained at 500 mA. HOT was still present four minutes later
when the check requested only register snapshots. The stock table maps
665 mV to 30.9°C under its calibration assumptions. This is a model estimate
and the read sequence does not establish what caused the comparator change.

The existing firmware selector and inhibition hooks pass on the exact
packaged r2 DTB in either order with simulated pack and PMIC inputs. Both
orders preserve the 16 existing charger properties and produce matching
profile data and references, including all 155 vendor OCV points. The
unknown-pack fixture leaves both the original DTB and the gated DTB byte
identical. The managed and legacy charger and VADC objects build with the
same Alpine Clang toolchain as r2. The installed configuration still has
the managed policy disabled. The firmware and policy pairing remains to
qualify on the handset.
[Installed observations and exact-r2 host checks](../evidence/2026-11-18-power-qualification-followup.json)

### Linked managed-policy RAM candidate

The managed-policy kernel links on 6.18.64 with the reviewed SMBB
temperature-cache correction. The build uses the installed public module
certificate and preserves the 11,718 built-in symbol exports. All 482
files in the exact r2 module set match their hashes. The 468 signed ARM
modules pass independent signature verification and all 25,592 imported
symbol CRC checks against the linked kernel and retained module set.

The private RAM image uses the exact r2 DTB and initramfs, including the
existing return timers, WLAN blacklist and signature enforcement. The
static tree carries the opt-in control declaration. The paired firmware
supplies the profile and early-inhibition marker at runtime. Two retained
firmware builds have identical images and a verified Madai QCDT. They
preserve the PON raw-boot support and carry the earlier handoff code. The
combined firmware reproduces the expected generated r2 tree in simulation
and leaves the gated tree byte-identical when the pack ID is unknown.

On r2 the SMBB parent's battery-voltage lookup can defer the whole probe
when VADC is missing. The older diagnostic's assumption that the parent
supply already exists before loading the ADC needs a different sequence
on this kernel. The prepared kernel and firmware have passed host checks.
The hardware checks below cover the installed and paired loaders.
[Kernel source](https://github.com/timschmidt/fx0-linux/commit/6d7f378fc071fc88dbfdc9ee37c66cad27a13843)
[Firmware source](https://github.com/timschmidt/fx0-lk2nd/commit/b3332cf75d7c5b58a6890c2be431f95f84f0fd55)
[Linked candidate evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Managed boot with the installed loader

The linked managed kernel booted in RAM using the installed loader. The
live tree contained neither the charging handoff marker nor a selected
pack profile. The driver logged a protocol rejection and the managed
policy child stayed unbound with the voltage ADC loaded.

The charger reported `inhibit-charge`. Two snapshots 12 seconds apart
showed the PMIC charge-enable bits clear, BTC at `0x81`, and USB online
with a configured 500 mA input limit. The process-scoped capture recorded
16 SPMI reads and zero writes. The observer issued no charger sysfs
writes. Both return timers were active during the observations.

The normal return service brought the phone back to installed r2. The
independent audit matched the protected boot and package hashes and all
482 module files. Its only SMBB/VADC diagnostic was the policy-child
probe returning `-EPROTO`, the expected consequence of the missing
handoff. The test qualifies that rejection using the installed loader.
[Missing-handoff evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Paired firmware and managed kernel in RAM

The installed loader chainloaded `fx0-pm-host-01` in RAM over the pinned
USB port. The workstation verified exact byte-for-byte RAM readbacks
before booting the loader and kernel. Linux's live device tree reported
the expected loader version, charge-inhibited handoff marker and
`tocad-madai` battery profile. The profile's phandle resolved to the
expected battery data, and the signed VADC provider and managed policy
child bound successfully. Both return timers were active.

Across six fresh snapshots, the software policy reported 31.3 °C and
4.189–4.190 V, requested charging and kept the programmed USB input
limit at 500 mA. Direct PMIC reads showed charge enable set, the
`0x81` comparator configuration and HOT status. A separate trace of
six snapshots confirmed USB valid, with the temperature-OK, fast-charge,
trickle-charge and charge-done lines all deasserted. The observations
confirm the software charge request under the conservative comparator
setting. A previous stock-kernel test reproduced HOT with that setting
near the same reported temperature. [Stock comparator comparison](../evidence/2026-10-30-stock-BTC-window.json)

The scheduled service returned the phone to installed r2 without a
Fastboot recovery command. The independent audit found the protected
boot and package hashes and all 482 module files intact. The retained
journal showed an orderly shutdown with no charger or VADC errors.

Battery current, charge completion and protection across
temperature and power-source changes still require qualification.
[Paired-handoff evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Managed comparator candidate

The candidate keeps the conservative `0x81` window during handoff.
A fresh, uninhibited managed policy can request the stock `0x82` window.
The driver verifies charge disable before changing the window, checks
the comparator readback, and tests sample age immediately before and
after enabling charge. It restores `0x81` on inhibit, including after
sensor errors, pack loss, expiry or suspend. The comparator stays
enabled, and the transaction preserves unrelated PMIC bits.

The host fixture passed 44 comparator cases covering ordering, failed
and dropped writes, readback, expiry and recovery. It also passed the
existing 2,604 policy and 6,242 legacy control cases. All 27 child
lifetime cases passed. The complete ARM charger object compiled with
`W=1` in both managed and legacy configurations. The USB input fixture
passed 59 cases on each source after its extractor was corrected to
read the attribute enum without the adjacent battery property table.

The linked RAM candidate matches all 11,718 built-in exports and
verifies the existing 468 signed modules, 482 overlay files and
25,592 import CRCs. The device tree, initramfs, return timers, signature
enforcement and trial WLAN blacklist match the paired handoff run.
The temporary build and standalone kernel and DTB copies were removed.

[Comparator source](https://github.com/timschmidt/fx0-linux/commit/91d201fde1f89de650c7bcafc14856f9a983b781)
[Comparator evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Managed comparator handset trial

The installed loader chainloaded the previously verified
`fx0-pm-host-01` loader and the new managed comparator kernel in RAM.
Both images matched their USB readbacks. The live tree carried the
expected inhibition handoff and `tocad-madai` profile. The exact
kernel and module overlay passed verification with both return timers
active.

In both automatic phases the comparator read `0x82`, the charger
reported temperature OK and the fast-charge line was asserted in all
six snapshots. Each inhibit request cleared charge enable and the
fast-charge line and restored `0x81`. The tighter window reported HOT
in all five inhibited snapshots. The software policy reported
30.8–31.2 °C throughout. USB remained valid at a programmed 500 mA
input limit.

The installed IADC driver reported 263–331 mA on its internal channel
and 243–299 mA on its external channel during automatic charging.
During inhibit it reported approximately −1.8 mA and −7.2 mA,
respectively. The mode-dependent current response agrees with the PMIC
charge-state line. The external sense resistance and absolute accuracy
remain unverified. The charge-done line stayed clear during the trial.

A separate read-only check confirmed that final inhibition, `0x81`
and valid USB persisted through 250 seconds of kernel uptime. The
scheduled service returned to installed r2. The protected boot and
package hashes and all 482 module files matched. The journal recorded
an orderly reboot and no charger or VADC errors.

Charge completion, thermal and power-source transitions, and cutoff
during a stalled CPU or persistent bus fault require further hardware
evidence. [Handset evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Capped charge completion test

The same RAM kernel started fast charge at the original 4.35 V
ceiling. The observer then set `voltage_max` to 4.20 V. Direct
readback confirmed the ceiling changed and the hardware termination
register stayed at `0x08`. The recharge threshold stayed at 4.28 V,
above the temporary ceiling. USB remained valid at a programmed
500 mA input limit.

The observed battery voltage settled to about 4.210 V. The internal
IADC reported 54–68 mA and the external IADC 47–63 mA across 19 capped
snapshots spanning 118 seconds. The charge-done IRQ count rose from
zero to 74 between the last uncapped sample and the first capped
sample. The count then held at 74. All capped snapshots showed the
charge-done line low, fast charge asserted and Linux status
`Charging`. Completion at the cap remains unverified. The ceiling
and recharge-threshold mismatch is one candidate explanation for the
IRQ burst.

The observer requested inhibit before restoring the original 4.35 V
ceiling, verified the conservative comparator window and checked that
all three charger configuration registers matched their initial values.
The scheduled return restored installed r2. The independent audit
matched the protected boot and package hashes and all 482 module
files. The journal showed an orderly shutdown with zero charger or
VADC errors. [Capped-charge evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Managed recharge tracking candidate

The driver records the board's effective charge ceiling and recharge
threshold at probe. A managed voltage change verifies charge disable,
programs the ceiling, and derives the recharge threshold from the
verified ceiling and the board's gap. The observed 4.35 V and 4.28 V
board settings give a 70 mV gap. At a 4.20 V ceiling the driver's 20 mV
recharge step rounds the threshold down to 4.12 V.

The transaction verifies both writes. On a write or readback error
it attempts to restore both original values and latches the existing
charge fault. Following a successful change, a fresh policy sample
authorizes charge to resume. The worker adjusts thermal current without
rewriting the voltage ceiling.

The host fixture passed 143 voltage and recharge cases, including the
representable voltage range, safe-limit clamping, rollback and 400
concurrent cap requests interleaved with policy sampling. It rejected
five mutations that bypassed the transaction
checks. The complete ARM charger object compiled with `W=1` in
both managed and legacy configurations. The linked RAM image matched
all 11,718 built-in exports and verified 468 installed module
signatures, 482 overlay files and 25,592 import CRCs. It retained the
prior DTB, initramfs and return timers.
[Recharge tracking source](https://github.com/timschmidt/fx0-linux/commit/8e5eacff1484771c0c96de28b018896a2cd7b738)

### Handset repeat with recharge tracking

The RAM trial read back the 4.20 V ceiling and 4.12 V recharge
threshold. The termination register stayed at `0x08`. Across 19
samples over 119 seconds, the PMIC kept the fast-charge, trickle-charge
and charge-done lines low, and the charge-done IRQ count stayed at
zero. USB stayed valid at a programmed 500 mA. The reported battery
voltage was 4.200–4.204 V.

The onboard ADCs reported 269–314 mA during the initial automatic
phase and −7.2 to −4.8 mA after the cap. Linux reported `Discharging`
in all capped samples while the charge-enable bit stayed set. This
verifies charge-to-idle at the cap. The repeat
changed the recharge threshold and the order of programming, so the
comparison leaves the cause of the earlier interrupt burst unresolved.
Full-charge reporting, normal 4.35 V completion, thermal boundaries
and source-loss behavior remain unverified.

The observer restored the original 4.35 V ceiling and 4.28 V
threshold under inhibit and verified both registers. The scheduled
return brought the phone back to installed r2. The protected boot and
package hashes and all 482 module files matched, and the retained
journal showed a clean shutdown. [Recharge tracking evidence](../evidence/2026-11-18-power-qualification-followup.json)

### Nominal-voltage charge diagnostic

The nominal-voltage diagnostic uses the same kernel, device tree and
signed module payloads as the tracked-recharge trial. It checks the
board's 4.35 V ceiling, 4.28 V recharge threshold and termination
register `0x08` during each sample. An observation checks the USB input
limit, the reported battery voltage and temperature, charger status,
PMIC charge state, charge-done interrupts and both onboard current
readings.

The early helper initially arms a return at 420 seconds of boot uptime.
Once the host is sampling, each healthy sample sends a root-only
heartbeat. The host checks the helper's identity and reads its actual
boot-time timer to confirm a fresh 120-second deadline. The helper caps
renewals at 3,720 seconds, and systemd independently schedules an
orderly return at 3,600 seconds. ARM emulation verified timer expiry
and renewal. Both return paths depend on a running kernel.

The observer requires three consecutive samples with Linux `Full`,
the PMIC charge-done line asserted, fast and trickle charge inactive,
and both current readings within 20 mA of zero. It requests inhibit
before triggering orderly return. The observation window ends at
approximately 57 minutes of boot uptime if those criteria are still
unmet.

#### Handset charge and recharge

At the normal voltage settings, the last sample in the initial fast
charge measured 4.349 V. The next sample, 29 seconds later, measured
4.302 V with fast and trickle charge inactive. The two onboard current
readings dropped to −1.2 mA and −4.4 mA. Charge enable stayed set, the
comparator stayed at `0x82`, and the policy registered no inhibit vote.

The handset resumed fast charge automatically about 14 minutes after
the first idle sample. The last idle sample before the restart measured
4.287 V. The sample interval leaves the exact hardware trip voltage
unresolved. In the second fast-charge phase, the last active sample
measured 4.346 V before current again returned near zero.

Across 117 samples, the charge-done bit stayed clear and the
charge-done interrupt count stayed at zero. Linux reported `Charging`
during fast charge and `Discharging` during both idle periods. The
observation verifies two charge-to-idle transitions and automatic
recharge at the normal limits. Hardware charge-done, `Full` reporting
and absolute current accuracy remain open.

Every sample confirmed a timer renewal. At the observation limit, the
observer verified that charging was inhibited and requested orderly
return. The independent audit verified the return service and shutdown
in the journal. The installed r2 boot matched the protected boot and
package hashes and all 482 module files.
[Nominal charge evidence](../evidence/2026-11-18-power-qualification-followup.json)

#### Charge termination configuration

On installed r2, two read-only snapshots of PM8226 SID 0 agreed.
The SPMI trace recorded all 18 expected reads, zero writes and zero
lost events. The reads used the uncached regmap and the same trace
validation as the PON diagnostic. The kernel notes hash matched the
signed r2 baseline. [Trace validation](../diagnostics/pm8226-reset-reasons/read-installed.py)

| Register | Value in both snapshots | Field |
| --- | --- | --- |
| `0x1010` | `0x00` | Charger live interrupt status |
| `0x1040` | `0x6f` | Charge ceiling, 4.35 V |
| `0x105b` | `0x08` | Termination current register |
| `0x105d` | `0x34` | Recharge threshold, 4.28 V |
| `0x1105` | `0x32` | SMBBP buck subtype |
| `0x1110` | `0x40` | Buck live interrupt status, `VDD_LOOP` asserted |
| `0x11eb` | `0x00` | Buck comparator override |
| `0x1210` | `0x03` | Battery interface live interrupt status |
| `0x1310` | `0x03` | USB charge path live interrupt status |

LG's Madai kernel programs `0x08` for analog termination and sets the
SMBBP buck comparator override mask `0xc0` to `0x80` to disable the
charger's charge-done logic. Its software end-of-charge worker checks
the battery FET, active charge state, voltage loop, taper current and
repeated samples. The `CONFIG_LGE_PM` path also requires a reported
state of charge of 100%. The board specifies a 150 mA termination current.
[LG charger source](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/power/qpnp-charger.c)
[LG board settings](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226-madai/msm8226-madai-pm.dtsi)

The installed comparator value differs from LG's programmed value.
The `VDD_LOOP` bit was already high while the charger reported no
active charge or charge-done bits. The earlier managed RAM samples
establish automatic recharge and charge-to-idle with zero charge-done
interrupts. The installed snapshots leave the cause of the missing
interrupt unresolved. A validated taper-current measurement and
samples during the transition are still needed to qualify `Full`.

#### Installed charger timer state

Two PM8226 snapshots on installed r2 agreed. Both read `0x00` at the
charge-duration enable register `0x1060` and the charger watchdog enable
register `0x1065`. The raw values at `0x1061`, `0x1062` and `0x1063` were
`0x1d`, `0x20` and `0x50`. The trace verified ten reads and zero PMIC
writes. Hardware charge cutoff with a stalled CPU remains unqualified.
[Trace validation](../diagnostics/pm8226-reset-reasons/read-installed.py)

#### Charge-duration candidate

LG's Madai device tree selects a 480-minute charge duration. Its driver
programs the PM8226 duration register in four-minute steps and then
enables the timer. Its charge-failure handler disables charging on the
LG configuration. [LG board settings](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226-madai/msm8226-madai-pm.dtsi#L291)
[LG driver](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/power/qpnp-charger.c#L3613)

The candidate programs and verifies the same limit while the charger
is inhibited at startup. A configuration error or a latched PMIC
charge failure holds the driver's fault vote. Steady policy samples
leave an already enabled timed charge session alone. The ARM driver
object and Madai DTB compiled. The binding passed validation, and the
host model covered duration bounds, readback errors, the charge-failure
latch and an injected failure during enable. Timer expiry and recovery
on the handset remain open.
[Candidate source](https://github.com/timschmidt/fx0-linux/commit/1e75e586a6e8f03fd013430135e5abf86a8643e0)
[Host checks](../diagnostics/smbb-charging-policy/check-duration.py)

The follow-up adds the charger-failure IRQ from LG's PM8226 device tree.
It latches the existing fault vote even if the failure signal pulses
between samples. Orderly shutdown and driver cleanup verify charge
cutoff, disarm the duration timer and restore the saved period. They
leave the PMIC failure latch intact. The model exercised retries after
uncertain writes and rejected rollback when cutoff could not be verified.
[IRQ mapping](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm-pm8226.dtsi#L95)
[Charger return candidate](https://github.com/timschmidt/fx0-linux/commit/272ba42f0202498b83c2cabfe922464c46c0cf0c)

The installed reference read charger subtype `0x31`, period `0x1d`,
and zero at the timer enable, charger watchdog enable and failure latch
registers. Both read-only snapshots agreed. This is the reference for
the 480-minute RAM rollback rehearsal.
[Installed reference and host controls](../evidence/2026-11-19-fx0-charge-duration-return-controls.json)

On the 480-minute RAM boot, six snapshots showed fast charge active,
timer enable `0x80` and period `0x77`. The charger watchdog and failure
latch stayed clear, and the charger-failure IRQ count stayed at zero.
The snapshots accounted for 60 SPMI reads and zero observer writes.

The scheduled reboot returned to installed r2. All seven protected
hashes and 482 installed module files matched. Both postflight snapshots
matched the installed reference, including timer enable `0x00`, period
`0x1d` and failure latch `0x00`. The RAM boot's journal contained no
charger timer or cutoff errors. Timer expiry and charge cutoff with a
stalled CPU still require handset tests.
[Handset rollback evidence](../evidence/2026-11-19-fx0-charge-duration-rollback.json)

#### Managed charger suspend refusal and wake notifications

The paired managed RAM image started with fast charge active at the
nominal voltage settings. The RTC-backed `s2idle` request returned
`EBUSY` during userspace freeze, before the charger suspend callback.
The alarm was cleared, and the final PMIC readback showed charge disabled
and the conservative `0x81` comparator window. A second request was
gated by the RAM trial's readiness and time limits.

A separate 7.25-second trace in the same boot held the user inhibit
vote. All seven `smbb-bif` wake-source activations occurred inside the
managed sample worker, about 1.04 seconds apart. The trace captured all
seven deactivations and reported zero lost events. This establishes
steady policy polling as a source of wake activity during inhibition.
The wake source for the original freezer refusal remains unverified.

The source change keeps the sample and age workers' safety checks and
register verification. These workers now notify the battery supply when
the inhibit votes or effective current limit change. The regression
rejected the old steady-sample notifications and verified notifications
on expiry, recovery, fault and a reduced-current transition. The full
charger object compiled for ARM with `W=1`. [Kernel change](https://github.com/timschmidt/fx0-linux/commit/1562a10bf78522776079c2aa7880d4b539324583)

The candidate returned through the scheduled reboot. The independent
audit matched all seven protected hashes and all 482 installed module
files, and the journal matched the failed suspend receipt.
[Handset and regression evidence](../evidence/2026-11-19-fx0-managed-charger-freezer.json)

#### Handset repeat with notification gating

The rebuilt RAM image retained the prior configuration, device tree,
initramfs and return timers. It matched all 11,718 built-in symbol exports
and checked 468 module signatures, 482 files and 25,592 imported-symbol
CRCs. The paired temporary loader and kernel both matched their USB
readbacks. WLAN stayed disabled in the RAM boot.

With the user inhibit held, the patched sample worker ran seven times in
7.25 seconds and caused zero `smbb-bif` activations. The earlier build
caused seven activations under the same observation. The first suspend
request under user inhibit returned `EBUSY` around a battery-temperature
interrupt. The repeat reached 14.358 seconds of `s2idle` and woke on the
RTC alarm. The trace verified charge disable and its readback, zero
charge-control writes during sleep, and zero enables after resume. The
conservative `0x81` comparator window and user inhibit persisted.

Both automatic-charge attempts stopped before machine suspend. Each
trace recorded a fast-charge interrupt activating the battery wake
source during device suspend. The first arrived before the managed
charger callback. The second arrived 41 µs after the callback completed
the charge-disable write. These traces show a separate source of suspend
interference after the fix for
periodic polling. Sleep from automatic charge and fresh-sample-gated
re-enable after a completed wake remain unqualified.

The scheduled reboot returned to installed r2. The independent USB
audit matched all seven protected hashes, all 482 module files, and the
worker's receipt in the retained journal. The journal recorded four
`s2idle` requests and exits, including the three early returns.
[Trace checker](../diagnostics/smbb-charging-policy/check-suspend-trace.py)
[Handset and return evidence](../evidence/2026-11-19-fx0-managed-charger-suspend.json)

#### Inhibit charging before requesting sleep

The same linked RAM image completed two prepared cycles. The first
started in fast charge. The second started with automatic charging
enabled and the charger idle. The diagnostic set a temporary user
inhibit and verified the charge-disable write and conservative `0x81`
comparator readback. It waited for charger wake-source counters to stay
quiet for at least 0.9 seconds before starting the RTC suspend request.

The RTC woke both cycles after 14.509 and 14.010 seconds. The PMIC
trace recorded zero charge-control writes during sleep. The resume
worker converted both the thermistor and battery-voltage channels
before the diagnostic released the temporary inhibit. The first charge
enable followed those conversions and the `0x82` comparator readback.
The probe then verified the enable bit. The trace checker replayed both
cycles and rejected four mutations covering charger readback, missing
temperature conversion, missing suspend completion and early enable.

The workstation observer was interrupted after capturing both cycles.
The resumed observer verified the scheduled return to installed r2. An
independent USB check matched the worker receipt in the journal, all
seven protected hashes and all 482 installed module files.
[Handset evidence](../evidence/2026-11-19-fx0-prepared-charger-suspend.json)

A separate kernel candidate defers fast- and trickle-charge status
notifications between device PM prepare and complete. The IRQ handlers
still update charge status, and PM complete delivers a pending update
after resume or an abort. Temperature, battery presence, charge
completion and power-source notification paths are preserved. The
charger object compiled for ARM with `W=1`. The lifetime model passed
29 cases and rejected five mutations, including early notification
and lost notification on abort.
[Charge-phase kernel candidate](https://github.com/timschmidt/fx0-linux/commit/614a0266edf151ea8cb174c944614e54e6477352)

#### Direct suspend from fast charge

The linked charge-phase candidate matched all 11,718 built-in kernel
exports, 468 module signatures, 482 installed overlay files and 25,592
module import CRCs. It reused the verified device tree, initramfs,
temporary loader and return guards. WLAN stayed disabled in the RAM boot.

Two direct `s2idle` cycles started in automatic fast charge. The driver
verified charge disable and the conservative `0x81` comparator window
before each sleep. In both cycles the fast-charge IRQ handler ran after
device PM prepare and before machine suspend. The trace recorded zero
battery wake-source activations from the handler in either window. The
RTC woke the phone after 14.073 and 14.151 seconds. The trace recorded
zero charge-control writes during sleep. The resume worker converted
both thermistor and battery voltage channels before verifying the
`0x82` comparator and enabling charging again.

The separate user-inhibit cycle woke by RTC after 14.420 seconds. Its
trace verified zero charge enables after resume and a conservative
comparator readback. Seven later samples with the inhibit held triggered
zero battery wake-source activations. The trace also captured a
battery-temperature notification after an automatic-charge wake.
[Trace checker](../diagnostics/smbb-charging-policy/check-suspend-trace.py)

After the scheduled return to installed r2, an independent USB audit
matched all seven protected hashes and all 482 installed module files.
It also matched the worker receipt and three suspend entries and exits
in the saved journal. The phase-notification kernel ran from RAM.
[Handset and return evidence](../evidence/2026-11-19-fx0-direct-charger-suspend.json)

#### Voltage ADC driver removal

The same RAM candidate entered automatic charge with a fresh policy
sample and a readable battery voltage. The first observer hit a trace
parser error before issuing the unbind. The corrected observer reached
the unbind test, then failed before recording a post-unbind sample. Its
final inhibit check also encountered a missing sysfs path. The candidate
returned on schedule and the independent USB audit matched all 482
installed module files and the protected hashes. The saved journal
contained the worker receipt. No register trace was available after
reboot, so that run could not establish cutoff or recovery.

The device tree declares a VADC dependency for the parent charger’s
`voltage_now` property. Linux can unbind the parent through that firmware
device link when VADC is removed. The repeat tracked the parent, policy
child and USB gadget through that transition. It measured hardware cutoff
independently of the disappearing power-supply sysfs entries.
[Trial evidence](../evidence/2026-11-19-fx0-vadc-driver-removal.json)
[Charger device-tree node](https://github.com/timschmidt/fx0-linux/blob/614a0266edf151ea8cb174c944614e54e6477352/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts#L450)

The repeat started in verified fast charge. Removing VADC unbound the
parent charger, removed the policy child, and dropped the USB gadget.
The PMIC still reported the physical USB source. The trace verified
charge disable and the conservative `0x81` comparator window before
IIO unregister. Two independent register captures about four seconds
apart confirmed that charge and fast/trickle status stayed off.

VADC rebound successfully. The charger parent was still unbound after
seven seconds and required an explicit reprobe. Its policy child then
bound automatically. The trace verified fresh thermistor and voltage
conversions before charge re-enable. USB gadget state stayed absent at
the post-rebind capture, and the host recovered the report and the
complete 264-event trace from the journal after the scheduled return.
All 482 installed module files and the protected hashes matched.

The isolation candidate uses the policy child’s named voltage input
for on-demand battery readings. The Madai charger parent no longer
declares its own VADC reference. The legacy parent input path is still
supported. Host tests covered absent and restored IIO providers and
reading errors. The full linked kernel matched 11,718 built-in symbol
exports, 468 signed modules, 482 module files and 25,592 import CRCs.
[Repeat and candidate evidence](../evidence/2026-11-19-fx0-vadc-cutoff-and-reprobe.json)
[Isolation candidate](https://github.com/timschmidt/fx0-linux/commit/5796fb92a078920740ee70857837cc070101c1ba)

#### Supplier isolation on the handset

The charger stayed bound and the USB gadget stayed configured through
two VADC removals. The host retained the same USB enumeration and network
interface across five checks. Battery voltage reported `ENODATA` while
the ADC was unbound and returned a measurement after rebind. The charge
policy reprobed automatically in both cycles.

The first cycle started in fast charge. Both traces showed charge
disable and the conservative `0x81` comparator window before the ADC
unregistered. Each cycle held the disabled state across two snapshots.
The first cycle then took fresh thermistor and voltage readings before
enabling charge. The second started with the user's inhibit vote and
recorded zero enable writes through rebind. The final PMIC readback
confirmed charge was still inhibited.

On the same RAM boot, two automatic-charge `s2idle` cycles woke by RTC
after 13.587 and 13.911 seconds. The second started in fast charge. Both
traces confirmed zero charge-control writes during sleep and fresh
thermistor and voltage samples before re-enabling charge. The test's
return-time guard stopped the later user-inhibit suspend cycle before
it requested sleep. Final charge inhibition and the RTC alarm cleanup
were verified.

The phone returned to installed r2 on schedule. An independent audit
matched the two workload receipts, both supplier traces, both suspend
entry and exit pairs, the protected file hashes and all 482 installed
module files. [Handset and return evidence](../evidence/2026-11-19-fx0-vadc-supplier-isolation.json)

An early test on a fresh boot of the same image covered the deferred
user-inhibit case. The RTC woke the phone after 14.275 seconds. The
PMIC trace confirmed the conservative comparator, zero charge-control
writes during sleep and zero charge-enable writes after wake. The
explicit inhibit still held at the final readback. Both automatic
return safeguards stayed armed. The phone returned to
installed r2, and the journal, protected hashes and 482 installed
module files passed the independent audit.
[Inhibited suspend evidence](../evidence/2026-11-19-fx0-vadc-isolated-inhibited-suspend.json)

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

On a subsequent owner report that the visible desktop was unresponsive
until reboot, a USB-only audit confirmed the running installed kernel and
package baseline. Sway reported one active output and Linux enumerated
the touchscreen. The immediately preceding retained boot was the
battery-voltage RAM trial. Its journal logged an orderly shutdown, and
the newly archived pstore console record contains a shutdown marker with
zero panic, oops, lockup or suspend markers. Both boots show the same
early Adreno firmware warning. The journal and console cannot distinguish
the owner's reboot from the trial's scheduled return or identify the
cause of the freeze. Physical touch after recovery remains unverified.
[USB freeze follow-up](../evidence/2026-11-18-power-qualification-followup.json)

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

### Installed display power cycling

The signed r2 kernel completed six Sway `DSI-1` power-off and power-on
cycles over wired USB. Each transition reached the requested state in
Sway and the DRM CRTC. The first restore was driven by an independent
five-second systemd timer. The DRM vblank sequence advanced by six or
seven frames over the 110 ms check after each restore at 720 × 1280 and
60 Hz.

The kernel trace recorded six successful Synaptics RMI4 suspend calls,
six successful resume calls, and six successful panel-follower prepare
calls. The same Sway and gesture processes survived the series. A separate
USB audit checked the active output, zero remaining transient units or
trace objects, and no matching DRM, RMI4 or I²C timeout errors in the
recent kernel journal. The corrected probe accepts inactive units that
systemd has already collected. The first attempt treated this as a cleanup
error after a successful restore. This test exercised display power with
the system awake. Physical touch events still require verification.
[Handset evidence](../evidence/2026-11-19-fx0-display-power.json)
[Display test](../diagnostics/sxmo-fx0-profile/check-display-power.py)

### Display recovery after RTC wake

The guarded RAM trial reused the exact signed r2 kernel and device tree
from the installed package, with WLAN disabled and all 482 module files
verified. It completed three `s2idle` cycles. Each trace recorded the RTC
alarm as the only wake IRQ. The IRQ counter advanced by one per cycle,
and the inactive-clock intervals ranged from 13.905 to 14.492 seconds.

The active Sway output returned to the same DRM CRTC at 720 × 1280 and
60 Hz. The vblank sequence advanced seven frames over each 110 ms sample.
The RMI4 suspend, resume and panel-follower prepare callbacks all returned
zero once per cycle. The same Sway and gesture processes survived. The
probe cleared the RTC alarm and removed its trace objects after each
cycle. On the workstation the combined probe also rejected three
negative controls covering the wrong wake IRQ, a failed RMI4 resume and
a changed DRM CRTC.

The scheduled return restored installed r2. An independent USB audit
matched all seven protected hashes and all 482 installed module files.
The saved kernel journal contained three `s2idle` entries and three
exits, and the worker's journal result matched the wired receipt. The
installed Sway output also passed the vblank check.

Physical touch, power-key or motion wake, and display recovery from
deep suspend remain open.
[Combined probe](../diagnostics/rtc-s2idle/display.py)
[Handset and return evidence](../evidence/2026-11-19-fx0-rtc-display-recovery.json)

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
