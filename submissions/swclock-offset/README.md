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

The stable pmaports recipe draft `ca9dd83b1241f9059ac1242068bb1d1453a942e3`
starts from the current v26.06 maintainer head
`2a8621d64d91647f7362eac59e7cdc091ff2bba8` and carries this patch as
0.3.0-r1. Two fresh normal abuild runs produce identical signed main, OpenRC
and systemd APKs and an identical signed index. Independent signature and
valid-format altered-payload rejection checks pass. Only the installed boot
unit changes; scripts, the shutdown unit and removal hook remain byte exact.

The actual old and new packaged units pass the offline manager regression
with two filesystem checks. On the phone, APK 3.0.9-r1 resolves exactly the
main and systemd upgrades using an isolated copy of its current 775-package
database. The OpenRC subpackage is not selected. These checks install nothing.
See [package evidence](../../evidence/2026-11-14-swclock-ordering-package.json).

The phone retains its original 0.3.0-r0 packages. A completed warm reboot
now has actual prior-boot PID1 shutdown success records and a current boot
invocation with exit status 0, MainPID 0 and no remaining cgroup. Corrected
RTC time agrees with the synchronized wall clock within a second. This
qualifies service execution on that reboot; it does not establish wall-time
restoration before NTP or cold/long-term retention. See
[execution evidence](../../evidence/2026-11-14-swclock-warm-service-execution.json).
Native transaction/recovery qualification and a boot with the fixed unit
remain open, along with full RTC and hardware acceptance.
