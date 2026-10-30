# SMBB charge inhibition

The experimental [kernel branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-charge-control)
adds the standard `charge_behaviour` API to `smbb-bif`. It supports `auto` and
`inhibit-charge`, updating only the charge-enable bit. It preserves forced-battery
mode, USB power and all other charger control bits. This is a control primitive;
it does not implement battery temperature policy or change comparator limits.
The [upstream ABI](https://github.com/torvalds/linux/blob/d89e1d186ec9271bf78e62771779e9fc03bf0fc3/Documentation/ABI/testing/sysfs-class-power#L506)
defines the mode names.

Run the actual driver helpers and callbacks against instrumented register I/O:

```sh
python3 diagnostics/smbb-charge-control/check.py /path/to/linux/drivers/power/supply/qcom_smbb.c
```

The 1,051 ASan/UBSan cases cover every initial control byte, supported and
unsupported modes, read/write failures, notifications and status precedence.
They do not establish physical current accuracy or thermal protection.

For hardware qualification, boot the exact full ARM kernel from RAM with the
unchanged installed r4 DTB/initramfs, verify its GNU build ID, and use a read-only
[register observer](../pm8226-therm-reference/README.md). Preserve reset logs and
record module verification taint. In this test, unsigned/out-of-tree diagnostics
are confined to RAM; normal r4 must return with taint zero. Do not flash this
experimental kernel or widen the comparator window as part of this test.

With external USB power present and the battery initially reporting Good, record
the original mode and input budget. Temporarily use the configured host's
500 mA budget and verify positive charging response. Perform three cycles:

1. Request `inhibit-charge`; collect three samples two seconds apart. Verify
   charge enable is clear, status is `Not charging` and current decreases.
2. Request `auto`; collect three samples two seconds apart. Verify charge enable
   is set and charging response returns.
3. Throughout, verify USB remains online, forced-battery mode and all other
   control bits stay unchanged, and BTC/reference/current/voltage limits match.

Reject `force-discharge`, `inhibit-charge-awake` and invalid strings without a
control change. Always restore the original mode and actual input budget,
unload diagnostics, retain logs and boot installed r4. No gauge counter reset,
thermistor read, temperature-policy change or suspend test belongs in this control
qualification. Do not override an unexpected hardware protection trip to finish.

The completed test recorded approximately 249 mA before inhibition, 18.4 mA
while inhibited and 230–290 mA after resuming. These are live IADC readings with
positive charging; inhibition is not a claim of electrically measured zero
current. Independent accuracy, thermal policy, unplug/replug and suspend tests
remain open. See [the hardware evidence](../../evidence/2026-10-30-smbb-charge-control.json).

A separate submission branch now applies directly to the power-supply
maintainer's `for-next` at `f0f400459bf6a037e70768de623fff3f8920b8bb`.
Its 1,051 host cases and ARM W=1 object build pass without warnings. See
[draft patches and validation limits](../../submissions/power-supply/README.md).
