# Fx0 CPU atomic register maps and current regulator port

CPU voltage transitions run in a synchronous CPU0 IPI. The new MSM8226 L2
owner and the existing SPMI PMIC parent both configured `fast_io` maps without
requesting raw spinlocks. Actual regmap selection then chose `spinlock_t`,
which can sleep on PREEMPT_RT. Correcting only the L2 owner left the PMIC
accesses in the same invalid context.

Both maps now request raw spinlocks. The current regulator port also preserves
the private raw-lock MMIO mapping for legacy SAWs from Dmitry Baryshkov's
[053c50a70525 fix](https://github.com/torvalds/linux/commit/053c50a7052549aab0d310ad505947db3e211592).
Only the explicit MSM8226 L2 master obtains the permanent map published by its
SPM owner; probe defers until that map exists. Legacy devices retain separate
private maps, and mapping errors propagate. The complete fixed-range APC
algorithm, confirmed old-voltage recovery and always-on policy remain intact.

The regulator series is based on freshly verified official for-next
`a2a6f6b0b394eda55bd3483ecafbdc8228819a98`, ending at
`fa4d0bf7b86d5b61cd1c20542584b2af918e7f1b`. Its binding and driver are separate
commits. Timothy Schmidt's original component authorship/dates are retained;
Codex performed the mapping split, current API port and qualification. Newer
allocator APIs remain intact.

The PMIC fix is separately based on official MFD for-mfd-next
`c92739a23a80f5f0a7c6f3c10aa792102d252ac4`, ending at
`fb3593ced57b48edb0a0c17cf00df7df9d80bc47`. Its verified Fixes tag identifies
the original PMIC driver introduction. The L2 fix is a follow-up to the
combined CPU feature commit, with its own verified Fixes tag; it must be
folded into the eventual standalone SPM feature series.

The combined runtime ends at `76068f3c6a4ed1b37d4c7499d7b673e1872839d7`, tree
`421695cbc5d2372f0b763daf92c05ea79a941865`, on retained runtime10
`9a45b7096c83954703f6852a948d838704fa8f63`. Exactly four paths change: SPM,
PMIC, regulator Kconfig and the regulator driver. All other paths, including
the entire architecture and binding trees used by the previous twenty-DTB
full-schema qualification, are preserved. Driver/helper/binding bytes match
the standalone regulator series. Source and review are local and unpublished.

## Evidence and scope

The actual regmap lock-selection statements and lock/unlock callbacks execute
against synthetic lock services and RT/IPI context flags. Across twenty cases,
the two original maps fail eighteen checks; fixing only the owner still fails
nine. Both corrected maps pass all 149 checks. Controls that ignore the raw
lock or disable serialization fail 27 and 12 checks. This models the kernel's
choice of callbacks; it is not a physical RT scheduling or lockdep run.

The real regulator acquisition helper passes 47 cases and 407 checks covering
two devices, missing phandles, legacy ownership, published ownership, deferred
publication, reference balance and injected mapping failures. Four controls
reject unconditional shared lookup, lost probe-defer, swallowed mapping errors
and a legacy regular-spinlock map. OF, resource mapping and hardware services
are synthetic. Address, undefined-behavior and normal leak sanitizers report
no diagnostics on the accepted models.

Existing actual-function models also exercise L2 initialization/publication
and the FTS2 selector, provider, recovery and fail-stop paths. The portable
replay runs seven methods: one L2 method and the three FTS2 methods against
both runtime and standalone regulator core source. The L2 fixture needs only
the additional `use_raw_spinlock` field in its mock config structure.

Eight native QCOM profiles compile 44 objects with LLVM 21, `W=1`,
`COMPILE_TEST=n` and no diagnostics: ARM/ARM64 combined RT and ordinary builds,
plus ARM/ARM64 RT builds on each standalone regulator and MFD base. These are
component builds, not complete RT kernels. Binding examples, lint and meta
validation pass on the fresh regulator source; the binding bytes are identical
to those already accepted by the twenty-DTB full validation.

The complete ordinary ARM kernel and all 455 modules link after integration.
Standard private `modules_install` succeeds. All 455 compressed modules pass
explicit-certificate CMS signature, ELF32 ARM, release and dependency checks;
both signature corruption controls fail. This is an incremental build using
the prior complete output. The prior exact kernel artifacts were retained
privately before rebuilding. It does not establish a clean reproducible package,
runtime ABI/loading, phone boot, installation, update or recovery acceptance.
Earlier full-build warnings remain recorded in the preceding CPU packet.

The two raw-lock fixes and runtime integration pass strict checkpatch without
ignored types. The standalone regulator port retains the four justified
exceptions for inherited voltage-unit names, per-instance operation tables,
an atomic 42-microsecond delay, and the new private header covered by the
regulator directory's maintainership. Maintainer discovery was read-only.
Codex authored the new fixes; no agent adds Signed-off-by and human DCO remains
pending. Nothing was sent to maintainers or published.

## Replay

```sh
python3 -B replay.py /tmp/fx0-cpu-atomic-regmaps-replay
```

Use a fresh output directory. Python 3, GNU patch and Clang 21 are required.
The packet verifies every hash, applies six patches at zero fuzz to the three
source snapshots, checks exact resulting bytes, runs both partial/baseline
controls, the six deliberate regressions, and all seven existing model methods.
It requires no Git, network, device or private input. Normal leak detection is
enabled. Native, schema, kernel and module checks are recorded as evidence;
the portable replay does not repeat those builds.

## Remaining bringup work

The PM and clock CPU ports still need standalone current maintainer bases, and
the SPM owner needs its standalone feature series. The fresh regulator port
depends on that owner plus the PMIC raw-lock fix for the atomic fixed-range
path. These source drafts are not accepted physical implementations by
themselves. Human review and DCO remain required.

Deep CPU suspend still needs RPM sleep-vote handoff. Physical RT/lockdep,
voltage/settling, CPU/thermal stress, standby/battery and all nonaudio hardware
interactions remain open, as does the original r2 display/IOMMU fault. The
ordinary safe CPU policy, board charging/USB/NFC definitions, prior source
qualifications, stock-restoration/layout acceptance and all seven bringup
requirements are preserved. Audio execution stays excluded. The absent SIM
affects only final cellular acceptance.

Kernel sources retain their original notices and GPL-2.0-only terms. Existing
project fixtures retain the included MIT license; the new model/replay tools
carry GPL-2.0-only identifiers. No firmware, initramfs, boot image, unit fuse
data, credentials, device record or private signing key is included.
