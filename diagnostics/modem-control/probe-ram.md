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

Before entry, prepare one-use controllers and fresh native preflight/return
checks. Native S5 base0x2000 currently has revision2/type3/subtype8, range0,
selector62, mode0x40 and enable0: 1.15 V programmed target with enable bit7 clear.
APC remains at its 1.15 V target. Require those exact raw controls to match on
return; neither report is an analogue measurement. Preserve original boot hash,
r50/r5 services, modem-disabled native state, host network and protected index.
The current native boot's physical display/touch question is still pending.

The intermittent USB download defect remains unresolved. Existing terminal-PID,
full-readback, observer and single-BOOT rules continue to apply. No entry helper
or trial is launched by this procedure. Firmware/EFS ownership, true modem
startup, RF, SIM, GNSS and full bringup remain open. See
[evidence](../../evidence/2026-11-09-modem-offline-probe-preparation.json).
