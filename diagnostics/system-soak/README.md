# System soak

`soak.sh HOURS LOGDIR` logs one JSON line per minute: Wi-Fi state, gateway ping
and DNS, a 25 MB download every 30 minutes, available memory, load, the hottest
thermal zone, battery status, running remoteprocs, whether Sway and PipeWire
are running, failed units, root free space, kernel warnings in the last minute,
and taint.

Run it as a transient unit so it survives SSH disconnects:

```sh
install -m755 soak.sh /usr/local/libexec/fx0-system-soak.sh
systemd-run --unit=fx0-system-soak --property=Nice=10 \
	/usr/local/libexec/fx0-system-soak.sh 24 /var/log/fx0-system-soak
```

The `smbb-bif` battery supply exposes no capacity or voltage on the current
kernel, so only its status is recorded.

## Mixed-use soak

`soak-mixed.sh HOURS LOGDIR` logs the same fields plus mixed load: an IMU and
magnetometer read and the CPU idle entry count every minute, a 64 MB hashing
burst every 10 minutes, a one-second speaker tone through PipeWire every 30
minutes, and five raw frames from each camera (selected by name) every 60
minutes.

```sh
install -m755 soak-mixed.sh /usr/local/libexec/fx0-mixed-soak.sh
systemd-run --unit=fx0-mixed-soak --property=Nice=10 \
	/usr/local/libexec/fx0-mixed-soak.sh 24 /var/log/fx0-system-soak
```
