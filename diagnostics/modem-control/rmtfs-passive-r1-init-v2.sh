#!/bin/sh
# SPDX-License-Identifier: MIT
# PID1 for the credential-free, exact-r1 passive RMTFS RAM trial.
set -eu
/bin/busybox --install -s /bin
export PATH=/bin:/usr/bin
fatal() {
    printf '<2>RMTFS_RAM_INIT_FAIL %s\n' "$*" >&2
    sync
    reboot -f
    while :; do sleep 1; done
}
mkdir -p /proc /sys /dev /tmp
mount -t proc -o nodev,noexec,nosuid proc /proc || fatal proc
mount -t sysfs -o nodev,noexec,nosuid sysfs /sys || fatal sysfs
mount -t devtmpfs -o nosuid devtmpfs /dev || fatal devtmpfs
mount -t tmpfs -o mode=1777,nodev,nosuid,size=4m tmpfs /tmp || fatal tmpfs
exec >/dev/kmsg 2>&1
printf '<2>RMTFS_RAM_INIT_ENTER\n'
/bin/fx0-native-return --check || fatal 'return helper check'
/bin/fx0-native-return &
return_pid=$!
ready=no
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if [ -f /tmp/fx0-native-return-armed ]; then ready=yes; break; fi
    sleep 0.1
done
[ "$ready" = yes ] || fatal 'return helper did not arm'
kill -0 "$return_pid" || fatal 'return helper not live'
grep -qx "PID=$return_pid" /tmp/fx0-native-return-armed || fatal 'return helper PID'
grep -qx 'DEADLINE=180' /tmp/fx0-native-return-armed || fatal 'return helper deadline'
grep -qx 'TOKEN=fx0.native_trial=r1-rmtfs-passive-01' /tmp/fx0-native-return-armed || fatal 'return helper token'
printf '<2>RMTFS_RAM_RETURN_ARMED PID=%s\n' "$return_pid"
# All optional modules stay unavailable; the worker explicitly loads QRTR only.
printf '/bin/false\n' > /proc/sys/kernel/modprobe
[ "$(cat /proc/sys/kernel/modprobe)" = /bin/false ] || fatal 'module autoload'
mkdir -p /sys/kernel/config /dev/pts
mount -t configfs -o nodev,noexec,nosuid configfs /sys/kernel/config || fatal configfs
mount -t devpts -o nosuid,noexec devpts /dev/pts || fatal devpts
gadget=/sys/kernel/config/usb_gadget/fx0-rmtfs
mkdir "$gadget" || fatal 'gadget exists'
printf '0x1d6b\n' > "$gadget/idVendor"
printf '0x0104\n' > "$gadget/idProduct"
mkdir -p "$gadget/strings/0x409" "$gadget/configs/c.1/strings/0x409"
printf 'fx0-rmtfs-passive-r1\n' > "$gadget/strings/0x409/serialnumber"
printf 'Nura Fx0 development\n' > "$gadget/strings/0x409/manufacturer"
printf 'Fx0 passive RMTFS RAM trial\n' > "$gadget/strings/0x409/product"
printf 'Bounded serial diagnostic\n' > "$gadget/configs/c.1/strings/0x409/configuration"
printf '500\n' > "$gadget/configs/c.1/MaxPower"
mkdir "$gadget/functions/acm.usb0"
ln -s "$gadget/functions/acm.usb0" "$gadget/configs/c.1/"
udc=
for attempt in $(seq 1 30); do
    set -- /sys/class/udc/*
    if [ "$#" -eq 1 ] && [ -e "$1" ]; then udc=${1##*/}; break; fi
    sleep 1
done
[ -n "$udc" ] || fatal 'one USB device controller required'
printf '%s\n' "$udc" > "$gadget/UDC"
(
    while :; do
        setsid getty -L -n -l /bin/sh 115200 ttyGS0 vt100 || :
        sleep 1
    done
) &
printf '<2>RMTFS_RAM_READY worker=idle helper=%s boot=%s\n' "$return_pid" "$(cat /proc/sys/kernel/random/boot_id)"
# PID1 watches the helper as well as its atomic armed marker. A runtime helper
# error forces an immediate return; a successful reboot does not return here.
while kill -0 "$return_pid" 2>/dev/null; do sleep 1; done
set +e
wait "$return_pid"
result=$?
set -e
fatal "return helper exited $result"
