# Modem and GNSS bringup

Native r50 has no active modem. Its live `/soc/remoteproc@fc880000` node is
disabled and inherits `qcom,msm8226-mss-pil`. Only WCNSS and ADSP remote
processors run. ModemManager is active, but its already-running D-Bus object
manager returns no modem objects. No QMI/WWAN device is exposed. This is an
implementation gap, not evidence that the product lacks cellular or GNSS.

Read-only inventory on boot `c3ac8f04-888e-493c-bb5d-a1729a275f7d` confirms
kernel `6.18.59-fx0-dmp`, package r50, UPower r5, original raw boot hash and
zero taint. The configuration includes modular Q6V5 MSS and RPMSG WWAN control;
the installed MSS module exists but is not loaded. QRTR/SMD are loaded for the
other remote processors. `mmcli` and `qrtr-lookup` are installed; `qmicli`, rmtfs,
pd-mapper, tqftpserv and gpsd executables are absent. Their absence does not
establish which ones this firmware will require. No radio state is changed.

## Firmware lookup and reserved memory

The firmware loader sets `/sys/module/firmware_class/parameters/path` to
`/run/msm-firmware-loader/target`. The stock `mba.b00` and `modem.mdt` names
resolve there to the original modem partition. ADSP and WCNSS names also resolve
there. Missing files in `/lib/firmware` alone would give a misleading inventory.
That initial check read names, symlinks and sizes only. A later on-phone
inspection below verifies file digests and segment ranges. Successful loading
and firmware authentication remain unqualified.

The original modem filesystem is mounted read-only from `/dev/mmcblk0p1`;
persist is mounted read-only from `/dev/mmcblk0p14`. No firmware, calibration,
IMEI, SIM identity, subscriber data or location is exported. The live modem
memory references resolve to `mba@d100000` (1 MiB) and `mpss@8000000` (81 MiB),
both enabled reserved regions with `no-map`. Those descriptions do not prove
that a particular firmware load is safe or correct.

## Disabled MSM8926 description prepared on host

The unit is MSM8926. The stock DTB links MSS to PM8226 S5, PLL to L8 and MX to
L3. Their stock constraints are S5 1.15 V fixed, L8 1.8 V fixed and L3
0.75–1.3375 V. These are described limits, not independently measured rails.

The [candidate patch](../diagnostics/modem-control/fx0-msm8926-modem-description.patch)
against the reconstructed r50 board description selects
`qcom,msm8926-mss-pil`, supplies MX/PLL/MSS correctly, and removes the inherited
MSM8226-only external BHS property. It adds S5 at the stock fixed constraint.
Both the modem and new S5 node stay disabled. The RPM regulator driver visits
available children; this candidate does not make the new S5 available.

The shared 6.18.59 driver has a separate MSM8926 resource descriptor, including
the active MSS supply and no external BHS. Its 1.05 V request is a minimum
with `INT_MAX` upper bound, so the stock fixed 1.15 V constraint is compatible;
it is not an instruction to lower this board's rail to 1.05 V. The source sets
remoteproc `auto_boot` false. Userspace and lifecycle effects still require
audit before any physical probe/start procedure.

The patch applies without fuzz and both board descriptions compile with the
same inherited warnings. A verifier resolves the stock and candidate supply
phandles and checks the exact carveouts. It rejects the old description, a
same-type wrong MSS supply and unexpected S5 enablement. Full processed kernel
schemas validate MSS and RPM regulator descriptions using separate host copies
with modem/S5 marked enabled. This is necessary because disabled nodes relax
required-property checks. The old enabled copy exposes missing MX/PLL supplies;
a retained MSM8226 BHS property is also rejected. The real candidate remains
disabled and unbooted. See [verification](../diagnostics/modem-control/README.md)
and [evidence](../evidence/2026-11-09-modem-control-description.json).

## Next hardware requirements

A new physical UI result for the current boot is still required before another
RAM entry. Keep the
original source/builds, installed r50 and its recovery path until a matching,
bounded RAM procedure is prepared and verified.

The read-only layout check below now passes for the installed files. Before
starting MSS, finish bootloader, loader, module and remoteproc ownership
qualification.
Prepare current calibration/EFS backups and explicit remote-filesystem handling;
starting firmware must not silently redirect or overwrite provisioning. A
driver probe, firmware start and QMI service discovery are separate milestones.

Then qualify modem startup/stop/recovery, control transport, ModemManager,
radio state, SIM handling, data and supported calls/messages. The planning
baseline has no SIM, so final cellular acceptance remains pending. GNSS needs
its actual location service and outdoor acquisition/position/time evidence;
absence of a generic GNSS class node is not a product-absence finding. Audio
tests remain excluded. No modem, GNSS, radio, power-management, coexistence or
full-hardware pass follows from this description work.

