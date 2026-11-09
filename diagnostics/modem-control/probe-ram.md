# Native r50 offline modem probe preparation

The prepared image is `local/modem-probe-preparation-01/fx0-r50-modem-offline-probe-ram.img`,
SHA-256 `e7ae8e67f9d97ffa02576447c23af2d0c72853d98d61d8033e4405a11f400659`,
6,301,696 bytes. It is unstaged/unbooted. No radio, firmware start, GNSS or
physical modem-probe qualification follows from its preparation.

The exact retained native r50 kernel and five signed modules provide a matching
family. `extract-native-inputs.py` accepts only the already-audited local backup
hash and selects kernel, map/config, modules.dep and the MSS dependency closure.
It extracts no firmware, calibration or private keys. `verify-native-family.py`
derives the runtime Image, notes and entire kernel certificate list, checks
11,709 actual kernel export/CRC entries against System.map, verifies all five
CMS signatures and compares 197 imported CRCs with kernel/earlier module exports.
Modified payloads, signatures and module_layout CRCs are rejected independently.
No reconstructed signing key or embedded CMS certificate is trusted instead.

```sh
python3 diagnostics/modem-control/extract-native-inputs.py \
  --backup local/upower-r5-deploy-01/host-backup/before-files.tar.gz \
  --output local/modem-probe-rebuild
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 diagnostics/modem-control/verify-native-family.py \
  --inputs local/modem-probe-rebuild
```

Create a private copy of the [inactive description](README.md)'s verified DTB.
Using host `fdtput`, set `/soc/remoteproc@fc880000/status` and
`/remoteproc/smd-edge/rpm-requests/regulators/s5/status` to `okay`, then
`/soc/remoteproc@fc880000/bam-dmux/status` to `disabled`. Do not modify the
inactive source candidate or a phone. Every other property byte/path must remain
identical. Validate actual MSS/RPM bindings using the processed kernel schemas.
Disabling BAM-DMUX matters because probe otherwise creates that child device.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 diagnostics/modem-control/build-probe-image.py \
  --inputs local/modem-probe-rebuild \
  --probe-dtb /private/verified-modem-probe.dtb \
  --qualified-image local/kernel-reconstruction/fx0-r50-reconstructed-ram.img \
  --output local/modem-probe-rebuild/probe.img
```

The builder preserves all ten qualified init/USB/BusyBox payloads and modes,
including the independent 180-second return timer. It adds only the offline
worker, permits/digests and five signed modules. There is no firmware, service,
CPUfreq provider or positive OPP request. Independent parsing checks all 23 CPIO
entries, load addresses/checksum, original kernel and exact derivative DTB.

`probe-only.sh` is intended for an identified RAM diagnostic environment. Its
permit, kernel notes, seventeen DT properties, module hashes, signature policy,
CPU topology/default governor, RAM-only mounts, temperature and absent firmware/
helper guards run before module operations. It requires one initially empty
module/remoteproc set, one five-module load in dependency order, offline modem
registration, then reverse unload and an empty final set. It checks parent,
driver and default firmware name, rejects any startup log or BAM-DMUX child,
and bounds the five IRQ counters. It never writes remoteproc state.

Each operation must terminate within the observation budget and the worker
must stay within 90 seconds. A nonterminal operation is left to the independent
init return timer: the worker does not kill or retry it. No cleanup operation
follows a failed guard. The RAM kernel/module paths and any RPM S5 registration
effects remain physically unqualified even though no firmware is requested.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s tests -p test_modem_probe.py -v
```

Set `FX0_MODEM_TEST_BUSYBOX` to the exact extracted ARM BusyBox and
`FX0_MODEM_TEST_SHELL` to `/usr/bin/qemu-arm-static ABSOLUTE_BUSYBOX sh` for the
ARM shell/ten-applet path. Both runners pass five methods/44 subcases. Tests
mock module syscalls and sysfs, cover complete cleanup, repeat refusal, ten
operation failures and eight dynamic failures, and detect removed offline-state
or module-hash guards. They do not exercise actual driver/DMA/IRQ/rail behavior.

