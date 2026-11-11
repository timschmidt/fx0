#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
fail() { printf 'VIBRATOR_RAM_FAIL %s\n' "$*"; exit 1; }
value() { cat "$1" 2>/dev/null; }
[ "$(value /etc/fx0-vibrator-trial)" = reconstructed-r50-vibrator ] || fail 'trial permit'
[ "$(uname -r)" = 6.18.59-fx0-dmp ] || fail 'kernel release'
[ "$(value /sys/module/module/parameters/sig_enforce)" = Y ] || fail 'signature enforcement'
notes=$(sha256sum /sys/kernel/notes)
[ "${notes%% *}" = "$(value /etc/fx0-vibrator-notes.sha256)" ] || fail 'kernel notes'
(cd / && sha256sum -c etc/fx0-vibrator-inputs.sha256) || fail 'payload and DT hashes'
guard() {
    [ "$(value /proc/sys/kernel/tainted)" = "$1" ] || fail 'unexpected kernel taint'
    awk 'NR==1 && $1 ~ /^[0-9]+[.][0-9]+$/ && $1 < 120 {ok=1} END {exit !ok}' /proc/uptime || fail 'trial deadline'
    awk '
        NF && $3 !~ /^(rootfs|ramfs|tmpfs|devtmpfs|proc|sysfs|devpts|debugfs|configfs)$/ {bad=1}
        $2=="/" && $3 ~ /^(rootfs|ramfs|tmpfs)$/ {ram=1}
        $2=="/dev" && $3=="devtmpfs" {dev=1}
        END {exit bad || !ram || !dev}
    ' /proc/mounts || fail 'RAM mounts'
    [ "$(value /sys/kernel/debug/regmap/0-01/range)" = 0-ffff ] || fail 'PMIC map'
    for policy in /sys/devices/system/cpu/cpufreq/policy*; do
        [ ! -e "$policy" ] || fail 'unexpected CPUfreq policy'
    done
    zones=0
    for sensor in /sys/class/thermal/thermal_zone*/temp; do
        temp=$(cat "$sensor")
        [ "$temp" -ge -40000 ] && [ "$temp" -lt 60000 ] || fail 'temperature bounds'
        zones=$((zones+1))
    done
    [ "$zones" -eq 2 ] || fail 'temperature sensors'
}
module_set() {
    names=$(awk 'NF {if(NF<6 || $5!="Live") exit 1; print $1}' /proc/modules) || fail 'module state'
    [ "$names" = "$1" ] || fail 'module set'
}
guard 0; module_set ''
mkdir -m 700 /tmp/vibrator-trial || fail 'already attempted'
printf 'VIBRATOR_RAM_BEGIN %s\n' "$(cat /proc/sys/kernel/random/boot_id)"
insmod /modules/evdev.ko || fail 'signed evdev load'
guard 0; module_set evdev
insmod /modules/pm8xxx-vibrator.ko || fail 'signed module load'
guard 4096; module_set "$(printf 'pm8xxx_vibrator\nevdev')"
count=0; event=
for node in /sys/class/input/event*/device/name; do
    [ -r "$node" ] || continue
    [ "$(cat "$node")" = pm8xxx_vib_ffmemless ] || continue
    input=${node%/device/name}; name=${input##*/}
    parent=$(readlink -f "$input/device/device")
    case "$parent" in */0-01/fc4cf000.spmi:pm8226@1:vibrator@c000) :;; *) fail 'vibrator parent';; esac
    event=/dev/input/$name
    [ -c "$event" ] || fail 'input character device'
    count=$((count+1))
done
[ "$count" -eq 1 ] || fail 'vibrator input count'
printf 'VIBRATOR_RAM_INPUT %s\n' "$event"
/bin/vibrator-pulses "$event" || fail 'pulse and intensity checks'
guard 4096; module_set "$(printf 'pm8xxx_vibrator\nevdev')"
rmmod pm8xxx_vibrator || fail 'module removal'
guard 4096; module_set evdev
for node in /sys/class/input/event*/device/name; do
    [ ! -r "$node" ] || [ "$(cat "$node")" != pm8xxx_vib_ffmemless ] || fail 'input remains'
done
rmmod evdev || fail 'evdev removal'
guard 4096; module_set ''
printf 'VIBRATOR_RAM_PASS\n'
