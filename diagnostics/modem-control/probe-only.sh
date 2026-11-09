#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# One offline driver probe/remove. Never write remoteproc state or request firmware.
set -eu
root=${FX0_MODEM_TEST_ROOT:-}
fail() { printf 'MODEM_PROBE_FAIL: %s\n' "$*" >&2; exit 1; }
value() { cat "$root$1" 2>/dev/null; }
[ "$(value /etc/fx0-modem-trial)" = native-r50-offline-probe ] || fail 'trial permit'
[ "$(uname -r)" = 6.18.59-fx0-dmp ] || fail 'kernel release'
[ "$(value /sys/module/module/parameters/sig_enforce)" = Y ] || fail 'signature enforcement'
case " $(value /proc/cmdline) " in *' module.sig_enforce=1 '*) :;; *) fail 'signature parameter';; esac
[ "$(value /sys/module/cpufreq/parameters/default_governor)" = schedutil ] || fail 'default governor'
[ "$(value /sys/devices/system/cpu/online)" = 0-3 ] || fail 'CPU topology'
notes=$(sha256sum "$root/sys/kernel/notes") || fail 'kernel notes'
[ "${notes%% *}" = "$(value /etc/fx0-modem-notes.sha256)" ] || fail 'linked kernel identity'
(cd "${root:-/}" && sha256sum -c etc/fx0-modem-DT.sha256 && sha256sum -c etc/fx0-modem-modules.sha256) || fail 'DT/module digests'
[ ! -e "$root/sys/firmware/devicetree/base/soc/remoteproc@fc880000/qcom,ext-bhs-reg" ] || fail 'wrong MSM8226 BHS'
for path in /lib/firmware /usr/lib/firmware /lib/modules /sbin/modprobe /sbin/udevd /sbin/init; do
    [ ! -e "$root$path" ] || fail 'unexpected firmware/loader/service path'
