# swclock-offset systemd ordering draft

The installed Fx0 clock-offset boot unit names `systemd-fsck@.service` in
`Before=`. systemd expands that empty template with the clock unit's own
instance name: `systemd-fsck@swclock-offset-boot.service`. The same source is
present in the official maintainer branch at
`82a52fab5530509be47827931ccd884183ee2d1f`.

The local draft `83d60105c3714e8f16eeb8188e978c6ee3b7cac7` pulls in the passive
`local-fs-pre.target` and orders clock restoration before it. Actual filesystem
fsck instances already order after that target. The explicit root-filesystem
check ordering remains. This changes dependency routing; it does not change
the offset scripts, RTC counter, stored offset format or shutdown unit.

The formatted patch records the exact maintainer base. No message or pull
request has been sent. The patch and routing file are local review material.

The reusable regression runs the actual offline systemd manager against the
baseline and draft dependency instructions and two distinct fsck instances:

```sh
python3 verify-ordering.py /path/to/swclock-offset \
  82a52fab5530509be47827931ccd884183ee2d1f /new/empty-output-directory
```

It uses the host's actual fsck template and local-fs-pre target. The clock
command alone is replaced by `true` in the fixture so that installation is
unnecessary. `systemd-analyze verify` starts no services. Both graphs must
validate; the baseline must exhibit the spurious template instance and the
candidate must queue the explicit clock/fsck barrier without that instance.
The captured dependency edges show both tested filesystem checks after it.

Normal `make install` passes. Compared with the five runtime scripts and units
on the current accepted phone, only the intended boot unit changes. Upstream
`.ci/shellcheck.sh` passes with Alpine's signed shellcheck 0.11.0-r1 in a
disposable container. The baseline/draft offline checks and the reusable
reproducer all pass. Earlier restricted-sandbox and fixture-command setup
failures are retained privately; they did not execute services or clock code.

This is source and offline-manager qualification. The phone still has its
original 0.3.0-r0 package and unit. Real boot/shutdown execution, RTC accuracy,
cold/warm offset retention and the full hardware matrix remain open.
