# System suspend admission and corrected phase ordering

This local prerequisite adds an owned RPM request freeze/drain operation.
It is not a complete coordinator, has no production caller, and is not an
upstream-ready standalone API proposal. CPR's deep-suspend guard and covering
SO voltage floor remain unchanged. Runtime36 is unchanged and nothing is
installed on the phone. The original seven bring-up requirements all remain.

Freeze takes the existing request mutex while the receive IRQ can still run,
drains its send/ACK pair and closes request admission. It returns with no
mutex held. Writers then return EBUSY. Thaw requires the original token address
and non-reused cookie. Wrong-channel, copied and stale tokens cannot release
admission. Local IRQ-disabled calls fail before locking; the caller separately
must ensure the receive IRQ is available. Any failed submitted request retains
uncertainty, which later success cannot clear. Pre-submission allocation/size
failures and rejected frozen writes do not poison the channel. Reprobe resets
local state; it does not establish firmware reset or safe voltage state.

The exact-source admission model passes 147 cases / 13235 checks, including
40 runs that block a real host writer while a freezer waits, then reject eight
concurrent late writers per run. Twelve behavioral controls fail clean
assertions. Four native ARM/ARM64 ordinary/RT profiles compile sixteen objects
with no new diagnostics; two identical inherited RPMsg documentation warnings
per profile are retained. The retained ACK model still passes its 111537
bounded packet cases; only synthetic u64/EBUSY declarations were added. The
new models use ASan/UBSan with normal leak detection; the old ACK model retains
its original compiler and is not claimed sanitized. No native kernel thread,
firmware, electrical or real IRQ behavior is qualified by the host services.

The phase model executes actual suspend_enter and six dispatch wrappers in
176 cases / 3634 checks; four controls reject the earlier incorrect phase
assumptions. For MEM, platform prepare_late runs after device IRQ suspension,
platform early restore does nothing, and finish runs after device early resume.
This supersedes prior prose that inferred platform callback timing from wrapper
names. Synchronous RPM preparation/restore needs ordered device late/early
callbacks. The model's device and platform callbacks are synthetic services;
it is not an implemented production coordinator.

The MSM8226 hotplug path only parks secondaries in WFI. An offline CPU count
is insufficient to authorize L2_OFF. The vendor sleep-status address/bit is
recorded as source evidence only. Actual secondary entry, bounded state proof,
CPR/clock/APC/SO preparation, CPU program validation, cache/CPU-PM/cluster-PM,
SCM and MPM wake/timer/routing/replay composition remain required. Independent
SLIMbus hardware-stop, failed-suspend rollback and endpoint recovery, maintained
LTS clean public-source packaging/update/recovery, original r2 display/IOMMU
resolution and all physical acceptance also remain open.

Run `python3 -B replay.py /fresh/private/output` outside ptrace with clang-21,
cc and patch. Replay verifies inputs, applies the source patch with no fuzz or
offset, and executes the admission, phase, controls and retained ACK models
without Git, network or devices. Complete pinned trees are needed for native
builds. No new full kernel build or runtime merge is claimed at this checkpoint.

Codex generated the source, tests and draft. Human review and DCO are pending.
The patch is a feature prerequisite, so no Fixes tag is invented. No phone,
firmware, real radio/audio, Wi-Fi scan, Replimat3 or network configuration
operation occurred. All new commits remain local and unpublished; nothing has
been sent to maintainers. No public download was needed for this source step.
