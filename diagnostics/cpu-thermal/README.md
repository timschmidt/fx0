# Bounded CPU and thermal observation

`check.py OUTPUT_DIRECTORY` records five seconds of baseline, a 30-second
four-core SHA256 load, and 15 seconds of recovery. Each worker is pinned to
one online CPU and repeatedly checks a known one-MiB byte pattern. It records
per-core CPU accounting, the shared cpufreq policy, cpuidle entry counts and
both CPU thermal sensors once per second.

The helper requires four online CPUs, zero taint and initial reported
sensor temperatures below 60°C. A reported 65°C stops the load. Frequency,
governor, voltage, trip settings and cooling policy are never written.
Workers are stopped and joined on normal completion, exceptions or handled
termination signals. Run under an idle/sleep inhibitor and do not start a
second copy while one is live.

This is a short correctness/load/recovery check at the installed OPPs. It
does not establish calibrated temperature accuracy, thermal throttling,
long-duration CPU/RAM stability, full hardware speed-bin support or battery
power behavior. The current source limits CPU OPPs to 787.2 MHz and explicitly
requires speed-bin support for higher rates. Audio, storage contents and
host network configuration are not exercised.