One-use entry/observer/return controllers are now prepared and their host guard
checks pass. They remain unexercised on the phone. Fresh preflight/return checks
are required for an actual trial. Native S5 base0x2000 currently has revision2/type3/subtype8, range0,
selector62, mode0x40 and enable0: 1.15 V programmed target with enable bit7 clear.
APC remains at its 1.15 V target. Require those exact raw controls to match on
return; neither report is an analogue measurement. Preserve original boot hash,
r50/r5 services, modem-disabled native state, host network and protected index.
The current native boot's physical display/touch question is still pending.

The intermittent USB download defect remains unresolved. Existing terminal-PID,
full-readback, observer and single-BOOT rules continue to apply. No entry helper
or trial has been launched. Firmware/EFS ownership, true modem
startup, RF, SIM, GNSS and full bringup remain open. See
[evidence](../../evidence/2026-11-09-modem-offline-probe-preparation.json).


## Prepared entry and return controls

The private one-use directory is `local/ram-modem-probe-01`. Its `stage.py`
requires a passed display/touch ledger for native boot
`c3ac8f04-888e-493c-bb5d-a1729a275f7d` before importing the phone client. The
older post-UPower-install reply belongs to boot `2e6126b9-498e-4d89-b23e-f08fe6ccc361`
and does not satisfy that gate. The current question remains pending.

After that gate passes, staging runs a fresh native preflight, identifies the
same physical USB port and private unit serial, requests one bootloader reboot,
then performs a persistent data-only transfer with the existing I/O journal.
It requires terminal success and exact full-image readback; it sends no BOOT.
No OEM log query may intervene between readback and BOOT because it overwrites
the bootloader staging buffer.

Only after transfer completion may the persistent observer and the existing
`scripts/connect_fx0_ram_usb.py` network controller be started. The latter uses
an identified RAM gadget and its own volatile, non-default, DNS-free profile.
`boot-once.py` checks the exact image/readback, absent transfer PID and both
live observer commands. It records and attempts BOOT once. An uncertain reply
consumes the attempt; it must never be retried.

The serial observer executes the offline worker once, captures its status,
kernel version, all 84 kernel-note bytes with `od -v`, original raw boot hash
and `/dev/kmsg` through the independent timer return. After RAM detachment and
terminal observer/network completion, `wait-native.py` observes normal native
startup and runs read-only postflight. It does not activate services. Postflight
allows up to 120 seconds for normal time synchronization jobs, checks r50/r5
package and file hashes, CPU policy, taint, MSS-disabled/ADSP/WCNSS state, three
UPower samples, Sway, temperatures, NFC baseline and all nine APC/S5 controls.
It verifies deletion of its own volatile profile and restoration of host default
routes, resolver and protected index.

If staging instead terminates with the known errno110 timeout before BOOT,
`recover-native.py` requires both terminal failed controllers, both PIDs absent,
the exact error and same identified bootloader. Only then does it allow the
established USB reset/identity check and one standard reboot to installed r50.
It has no transfer retry. Pending transfers, uncertain BOOT and other failures
do not qualify for that path. This preparation does not fix the USB defect.

Fourteen staging and fourteen BOOT guard cases pass with instrumented actual
sources. Six native phase cases and twelve recovery guard cases also pass;
recovery tests stop before real device lookup/open/reset/reboot. Nine changed
register controls are rejected. One real read-only preparation check passes on
the unchanged current boot, including three UPower samples and unchanged host
state. Neither actual entry nor postflight/recovery has run for this image.

The public `verify-probe-return.py` reads completed artifacts only. It requires
one successful worker, ten ordered module operations, offline state, five bounded
IRQ rows, exact notes/raw boot identity, a timer return 180–190 seconds after
init, a distinct native boot and successful native/host restoration. It checks
receipts produced by the controllers; it does not independently authenticate
them or send commands. It explicitly leaves physical display/touch unconfirmed.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s tests -p test_modem_probe_return.py -v
# Only after a completed trial, using a fresh output path:
python3 diagnostics/modem-control/verify-probe-return.py \
  --trial local/ram-modem-probe-01 --output /private/completed-probe-return.json
```

Three artifact-test methods pass using actual mocked-worker output and synthetic
observer/native receipts. They reject bad cleanup/order/state, changed notes or
boot hash, wrong timer/IRQ evidence, changed raw controls, bad UPower state and
incomplete host restoration. They confer no physical driver, rail, firmware,
radio or GNSS qualification. See [controller preparation evidence](../../evidence/2026-11-09-modem-probe-entry-preparation.json).
