# SMD RPM regulator sleep-set prerequisite

The provider only writes ACTIVE_STATE and has no callbacks for explicit
regulator suspend voltage or enable/disable requests. Add the standard
set_suspend_voltage, set_suspend_enable and set_suspend_disable operations.
Send SLEEP_STATE key/value requests through the existing synchronous SMD RPM
API and return its errors. Preserve active cache values and pending dirty flags.
Wire all five existing operation tables; switches get only enable/disable.
No DT policy or binding changes are needed for these existing standard APIs.

This is the regulator provider layer of the full CPU/MX/RPM handoff. The current
CPR deep-suspend rejection remains. Core calls suspend enable/disable before
voltage, so successful enable followed by failed voltage is a partial sleep-set
update. These provider primitives do not make that an atomic CPU/MX transition
or authorize entering sleep after an error. The audit also identifies shared MX
ownership, CPR quiescence and recovery, L2/SPM/SCM sequencing, RPM entry/IRQ
ownership, MPM wake topology and physical validation as required work. A vendor
750000 uV sleep-only L3 initialization is not proof that the current permanently
live APC configuration can safely use that MX voltage.

The source is based on the official regulator for-next head, rechecked as
a2a6f6b0b394eda55bd3483ecafbdc8228819a98. Its stale GitHub mirror was rejected.
The runtime preserves its preexisting allocation API; that is the only parent
file difference and the generated callback composition is byte-identical.

The logical model composes 17 exact regulator-core, provider and RPM bodies and
five exact operations tables. It passes 6,310 cases and 77,934 checks after
6,516 baseline failures. Cases cover all tables, configured suspend targets,
enable/disable/voltage, two resource types/IDs, pending active updates, allocation
and send failures, timeout, unrelated replies, remote NACK and timeout boundaries.
Fourteen fault controls are rejected. All 1,280 active-request trace bytes are
unchanged. Normal LSan and fail-fast ASan/UBSan remain enabled. Allocation,
completion, locks, regulator/PM state and RPMsg endpoints are logical services;
reply ordering is deterministic and does not establish kernel concurrency or
firmware behavior. Snapshots intentionally pair the provider with the earlier
reply-correlation transport (RPM-prerequisite.json). This patch changes no RPM
transport code. Native provider/core builds use the official maintainer API.

Four ARM/ARM64 provider/core objects build with LLVM21 W=1 and strict callback
checking without diagnostics. The combined runtime kernel and 459 modules build;
CMS, ELF, release and dependencies pass. Existing module paths and 20 DTB hashes
are preserved. Ten earlier generated regression programs are byte-identical.
This incremental development-kernel build is not clean maintained-LTS package
reproducibility, installed update/recovery or physical acceptance.

Run `python3 -B replay.py /tmp/new-regulator-sleep-replay` with clang-21 and patch
installed, outside ptrace for normal LSan. It checks pinned inputs, applies source
and runtime patches without fuzz or offset, reruns the before/after composition
and 14 controls, and compares the generated programs and active packet traces.
It needs no Git, Internet, real kernel services or device.

The paired RPM source was qualified in ../fx0-spm-rpm-current at review commit
c1c0a9675ac0726b99d24033d05d9945b2a13ee2. The preceding complete local runtime and
SLIMbus work remain in review history at parent
7fae99511a7c6acf4996845510808e89eda6cc04. Current SLIMbus hardware stop, suspend
rollback, endpoint recovery, deep PM and whole-phone physical acceptance remain
open. All seven bring-up requirements remain in scope.

Codex generated this source and logical qualification; human review and DCO
remain pending. No Signed-off-by is invented. All heads are local and unpublished,
and the draft is unsent. No actual suspend, power hardware, firmware, audio,
phone, WiFi scan or network configuration is exercised.
