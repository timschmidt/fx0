# On-phone modem layout and host RMTFS description

Run `inspect-firmware.py` on the phone against its existing read-only firmware
mount. Send the script through the established SSH client and collect its JSON;
do not copy modem firmware or provisioning payloads to the host for inspection.
The script writes no files and invokes no kernel firmware or modem operation.

```sh
# On the phone, with carveouts first checked against its live DT:
python3 inspect-firmware.py --firmware-root /run/msm-firmware-loader/target \
  --mpss-base 0x08000000 --mpss-size 0x05100000 \
  --mba-base 0x0d100000 --mba-size 0x00100000
```

It requires bounded ELF32 little-endian Hexagon headers and the adjacent program
table used by the native MSS loader. It identifies the authenticated metadata
source, checks fixed/global-relocation offsets, filesz/memsz, carveout bounds,
nonoverlap, split-file size and original-directory containment, and computes
digests on that filesystem. It records zero-filled regions separately. MBA's
raw file and selected MDT description must fit its separate region. Output has
numbers, file names and digests; no payload, signature or arbitrary file strings.
This does not test secure authentication, firmware startup, RF or GNSS.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s tests -p test_modem_firmware_layout.py -v
```

Four methods/22 synthetic cases cover fixed/relocatable load, zero-fill, packed/
embedded/split metadata, malformed/truncated headers, missing/wrong-size files,
bad bounds/overlap, MBA mismatch and a split file redirected outside the original
directory. No proprietary firmware fixture or physical device is required.

The separate `fx0-rmtfs-memory.patch` applies to the exact reconstructed r50
board source. It leaves MSS disabled and partitions the existing 4 MiB reserved
range so `0x0fd80000+0x180000` is described as RMTFS memory. This address/size is
checked against the unit's private stock DTB; client 1 is the audited userspace
expectation. The reserved union, original SMEM and all unrelated properties are
preserved. It is outside the installed recipe and prepared offline-probe image.
Booting it would register/map RMTFS memory, which remains physically unqualified.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 diagnostics/modem-control/verify-rmtfs-description.py \
  --source worktrees/linux-fx0-integration --stock-dtb /private/stock-unit.dtb \
  --patch diagnostics/modem-control/fx0-rmtfs-memory.patch \
  --schema /private/processed-kernel-schema.json \
  --schema-tools /path/to/dtschema/bin --output local/rmtfs-description-replay
```

Use a fresh output directory and a full processed schema from that kernel's
bindings. The verifier compiles baseline/candidate, compares every property,
validates the actual RMTFS binding and rejects wrong base/client, memory overlap/
gap and missing required client ID. The original manual hunk-length failure is
retained separately from the passing generated patch.

The [pinned upstream RMTFS sources](https://github.com/linux-msm/rmtfs/tree/b30a3eb38f9af283f18dbd3c7755653efc52c094)
are reviewed, not installed. In [storage.c](https://github.com/linux-msm/rmtfs/blob/b30a3eb38f9af283f18dbd3c7755653efc52c094/storage.c),
`-r` backs storage operations with a RAM shadow. [The default service](https://github.com/linux-msm/rmtfs/blob/b30a3eb38f9af283f18dbd3c7755653efc52c094/rmtfs.service.in)
also selects `-s`, which delegates remoteproc start/stop to the daemon. That is a
separate firmware-start action. A future startup trial needs explicit lifecycle
ownership, a qualified memory device and current provisioning rollback coverage.

Original backup comparisons match modem/FSG/FSC but differ for persist and both
modemst partitions. Current verified private copies are still required before
startup. Keep the original images; this comparison does not diagnose corruption
or authorize restoring old provisioning. The current native UI question is
pending, and this procedure has not launched a RAM trial or changed the phone.
See [evidence](../../evidence/2026-11-09-modem-firmware-layout.json).
