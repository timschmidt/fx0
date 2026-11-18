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
