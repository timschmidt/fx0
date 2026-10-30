# PM8226 BMS1 coherent output diagnostic

This development module tests output latching on the Fx0's non-VM BMS1 at
0x4000. It accepts only `lg,madai` and the observed BMS type/subtype. It is not a
fuel gauge, and it does not register a battery power supply or report capacity.

`snapshot` sets bit 0 of CC_DATA_CTL, verifies the hold, reads the counter,
shadow counter, OCV, battery voltage and sense-voltage outputs twice, and rejects
inconsistent results. It restores the previous hold state on every exit,
including an enable write that may have reached hardware before returning an
error. Release has one bounded retry and readback verification. An already-held
output returns EBUSY without writes. A permanently failed bus returns an error;
the helper cannot guarantee release when hardware is inaccessible.

The only register writes are to the output-hold bit. There are no counter resets,
charger writes or calibration writes. Configuration reads include private
per-unit calibration: keep the resulting files out of public repositories.
The module holds a provider-device reference, and debugfs operations pin the
diagnostic module. This fixture assumes no provider removal and no concurrent
driver owns the BMS or changes its registers.

Run the actual helper fault tests on the host:

```sh
python3 diagnostics/pm8226-bms-snapshot/check.py
```

Clang with AddressSanitizer and UndefinedBehaviorSanitizer is required by default;
`--cc` selects another compatible compiler. Tests cover success, 30 single-operation
faults, four ownership/consistency/permanent-failure cases and nine signed 36-bit
decoder vectors. The register backend alone is mocked.

Build as an external module against the exact running ARM kernel configuration
and matching exported symbol versions:

```sh
make -C /path/to/linux O=/path/to/prepared-output ARCH=arm LLVM=1 W=1 \
    M="$PWD/diagnostics/pm8226-bms-snapshot" modules
```

On the development phone, loading the unsigned external module sets taint 12288.
Root can read these files under `/sys/kernel/debug/fx0-bms-snapshot/`:

- `snapshot`: JSON containing capture times, control readbacks and raw outputs.
- `control`: independent readback of CC_DATA_CTL.
- `configuration`: a fixed read-only list of BMS, companion-IADC, trim and
  charger-comparator fields. The trim values are private calibration.

Use a private output directory, unload the diagnostic after capture and reboot
to restore the signed installed kernel state. Do not infer state of charge from
raw counters or assume that readable outputs have valid configuration/calibration.

Two native sample sets confirm changing latched counters and restored hold state.
The stock comparison also finds different BMS sense configuration and charger
temperature policy. See [battery evidence](../../evidence/2026-10-30-bms-coherent-stock-comparison.json)
and [the implementation sequence](../../docs/battery-bringup.md).
