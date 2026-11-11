# Fx0 vibrator integration

Installed r50 exposes `pm8xxx_vib_ffmemless` on the PM8226 vibrator at
`0xc000`, with its persistent input path containing the SPMI parent. The
installed Sxmo utility defaults to `/dev/input/by-path/platform-vibrator-event`,
which is absent on this board. Its implicit strength of 1 produces no enabled
PMIC samples even when given the correct device path.

The Fx0 device profile now exports the persistent device path and strength
39168. The installed timer already passes `SXMO_VIBRATE_STRENGTH` to
`sxmo_vibrate`. The native test runs with the graphical user's UID, GID and
supplementary groups. The profile installation retains the original file at
`/var/tmp/fx0-vibrator-profile-01/profile-before.sh` and verifies the new file
through Sxmo's actual environment loader. Existing long-lived processes keep
their inherited environment until the next session startup.

## Native measurements

```sh
python3 native-test.py --boot-id "$fx0_native_boot_id"
```

The diagnostic measures the original failure and then 150, 300 and 600 ms
pulses through the installed `sxmo_vibrate`, reading the PM8226 drive/enable
registers and the MPU-6515 raw accelerometer. It requires the original r50
behavior and runs before installing the corrected profile. The selected
strength programs drive code 21, corresponding to a 2.1 V target. The
actuator returns off after every pulse. Motion variance rises during pulses
and remains elevated during the short ring-down observation. The fourfold
comparison against both pre-pulse and late samples is false in these runs.
These data establish electrical timing and a motion response, while tactile
quality and system suspend still need acceptance.

## Kernel candidate

The driver chooses its voltage range from `drv2_addr`, although probe always
adds the peripheral base to that address. PM8226 therefore uses the range
intended for a different register layout. The candidate chooses the range
from `drv2_mask`. It also clamps the inclusive endpoint and replaces cached
drive bits when intensity changes while active. Host fixtures reproduce
the original failure and independently reject each reverted fix. The
advertised legacy drive field stays between codes 12 and 31 across the full
byte-scale speed range. The unchanged upstream source has the same address
predicate. [Upstream driver](https://github.com/torvalds/linux/blob/master/drivers/input/misc/pm8xxx-vibrator.c)

```sh
base=local/vibrator-r50-01
python3 check-voltage.py \
  --control /path/to/original/pm8xxx-vibrator.c \
  --candidate "$base/candidate/drivers/input/misc/pm8xxx-vibrator.c" \
  --output "$base/voltage-recheck"
```

The actual driver functions pass 768 host ASan/UBSan speed/layout cases.
Leak detection is disabled because the host tracing environment prevents
LeakSanitizer operation. The W=1 ARM object and strict checkpatch pass. The
test covers voltage selection, driver level and legacy drive fields.
PMI632 high-byte encoding is outside its scope. The corrected module is
unpackaged and unbooted. Its predicted code at strength 39168 is 24,
corresponding to the stock 2.4 V target. The October 31 evidence's 2.4 V
description at this strength was an inference from the intended mapping.
The new exact PMIC read supersedes that inference for uncorrected r50.
[Patch](pm8xxx-voltage-range.patch), [evidence](../../evidence/2026-11-10-vibrator-r50-integration.json)
