#!/bin/busybox ash
# SPDX-License-Identifier: MIT
set -eu
fatal() {
    printf '<2>FX0_NATIVE_PREFIX_FAIL %s\n' "$*" >&2
    /bin/busybox sync
    /bin/busybox reboot -f
    while :; do /bin/busybox sleep 60; done
}
[ -e /dev/kmsg ] || /bin/busybox mknod -m 600 /dev/kmsg c 1 11
exec >/dev/kmsg 2>&1
printf '<2>FX0_NATIVE_PREFIX_ENTER\n'
[ -e /dev/null ] || /bin/busybox mknod -m 666 /dev/null c 1 3 || fatal dev-null
/bin/busybox mount -t proc -o nodev,noexec,nosuid proc /proc || fatal proc
printf '<2>FX0_NATIVE_PREFIX_STATE release=%s uid=%s uptime=%s\n' "$(/bin/busybox uname -r)" "$(/bin/busybox id -u)" "$(/bin/busybox cut -d ' ' -f 1 /proc/uptime)"
set +e
/bin/fx0-native-return --check
checked=$?
set -e
printf '<2>FX0_NATIVE_RETURN_CHECK status=%s\n' "$checked"
[ "$checked" -eq 0 ] || fatal 'return helper check'
/bin/fx0-native-return &
helper=$!
ready=
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if [ -r /tmp/fx0-native-return-armed ]; then ready=yes; break; fi
    /bin/busybox sleep 0.1
done
if [ "$ready" != yes ]; then
    if ! kill -0 "$helper" 2>/dev/null; then
        set +e
        wait "$helper"
        result=$?
        set -e
        fatal "return helper exited $result"
    fi
    fatal 'return helper did not arm'
fi
kill -0 "$helper" || fatal 'return helper exited'
/bin/busybox grep -qx "PID=$helper" /tmp/fx0-native-return-armed || fatal PID
/bin/busybox grep -qx 'DEADLINE=420' /tmp/fx0-native-return-armed || fatal deadline
printf '<2>FX0_NATIVE_RETURN_ARMED PID=%s\n' "$helper"
/bin/busybox umount /proc || fatal 'temporary proc unmount'
exec /init.fx0-original