done
[ -r "$root/sys/module/firmware_class/parameters/path" ] || fail 'firmware search metadata unavailable'
[ -z "$(value /sys/module/firmware_class/parameters/path)" ] || fail 'firmware search override'
boot_id=$(value /proc/sys/kernel/random/boot_id) || fail 'boot identity'
case "$boot_id" in ????????-????-????-????-????????????) :;; *) fail 'boot identity';; esac
case "$boot_id" in *[!0-9a-f-]*) fail 'boot identity';; esac
[ "$(printf '%s' "$boot_id" | tr -d '-' | wc -c)" -eq 32 ] || fail 'boot identity'
[ -r "$root/etc/fx0-modem-native-boot-id" ] || fail 'native boot permit'
[ "$boot_id" != "$(value /etc/fx0-modem-native-boot-id)" ] || fail 'native boot reused'
uptime_seconds() {
    awk 'NR==1 && $1 ~ /^[0-9]+([.][0-9]+)?$/ {print int($1); ok=1} END {if (!ok) exit 1}' "$root/proc/uptime"
}
started=$(uptime_seconds) || fail 'monotonic clock'
work="$root/tmp/modem-probe"
mkdir -m 700 "$work" || fail 'already attempted'
platform="$root/sys/bus/platform/devices/fc880000.remoteproc"
driver="$root/sys/bus/platform/drivers/qcom-q6v5-mss"
order='qcom_pil_info qcom_common qcom_q6v5 mdt_loader qcom_q6v5_mss'
guard() {
    [ "$(value /proc/sys/kernel/random/boot_id)" = "$boot_id" ] || fail 'boot changed'
    [ "$(value /proc/sys/kernel/tainted)" = 0 ] || fail 'kernel tainted'
    current=$(uptime_seconds) || fail 'monotonic clock'
    [ "$current" -ge "$started" ] && [ "$((current-started))" -lt 90 ] || fail 'overall deadline; leave return to init timer'
    awk 'NF && $3 !~ /^(rootfs|ramfs|tmpfs|devtmpfs|proc|sysfs|devpts|debugfs|configfs)$/ {exit 1}' "$root/proc/mounts" || fail 'non-RAM mount'
    for policy in "$root"/sys/devices/system/cpu/cpufreq/policy*; do
        [ ! -e "$policy" ] || fail 'unexpected CPUfreq policy'
    done
    [ ! -e "$root/sys/kernel/debug/qcom_cpr/debug_info" ] || fail 'unexpected CPR provider'
    zones=0
    for sensor in "$root"/sys/class/thermal/thermal_zone*/temp; do
        [ -f "$sensor" ] || continue
        temp=$(cat "$sensor"); digits=${temp#-}
        case "$digits" in ''|*[!0-9]*) fail 'temperature format';; esac
        [ "$temp" -ge -40000 ] && [ "$temp" -lt 60000 ] || fail 'temperature bounds'
        zones=$((zones+1))
    done
    [ "$zones" -eq 2 ] || fail 'temperature sensors'
    log=$(dmesg) || fail 'kernel log unavailable'
    if printf '%s\n' "$log" | grep -Eiq 'Booting fw image|remoteproc.*powering up |MBA boot|remote processor .* is now up'; then
        fail 'unexpected remoteproc startup'
    fi
}
modules() {
    count=$1
    awk 'NF && (NF<6 || $5!="Live") {exit 1}' "$root/proc/modules" || fail 'module state'
    actual=$(awk 'NF {print $1}' "$root/proc/modules" | sort)
    expected=$(printf '%s\n' "$order" | tr ' ' '\n' | head -n "$count" | sort)
    [ "$actual" = "$expected" ] || fail 'unexpected module set'
}
remoteproc() {
    expected=$1; rproc_count=0
    for device in "$root"/sys/class/remoteproc/remoteproc*; do
        [ -e "$device" ] || continue
        [ -r "$device/name" ] || fail 'remoteproc metadata unavailable'
        rproc_count=$((rproc_count+1))
        [ "$(cat "$device/name")" = fc880000.remoteproc ] || fail 'unexpected remote processor'
        [ "$(cat "$device/state")" = offline ] || fail 'modem is not offline'
        [ "$(cat "$device/firmware")" = mba.b00 ] || fail 'unexpected firmware name'
        [ "$(readlink -f "$device/device")" = "$(readlink -f "$platform")" ] || fail 'wrong modem parent'
        printf '__MODEM_STATE__offline %s\n' "${device#"$root"}"
    done
    [ "$rproc_count" -eq "$expected" ] || fail 'remoteproc count'
    if [ "$expected" -eq 1 ]; then
        [ "$(readlink -f "$platform/driver")" = "$driver" ] || fail 'wrong platform driver'
    else
        [ ! -e "$platform/driver" ] && [ ! -L "$platform/driver" ] || fail 'driver remains bound'
    fi
    for device in "$root"/sys/bus/platform/devices/*bam-dmux*; do
        [ ! -e "$device" ] || fail 'unexpected BAM-DMUX child'
    done
}
operation=0
bounded() {
    guard
    operation=$((operation+1)); label=$1; shift
    status="$work/$operation.status"; output="$work/$operation.log"
    (set +e; "$@" >"$output" 2>&1; rc=$?; printf '%s\n' "$rc" >"$status") &
    child=$!; attempts=0
    while [ ! -r "$status" ]; do
        attempts=$((attempts+1))
        [ "$attempts" -lt 20 ] || fail "operation $label not terminal; leave return to init timer"
        guard
        sleep 1
    done
    wait "$child" || fail 'operation wrapper'
    rc=$(cat "$status")
    printf '__MODEM_OPERATION__%s %s %s\n' "$operation" "$label" "$rc"
    cat "$output"
    [ "$rc" = 0 ] || fail "operation $label failed"
}
guard; modules 0; remoteproc 0
printf '__MODEM_PROBE_BEGIN__%s\n' "$boot_id"
count=0
for module in $order; do
    bounded "load-$module" insmod "$root/modules/$module.ko"
    count=$((count+1)); guard; modules "$count"
    if [ "$count" -eq 5 ]; then remoteproc 1; else remoteproc 0; fi
done
awk '/q6v5 (wdog|fatal|ready|handover|stop)/ {n++; for(i=2;i<=5;i++) {if ($i !~ /^[0-9]+$/) bad=1; total+=$i}} END {exit n!=5 || bad || total>8}' "$root/proc/interrupts" || fail 'missing or excessive modem IRQ counts'
cat "$root/proc/interrupts"
cat "$root/sys/kernel/debug/regulator/regulator_summary"
for module in qcom_q6v5_mss mdt_loader qcom_q6v5 qcom_common qcom_pil_info; do
    remoteproc "$((count==5))"
    bounded "unload-$module" rmmod "$module"
    count=$((count-1)); guard; modules "$count"; remoteproc 0
done
guard; modules 0; remoteproc 0
printf 'MODEM_PROBE_PASS\n'
