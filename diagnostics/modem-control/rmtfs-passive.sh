#!/bin/sh
# SPDX-License-Identifier: MIT
# One local RMTFS publication in the timer-return RAM image.
set -eu
root=${FX0_RMTFS_TEST_ROOT:-}
fail() { printf 'RMTFS_PASSIVE_FAIL %s\n' "$*" >&2; exit 1; }
value() { cat "$root$1" 2>/dev/null; }

[ "$(value /etc/fx0-rmtfs-trial)" = native-r50-passive-rmtfs ] || fail 'RAM trial permit'
[ "$(uname -r)" = 6.18.59-fx0-dmp ] || fail 'kernel release'
[ "$(value /sys/module/module/parameters/sig_enforce)" = Y ] || fail 'signature enforcement'
case " $(value /proc/cmdline) " in
    *' module.sig_enforce=1 '*) :;;
    *) fail 'signature parameter';;
esac
notes=$(sha256sum "$root/sys/kernel/notes") || fail 'kernel notes'
[ "${notes%% *}" = "$(value /etc/fx0-rmtfs-notes.sha256)" ] || fail 'linked kernel identity'
(cd "${root:-/}" && sha256sum -c etc/fx0-rmtfs-inputs.sha256) || fail 'DT and payload digests'

boot_id=$(value /proc/sys/kernel/random/boot_id) || fail 'boot identity'
printf '%s\n' "$boot_id" | grep -Eq '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' || fail 'boot identity'
rfsa=/dev/qcom_rmtfs_mem1
metadata="$root/sys/class/rmtfs/qcom_rmtfs_mem1"
work="$root/tmp/rmtfs-passive"
guard() {
    [ "$(value /proc/sys/kernel/random/boot_id)" = "$boot_id" ] || fail 'boot changed'
    [ "$(value /proc/sys/kernel/tainted)" = 0 ] || fail 'kernel taint'
    awk 'NR == 1 && $1 ~ /^[0-9]+[.][0-9]+$/ && $1 < 120 { ok=1 } END { exit !ok }' \
        "$root/proc/uptime" || fail 'RAM boot deadline'
    awk '
        NF && $3 !~ /^(rootfs|ramfs|tmpfs|devtmpfs|proc|sysfs|devpts|debugfs|configfs)$/ { bad=1 }
        $2 == "/" && $3 ~ /^(rootfs|ramfs|tmpfs)$/ { ram=1 }
        $2 == "/dev" { dev=($3 == "devtmpfs") }
        END { exit bad || !ram || !dev }
    ' "$root/proc/mounts" || fail 'RAM-only mounts and devtmpfs'
    dt="$root/sys/firmware/devicetree/base/reserved-memory/rmtfs@fd80000"
    for path in "$dt/qcom,vmid" "$dt/qcom,use-guard-pages" "$root/dev/qcom_rmtfs_uio1" \
        "$root/lib/firmware" "$root/usr/lib/firmware" "$root/lib/modules" \
        "$root"/sys/class/remoteproc/remoteproc* "$root"/sys/bus/rpmsg/devices/*; do
        [ ! -e "$path" ] && [ ! -L "$path" ] || fail "unexpected path ${path#"$root"}"
    done
    [ -c "$root$rfsa" ] && [ ! -L "$root$rfsa" ] || fail 'RFSA character device'
    grep -Eq '^0x0*[fF][dD]80000$' "$metadata/phys_addr" || fail 'RFSA address'
    grep -Eq '^0x0*180000$' "$metadata/size" || fail 'RFSA size'
    [ "$(cat "$metadata/client_id")" = 1 ] || fail 'RFSA client ID'
}
modules() {
    actual=$(awk 'NF { if (NF < 6 || $5 != "Live") exit 1; print $1 }' "$root/proc/modules") || fail 'module state'
    [ "$actual" = "$1" ] || fail 'module set'
}
lookup() {
    for attempt in 1 2 3 4 5; do
        guard; modules qrtr
        if "$root/bin/qrtr-local-rmtfs" "$1"; then return 0; fi
        sleep 1
    done
    fail "RMTFS publication should be $1"
}
check_empty() {
    contents=$(ls -A "$work/storage") || fail 'RAM storage directory unavailable'
    [ -z "$contents" ] || fail 'unexpected storage contents'
}

guard; modules ''
mkdir -m 700 "$work" || fail 'already attempted'
mkdir -m 700 "$work/storage"
check_empty
# The RAM devtmpfs node is the daemon's legacy fallback. Allow RFSA only.
rm -f "$root/dev/mem"
[ ! -e "$root/dev/mem" ] && [ ! -L "$root/dev/mem" ] || fail 'legacy memory path'
printf 'RMTFS_PASSIVE_BEGIN %s\n' "$boot_id"
insmod "$root/modules/qrtr.ko" || fail 'load QRTR core'
lookup absent

"$root/bin/rmtfs" -r -o "$work/storage" >"$work/rmtfs.log" 2>&1 &
pid=$!
lookup present
memory_open=false
for fd in "$root/proc/$pid/fd/"*; do
    if [ "$(readlink "$fd" 2>/dev/null)" = "$rfsa" ]; then memory_open=true; fi
done
"$memory_open" || fail 'daemon RFSA descriptor'
printf 'RMTFS_RFSA_OPEN %s\n' "$rfsa"

guard; modules qrtr
kill -TERM "$pid" || fail 'stop daemon'
for attempt in 1 2 3 4 5; do
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 1
done
if kill -0 "$pid" 2>/dev/null; then fail 'daemon exit pending; init timer remains armed'; fi
wait "$pid" || fail 'daemon exit status'
cat "$work/rmtfs.log"
lookup absent
check_empty
rmmod qrtr || fail 'unload QRTR core'
guard; modules ''
printf 'RMTFS_PASSIVE_PASS\n'
