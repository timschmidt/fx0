#!/bin/sh
# SPDX-License-Identifier: MIT
# Move a checksum-verified module copy over the installed search path in RAM.
set -eu
fatal() {
    echo "FX0_NATIVE_MODULES_FAIL $*" >&2
    sync
    reboot -f
    while :; do sleep 60; done
}
release=6.18.63-fx0-vibrator-alpine
[ "$(uname -r)" = "$release" ] || fatal release
case " $(cat /proc/cmdline) " in
    *' fx0.native_trial=stable-6.18.63-01 '*) :;;
    *) fatal permit;;
esac
[ "$(cat /proc/sys/kernel/tainted)" = 0 ] || fatal taint
source=/sysroot/var/lib/fx0-diagnostics/kernel-native-6.18.63-01/candidate/lib/modules
[ -d "$source/$release" ] && [ -d /sysroot/usr/lib/modules ] || fatal 'module paths'
(cd "$source/$release" && sha256sum -c /etc/fx0-native-modules.sha256 >/dev/null) || fatal 'staged module bytes'
[ ! -e /fx0-ram-modules ] || fatal 'already attempted'
mkdir /fx0-ram-modules
mount -t tmpfs -o size=64m,nodev,nosuid,mode=0755 tmpfs /fx0-ram-modules || fatal tmpfs
cp -a "$source/$release" /fx0-ram-modules/ || fatal copy
cp /usr/lib/modules/initramfs.load /fx0-ram-modules/initramfs.load || fatal 'init module list'
(cd "/fx0-ram-modules/$release" && sha256sum -c /etc/fx0-native-modules.sha256 >/dev/null) || fatal 'copied module bytes'
mount --move /fx0-ram-modules /sysroot/usr/lib/modules || fatal 'module mount move'
mkdir -m 700 /run/fx0-native-trial
cp /tmp/fx0-native-return-armed /run/fx0-native-trial/return-armed
mkdir -p /run/systemd/system/sysinit.target.wants
cp /etc/fx0-native-return.service /run/systemd/system/fx0-native-return.service
cp /etc/fx0-native-return.timer /run/systemd/system/fx0-native-return.timer
ln -s ../fx0-native-return.timer /run/systemd/system/sysinit.target.wants/fx0-native-return.timer
printf 'FX0_NATIVE_MODULES_READY release=%s\n' "$release"
