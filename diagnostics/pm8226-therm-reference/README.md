# Thermistor reference and comparator observation

This Fx0-only RAM diagnostic observes a short fixed register list. It requires
the Fx0 compatible, PM8226 IADC node and non-VM BMS identity. Default
`force_on=0` makes no register writes. Read the snapshot through:

```sh
insmod /tmp/fx0-btc-reference.ko
cat /sys/kernel/debug/fx0-btc-reference/registers
rmmod fx0_btc_reference
```

Use an isolated, verified diagnostic boot, stop other ADC consumers, and retain
raw captures privately. The registers cover charger status, battery-temperature
status, BATIF real-time status, BTC/reference controls and VADC configuration;
factory trim/calibration banks are excluded. Reads are sequential, not an atomic
snapshot. A changing BATIF bit does not by itself identify its electrical cause.
The module does not request a BATFET IRQ.

Optional `force_on=1` requests the stock awake reference mode: mask `0xc0` at
`0x124a`. It preserves other bits and checks readback. Unload restores the saved
mode with two bounded attempts, including when an effective write reports an
error. Confirm restoration with another default read-only load; module removal
cannot return an error to userspace if bus restoration fails. No charging enable,
current/voltage limit or BTC temperature threshold is written.

The stock driver explicitly forces this mode while awake and uses FSM mode in
suspend. In the actual comparison the native register was already `0xc0`, so the
force request did not change mode and did not clear Overheat. This does **not**
qualify a mode-changing hardware sequence or justify a production reference fix.
The module also shows that a battery-voltage conversion changes the VADC mux
away from the thermistor but does not clear the reported fault. A five-minute
backlight-off control moves the inferred temperature by less than 1°C and does
not rule out hysteresis. The subsequent original-stock-kernel comparison
reproduces HOT at 31.6°C with native's tighter window and clears it by restoring
stock's window. This directs work toward complete native thermal policy, not a
reference or mux fix. See [stock-window evidence](../../evidence/2026-10-30-stock-BTC-window.json).

Build against the exact running kernel's prepared module output directory with
`ARCH=arm LLVM=1 W=1 M=...`. The exact source passes ARM W=1 and checkpatch with
zero errors/warnings. The host regression executes its actual write/restore
helpers with mask preservation, before/after-write faults, ignored writes and
unrecoverable rollback faults:

```sh
python3 diagnostics/pm8226-therm-reference/check.py
```

All 524 cases pass ASan/UBSan. These model checks do not establish analog accuracy,
thermal protection or suspend qualification. Keep this tool separate from the
production driver and native package.
