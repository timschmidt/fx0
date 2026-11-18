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

The CPU target's earlier pre-init result still requires investigation. An isolated
`6.18.64-fx0-power-trace-alpine` build adds requested L3 vote/acknowledgement
logging without changing vote construction, ordering or error propagation.
The source and recipe hashes are in the evidence; its signed build is running.
The actual core/boot and sleep-voter models pass 317 and 1,785 cases under normal
ASan/UBSan/LSan with only diagnostic printk mocked and the current sleep-token
structure supplied verbatim. Earlier fixture/sandbox failures remain recorded.
This diagnostic is not a production fix and has not been booted.

## Remaining physical scope

The installed firmware lacks the verified early charge-inhibition marker.
The policy rejects that handoff; no gate is forged or bypassed. The owner's
observation that the current USB connection maintains charge is preserved as
an observation, without inferring gauge calibration or fault protection.

CPU registration, bounded transitions and feedback, the L3 startup failure,
full-system wake and supplier recovery, battery telemetry accuracy, firmware
handoff, charge completion, thermal/source-loss behavior and standby/reliability
remain open. Manual display/touch, USB removal and wall-charger checks are
unavailable during this autonomous pass. No Wi-Fi scan, interaction with the excluded workstation network,
network reconfiguration, audio test or maintainer contact is performed.

[Sanitized evidence](../evidence/2026-11-17-power-management-6.18.64.json)