## Offline-probe RAM image prepared

A separate 6,301,696-byte image uses the exact installed r50 kernel encoding
and five matching retained signed modules. All signatures verify against the
entire certificate list extracted from that kernel; all 197 imported CRCs match
its actual export tables or earlier signed dependencies. System.map resolves
11,709 kernel exports, the linked notes, certificate bounds and decompressed
footprint. Payload/signature/CRC corruption controls reject for each module.
The public extraction helper and a fresh native-family replay reproduce the
inputs and checks; a final image rebuild is byte-identical on this host.

Relative to the inactive candidate, only three DT property values change:
modem and S5 become available, while BAM-DMUX is explicitly disabled. Every
other property byte/path is unchanged. This avoids the driver's otherwise
created BAM child. Actual MSS/RPM bindings pass. Native source has auto_boot
false; core registration only auto-boots when requested, and the offline crash/
shutdown paths do not start firmware. This is a source audit, not a runtime pass.

The image initially loads no modules. Its explicit worker verifies kernel notes,
seventeen DT properties, five module hashes, enforced signatures, RAM-only mounts,
no CPUfreq/CPR provider or firmware/helper paths and bounded temperatures. It
performs one five-module load and reverse unload, requiring only the expected
modem remoteproc, offline state, expected parent/firmware name, no startup log,
no BAM child and bounded IRQ counts. It never writes remoteproc state, requests
firmware, retries an operation or kills a pending one. The original independent
180-second init timer, BusyBox and USB diagnostics stay byte-identical.

Host and exact ARM BusyBox each pass five test methods/44 subcases, including
ten failed-operation boundaries and eight dynamic failures. They detect two
weakened guards. An early shell-counter collision is reproduced and fixed;
positive tests require the full ten operations and cleanup. These are mocked
sysfs/module operations, not physical driver, IRQ, power or radio qualification.
Independent parsing checks all 23 CPIO entries, Android checksum/addresses,
original kernel bytes, three ARM shell scripts and absence of firmware/services.

Read-only native sampling on the same boot captures APC's 1.15 V target and S5
at base 0x2000: type3/subtype8/revision2, range0/selector62 (1.15 V programmed
target), mode0x40 and enable0. Bit7 is clear; this does not measure analogue
voltage or prove every possible physical enable path is off. Future entry and
return checks must freshly preserve those raw controls, together with r50/r5,
services, boot hash and the newest physical UI result. The image is unstaged/
unbooted. Entry/observer/native-return controllers are prepared and their host
guards pass; the newest native UI gate remains pending and no trial has run. Firmware start/EFS/RF/GNSS and full
bringup remain open. See [procedure](../diagnostics/modem-control/probe-ram.md)
and [preparation evidence](../evidence/2026-11-09-modem-offline-probe-preparation.json).


The prepared controllers require exact native preflight, data-only transfer/full
readback, live identified observers and one recorded BOOT attempt. Return checks
cover the original raw boot and r50/r5 files/services, nine exact APC/S5 controls,
CPU/NFC/MSS state and host network/index restoration. One real read-only
preparation sample passes on the unchanged boot. Host tests exercise refusal
boundaries and artifact validation; no physical modem entry, return, reset,
firmware start or radio action occurs. A pure artifact verifier leaves physical
display/touch explicitly unconfirmed. The older post-install UI reply is already
recorded for its earlier boot and does not satisfy the current gate. See
[controller preparation evidence](../evidence/2026-11-09-modem-probe-entry-preparation.json).


## Installed firmware layout and RMTFS prerequisite

The on-phone inspector reads bounded ELF headers/program tables and computes
file digests on the phone. Only numeric metadata and hashes return to the host.
The 27-header modem MDT contains 21 loadable segments, including three pure
zero-fill segments. The fixed-address, nonoverlapping load span is 81,788,928
bytes inside the 84,934,656-byte MPSS carveout at `0x08000000`. All eighteen
payload segment files have exactly their declared sizes. The authenticated
metadata consists of the 916-byte header/table and a packed 904-byte hash region.
MBA's raw `mba.b00` is 295,824 bytes, within its separate 1 MiB region at
`0x0d100000`; its selected MDT fields agree. No payload, signature block, modem
identifier or provisioning contents are exported. Layout validity does not
establish MBA authentication or successful startup.

The exact native configuration has `CONFIG_QCOM_RMTFS_MEM=y`, but the live tree,
memory class and device nodes contain no RMTFS memory device. The unit's stock
DTB and vendor source place its shared region at `0x0fd80000`, size `0x180000`.
That interval lies inside the existing `reserved@fb00000` exclusion. A separate
[host candidate](../diagnostics/modem-control/fx0-rmtfs-memory.patch) splits that
4 MiB exclusion into a leading `0x280000` reserved interval and the stock-sized
RMTFS region. Their union is identical, with no overlap/gap. SMEM and every other
existing property stay byte-identical. Client 1 matches the audited userspace
expectation. The candidate would expose the RMTFS memory device if booted; MSS
stays disabled. It is outside the active kernel recipe and has not been packaged,
included in the prepared modem probe image, or booted.

