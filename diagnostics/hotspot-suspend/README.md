# Hotspot suspend coordinator

`fx0-hotspot-suspend` runs a blocking sleep command after disconnecting active
wcn36xx access-point profiles, then restores those profiles when the command
returns. Station connections and other wireless drivers are excluded. Profile
autoconnect settings are preserved. Restoration also runs on command failure
and handled signals; abrupt process termination or power loss cannot be recovered
by a shell trap.

For the Sxmo wakeup-count protocol, `--sync-wakeup-count` refreshes the count after
network preparation through the existing `doas tee /sys/power/wakeup_count`
permission. A rejected count aborts sleep and restores the AP. The caller must
provide an appropriate blocking sleep command and preserve any scheduled wake
deadline when adding preparation time.

The coordinator is installed experimentally through the signed Sxmo 1.18.1-r6
source package. Its Fx0 branch uses an absolute RTC wake deadline and refreshes
wakeup_count after preparation. The AP-mode guard preserves Sxmo's policy of
blocking automatic suspend while a hotspot is active, including renamed APs.

Two bounded tests of the installed Sxmo suspend path pass with both external
Wi-Fi clients automatically reconnecting and transferring verified data after
wake. Temporary mnc and wakelock hooks bound the wait and record the expected
cron hold without leaving one active. These trials do not qualify the full UI
or autosuspend loop. See [installed evidence](../../evidence/2026-11-06-sxmo-hotspot-installed.json)
and the maintained source/packaging patches under `patches/sxmo/`.

Run the transaction regression tests from the coordination repository:

```sh
python3 -m unittest discover -s tests -p test_hotspot_suspend.py
```

The tests replace network and privilege commands with fixtures and do not change
the host's network configuration.
