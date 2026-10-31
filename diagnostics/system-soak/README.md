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
