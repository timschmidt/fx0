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
