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
through Sxmo's actual environment loader. After the later transfer recovery,
the new native Sway process inherits both settings; next-session inheritance
is now verified.

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
PMI632 high-byte encoding is outside its scope. The corrected module remains uninstalled; the later RAM result below qualifies
its bounded pulse, active-level and unload behavior. Its predicted code at strength 39168 is 24,
corresponding to the stock 2.4 V target. The October 31 evidence's 2.4 V
description at this strength was an inference from the intended mapping.
The new exact PMIC read supersedes that inference for uncorrected r50.
[Patch](pm8xxx-voltage-range.patch), [evidence](../../evidence/2026-11-10-vibrator-r50-integration.json)


## Signed RAM trial and transfer failure

The prepared 6,502,400-byte image retains the qualified reconstructed r50
kernel, DTB and original 180-second return timer. Signature enforcement is
enabled. The external corrected module is signed by that kernel's retained
key; its CMS signature, actual embedded trust list and all 25 imported CRCs
verify. Expected out-of-tree taint is 4096. It is not a module for the installed
r50 kernel, whose signing certificate differs.

[`ram-trial.sh`](ram-trial.sh) checks the exact kernel notes, payloads,
DT properties, RAM mounts, temperature, module set and input parent. Its
[`ram-pulses.c`](ram-pulses.c) helper requests 150, 300 and 600 ms pulses
at code 24, then active code changes 24 → 17 → 22 and stop. It reads the
PMIC registers and stops on unexpected drive values. The host fixture runs
the actual helper with mocked hardware and rejects overdrive; the static
ARM executable rejects invalid arguments before device access. Those were host checks; the later working-port trial below adds the physical result.

The physical attempt used the installed `fx0-pon-reboot` lk2nd, 16 KiB
host requests and 5 ms pacing. It completed 85 data requests (1,392,640
bytes), then the next request timed out after 30.18 seconds. Delivery of
that request is unknown. The timeout lies inside compressed kernel bytes
identical to the qualified baseline. There was no readback or Linux BOOT.
The terminal controller was reaped before a single identified USB reset
and normal reboot returned to installed r50. Its boot, package and module
hashes match the preflight, with zero taint and the vibrator off. The new
Sway process has inherited the profile. The Wi-Fi gateway answers ping but
its DNS service times out; direct public DNS succeeds. A temporary active-device
DNS fallback lets NTP synchronize and startup finish. The fallback is removed,
restoring the prior DNS and routes without modifying a saved profile or
restarting a service. A fresh visual check remains pending; no new driver
acceptance is inferred from recovery. [Evidence](../../evidence/2026-11-10-vibrator-ram-transfer-timeout.json)


## Notification integration

The native notification monitor now waits for completed writes or atomic
moves. A board-specific user hook requests one 300 ms pulse and respects
Sxmo's existing `.novibrate` flag. Real normal/muted/re-enabled notifications
reach Dunst once each; the enabled cases program code 21 and return off,
and the muted case has no enabled samples. [Repair, rollback and evidence](../sxmo-notifications/README.md)
Tactile quality and system suspend remain open.

## Working-port RAM result (2026-11-11)

On the qualified host USB port `1-7`, full image transfer and byte-exact
readback now succeed. The first RAM run exposed a harness omission:
reconstructed r50 has `CONFIG_INPUT_EVDEV=m`, so the input character device
was absent. The corrected image loads its matching signed in-tree evdev
module before the signed external vibrator module and unloads them in reverse
order. It retains signature enforcement and the original 180-second return.

The next run captures three pulses but loses its log tail at exactly ten
user messages. The pinned kernel's default `/dev/kmsg` per-open-file limit is
ten messages per five seconds and suppressed writes still report success.
That supports logging loss, without proving that run's unobserved completion.
The following image saves worker output to a RAM file, an atomic exit/module
result, and an independent read-only 20-second snapshot. An allowlisted HTTP
server exports those files. Four host cases check full output, failed-worker
status and allowed/missing HTTP responses without changing kernel log policy.

The instrumented physical run records 150/300/600 ms requests as 152/303/607 ms,
all at drive code 24 (a programmed 2.4 V target). Active changes 24 → 17 → 22
match 15 samples each; both final off holds match. The helper and worker report
PASS, exit status is zero, both modules are removed, and taint is the expected
4096 from the external module. This is a bounded RAM result, not analogue
voltage, tactile-quality, system-suspend or final installed-kernel acceptance.
[Evidence](../../evidence/2026-11-11-sxmo-r7-and-vibrator-ram.json)
