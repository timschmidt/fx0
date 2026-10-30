# SMBB verified charge control

The experimental [charge-guard branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-charge-guard)
extends the earlier standard charge-behaviour actuator. Charging stays inhibited
through native probe setup. Separate initialization, user and latched I/O-fault
votes control the enable bit under one mutex. `auto` releases only the user vote.
A fault needs reinitialization; a successful later user request cannot clear it.

Enable writes preserve forced-battery mode and every other control bit. Both
enable and limit writes require readback. An uncertain transaction latches the
fault vote and attempts a separate verified inhibition. The original error is
returned even if that recovery succeeds. Persistent bus failure can prevent
inhibition: the software vote alone never proves that the PMIC stopped charging.
Cached limits change only after verification, and getters return an error while
a control fault is latched. A managed cleanup action attempts
inhibition after later probe failures and during unbind.

Run the actual driver functions against instrumented bus I/O:

```sh
python3 diagnostics/smbb-charge-guard/check.py --cc clang --negative-controls \
  /path/to/linux/drivers/power/supply/qcom_smbb.c
```

The harness compiles the source's attribute conversion/write functions,
charge helpers and battery property callbacks. It uses ASan/UBSan and real POSIX
mutexes. Its 6,242 cases include all control-byte/vote/user-mode combinations,
invalid input, errors before and after writes, dropped writes, incorrect readback,
fault retention, limit rounding/safety clamping, status precedence and 2,000
concurrent requests. Five deliberately broken variants must fail assertions:
missing enable verification, user override of other votes, missing fault latch
premature limit-cache publication and returning an untrusted cached limit.
The test disables core dumps.

Host tests do not execute the complete kernel probe, regmap implementation or
device-managed cleanup. The ARM build checks those call sites; physical boot
and control tests are recorded separately. The fixture represents each forced
masked write as a read and write, so failures cover both bus boundaries and the
additional readback. It does not establish electrical current accuracy.

This is a control foundation. Thermal/sample/profile/suspend votes and policy
are not implemented yet. In particular, probe-entry inhibition cannot protect
the interval before fw_devlink permits the driver to probe. An explicit firmware
charge gate, validated temperature/voltage inputs, stock derating/hysteresis,
stale-sample protection, suspend coordination and battery replacement handling
remain required. Hardware BTC limits stay conservative. Neither this branch nor
its tests justify widening the temperature window or installing the prototype
as a production charging solution.

For RAM qualification, preserve the exact candidate, current boot files,
bootloader prefix and both GPT captures on two host filesystems. Boot the full
kernel with the original r4 DTB/initramfs and verify its GNU build ID. Use the
register observer only with `force_on=0`; do not read the thermistor or alter
BTC/reference settings. Record module-verification/out-of-tree taint explicitly.

The bounded control test uses three inhibit/resume cycles, with three samples
one second apart in each state. During each inhibited interval, rewrite both
existing current/voltage limits unchanged and check their values. Reject three
unsupported mode strings and negative limits. Check USB remains online, the
actual input budget stays unchanged, and forced-battery/BTC/reference bits are
preserved. Record status/current observations without forcing a hardware
temperature trip to recover. No fault is injected on the physical PMIC.

Always restore the original mode, unload the observer, retain reset logs and
return to installed r4 with taint zero, active UPower/Sxmo and automatic display
controls. Compare the bootloader prefix and both GPT copies again. These narrow
readbacks do not claim a whole-device backup or a factory restoration rehearsal.
Export only a completed run through the allowlist:

```sh
python3 diagnostics/smbb-charge-guard/export.py local/smbb-charge-guard-01 \
  evidence/2026-10-30-smbb-charge-guard.json
```
