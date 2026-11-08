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
