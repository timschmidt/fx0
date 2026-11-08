# MSM8226 CPU performance support

The restored Fx0 r50 retains one shared schedutil policy for CPUs 0–3 with
300/384/600/787.2 MHz OPPs. A bounded four-core load passes at that ceiling;
this does not establish full CPU performance. The current SoC DTS explicitly
reserves higher CPU OPPs for speed-bin support.

The live SoC inventory reports MSM8926, ID 200, revision 1.1, and a qfprom0
NVMEM provider at the corrected QFPROM region. The later compiled-recovery comparison validates the CPU raw fuse resource
and a bounded read identifies speed bin 0 / PVS version 1. An accessible
corrected provider alone was not used to guess an offset.
Do not substitute another SoC's fuse address or voltage plan.

## Reference and decoder

The Qualcomm clock-a7 driver at commit
[866b728388bc6a1d774e8433482a08f11e8245d4](https://android.googlesource.com/kernel/msm/+/866b728388bc6a1d774e8433482a08f11e8245d4/drivers/clk/msm/clock-a7.c)
explicitly matches `qcom,clock-a7-8226`. Its generic format reads primary
speed bits 2:0, validity bit 3, version bits 5:4, redundant selector bits
26:24 and redundant speed bits 29:27. Selector one chooses the redundant
copy; other selectors retain the primary copy. Invalid speed selection
falls back to zero while retaining the version. Failure to find the
resulting voltage plan triggers a separate conservative-plan fallback.

The diagnostic [decoder](../scripts/decode_msm8226_speedbin.py) implements
only this word decoding and property-name selection. It accepts a supplied
uint32 and performs no hardware access. Five tests cover validity/version,
redundant selection, unrelated bits and invalid inputs. These tests do not
prove which fuse resource the Fx0 uses.

The [clock-a7 binding](https://android.googlesource.com/kernel/msm/+/android-7.1.0_r0.2/Documentation/devicetree/bindings/arm/msm/acpuclock/clock-a7.txt)
requires a CPU supply and per-bin/version frequency-to-supply plans. The
reference driver obtains that supply before selecting a plan and changes
its vote with the clock. Some downstream plans use virtual regulator
corners; their numeric entries must not be treated as literal microvolts.
A newer clock-a7 source lacking the MSM8226 match was rejected as the sole
basis for this implementation.

## Implementation gates

1. Recover the Fx0 stock clock and APC/CPR regulator description, including
   the actual optional efuse resource and corrected/raw mapping. Validate a
   bounded read through the existing NVMEM provider only after that mapping
   is established. Preserve raw words privately.
2. Identify the unit-specific frequency/voltage or virtual-corner plans,
   regulator path and conservative fallback. Current CPU nodes lack a supply
   association, and the existing generic CPR driver does not list MSM8226.
3. Implement the required supply/performance-domain control, bin/version
   selection and OPP filtering together. Preserve the current conservative
   OPPs on missing/invalid/unsupported data. Do not enable frequencies merely
   because the PLL frequency table can generate them.
4. Test parsing and regulator/clock transition ordering and unwind paths;
   compile the affected driver/DT/bindings before an isolated boot trial.
5. Qualify each supported operating point, transitions, all-core load,
   thermal response and recovery, then suspend and peripheral coexistence.
   Keep the verified r49 package/boot rollback available.

No frequency, voltage, fuse or thermal configuration was changed by this
audit. Audio remains excluded. Card reseat coordination is independent.

## Madai vendor source follow-up

The project's pinned [Madai vendor tree](https://github.com/peremen/android-kernel-lg-madai/tree/03aba4427a7666d57b5ae06d375e259ea337f351)
provides the actual board source rather than a different MSM8226 product.
Its board DTS includes the LGE MSM8926 description, MSM8926 v1 and then the
MSM8926/8226 common files. The MSM8926 v1 ID table includes ID 200 revision
1.1, matching the live inventory. This is source applicability evidence;
the current recovery compiled CPU data now matches these plans, while
whole-image identity against the unavailable original stock backup remains
unverified.

The MSM8926 clock override declares an eight-byte raw efuse resource at
0xfc4b80b0, of which the clock driver reads the first word. This is outside
the currently exposed corrected QFPROM base at 0xfc4bc000. A later read-only raw MMIO mapping accessed four bytes at that compiled
resource and verified a matching reread; no corrected-provider offset
translation was assumed. MSM8926's version-1 plans differ
from the MSM8226 version-2 plans, so those tables must not be interchanged.

[The diagnostic plan manifest](../manifests/msm8926-cpu-corner-plans.json)
records five source plans and their virtual corner units. The stock clock
selects the first maximum-frequency entry covering a requested frequency.
For example, 300 MHz maps to corner 2 in the conservative plan, and 998.4 MHz
maps to corner 7 under speed0/v0 but corner 5 under speed0/v1. Unknown plan
properties fall back separately to speed0/v0. The helper's optional
`--frequency HZ` previews that decision without hardware access; eight tests
cover decoding, boundary mapping, fallback, and malformed plans.

The vendor CPR node is at 0xf9018000 and controls PM8226 S2 at SPMI peripheral
0x1700 through the direct SPM regulator path; it also votes the L3 MX rail.
Its voltage/PVS/quotient data and corner-frequency map are required input to
a real implementation. Mainline's SPMI regulator driver already describes
PM8226 S2 and has SAW-assisted voltage operations, but the correct APC/SAW
association and MSM8926 CPR behavior remain unimplemented/unqualified here.
No RPM S2 vote or literal-corner voltage write is a substitute.

## Compiled reference and unit fuse validation

The current recovery partition contains one libfdt-valid DTB that independently
decompiles with dtc. Its Madai model, board ID 150 and MSM8926 revision list
match the source applicability check. All five clock plans match the source
manifest exactly, and compiled supply phandles resolve CPU clock -> CPR ->
direct PM8226 S2 and MX/L3. Recovery/DTB hashes are recorded in
[comparison evidence](../evidence/2026-11-06-cpu-recovery-dtb-and-bin.json); raw
images remain private. The current recovery image was not compared with the
unavailable original backup, so this does not prove whole-image originality.

The compiled clock resource confirms raw efuse address 0xfc4b80b0. A four-byte
read-only MMIO mapping and reread agree; the decoded word is valid, uses the
primary copy, and selects speed0/version1 without fallback. Its compiled
plan's maximum is 1.1904 GHz, with virtual corner 4 at 787.2 MHz and corner 7
at 1.1904 GHz. Raw fuse bytes remain private. No higher CPU clock or voltage
was requested: closed-loop CPR and supply sequencing remain implementation
requirements, followed by isolated boot and hardware qualification.

The host [DTB inspector](../scripts/inspect_fx0_cpu_dtb.py) validates embedded
blobs with libfdt, optionally decompiles them with dtc, selects only reviewed
CPU properties and resolves supply phandles. Four tests cover embedded data,
corrupt offsets, truncation and multiple blobs; raw/extracted outputs should
remain in private directories.

## Read-only raw NVMEM foundation

A candidate kernel series now implements the native raw-read prerequisite in
`worktrees/linux-cpu-cpr` (`development/fx0-cpu-cpr`). It adds a dedicated
`qcom,msm8926-qfprom-raw` interface with one raw region, root-only/read-only
NVMEM configuration, and no writer callback. Extra memory resources are
rejected before mapping, preventing entry to the existing programming path.
The corrected provider and legacy writer behavior remain unchanged; no global
raw-read module parameter is toggled. The Madai DT adds cells for the clock/PVS
word and primary/redundant CPR rows, with no CPU performance consumer enabled.

The ARM QFPROM object and Madai DTB build. Nine contracts exercise the actual
C probe through fake resources, including raw rejection/permissions, legacy
read/write paths and errors. Seven schema tests check compiled raw/corrected
providers, invalid raw configurations and the legacy four-region schema.
Binding meta-validation, generated examples, YAML lint, separate-patch
checkpatch and exact series reproduction pass. The QFPROM driver is built-in. The r50 image now boots and its filtered raw
provider passes bounded native reads and comparison with the earlier CPU-word
capture; full CPR integration remains open. See
[candidate evidence](../evidence/2026-11-06-cpu-raw-nvmem-candidate.json) and
[series](../patches/linux-integration/msm8926-cpu-series.txt).

## APC/MX sequencing component

The next candidate patch routes CPR voltage requests through a private
regulator helper. With MX absent, it retains the existing direct APC request.
With an initialized MX handle, it raises the MX floor before APC, lowers APC
before releasing MX, and retains a raised MX vote if APC fails. Failed MX
reductions are logged while the safe higher vote is retained: APC has already
changed successfully, so reporting the whole OPP transition as failed could
induce an unwanted clock rollback. Future requests retry the deferred reduction.

An explicit bootstrap helper requires a floor covering every boot possibility
and never lowers an established vote. This avoids assuming that the existing
rounded-down initial clock corner safely characterizes boot MX requirements.
Uninitialized votes, out-of-range requests and MX floors below APC are rejected
before regulator calls. Regulator activation, handoff and locking remain the
caller's responsibility and are not implemented for MSM8926 yet.

Eighteen contracts compile the actual helper with fault-injected rails, while
the ARM CPR object and checkpatch pass. The four-patch exported series exactly
reproduces its five target files. No current compatible enables MX through
this change: MSM8926 calibration/lifecycle/binding/OPP integration and hardware
qualification remain required. See
[sequencing evidence](../evidence/2026-11-06-cpr-mx-sequencing-candidate.json).

## Secure conditional calibration prerequisite

The compiled recovery CPR configuration contains an additional rule that
requires secure firmware: row54 bits42–47 are compared with seven, and the
minimum rises to 1.14 V when the value does **not** match. Forty-four compiled
parameters are now preserved in
[the calibration manifest](../manifests/msm8926-cpr-parameters.json), including
that secure-access flag. Skipping the rule or interpreting a failed read as
valid data is not a supported initialization path.

Added a legacy-only SCM fuse-row reader using the Madai header's actual
service8/command7. It validates alignment/output, rejects other conventions,
checks transport and firmware status, and assembles two 32-bit result words
only on success. Thirteen contracts compile the actual C API with a captured
transport; ARM object and checkpatch pass. The r50 native secure read now passes with status0 and selector match1.

The complete r50 diagnostic kernel package is built and installed with
CPR/higher OPPs still disabled. The r50 source recipe passes eleven local checksums and its ten
patches reproduce eighteen changed source files; it has not been built as an
Alpine source APK. Current r49 boot/modules/package state is snapshotted and
mirrored/hash-verified on the laptop. The filtered raw provider is restricted to validated CPU/PVS and CPR windows;
protected fields use SCM. Native readback now passes; full calibration and
regulator/performance-domain lifecycle integration remain open. See
[secure API evidence](../evidence/2026-11-06-cpr-secure-fuse-api-candidate.json).

## Raw-access boundary follow-up

The candidate raw provider now uses NVMEM keepouts to expose only CPU/PVS
row22 and CPR rows138/139. All other offsets return zero-filled redactions
without touching MMIO, including the secure conditional row. These redactions
are not fuse values and must not be used instead of the secure SCM rule.
The actual NVMEM core routine and actual candidate match-data table pass
28,577 bounded-range contracts: a full 4 KiB read issues only two hardware
callbacks totaling 24 bytes, and the protected row causes none. Existing probe
contracts, source-recipe reproduction and checkpatch pass.

The full build was intentionally interrupted to apply this source correction
and resumed incrementally with the same signing key and recipe-aligned build
number. The package and first native boot/read trial now pass; the clean post-pilot
reboot and bounded raw/quaternion/SMD-retention RTC checks also pass with zero
taint and no MDP5 underruns. Historical r49 motion-wake
qualification does not qualify r50. See
[keepout evidence](../evidence/2026-11-06-cpu-raw-keepouts.json).

## r50 native calibration read pilot

The signed package verifies all545 payload files and464 module signatures
against the preserved original certificate. Installation preserves the lk2nd
prefix and partition tail with exact boot readback; the original r49 rollback
remains available. Build51 boots with zero taint. The new raw provider is
root-only0400, reads CPU/PVS and both CPR rows consistently, and matches the
prior bounded CPU MMIO capture. The protected conditional row returns only
a redaction. The separate secure pilot reports status0 and selector match1,
so the compiled mismatch-only1140000uV minimum rule is inactive for this unit.
Raw bytes remain private. Expected external-module taint4096 is recorded and
requires reboot before zero-taint qualification. CPU policy remains schedutil
300–787.2MHz; CPR is disabled. See
[native evidence](../evidence/2026-11-06-cpu-calibration-r50-native.json).

## Calibration decoder and fixed PMIC range

An unpackaged C helper now decodes Madai’s three fuse corners and virtual
quotient adjustments. It preserves distinct clock/CPR speed selectors and
PVS redundancy, original-row control bits when redundant CPR data is chosen,
conditional minimum and uplift ordering, the32-bin PVS table, turbo ceiling
expansion, invalid-fuse disabling and MHz-truncated interpolation. Read errors
leave output unchanged. Adjusted quotients exceeding the12-bit hardware field
are rejected for closed-loop use, avoiding wraparound. The helper performs
no MMIO, rail vote, clock change or driver activation.

Five host tests cover4060 decoded vectors and six error contracts against
the compiled parameter arrays and vendor sequence; an ARM object also builds.
The header passes checkpatch; the exported patch has only the generic
new-file MAINTAINERS reminder, with the ownership entry included. The patch
reproduces both files exactly. The installed r50 package contains the earlier
five foundation patches, not this follow-up.

This unit decodes PVS21/version1, primary CPU/PVS and CPR copies, speed0,
quotients798/931/1188 and oscillator2 for each fuse corner. Nominal initial
voltages are1075000/1075000/1140000uV, with quotient scaling637 and virtual
corner5/6 adjustments122/61. Those are calibration data, not applied voltages.
A bounded read of six PMIC registers and matching reread identifies S2 as
FTS2, fixed boot range1, setpoint115, or1150000uV. Taint remains0.

The pinned vendor SPM regulator forbids changing the range after power-on.
Range1 uses10000uV steps and rounds upward; the existing mainline SAW setter
rejects range1 and its callback does not propagate a failed poll/read. This
requires a proper fixed-range implementation, timeout/error handling and
settling before CPR is connected. Nominal1075000uV must map to1080000uV in
range1; rail voting must cover the actual selected APC voltage. Do not
blindly feed nominal values to the exact-voltage helper or switch ranges.
See [decoder and APC evidence](../evidence/2026-11-06-msm8926-calibration-decoder-candidate.json).

## Fixed-range SAW driver candidate

An unpackaged opt-in `qcom,saw-fixed-range` path now handles PM8226 S2
without changing its power-on range. It validates the FTS2 and SAW identities,
initialized L2 master configuration, AVS ownership, range, mode and slew
control. Unconfigured L2 ownership defers probing; unexpected configuration
or active hardware AVS is rejected. SAW maps, operation tables and range
data belong to each regulator. The legacy range 0 transaction remains separate.

The fixed path maps only its selected range, propagates getter/read/write,
SMP and acknowledgement timeout errors, and executes VCTL on CPU 0 using
port 0 without altering PMIC data slots. Rising AUTO transitions use PWM and
the vendor slew margin before restoring mode. A failed mode restore after
confirmed voltage success is reported and retried while keeping the voltage
transition successful, avoiding an unsafe clock rollback against changed APC.
Unknown command outcomes still require reconciliation in the CPR/OPP consumer.

Two C harnesses execute the actual helper, provider mapping/getter and SMP
dispatch code. They cover 514 selector candidates, 321 valid roundtrips,
11 initialization read faults and10 transaction I/O faults. Eight compiled
DT/schema cases cover the opt-in and legacy nodes; binding meta/examples/lint
and ARM driver compilation with W=1 pass. Binding checkpatch is clean; two
driver warnings are documented (necessary mutable per-instance ops and a
generic new-file ownership reminder). Exports reproduce all three files.
Host polling fixtures do not qualify real timing or analog settling.

Read-only L2 SAW inventory on r50 confirms major version 2, PMIC arbiter present,
AVS disabled, but CFG, VCTL and PMIC data slots are zero. The stock compiled
Madai L2 master specifies CFG `0x14`, DATA0 `0x02030080` and DATA1 `0x00030000`. The
SPM owner must initialize and expose that controller before this provider
is enabled; no new DT opt-in, voltage command or package installation has
occurred. CPU limits remain 300–787.2MHz, taint 0. Full calibration quantization,
rail/domain lifecycle and hardware qualification remain open. See
[fixed-range candidate evidence](../evidence/2026-11-06-pm8226-saw-fixed-range-candidate.json).

## Failed r51 L2 owner boot trial

The r51 candidate adds a Madai L2 owner that validates an idle controller,
configures delay/data before CFG, checks readback and then publishes its
permanent regmap. Eighteen initialization I/O failure points, partial retries,
4096-address access-policy checks and eight schema cases pass. The compiled
Madai DT links S2 to that owner and marks the CPU rail always-on. The source
recipe verifies17 local checksums and16 patches reproducing27 files; the full
host build,464 module signatures,545 APK payload files and boot readback pass.

**The native boot failed into Qualcomm9008 emergency-download mode.** Those
host checks do not qualify the power-controller implementation. The failure
point and cause are unknown; no new kernel log, provider readback or voltage
transition result was retrieved. r51 is quarantined and must not be deployed
as working support. The r50 boot image and full installed-state rollback are
verified on both phone and laptop. All464 module files are identical, allowing
the verified r50 RAM image to use the installed root for recovery. Physical
fastboot entry is pending; no compatible EDL loader is available.

A source audit found inherited generic PMIC gate callbacks on fixed S2. The
core invokes enable during always-on registration if reached, while the vendor
SAW provider uses logical online state and voltage requests instead. Whether
that callback caused a hardware write or the boot failure is unproven. A
separate unpackaged correction removes enable/disable/is-enabled hooks for
this always-on rail and requires the DT constraint. Tests execute the actual
provider ops builder and kernel core enable dispatcher, proving that fixed
S2 avoids the generic gate while legacy rails retain it. Two C harnesses,
nine binding cases, ARM W=1 compilation and binding checks pass. The correction
has not been booted. Restore r50 first, then isolate owner initialization and
S2 registration with RAM-only trials before any persistent installation.
See [failure and follow-up evidence](../evidence/2026-11-07-l2-master-r51.json).

## Offline APC/MX voltage planning

The new unpackaged `cpr-msm8926-voltage.h` computes mapped voltages from the
nominal calibration and regulator metadata. It calls only count/list/step
queries. It never enables a rail or sets voltage, and has no live CPR consumer.
Floors, initial values and ceilings must map to exact FTS2 points; missing
points cause failure rather than a higher substitute. Rounded ceilings must
stay within the nominal global APC ceiling. L3 votes use the verified
750 mV + n*12.5 mV grid and must cover actual mapped APC ceilings within the
1.3375 V limit. Initial MX also covers the actual boot APC read, even when
that voltage is above the selected plan’s ceiling. Failed boot-voltage reads
and provider metadata errors propagate with output unchanged.

For the previously captured unit data, the range 1 model produces APC
floors 1080/1080/1130mV, ceilings 1080/1180/1280mV and initial values
1080/1080/1140mV. Corresponding MX floors are 1087.5/1187.5/1287.5mV; a
1150mV boot read requires a 1287.5mV initial MX floor covering the whole plan.
These are computed values using old capture data, not current measurements.
The compiled 1280mV ceiling cannot be represented in fixed range 0; this
planner rejects that configuration instead of silently weakening calibration.

Six tests cover 512 bin/rule/range combinations and inject errors at all 1608
provider metadata call positions for the range 1 fixture, plus holes, bounds,
missing handles and failed boot reads. A synthetic representable range 0 plan
also passes. ARM W=1 object compilation and header checkpatch pass. The
export reproduces the helper exactly. No new kernel package or phone trial
was produced. The phone remains in Qualcomm 9008 awaiting physical fastboot
entry for r50 recovery. See
[offline planner evidence](../evidence/2026-11-07-msm8926-voltage-plan-candidate.json).

The vendor `pm8226_l3_ao` supply is an **active-only** RPM voter: its
`qcom,set = <1>` selects bit0 (active) and omits bit1 (sleep) in the pinned
RPM driver. The mainline SMD regulator driver likewise sends active-state
requests. The suffix does not establish an always-on constraint. Activation,
suspend handoff and vote lifetime still need explicit CPR integration.

## Reconnected r51 boot and verified r50 restoration

After the owner reconnected the phone, r51 build 52 booted with zero taint.
The L2 owner was bound, its delay/data/CFG registers matched the reference,
VCTL and PMIC status remained zero, and the programmed APC target was still
1150000uV in range1/PWM. The named S2 provider and 300–787.2MHz policy were
present. This is one successful bootstrap observation, not repeatable boot
or voltage-transition qualification. The initial download-mode failure may
have happened during shutdown, bootloader handoff or kernel startup; no
pstore files were available to identify the stage.

Restored the exact r50 snapshot via SSH, using the installed apk’s supported
local-file downgrade syntax. An initial unsupported option failed before
package/boot mutation and was corrected after help and simulation checks.
All restored files were verified against the archive. Boot payload/tail
readback matches the saved 32 MiB snapshot; the 512 KiB lk2nd prefix was never
written. A normal reboot now runs r50 build 51 with taint 0. The APC target
remains 1150mV, CPU limits remain unchanged, the L2 register state returned
to pre-trial zeros, raw sensors work and no MDP5 underruns were logged.
No suspend/audio/voltage transition test ran during this recovery. See
[restoration evidence](../evidence/2026-11-07-r50-restored-after-r51.json).

## MX bootstrap activation candidate

The SMD regulator caches voltage requests while disabled. The CPR voltage
helper now tracks a successful MX enable separately from its requested floor,
enables MX after establishing the boot floor, and rejects APC transitions until
activation succeeds. Failed activation retains the requested floor for retry;
repeated bootstrap neither lowers the floor nor adds enable references. No
automatic disable is provided while the always-on APC rail can remain live.

The actual C helper passes sequencing and fault-injected activation tests,
including a disabled-provider cache model, retry and idempotence. ARM W=1 CPR
object compilation and all six planner tests pass. This is an unpackaged
follow-up, with no live consumer or phone voltage trial. CPR attachment,
error-unwind lifetime and suspend handoff remain open. The restored r50 phone
is reachable over SSH with zero taint and the 787.2MHz ceiling. Audio remains
excluded and host built-in Wi-Fi was untouched. See
[activation evidence](../evidence/2026-11-07-cpr-mx-activation-candidate.json).

## CPR attachment retry prerequisite

The generic CPR attachment callback recorded the first CPU before its corner,
controller and ACC initialization succeeded. A retry could therefore return
success without finishing setup. It now passes the candidate CPU explicitly to
corner initialization and records the attachment only after every stage passes.
ACC configuration and enable errors are propagated rather than ignored.

An actual-callback C harness injects ten initialization failures, retries each
and verifies completion, then checks subsequent CPU attachment is idempotent.
The CPR voltage harness, ARM W=1 object compilation and checkpatch pass. This
is CPU-series patch 16, unpackaged and uninstalled; it does not establish
hardware rollback or finish Fx0 calibration/OPP and suspend integration. See
[attachment evidence](../evidence/2026-11-07-cpr-attach-retry-candidate.json).

## Vendor clock-to-CPR corner mapper

Added a metadata mapper that selects the first covering vendor clock fmax
entry, preserving speed0/v0 fallback when a clock bin/version table is absent.
It returns virtual and fuse corners, adjusted quotient, oscillator and
quantized APC/MX limits without accessing hardware. Clock speed-bin selection
remains independent of the CPR fuse speed bin. The caller must still validate
the clock's supported rates before installing OPPs.

All five reference tables were rechecked against the pinned vendor source and
its SHA256. C tests cover all eight clock bins and four versions at every table
boundary, low rates, excessive frequencies and invalid metadata; failed calls
preserve output. All 13 calibration/mapper/planner tests and ARM W=1 object
compilation pass. This is CPU-series patch 17, unpackaged and uninstalled.
The CPR domain consumer, OPP installation, MX lifetime and suspend handoff
remain incomplete. See [mapper evidence](../evidence/2026-11-07-msm8926-corner-map-candidate.json).

## Full-row calibration acquisition (November 8)

The next source-only helper joins NVMEM acquisition to the existing nominal
decoder. It reads protected row54 through the legacy SCM service and reads
raw rows22/138/139 through three named NVMEM cells. Every raw cell must return
exactly eight bytes. The earlier four-byte CPU cell covered clock/PVS decoding
but omitted bit53, which selects the manufacturer's uplift rule. The candidate
DT now exposes the full eight-byte CPU row, within the existing raw keepout
boundary. The installed r50 DT has not changed.

Acquisition errors leave calibration output untouched. Cell references are
released on all read outcomes, and successful read buffers are freed with
`kfree_sensitive()`. An unavailable secure service remains an error rather than
an inferred selector. The future consumer must provide cell names
`cpu_calibration`, `cpr_primary` and `cpr_redundant`, each mapping a complete,
unshifted raw row. No compatible match, regulator activation or higher OPP is
enabled by this helper.

All 46 CPU foundation tests pass with no skips, including SCM/NVMEM fault
injection and 18 malformed cell lengths. The emitted ARM loader object, generic
CPR object and Madai DTB compile with W=1; the DTB retains three earlier warnings.
The full processed schema validates the candidate provider and existing legacy
cases. Patch reproduction is byte-exact. Binding tests accept `FX0_CPU_BUILD`
to select the actual compiled tree and `FX0_DT_SCHEMA_CACHE` to select its
processed schema; use the dtschema environment's Python to avoid silently
skipping schema checks. See [acquisition evidence](../evidence/2026-11-08-msm8926-calibration-load-candidate.json).

The CPU validation checkout was recovered from local commit
`bdc0b5c00e7bcaa3375a394a9b376d391e4972fd` plus all preceding exported CPU
patches. It is not a complete source reproduction of the installed r50 image
and must not be packaged as its replacement. The remaining implementation is
the CPR probe/domain/OPP consumer, rail lifetime and suspend handoff, followed
by RAM-only bootstrap and hardware qualification.

The restored r50 separately passes five USB-powered RTC suspend controls:
11.69–12.49 seconds of traced s2idle per cycle, RTC IRQ +1, IMU IRQ +0, retained
DMP execution and 373 recovered quaternion samples. No MDP5 underrun or taint
appeared. CPU limits remain 300–787.2MHz, sensor proxy is active, SMD/buffer
are off, IMU wake is disabled and RTC is clear. The owner confirmed display
and touch before these tests. These are RTC controls, not physical DMP wakes
or battery/overall reliability acceptance. See [native regression evidence](../evidence/2026-11-08-r50-rtc-regression.json).

## CPR probe and performance-domain bridge (November 8)

The next two exported patches connect calibration to the CPR driver rather
than leaving it in an independent helper. The new MSM8926 probe reads the
three complete raw rows and secure conditional selector, queries the fixed
APC range and MX provider, and constructs quantized fuse corners. It does not
reuse QCS404's signed voltage-fuse format or ACC register settings.

Attachment constructs one corner per required CPU OPP. It checks consecutive
levels, increasing frequencies, exact clock rounding, vendor fmax eligibility
and matching fuse-corner declarations. Invalid clock/feedback calibration
cannot authorize operation above 787.2MHz. Every OPP reference is released on
errors. The initial clock must have a listed corner; its voltage is never
inferred from a rounded-down frequency. After all setup succeeds, attachment
establishes an MX floor covering the measured boot APC target and all planned
ceilings, takes idempotent APC/MX references and publishes the attachment.

The domain is marked always-on and initialized as logically on, as genpd
requires for that flag. Its builtin-only option defaults off and requires
builtin CPR and SCM; manual bind/unbind is suppressed. Domain-off retains
both votes because the CPU supply remains live. Feedback starts only after
a successful nominal voltage request. Errors quiesce feedback. Suspend-to-idle
quiesces the controller, and resume waits for a fresh nominal request before
feedback resumes. Deeper PM is explicitly rejected until RPM sleep-state
voting exists. These are implemented paths, not physical PM qualification.

All 54 CPU tests pass without skips, including the actual driver initialization,
corner construction, 16 attachment failure/retry cases, performance/PM ordering
and six new binding cases. ARM W=1 builds pass with MSM8926 enabled and disabled;
only the enabled object references the new SCM fuse API. Binding meta-validation,
lint and the example build pass. Both exported patches reproduce the three
changed kernel files exactly. See [domain evidence](../evidence/2026-11-08-msm8926-cpr-domain-candidate.json).

No board consumer, CPUfreq attachment, higher OPP, package or native trial is
added. The subsequent recovery series below addresses failed writes across
the caller/provider fault model. Before enabling this driver, complete CPUfreq
domain attachment and speed-bin/PVS filtering, reconstruct the complete current
DMP/display integration, and qualify recovery physically. The local CPU
validation tree is not a replacement for restored r50. Full voltage/frequency,
thermal, PM and peripheral acceptance remains open.

## Transactional voltage recovery and RPM reply matching

A host test now reproduces the failure using the actual OPP, genpd and CPR
callbacks. A downward clock change succeeds, an APC write lowers the voltage
but returns an error, and OPP/genpd retain their prior performance state.
A subsequent intermediate or original-frequency request can then raise the
clock using that stale state. The old provider produces four unsafe clock
increases in four negative-control cases. The patched provider produces zero
in eight cases, including post-command verification failures.

The fixed-range SAW provider now restores the old physical selector directly
before returning a failed voltage command. It resets the uncertain command,
forces PWM for possible upward recovery, waits for the selector and idle PMIC
state, allows slew/mode settling, and rereads the PMIC range and selector.
Direct SAW submission avoids regulator request caching. It retries restoration
once. Two failed restoration attempts stop the kernel, preventing further clock
changes at an unknown voltage. A mode-only failure after confirmed voltage can
retain PWM and defer AUTO restoration.

MX voting has the same uncertainty: a failed RPM request may already have
lowered the dependency rail. The CPR helper now forces the prior consumer vote
through the kernel's `regulator_sync_voltage()` and actual RPM voltage callback
before retaining a supposedly higher MX floor. It also retries once and stops
the kernel if restoration cannot be confirmed. Restored votes let a later APC
increase rely on the cached floor safely in the tested model.

That restoration requires trustworthy RPM acknowledgements. The SMD RPM
transport previously ignored response IDs and reused completion state, allowing
a late reply to satisfy a newer request. It now allocates per-channel IDs,
publishes/retires the pending ID under an IRQ-safe lock, reinitializes completion
for each request, validates bounded unaligned TLVs and accepts only the matching
reply. Completion occurs under the same lock so timeout retirement cannot race
a reply into the next request. NACK, duplicate, stale, malformed and unbound
responses have explicit tests.

CPR restores feedback for the confirmed old corner after a recoverable
performance-request failure. This supersedes the earlier unconditional error
quiescing: genpd can retain that corner and skip a repeated request, so leaving
an adapted high-frequency voltage without feedback would be incorrect. An
initial failed nominal request still does not enable feedback, and system PM
still requires a fresh nominal request after resume.

All 58 targeted CPU/regulator/RPM tests pass with no skips. Coverage includes
248 before/after-effect I/O cases, 12 recovery retries, 12 persistent-failure
no-return controls, actual regulator-sync/RPM callbacks, and 111,537 packet
cases ending at a protected memory page. ARM W=1 builds pass for the regulator,
SMD RPM and CPR objects. All 24 CPU patches reproduce their 23 changed source
files exactly. See [recovery evidence](../evidence/2026-11-08-cpu-voltage-recovery-candidate.json).

These tests use modeled I/O and do not establish actual rail voltage, analog
settling, SAW reset behavior or RPM firmware recovery. No native fault injection,
kernel/package installation or CPU-limit change occurred. CPUfreq/bin filtering,
complete-source reconstruction and RAM-only hardware qualification remain the
next implementation/deployment gates. The installed phone stays on r50.


## CPUfreq attachment and separate qualification DTB (2026-11-08)

CPU-series entries 25–27 now connect the MSM8926 CPR supplier to
`qcom-cpufreq-nvmem`. The supplier validates calibration, the complete quantized
rail plan and exact clock rounding before exporting one immutable frequency
mask. Both its domain OPP table and every CPU receive that mask before table
parsing or domain attachment. This avoids CPU OPP references to filtered-out
CPR states. Consecutive domain levels must match the canonical frequency prefix.

The masks describe 4/7/10/12/14 eligible rates across the vendor clock plans.
Invalid clock-valid or disabled-feedback flags restrict the table to the
existing four rates; unused feedback metadata is cleared. Hard calibration,
provider or unrepresentable-plan errors still fail or defer. They do not create
an invented four-rate voltage plan. The unit's earlier native calibration
implies a seven-rate host plan through 1.1904 GHz, which remains unqualified on
hardware.

CPU attachment uses temporary virtual devices, whose managed resources are
released by device deletion even if a reference to the device remains. The
new provider therefore owns its CPU clock handle for its lifetime, and shared
plan publication uses a boolean rather than retaining a virtual-device pointer.
Probe failures unwind each CPU's OPP configuration and domain attachment;
completed shared initialization survives a retry.

The vendor audit also identifies the physical CPR reference selector at
APCS+0x64: bit 0 must be zero for 19.2 MHz XO. Supplying an XO phandle alone does
not verify that selection. The new `qcom,apcs-syscon` readback guard rejects AHB
or read errors before provider publication and on configuration/resume. It
changes no selector bits. Resume failure keeps the domain suspended and
feedback unarmed.

The new CPU OPP type is `operating-points-v2-msm8926-cpu`. Ordinary MSM8926
boards retain generic cpufreq-dt; only this explicit type routes through the
calibrated driver and suppresses early generic registration. The separate
`qcom-msm8926-lg-madai-cpr.dtb` describes all 14 canonical CPU rates and 14 CPR
states, with identical one-bit masks and matching required-OPP links. All four
CPUs share that table/domain. SPI15/rising, APC/S2, MX/L3 and the complete raw
rows follow the pinned vendor/reference wiring. The ordinary board DTS bytes
are unchanged by these three patches.

All 71 targeted tests pass with no skips, including actual supplier/probe/remove,
registration-order, unwind/retry and platform-routing paths. Both ARM option
configurations compile the three affected objects; export/consumer and disabled
stub symbols match. Binding meta-validation, lint, examples and the compiled
candidate's selected schemas pass. The candidate inherits three existing
common-DTS warnings. All 27 CPU patches reproduce 31 changed source files byte
for byte. Checkpatch reports no errors/checks with existing uV naming ignored;
its generic new-file ownership reminders have been reviewed.
See [candidate evidence](../evidence/2026-11-08-msm8926-cpufreq-candidate.json).

This remains a subsystem validation checkout with unqualified L2/S2 integration,
not a reproduction of the complete installed r50 DMP/display source. No package
or boot payload changed. Read-only SSH still finds the same restored r50 boot,
taint 0, no failed services and 300–787.2 MHz. The next gate is complete-source
reconstruction and controlled RAM-only bootstrap/recovery, followed by actual
rail/feedback, supported-OPP, thermal, suspend and peripheral qualification.
Deeper PM remains rejected until RPM sleep-state voting is implemented.


## Complete-source reconstruction (2026-11-08)

The complete r50/CPU source reconstruction gate now has host evidence. The
pinned pre-DMP base plus ten patches reproduces the installed r50 DTB exactly.
The separate 32-patch candidate restores the same idle/peripheral base and
matches all 31 CPU-series files; all 41 source changes are accounted for.
Both complete Clang/CFI kernels link with LLD 18.1.8 and build 464 modules.
All 928 staged module signatures verify against their explicit kernel
certificates, including corruption/wrong-build rejection controls. The 109
combined source tests and three image-placement tests pass.

A checked r50-source RAM baseline now passes two physical boots and returns
to the unchanged installed r50. The second captures the timed return at
181.641642 kernel seconds and 22 HTTP status/log samples, with taint zero and
four online CPUs. Its moduleless image leaves `CPUFREQ_DT=m` unloaded.
CCF reports the inherited CPU clock as 800 MHz, outside the canonical table.
The actual `cpr_find_initial_corner()` host harness confirms that the current
MSM8926 driver rejects this rate before MX/APC bootstrap. This predicts an
attachment failure; no CPR candidate has yet booted and no analog frequency
measurement is claimed. Do not merely label 800 MHz as the 787.2 MHz corner:
OPP direction and cached state must agree with the actual clock handoff.

The next implementation gate is a safe startup clock handoff with feedback
disabled and a confirmed rail floor, including the clock notifier and
failures/retries. The notifier programs source 4, divider 3: the RAM log's
600 MHz GPLL0 produces 300 MHz (`600 * 2 / (3 + 1)`), despite its generic
400 MHz comment. The vendor `clock-a7.c` likewise names 300 MHz as its safe
frequency. CCF's `clk_change_rate()` ignores the return from the provider's
set-rate callbacks; a successful `clk_set_rate()` alone therefore cannot
authorize lowering APC. The final implementation must verify hardware clock
state and retain voltage/floors on an uncertain result. No normalization or
clock-error fix has been applied to the current candidate checkpoint.
Source packaging, staged L2/S2/CPR bootstrap,
actual rail/OPP/thermal/suspend and peripheral qualification remain open.
See [RAM evidence](../evidence/2026-11-08-r50-ram-baseline.json),
[rebuild evidence](../evidence/2026-11-08-kernel-reconstruction.json) and
[reproduction procedure](building.md#reconstruct-r50-and-the-cpucpr-source-candidate).

## Startup-clock handoff draft (2026-11-08)

A separate 35-patch source draft adds the auxiliary clock dependency and
implements the startup part of the handoff above. It preserves boot APC's
programmed target while activating the MX floor and one logical APC reference,
then requests the lowest 300 MHz OPP. It verifies two stable APCS command/config
samples for source 4/HID 3, the 600 MHz auxiliary clock and CCF's 300 MHz result
before initial-corner lookup. It rejects an inherited rate below 300 MHz or a
boot target below that OPP's nominal voltage/above the prepared MX floor.
These checks are controller readback, not analog frequency or voltage measurements.

Host tests execute the actual helper, supplier initialization and attach callback.
They cover 24 handoff faults, seven attachment failures, partial activation,
retry/idempotency and cached-success/hardware-mismatch rejection. Removing the
mux signature check or boot-voltage floor makes the executing C harness fail.
All 16 targeted source/binding/compiled-DTB tests pass, as does the ARM W=1 CPR
object. Binding/driver/DT patches are split; checkpatch reports no errors,
warnings or checks with inherited uV naming ignored. All 41 files reproduce
from the pinned base plus 35 patches. The earlier 32-patch source/build and
installed r50 remain unchanged.

This draft does not yet handle runtime clock-programming failures. A fresh
hardware clock check before voltage reduction remains necessary because CCF
can discard provider errors and PLL-rate caches can be stale. Complete that
guard, full kernel/module linkage and staged RAM controller/recovery tests
before enabling CPR or higher OPPs. No hardware trial or analog rail/feedback
qualification follows from these host checks.
See [startup evidence](../evidence/2026-11-08-msm8926-startup-clock-candidate.json)
and the [build procedure](building.md#startup-clock-source-draft).

## Runtime clock-error guard (2026-11-08)

The separate 39-patch runtime candidate now implements the next source gate.
CPR obtains its own CPU-PLL reference and refreshes both PLL parents before
an uncached CPU mux query. Each voltage change, including feedback IRQ changes,
rejects a zero/unknown clock or an actual reported rate above the requested
corner. This prevents a failed downclock from authorizing a lower APC target.

The clock-provider audit also finds errors that cannot safely return to CCF:
it may select a PLL after a failed enable/lock or release the old PLL after a
failed mux switch. On MSM8226, CPU PLL/mux programming errors therefore panic
before CCF can continue. Successful rate writes require PLL-rate readback;
enable requires mode/lock readback; mux programming requires settled CMD/CFG
readback. Ordinary PLL/mux reads fail with a zero rate on I/O/unstable state
instead of using uninitialized values. PLL rate arithmetic avoids ARM32
truncation. Uncached rate flags and strict failure behavior are selected by
the actual MSM8226 provider probes; the legacy probe policy remains unchanged.

All 114 selected tests pass against this source with no skips. Executing actual
kernel functions covers 76 PLL I/O faults, 25 mux I/O/unstable-state controls,
28 CPR query I/O faults, timeout/lost-write controls, stale caches/topology and
the startup path. Five unsafe mutations are rejected at execution. The six
changed ARM objects and both DTBs build; all 48 files reproduce from the pinned
base plus 39 patches. The complete kernel/module build now passes. All 464
staged module signatures match the certificate embedded in the kernel, and
corruption/wrong-build controls fail as required. A 64-bit division identified
in the ARM object was changed to `do_div()` before successful full linkage;
the resulting PLL object has no unavailable `__aeabi_uldivmod` dependency.
The earlier
checkpoints and installed r50 are unchanged.

Hardware frequency/voltage/feedback, fail-stop recovery and higher OPPs remain
unqualified. The checked moduleless L2/S2 image uses the ordinary DTB, with
CPR absent, before a separate CPR-bootstrap trial. A current read-only native
r50 preflight reaches running systemd startup with Sway, unchanged limits/hash
and taint zero. Its stable APCS CMD=0x2/CFG=0x501 and PLL MODE=0x7/STATUS=0x10001
confirm the command and PLL-lock bit layout while the existing governor runs;
they do not qualify the new controller. Next perform staged moduleless RAM
bootstrap/recovery, followed by controlled CPUfreq/governor trials. None of
these host models proves analog timing or settling.
See [runtime evidence](../evidence/2026-11-08-msm8926-runtime-clock-candidate.json).

## First L2/S2 RAM bootstrap and return (2026-11-08)

The 39-patch kernel now boots the ordinary DTB in a moduleless RAM environment.
All four CPUs are online with taint zero; the L2 master at f9012000 binds to
qcom_spm, the APC provider reports its 1.15 V programmed boot target, and CPU0
reports cpu-spc idle with 344 uses at the initial snapshot. CCF reports the
inherited 800 MHz CPU clock. No CPUfreq module, governor or CPR node is active.
These are controller/framework observations rather than analog measurements.

Serial logs and 22 HTTP status/dmesg pairs capture the 180-second return timer
at 181.611751 kernel seconds. The fresh r50 return has the same boot-partition
hash, four conservative rates, taint zero, Sway and sensor proxy. Host routes
and resolver match before, and the temporary USB profile is removed. Physical
display/touch confirmation for this return is pending. A later read-only check
of the same boot reaches running systemd startup, with no failed services or
pending jobs. The
earlier r51 EDL event remains unexplained; this one RAM result does not clear
persistent installation or broader reliability gates.

An input-dependent lk2nd USB download stall initially prevents transferring
the default image. A 32 KiB block reproduces without booting any kernel.
Gzip level 1 preserves the exact kernel/DTB and unpacked initramfs, verifies
full RAM readback and permits this boot. The USB root cause remains open.
The next CPU gate is a separate moduleless CPR startup/clock-normalization/MX
floor trial, followed by governor-controlled CPUfreq and actual rail/feedback,
thermal, suspend and peripheral qualification. See
[native evidence](../evidence/2026-11-08-l2-s2-ram-bootstrap.json).

The separate CPR-bootstrap RAM image is now prepared and host-verified, but
unbooted. It retains the exact successful diagnostic initramfs and command line,
uses the built qualification DTB, includes no modules or CPUfreq governor, and
has no CPU-level default performance-state request. Built-in calibration domain
attachment is intended to exercise the boot clock normalization and MX floor
before any CPUfreq policy exists. These remain source-reviewed expectations
until a native trial verifies them. See
[preparation evidence](../evidence/2026-11-08-cpr-bootstrap-preparation.json).

## Distribution source-package checkpoint (2026-11-08)

The complete 39-patch source now builds through pmbootstrap/abuild in an
isolated Alpine 3.24 container with Clang 22.1.3. All 48 prepared source files
match the frozen host candidate. The normalized recipe explicitly runs
olddefconfig; its actual community configuration, signed r54 APK, recipe commit,
kernel and both DTBs verify. All 464 module signatures match the exact
certificate embedded in vmlinux; modified payload/signature/metadata and a
different build's certificate reject. The five undefined symbols match the
accepted r50 baseline, with none introduced. Offline package simulation passes
only in the initialized usermode workspace database.

This closes the candidate's distribution source-build gap, while installed
update/recovery and native qualification remain open. The package is unbooted
and uninstalled; existing L2 RAM evidence belongs to the Fedora-Clang build.
The phone remains on the same installed r50 boot, taint zero, running systemd,
Sway and sensor proxy, four conservative rates and unchanged boot hash. The
reviewable source/config/recipe branch remains local after automatic approval
review rejected its GitHub push; explicit publication approval is pending. See
[package evidence](../evidence/2026-11-08-runtime-kernel-source-package.json).

## First CPR RAM startup failure (2026-11-08)

The checked qualification image stages and reads back in 5.63 s. One RAM boot
reaches diagnostic USB, four CPUs and taint zero, but CPR probe returns -EINVAL
under the broad calibration message. The provider remains unbound, its CPU
calibration supplier defers and no CPUfreq policy loads. CCF reports the
inherited 800 MHz and APC its 1.15 V programmed target; this does not pass
the 300 MHz/MX/domain bootstrap gate. No raw calibration or analog voltage
measurement is published.

Twenty-two HTTP status/log pairs and serial capture the return timer at
181.623794 kernel seconds. The new r50 boot is running with no failed services,
Sway, sensor proxy, four rates/schedutil and the unchanged boot hash. The owner
confirms display/touch on this latest return. The temporary USB profile is
deleted and host routes/resolver match before. No persistent candidate install
or deliberate higher OPP occurs. See
[first trial evidence](../evidence/2026-11-08-cpr-bootstrap-first-ram.json).

The initial message does not identify the failing stage. A separate diagnostic source adds
context to fuse access, reference-source checks, voltage planning, eligibility
and parent-clock failures without changing their return values or relaxing a
guard. All 116 selected checks, its ARM CPR object, checkpatch and 40-patch
tree replay pass; its built-in RAM kernel links and boots once. The test fixtures add
only logging-return/header stubs, with prior versions archived and referenced
explicitly. See
[diagnostic preparation](../evidence/2026-11-08-cpr-probe-diagnostics-preparation.json).

That diagnostic identifies the CPR reference-source check returning -EINVAL.
An independent read-only native read of 0xf9011064 returns 1. The stock driver
defines bit0=1 as AHB, bit0=0 as 19.2 MHz XO, and explicitly selects XO before
CPR configuration. An XO phandle alone leaves the hardware selection inherited.
The next work is owned XO selection with CPR stopped and verified readback;
the read guard remains required. The native word is read after recovery, not
presented as an independent RAM register snapshot.

HTTP captures 22 status/log pairs after the serial open hits a host udev
permission race. Archived pstore recovers the own-kernel identity, exact stage
failure and timer message at 181.601496 seconds. The newest r50 boot is running,
taint zero, original hash/four rates, with Sway/sensor proxy and owner-confirmed
display/touch. Host networking restores. Missing RAM taint/clock/voltage fields
are left unmeasured. See
[reference diagnosis](../evidence/2026-11-08-cpr-reference-first-diagnostic.json).

### XO handoff reaches the moduleless startup gate

The first owned-XO candidate stops IRQ/CTL and waits for RESULT_0.BUSY before
selection. Its RAM trial returns -ETIMEDOUT: BUSY remains set with the controls
cleared. The stock driver does not impose this wait, and both stock/upstream
IRQ handlers consult BUSY only after checking LOOP_EN. The preserved
[41-patch trial](../evidence/2026-11-08-cpr-xo-handoff.json) returns to unchanged
r50 at 181.597437 seconds, with owner-confirmed display/touch.

The separate 42-patch follow-up verifies disabled IRQ/CTL both before and after
masked XO selection and keeps the selector readback guard. Its full ARM link,
independent patch replay, 118 selected checks, W=1 object and checkpatch pass.
One moduleless RAM boot initializes CPR with seven eligible OPPs and binds all
four virtual CPU consumers. The mux reads 300 MHz from the 600 MHz auxiliary
clock, with APC's reported 1.15 V boot target retained and an enabled MX vote
(requested floor 1.2875 V; summary truncates to 1287 mV). LOOP_EN is clear while
BUSY still reads one, directly supporting the corrected disabled-state check.
All four CPUs are online, taint is zero, five SPM controllers bind and CPU-SPC
usage increments. No CPUfreq policy or module is loaded.

The debugfs `current_volt = 1080000` is the unapplied corner cache, not the
programmed APC target. Correct this label before relying on it for runtime
qualification. Governor userspace is itself a module; schedutil remains the
built-in default, so load order/default-governor control must be settled before
loading cpufreq-dt. No positive pstate, feedback, higher OPP, physical analogue
rail, thermal or suspend acceptance follows from this startup result.

Serial captures the return at 181.782488 seconds; both observers exit zero and
host network state restores. Installed r50 retains its boot hash, four-rate
policy, zero taint, Sway and sensor proxy, with owner-confirmed display/touch.
Its time-sync target/service remain
pending, so full systemd startup is not claimed. See
[qualified startup evidence](../evidence/2026-11-08-cpr-disabled-reference.json)
and the published [source branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-cpr-disabled-reference).

### Signed runtime registration and first fixed-corner requests

The 43-patch observation source (`b721ebaecd7d`) distinguishes planned/cached
corner voltage, whether a performance request has been applied, feedback
eligibility and the APC target read through the regulator provider. Unattached,
applied/unapplied, suspended/inhibited, read-error and legacy cases execute the
actual C diagnostics without state mutation. The full kernel/both DTBs and
464 signed modules build; the embedded ELF trust list exactly matches their
certificate. CMS payload/signature corruption and the prior certificate reject.

The first packed kernel hits the unresolved USB download defect at 3,588,096
confirmed bytes before any BOOT. Re-encoding XZ at preset 3 leaves decompressed
Image, ELF, certificate and Module.symvers byte-identical. The new encoding
stages/reads back and RAM-boots. Under `module.sig_enforce=1` and a verified
`cpufreq.default_governor=userspace`, userspace loads before cpufreq-dt and
registration leaves the CPU at 300 MHz, APC at 1.15 V and performance unapplied.
This load order matters: actual CPUFreq tests demonstrate that an absent
userspace governor falls back to built-in schedutil. See
[registration and build evidence](../evidence/2026-11-08-cpr-voltage-observation.json).

A separate userspace-limited 300–384 MHz trial then requests 384 MHz and 300 MHz.
Both points pass ten state checks across two-second quiet holds. The 384 MHz
point uses a 768 MHz PLL; return to 300 MHz uses GPLL0/2. Both have applied
1.08 V APC targets and LOOP_EN clear because the first corner's rounded floor
and ceiling are equal. Feedback eligibility is true after application; this
is distinct from an enabled loop. The active MX vote requests a 1.0875 V
floor (summary truncates to 1087 mV); the direct L3 view still reports 1287 mV.
No analogue voltage or release of other clients' votes is inferred.

Taint remains zero, and serial captures the timer at 181.756403 seconds. Warm
return restores r50's original boot hash, four-rate schedutil policy, Sway and
sensor proxy. Two exact nine-byte PMIC debugfs reads, after validating its dense
range metadata, confirm S2 range/VSET 1/115 (the original 1.15 V target). The owner confirms display/touch and startup subsequently reaches running
without failed/pending jobs, as tracked in
[first fixed-corner evidence](../evidence/2026-11-08-cpr-first-fixed-corner.json).
Later-corner feedback, higher eligible rates, physical rails, sustained load,
thermal/suspend and installed/distribution qualification remain open.

### First bounded 600 MHz feedback response

The same `b721ebaecd7d` kernel, qualification DTB, signed CPU modules and boot
arguments pass a separate 300→600→300 MHz RAM trial. Only the feedback script
and its permit are added to the previously qualified registration initramfs.
The userspace policy is capped at 600 MHz. Fifty complete checks, separated by
0.2-second sleeps, require the uncached 600 MHz clock, four online CPUs, zero
taint, temperatures below 60°C and matching APC/cache targets within the
second corner's rounded 1.08–1.18 V bounds.

This unit's initial plan is already at the 1.08 V floor. All fifty samples
retain that target, with LOOP_EN set and one CPR interrupt in total. CTL reads
`0x20000469`: its auto-NACK-DOWN bit is set by the qualified IRQ handler's
DOWN-at-floor branch. This proves a handled floor response; it does not
demonstrate voltage adjustment. RESULT_0 continues to report down requests.
The active MX floor request is 1.1875 V (summary truncates to 1187 mV).
The script then verifies 300 MHz, the fixed 1.08 V target and LOOP_EN clear
(`0x20000428`), with MX's floor back to 1.0875 V.

Serial records the timer at 181.741527 seconds. Both observers exit zero and
host default routes/resolver restore, with the temporary profile removed.
Native r50 boot `8eda2570-36e5-43aa-a35c-6c531fdd349c` retains the original boot
hash, four-rate schedutil policy, zero taint, Sway and sensor proxy. Two bounded
PMIC reads confirm S2 range/VSET 1/115 and the restored 1.15 V target. Only the
existing time-sync target/service remain pending at the initial check; the
owner confirms display and touch on this newest return. The same time-sync
jobs remain pending at follow-up; details are tracked in
[600 MHz feedback evidence](../evidence/2026-11-08-cpr-feedback-600.json).

Three host shell tests cover 22 simulated modes, including voltage adjustment,
both clamps, inconclusive feedback and failed state/temperature/IRQ/return
checks. Actual hardware voltage adjustment under controlled load, repeated
transitions, higher rates, physical rails, sustained load/thermal/suspend and
installed/distribution qualification remain open. The successful kernel
encoding still works around the unresolved USB staging defect.

### Repeated transitions and short four-core 600 MHz load

The unchanged observation kernel/module family passes five pre-load
300→600→300 MHz round trips, followed by a 600 MHz four-core checksum load and
another verified 300 MHz return. The userspace cap remains 600 MHz throughout.
The RAM image adds only a permit, guarded shell controller, static userspace
worker and its SHA256 manifest to the qualified registration initramfs.
Kernel, DTB, signed modules, command line and 180-second return timer are
byte-identical to the registration trial.

Each worker pins itself, verifies affinity, checks every one-MiB repeating-byte
SHA256 result and exits after 30 monotonic seconds. Its reported accounting is:

| CPU | Verified one-MiB hashes | Process CPU seconds | Elapsed seconds |
| --- | ---: | ---: | ---: |
| 0 | 362 | 28.116 | 30.023 |
| 1 | 365 | 28.320 | 30.026 |
| 2 | 365 | 28.322 | 30.014 |
| 3 | 371 | 28.979 | 30.016 |

The 1,463 hashes cover 1,534,066,688 bytes of repeated computation over four
one-MiB buffers, not that much distinct RAM. All workers terminate before the
final frequency request. All 90 state checks pass, including 37 during load:
uncached clock, applied/allowed feedback, voltage/cache bounds and grid, policy,
four CPUs, zero taint, IRQ counts and both temperature sensors. Reported RAM
temperatures span 38–44°C. APC stays at 1.08 V; one floor-clamp interrupt sets
CTL 0x20000469 at 600 MHz. No voltage adjustment is observed. The fixed-corner
300 MHz return reads CTL 0x20000428. MX floor requests remain 1.1875 V at 600 MHz
and 1.0875 V at 300 MHz.

The timer returns at 181.714515 seconds. Both observers exit zero and the host
network state restores. Native r50 boot `28db1c68-3b08-4a53-8e5a-3397b8315813`
has the original hash, four-rate schedutil policy, zero taint, Sway and sensor
proxy. Bounded PMIC reads restore S2 range/VSET 1/115 and the native 1.15 V
target. Newest physical UI and startup status are tracked in
[repeat/load evidence](../evidence/2026-11-08-cpr-load-600.json).
Startup subsequently reaches running with NTP synchronized and no failed
units/jobs, without changing configuration. Exact-status probes distinguish
the successful bounded hostname lookup from missing `resolvectl`; see the
[natural startup follow-up](../evidence/2026-11-08-r50-time-sync-followup.json).
This does not establish a fix for earlier intermittent DNS/startup delays.

Four sanitizer-backed worker tests, six real-shell controller tests covering
17 modes, fifteen ARM-emulated digest cases and the exact ARM binary's
30-second emulated lifecycle pass before the physical run. Emulation is kept
separate from the hardware results above. This is short correctness/load and
repeat-transition evidence at 600 MHz. Higher rates, voltage adjustment,
long stress, whole-RAM testing, thermal throttling, analogue rails, battery
power, suspend and distribution/installed qualification remain open.

### Prepared 787.2 MHz PLL trial

The next RAM-only image is prepared with the same qualified kernel/module
family and worker. It limits userspace to 787.2 MHz, checks three
787.2→600→787.2→300 MHz cycles, then a bounded four-core load at 787.2 MHz
before returning through 600 MHz to 300 MHz. This rate shares virtual corner
4/fuse corner 2 with 600 MHz: the APC bounds remain 1.08–1.18 V and the MX
floor 1.1875 V. The new clock path uses a direct 787.2 MHz CPU PLL, while
600/300 MHz must disable that PLL and use the auxiliary source.

Six controller tests covering 22 modes, three tests executing the actual
PLL/mux selection code, and four actual C corner-mapper tests pass. The
selection fixture uses board PLL OPP frequencies, checks 42 canonical
decisions and rejects missing/incorrect parent points before programming.
Those parent callbacks and programming are modeled; no hardware result is
inferred. The shell requires matching uncached CPU/PLL rates and enable state
alongside the existing voltage, temperature, IRQ, CPU and policy guards.

The image is unbooted and unstaged. Its stage entry checks the exact previous
native boot ID and physical display/touch result before any phone command;
the pending-result path is verified to create no transfer or BOOT request.
The newest r50 return remains running, NTP-synchronized and untainted. Its UI
check remains pending. See
[787.2 MHz preparation](../evidence/2026-11-08-cpr-787-preparation.json).

### Independent Alpine observation package

Alpine r55 now source-builds the 43-patch observation tree at `b721ebaecd7d`,
including XO handoff and voltage diagnostics. The input changes only
LOCALVERSION to `-fx0-cpr-observe-alpine`; actual Clang 22.1.3 normalization
retains CFI, signed modules, the userspace module and the compiled schedutil
default. Both DTBs match the host versions, but kernel, certificate and module
family are independent. All 464 module signatures, embedded trust list, signed
APK, corruption/wrong-certificate controls and offline ARMv7 simulation pass.
The artifact is unbooted and uninstalled, so controlled Alpine startup,
registration, governor/OPP/load and recovery remain separate gates. See
[package evidence](../evidence/2026-11-08-cpr-observation-source-package.json).

The independent Alpine registration trial is prepared separately. Its script
checks the moduleless 300 MHz/1.15 V/unapplied bootstrap, MX vote, CPU PLL,
four CPUs, taint and both temperatures before loading userspace then cpufreq-dt,
and requires those states retained afterward. No explicit performance request
is made. Three shell tests cover 36 modes and the exact ARM BusyBox parses the
script. The image preserves exact APK kernel/DTB/module bytes and the qualified
timer/init logic; memory-footprint and observer-command checks pass. It remains
unstaged/unbooted while the preceding native return physical UI check is pending.
See [Alpine registration preparation](../evidence/2026-11-08-alpine-cpr-registration-preparation.json).
