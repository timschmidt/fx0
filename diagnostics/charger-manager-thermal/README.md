# Charger Manager thermal-stop regressions

The [experimental kernel branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-charger-manager)
contains two focused prerequisites for considering Charger Manager on the Fx0:

1. A charging/discharging duration expiry cannot override a temperature stop.
   Previously an already-enabled charger could stay enabled because its target
   remained Charging and the redundant-command check skipped the emergency stop.
2. A runtime temperature-read error stops monitored charging, blocks other enable
   requests and reports health Unknown. A fresh valid reading must clear the
   existing hysteresis window. Existing configurations without temperature
   monitoring retain their behavior.

The test extracts and executes the actual thermal check, duration check, target
decision, monitor, regulator control and power-supply property callbacks. Only
sensor I/O, time, regulators and external supply inputs are substituted. It
checks 8,330 cases under ASan/UBSan, including boundary temperatures, previous
hot/cold/fault states, input failures, enabled/disabled chargers, expired timers,
status/health and recovery. It does not model analog battery hardware.

```sh
python3 diagnostics/charger-manager-thermal/check.py /path/to/patched/linux/drivers/power/supply/charger-manager.c
```

The two original failures can be reproduced against the pinned upstream source
at `d89e1d186ec9271bf78e62771779e9fc03bf0fc3` or the unmodified LTS source:

```sh
python3 diagnostics/charger-manager-thermal/check.py /path/to/original/linux/drivers/power/supply/charger-manager.c --expect-vulnerable
```

Both fixes apply to that upstream revision, and its patched file passes the
same host suite. The LTS candidate module builds for ARM with LLVM22 and W=1;
strict checkpatch reports zero diagnostics. A full current-upstream build remains
open. The module is **not loaded on the phone** and the installed r4 package is
unchanged. This is neither a complete native charging policy nor a hardware
thermal qualification. Probe-time sensor setup can still disable measurement;
regulator errors, cached actuator state, strict sensor requirements, independent
user/thermal inhibition and suspend protection need further work before reuse.

The separate maintainer-tree branch now applies directly to power-supply
`for-next` at `f0f400459bf6a037e70768de623fff3f8920b8bb`. Its host suite and
ARM W=1 object build pass without warnings. See the
[draft submission and exact limits](../../submissions/power-supply/README.md).

See [the evidence](../../evidence/2026-10-30-charger-manager-thermal.json) and
[battery bringup](../../docs/battery-bringup.md). No wider hardware comparator
window is enabled by these patches.
