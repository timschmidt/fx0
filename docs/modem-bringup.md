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
This check reads names, symlinks and sizes only; firmware identity, segment
ranges and successful loading remain unqualified.

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

Before starting MSS, verify the exact stock firmware layout on the phone and
audit bootloader, firmware loader, module loading and remoteproc ownership.
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