The host verifier checks stock wiring, exact memory coverage and all property
differences. Both DTBs compile with the same three inherited warnings. The real
RMTFS binding passes; wrong base/client, reservation overlap/gap and missing
client controls reject. The first hand-authored patch had a bad hunk length and
was rejected before compilation. That attempt is preserved; the generated patch
passes dry-run/apply with zero fuzz.

Pinned [RMTFS source](https://github.com/linux-msm/rmtfs/tree/b30a3eb38f9af283f18dbd3c7755653efc52c094)
is audited, not installed. Its `-r` storage mode keeps writes in a RAM shadow;
it still exchanges QRTR messages and writes shared memory. `-P` selects EFS
partition labels. `-s` owns remoteproc start/stop, and the upstream default unit
includes it. A future trial must therefore control service/lifecycle ownership
explicitly. Starting that unit requests firmware startup; package hooks must
be inspected before any installation. No RMTFS service, memory device,
`/dev/mem`, QMI channel or modem control is opened
by this audit.

## Provisioning backup comparison

Read-only hashes of modem, persist, modemst1, modemst2, FSG and FSC are compared
with independently rehashed original private recovery images. Modem firmware,
FSG and FSC match. Persist and both modemst partitions differ. The audit does
not establish when or why they changed, and does not diagnose corruption.
Keep the original backups. That read-only audit exported no provisioning
payload. The later private snapshot below now captures current provisioning
state. Recheck its freshness before firmware start; an old factory image is
not a current-state rollback image.

Final native checks preserve the same boot, r50/r5 hashes, raw boot image,
taint0, services, CPU/NFC baseline and all nine APC/S5 controls. Original firmware
directory resolution and unchanged host routes/resolver/index are verified.
There is no reboot, RAM transfer, driver registration, firmware start, RMTFS
installation or radio change. The physical UI gate for the newest native boot
remains pending. See [reproduction procedure](../diagnostics/modem-control/firmware-layout.md)
and [evidence](../evidence/2026-11-09-modem-firmware-layout.json).


## Current private provisioning snapshots

A later one-use capture now preserves persist, modemst1, modemst2, FSG and FSC:
43,515,904 bytes in five images. It verifies exact labels/offsets/sizes, disabled
MSS, absent remote-storage writers and unmounted or read-only source filesystems.
All five source digests agree before capture, during each bounded copy and on
independent reads after host transfer. Every source device is opened read-only.
No source partition is restored or written.

Private mode-600 images and metadata are fsynced in
`/var/lib/fx0-rollback/modem-provisioning-01` on phone rootfs p35 and in
`local/modem-provisioning-backup-01/host-backup` on the encrypted workstation.
The phone copy shares the source eMMC; the workstation is one off-device copy.
Both persistent copies are rehashed, their manifests agree and the capture PID
is absent. Original card identity is compared privately with the retained card
record; no CID, provisioning bytes or per-partition digests are published.
The original factory-era images remain unchanged.

This writes seven new regular backup files on phone rootfs, not firmware or
source partitions. It excludes the modem firmware partition. A host payload
round-trip into five fresh regular files matches all bytes; disposable copies
are removed afterward. This does not rehearse physical partition restoration
or power-loss survival. Four synthetic test methods/25 cases pass for bounded
copy, no-clobber, private paths and snapshot acceptance/refusal.

Final r50/r5, original raw boot, services, CPU/NFC/MSS state, raw APC/S5 controls
and host routes/resolver/index are preserved on the same native boot. No reboot,
RAM entry, firmware start, package or radio change occurs. The newest physical
UI gate remains pending. See [backup and restoration procedure](../diagnostics/modem-control/provisioning-backup.md)
and [snapshot evidence](../evidence/2026-11-09-modem-provisioning-backup.json).


## RMTFS storage candidate and diagnostic builds

Actual pinned upstream storage code fails 15/20 host sanitizer cases and 13/20
static ARM cases, including three ARM segmentation faults. The storage-only
candidate checks live handles and signed/count bounds, completes initial reads,
preserves errors, frees failed buffers and zeroes grown shadows. It passes 20/20
on both runners with guarded synthetic files and a persistent-write control.
No QMI packet, shared-memory device or real provisioning image is used by tests.

Full host and static ARM daemons compile with exact patch replay. The ARM image
has no interpreter/shared dependencies and its isolated invalid-option path
exits before memory/socket access. This is not daemon startup qualification.
The target's retained systemd/libudev provider has `-dirty` recipe metadata;
its archive is hashed but clean source provenance is unresolved. Close that
dependency before trial/promotion. Packet/sector arithmetic, shared-memory
bounds, lifecycle and physical operation still require work. Nothing is uploaded
or installed, and firmware remains stopped.

Final read-only native checks preserve r50/r5, original boot hash, services,
taint0, CPU/NFC/MSS and raw APC/S5 controls. Current provisioning source/phone
snapshot rereads match the private host manifest. The current UI gate remains
pending. See [RMTFS procedure](../diagnostics/modem-control/rmtfs-userspace.md),
[draft](../submissions/rmtfs/README.md) and
[evidence](../evidence/2026-11-09-rmtfs-storage-candidate.json).

## RMTFS packet-handler candidate

The actual dispatcher/QMI/storage harness now passes 25/25 synthetic cases on
host Clang ASan/UBSan/leak detection and static ARM/QEMU. The storage-patched
baseline fails 11/25 on both runners, including four ARM segmentation faults.
The handler patch corrects GET_DEV_ERROR handle validation, verbose CLOSE,
wide sector multiplication, sync error reporting and initialization/formatting.
Far reads and writes check actual 64-bit storage offsets. Transport and memory
are mocked; guarded synthetic backing files remain unchanged.

This does not close malformed QMI decoding, shared-memory span checks, large
counts, lifecycle, dependency provenance or physical modem operation. The OPEN
request encoder has an unresolved descriptor mismatch; tests construct its
string TLV directly. All decoding and remaining encoding use the pinned codec.
No phone commands or hardware changes occur; the latest UI gate remains pending.
See [packet procedure](../diagnostics/modem-control/rmtfs-packets.md) and
[evidence](../evidence/2026-11-09-rmtfs-handler-candidate.json).

## QMI bounds and required-field candidate

The corrected codec and OPEN C buffer pass 52 codec cases plus 32 actual
RMTFS dispatcher cases on host Clang ASan/UBSan/leak detection and static
ARM/QEMU. Baseline codec failures are 35/52 host and 24/52 ARM. Six malformed
dispatcher cases fail on each: missing fields or incomplete arrays can close a
live handle, allocate or transfer data. The candidate rejects those requests
before effects. The 256-byte OPEN wire maximum is preserved with room for NUL;
empty/ordinary/maximum OPEN encoding now works.

This is finite synthetic qualification. Generator integration, shared-memory
spans, huge counts, ownership/lifecycle, dependency provenance and physical
modem operation remain open. No phone commands or hardware changes occur; the
latest UI check remains pending. See [procedure](../diagnostics/modem-control/rmtfs-qmi.md),
[unsent QRTR draft](../submissions/qrtr/README.md) and
[evidence](../evidence/2026-11-09-rmtfs-qmi-candidate.json).

## Pinned QMI generator regeneration

The matching qmic kernel-output patch now preserves the OPEN terminator byte
through regeneration and emits optional string validity markers. All 28 pinned
qmic files match upstream Git blob hashes. Direct generation and the actual
RMTFS Makefile target agree; RMTFS descriptor C bytes remain identical to
upstream. Sixteen normal wire-byte/round-trip cases pass on host sanitizers and
static ARM, including both current-generator 32-bit RMTFS count fields.

This verifies source regeneration, not distribution packaging or full daemon
qualification. Legacy 256-byte nested-string length encoding remains unresolved;
RMTFS uses only a top-level path string. Shared-memory/lifecycle, dependency
provenance and physical modem work remain open. No phone command or hardware
change occurs; the current UI check remains pending. See
[generator procedure](../diagnostics/modem-control/qmic-generation.md),
[unsent draft](../submissions/qmic/README.md) and
[evidence](../evidence/2026-11-09-qmic-generation.json).

## Verified libudev provider and runtime link inputs

A new ARM diagnostic build uses signed Alpine eudev 3.2.14-r6, whose source
archive matches its clean recipe. Every persistent linker input matches a
verified signed package member with a clean recipe commit. Five real libudev
API cases pass against read-only synthetic sysfs; only early CLI rejection is
executed for the full daemon. The old dirty-metadata library and builds remain
unchanged. No phone operation occurs.

The link audit also found dirty recipe metadata on the cross compiler's bundled
runtime files; the final build selects clean target GCC runtime files instead.
The compiler executable's own recipe identity remains unqualified. Distribution
packaging, full startup, shared-memory spans, lifecycle and physical modem work
remain open; the native UI gate stays pending. See
[provider procedure](../diagnostics/modem-control/rmtfs-libudev.md) and
[evidence](../evidence/2026-11-09-rmtfs-libudev-candidate.json).
