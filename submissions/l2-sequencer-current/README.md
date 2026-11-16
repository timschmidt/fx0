# Verified MSM8226 L2 sequence backend

The preceding L2 SPM owner initializes APC voltage arbitration but has no L2
power programs. The complete vendor RET/GDHS/PC-without-RPM/PC-with-RPM set is
82 bytes, larger than the CPU table's 64-byte storage. Add a separate 84-byte
table with two END padding bytes and the vendor copyright/provenance. All 84
bytes and starts 0/4/26/54 are checked against cached public vendor source.

Load and verify all 21 words with control and AVS disabled before permanent
syscon publication. Preserve the original arbiter initialization and never
issue VCTL/reset or mode-enable commands during setup. Known disabled partial
setup can retry; corrupt or inconsistently live arbiter configuration remains
unsupported and unpublished. Retain the bounded raw regmap owner.

The separate L2 mode API requires CPU0 and local IRQs off; arming also requires
secondary CPUs offline. APC voltage commands use synchronous CPU0 IPI context.
Invalid context performs no MMIO. An owned mode transition first disarms and
verifies zero, checks controller identity/configuration, idle PMIC status and
every program word, then writes and reads back the chosen index and enable.
An uncertain arm is disarmed before returning an error. Two unverified disable
attempts are fatal, including the recovery path, rather than returning to
generic WFI with unknown collapse enable. Both fatal policies are exercised
using caught synthetic fatal paths; no actual kernel panic is executed.

Seven actual functions plus the actual access tables compose 1259 passing
cases / 110383 checks. Cases cover all 64 initialization I/O points and 33 arm
I/O points, failed/dropped/corrupt reads and writes, applied/unapplied failures,
partial setup, lost RAM, each mode, context/resource/publication rejection,
invalid mode and both persistent recovery failures. Fourteen behavioral mutants
fail named assertions without compiler, process or sanitizer faults. Normal
LSan and fail-fast ASan/UBSan are enabled. Regmap/MMIO, CPU/IRQ/online state,
device resources and syscon services are synthetic; real concurrency, firmware
and electrical effects are not qualified. A separate parent-only demonstration
shows 21 missing program words in one publication case. It does not claim that
the new API or its full suite runs on a parent which lacks it.

Four native profiles (ARM/ARM64, ordinary/RT) compile 32 SPM/RPM/regmap objects.
The two RPMsg kernel-doc warnings per profile reproduce exactly on unchanged
parent source. Raw diagnostics and provenance remain included; no category is
suppressed and no new diagnostics are accepted. Strict checkpatch passes for
both source and runtime patches. Complete incremental development kernel and
459 modules build; CMS, ELF32 ARM, release and dependencies are verified. This
is not a clean reproducible maintained-LTS package or phone update/recovery.

Only spm.c, the L2 helper header and the public SPM header change. Source and
runtime files are byte-identical. Existing CPU-idle, APC/MX/SO/CPR code and the
deep-suspend guard are unchanged. Fifty-one other prior build-manifest entries
match. No DT source/include/schema input changes; the prior twenty validated
DTB artifacts are hash-verified and are not claimed rebuilt this turn.

Run `python3 -B replay.py /path/to/fresh-private-output` with clang-21 and patch
outside ptrace for normal LSan. Replay verifies every input, demonstrates the
parent's missing programs, applies source and runtime patches with no fuzz or
offset, runs both exact-source compositions and rejects all fourteen controls.
It needs no Git, network or device. Compiler temporary files stay in the output.
Full native/kernel/module builds require the complete pinned dependency trees.

This backend has no system-collapse caller. Full CPU SPM fallible programming,
CPU/APC/MX/clock preparation, CPR quiescence, L2 cache clean, SCM L2_OFF and warm
resume, RPM freeze/drain/context handoff and MPM wake topology remain incomplete.
The API's local context checks do not establish those global invariants. Keep
the CPR deep-suspend guard and covering SO ceiling. Do not install a low CPU
SLEEP floor while APC can remain live. Preserve the SAWv2 VCTL protocol; boot
PMIC_DATA0 is not a proven wake restore voltage.

All seven original bringup requirements remain intact, including the original
r2 display/IOMMU fault, all hardware/interactions and physical wake/soak/cold/
warm acceptance, maintained-LTS public-source packaging/update/recovery and
attributed review. Independent SLIMbus hardware-stop, PM rollback and endpoint
recovery remain open. Existing attribution is preserved. Codex generated this
source, tests, audit and draft, without a Signed-off-by. Human review and DCO
remain pending. All heads are local/unpublished and the draft is unsent.
No phone, real radio, audio, firmware, WiFi scan, Replimat3 interaction or network
configuration operation occurred. Existing-connection public downloads remain
authorized; none are needed for this checkpoint.
