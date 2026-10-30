# PM8226 BMS configuration and epoch experiment

This development fixture isolates the Fx0's BMS sense selection, primary-IADC
volatile offset trim and counter restart. It requires `lg,madai`, the observed
companion revision/type/subtype and non-VM BMS identity. It is not a production
battery driver and does not register a power supply.

Loading requires an explicit `apply=1`. Default mode 0 selects external sense
and writes its measured zero-reference code; mode 1 changes sense selection only,
and mode 2 changes trim only. It reads gain/zero reference codes through IIO on
the already-loaded reference-channel candidate. It uses device references and
assumes exclusive experiments, no provider removal and no other BMS owner.
This bus lookup tests IIO reads, not firmware channel-reference translation.

`trim_bank=0x3600` follows the stock protected-write path: SEC_ACCESS 0xa5 before
each MSB/LSB write at F2/F3. Both primary and companion trim readbacks must match.
Unloading restores the original trim and masked sense controls, with a bounded
retry and exact readback. No charger limits, firmware or flash storage are written.
The explicitly experimental `trim_bank=0x3800` path fails its physical test even
though readbacks appear mirrored; it is not a supported calibration path.

An optional `reset_epoch=1` is accepted only with mode 0 and the primary bank.
It intentionally clears both volatile counters for a new configuration epoch,
following the stock 100 µs clear pulse. **Counter contents cannot be restored.**
Ordinary snapshot reads do not reset counters. The clear command uses forced
regmap writes: an optimized update can skip deassertion when command bits read
zero, leaving counters stopped. Zero readback alone is insufficient; the final
physical test verifies that both counters advance during a bounded load.

Run host fault tests:

```sh
python3 diagnostics/pm8226-bms-configure/check.py
```

Clang with ASan/UBSan runs 238 actual-helper cases covering modes, protected byte
writes, alias rejection/ignored writes, partial-write faults, rollback, transient
release faults, occupied control bits and read-zero command behavior. Permanent
bus failure returns an error; software cannot guarantee restoration through an
inaccessible bus. Replacing the forced epoch writes with optimized updates fails
the command-register regression.

Build against the exact running configuration and matching symbol versions:

```sh
make -C /path/to/linux O=/path/to/prepared-output ARCH=arm LLVM=1 W=1 \
    M="$PWD/diagnostics/pm8226-bms-configure" modules
```

The unsigned external module produces taint 12288. Its root-readable debugfs
`/sys/kernel/debug/fx0-bms-configure/status` includes **private calibration**.
Keep captures private, unload the experiment and restore the signed native boot
afterward. The production implementation must serialize calibration inside the
IADC provider and coordinate its software calibration cache; this diagnostic is
not a replacement for that interface.

The input-budget/load experiment establishes sensor response and relative sign:
manual IADC is negative during discharge, while BMS VSENSE/counter increments
have the opposite sign. Provisional gain/resistor/time conversions agree around
0.2 A under load. External accuracy, temperature compensation, idle/charging
accuracy and capacity remain unqualified. See
[evidence](../../evidence/2026-10-30-bms-calibration-epoch.json).
