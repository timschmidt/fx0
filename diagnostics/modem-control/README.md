# Disabled Fx0 MSM8926 modem description

This host-only candidate describes the unit's modem and stock supply mapping.
It does not enable the modem or the new S5 regulator, load firmware, open a
control device, start a service or change radio state. It is outside the active
kernel recipe. Installed r50, prior RAM images and source worktrees are unchanged.

`fx0-msm8926-modem-description.patch` applies to the reconstructed r50 board
file (`5df5d19e8ab3cffebd0778a320298475ebe50e4e05712e40f654f44ea7ac3135`).
It selects the MSM8926 driver resources, removes the inherited MSM8226-only
external BHS property and supplies MX/PLL/MSS from PM8226 L3/L8/S5. S5 uses the
unit's stock fixed 1.15 V constraint. Both new activation points stay disabled.
Actual voltage, firmware start, RF behavior and GNSS are untested.

Run the host verifier with the preserved private stock DTB and a complete
reconstructed r50 source tree. Output must be a new private directory. The
schema tools may be read from an existing environment; output/cache stays in
the new directory and Python bytecode writes are disabled.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 diagnostics/modem-control/verify-description.py \
  --source worktrees/linux-fx0-integration \
  --stock-dtb /private/stock-unit.dtb \
  --patch diagnostics/modem-control/fx0-msm8926-modem-description.patch \
  --schema-tools /path/to/dtschema/bin \
  --output local/modem-description-check
```

The verifier validates the stock FDT and board ID, resolves only its selected
modem supply links and voltage constraints, applies the patch without fuzz and
compiles baseline/candidate DTBs. It checks candidate supplies, disabled states,
deleted BHS and the unchanged modem carveouts. Wrong description, wrong MSS
rail and unexpected S5 enablement controls must fail. It writes no full stock
DTB dump or other stock properties to its report.

For schema checks it creates separate enabled host copies, leaving the real
candidate disabled. Disabled nodes relax required-property checking. The old
enabled node must expose missing MX/PLL supplies, the complete candidate must
pass MSS/RPM regulator bindings, and a stale BHS control must fail. No copied
DTB is booted or packaged. Binding validity does not establish electrical or
runtime correctness. The first verification attempt caught this disabled-node
validation gap; its failed assertion and original artifacts are preserved.

Native inventory confirms that ModemManager has no objects and that MSS is
disabled, while ADSP/WCNSS run. Stock modem firmware names are available through
the configured `/run/msm-firmware-loader/target` search path, with modem/persist
mounted read-only. Only metadata is collected; firmware/calibration bytes and
modem identifiers are not exported. Before a real start, prepare firmware/range,
EFS, remote-filesystem, ownership, fault/stop and native-return handling.

See [bringup status](../../docs/modem-bringup.md) and
[evidence](../../evidence/2026-11-09-modem-control-description.json).


A later [offline-probe RAM preparation](probe-ram.md) uses exact retained native
r50 kernel/modules and a separate DTB derivative. It enables modem/S5 only in
that unbooted image and disables BAM-DMUX. The inactive source patch above and
installed system remain unchanged. The worker never starts firmware; physical
entry/return controls are now prepared and host-checked, while the current UI
gate remains pending. No trial has run. See the preparation procedure for the
separate controller evidence and remaining requirements.


The later [on-phone firmware layout check and separate RMTFS memory candidate](firmware-layout.md)
verify the installed segment bounds without exporting payloads and identify the
missing shared-memory device. The candidate is host-only and keeps MSS disabled.
Original and current provisioning hashes differ for three partitions; fresh
current-state rollback coverage remains required before firmware start.


Current [private provisioning backups](provisioning-backup.md) now match fresh
source reads on both phone and host storage. This closes the current-image
freshness gap as of capture, while physical restoration, RMTFS qualification,
the native UI gate and firmware startup remain separate unfinished work.
