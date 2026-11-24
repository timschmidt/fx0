#!/bin/sh
# Read-only first-startup checks. No module load, GPIO write, bus/RF scan or firmware action.
set -eu
root=${FX0_NFC_TEST_ROOT:-}
fail() { printf 'NFC_STARTUP_FAIL: %s\n' "$*" >&2; exit 1; }
value() { cat "$root$1" 2>/dev/null; }
check_modules() {
    [ -r "$root/proc/modules" ] || fail 'module list unavailable'
    loaded=$(value /proc/modules) || fail 'module list unavailable'
    [ -z "$loaded" ] || fail 'unexpected loaded modules'
}
[ "$(value /etc/fx0-nfc-trial)" = alpine-r59-moduleless-startup ] || fail 'trial marker missing'
[ "$(uname -r)" = 6.18.59-fx0-nfc-open-teardown-alpine ] || fail 'wrong kernel release'
expected=$(value /etc/fx0-nfc-notes.sha256)
case "$expected" in ''|*[!0-9a-f]*) fail 'invalid kernel-note fingerprint';; esac
[ "${#expected}" -eq 64 ] || fail 'invalid kernel-note fingerprint'
actual=$(sha256sum "$root/sys/kernel/notes") || fail 'kernel notes unavailable'
[ "${actual%% *}" = "$expected" ] || fail 'wrong linked kernel build'
[ "$(value /sys/module/module/parameters/sig_enforce)" = Y ] || fail 'module signatures not enforced'
cmdline=$(value /proc/cmdline)
case " $cmdline " in *' module.sig_enforce=1 '*) :;; *) fail 'signature boot parameter missing';; esac
[ "$(value /sys/module/cpufreq/parameters/default_governor)" = schedutil ] || fail 'wrong compiled/default governor'
[ "$(value /proc/sys/kernel/tainted)" = 0 ] || fail 'kernel tainted'
check_modules
boot_id=$(value /proc/sys/kernel/random/boot_id) || fail 'RAM boot ID unavailable'
case "$boot_id" in
    ????????-????-????-????-????????????) :;;
    *) fail 'invalid RAM boot ID';;
esac
case "$boot_id" in *[!0-9a-f-]*) fail 'invalid RAM boot ID';; esac
boot_hex=$(printf '%s' "$boot_id" | tr -d '-')
[ "${#boot_hex}" -eq 32 ] || fail 'invalid RAM boot ID'
[ "$(value /sys/devices/system/cpu/online)" = 0-3 ] || fail 'CPU topology changed'
for policy in "$root"/sys/devices/system/cpu/cpufreq/policy*; do
    [ ! -e "$policy" ] || fail 'unexpected CPUfreq policy in moduleless trial'
done
[ ! -e "$root/sys/kernel/debug/qcom_cpr/debug_info" ] || fail 'unexpected CPR provider'
[ -r "$root/proc/mounts" ] || fail 'mount table unavailable'
awk 'NF && $3 !~ /^(rootfs|ramfs|tmpfs|devtmpfs|proc|sysfs|devpts|debugfs|configfs)$/ {exit 1}' "$root/proc/mounts" || fail 'unexpected filesystem mount'
zones=0
for sensor in "$root"/sys/class/thermal/thermal_zone*/temp; do
    [ -f "$sensor" ] || continue
    temp=$(cat "$sensor")
    case "$temp" in -*) digits=${temp#-};; *) digits=$temp;; esac
    case "$digits" in ''|*[!0-9]*) fail 'invalid temperature';; esac
    [ "$temp" -ge -40000 ] && [ "$temp" -lt 60000 ] || fail 'temperature outside bounds'
    zones=$((zones + 1))
done
[ "$zones" -eq 2 ] || fail 'expected two temperature sensors'
node="$root/sys/firmware/devicetree/base/soc/i2c@f9925000/nfc@28"
[ "$(tr '\000' '\n' < "$node/compatible")" = "$(printf 'nxp,pn547\nnxp,nxp-nci-i2c')" ] || fail 'wrong NFC compatible'
[ "$(tr -d '\000' < "$node/../status")" = okay ] || fail 'QUP3 disabled'
if [ -e "$node/status" ]; then
    [ "$(tr -d '\000' < "$node/status")" = okay ] || fail 'NFC client disabled'
fi
count=0
client=
for device in "$root"/sys/bus/i2c/devices/*-0028; do
    [ -d "$device" ] || continue
    [ "$(readlink -f "$device/of_node")" = "$node" ] || continue
    [ ! -L "$device/driver" ] && [ ! -e "$device/driver" ] || fail 'NFC client unexpectedly bound'
    count=$((count + 1)); client=$device
done
[ "$count" -eq 1 ] || fail 'expected one unbound QUP3 NFC client'
awk '$1 == "cxo_d1_pin" {n++; if ($2 != 0 || $3 != 0 || $4 != 0 || $5 != 19200000) bad=1} END {exit n != 1 || bad}' "$root/sys/kernel/debug/clk/clk_summary" || fail 'moduleless reference-clock vote changed'
for pin in 20 21 22; do
    awk -v p="$pin" '$1 == "pin" && $2 == p {n++; if ($4 != "UNCLAIMED" || NF != 4) bad=1} END {exit n != 1 || bad}' "$root/sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins" || fail 'moduleless NFC pin owner present'
done
for pin in 20 22; do
    awk -v p="gpio$pin" '$1 == p {n++; if ($2 != ":" || $3 != "in" || $4 != "low" || $5 != "func0" || $6 != "2mA" || $7 != "pull" || $8 != "down" || NF != 8) bad=1} END {exit n != 1 || bad}' "$root/sys/kernel/debug/gpio" || fail 'moduleless enable/firmware GPIO changed'
done
awk '$1 == "gpio21" {n++; if ($2 != ":" || $3 != "in" || ($4 != "low" && $4 != "high") || $5 != "func0" || $6 != "2mA" || $7 != "pull" || $8 != "up" || NF != 8) bad=1} END {exit n != 1 || bad}' "$root/sys/kernel/debug/gpio" || fail 'moduleless IRQ GPIO changed'
printf '__NFC_STARTUP_BEGIN__\n'
printf '__NFC_BOOT_ID__%s\n' "$boot_id"
uname -a
printf '__NFC_CLIENT__%s\n' "${client#"$root"}"
for file in /proc/cmdline /proc/modules /proc/mounts /proc/interrupts /sys/devices/system/cpu/online /sys/kernel/debug/devices_deferred /sys/kernel/debug/clk/clk_summary /sys/kernel/debug/regulator/regulator_summary /sys/kernel/debug/gpio; do
    printf '__FILE__%s\n' "$file"
    if [ -r "$root$file" ]; then cat "$root$file"; fi
done
check_modules
[ "$(value /proc/sys/kernel/tainted)" = 0 ] || fail 'state changed during snapshot'
printf 'NFC_STARTUP_PASS\n'
