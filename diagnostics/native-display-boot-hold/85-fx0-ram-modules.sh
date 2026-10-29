#!/bin/sh
# SPDX-License-Identifier: MIT
# RAM-test helper: keep matching r1 modules available after switch_root.
# The installed kernel package is unchanged and its files are only hidden.
set -e
grep -Fq 'lg,madai' /sys/firmware/devicetree/base/compatible || exit 0
test "$(uname -r)" = 6.18.59
test -f /usr/lib/modules/6.18.59/modules.dep.bin
test -d /sysroot/usr/lib/modules
mount -t tmpfs -o size=64m,nodev,nosuid,mode=0755 tmpfs /fx0-ram-modules
cp -a /usr/lib/modules/. /fx0-ram-modules/
mount --move /fx0-ram-modules /sysroot/usr/lib/modules
echo 'Fx0 native RAM modules moved into target root; installed modules hidden for this boot' >/dev/kmsg
