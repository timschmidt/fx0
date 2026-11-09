#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Bounded cold registration only. No NCI up/reset, polling, RF or firmware command.
set -eu
root=${FX0_NFC_TEST_ROOT:-}
fail() { printf 'NFC_COLD_LIFECYCLE_FAIL: %s\n' "$*" >&2; exit 1; }
value() { cat "$root$1" 2>/dev/null; }
[ "$(value /etc/fx0-nfc-lifecycle)" = alpine-r58-cold-lifecycle ] || fail 'lifecycle permit missing'
"$root/bin/nfc-startup-check" || fail 'qualified startup guard'
[ -r "$root/etc/fx0-nfc-modules.sha256" ] || fail 'module manifest missing'
(cd "${root:-/}" && sha256sum -c etc/fx0-nfc-modules.sha256) || fail 'module payload digest'
uptime_seconds() {
    awk 'NR == 1 && $1 ~ /^[0-9]+([.][0-9]+)?$/ {print int($1); ok=1} END {if (!ok) exit 1}' "$root/proc/uptime"
}
started=$(uptime_seconds) || fail 'monotonic clock unavailable'
work="$root/tmp/nfc-cold-lifecycle"
mkdir -m 700 "$work" || fail 'lifecycle already attempted or workspace unavailable'
operation=0
budget() {
    current=$(uptime_seconds) || fail 'monotonic clock unavailable'
    [ "$current" -ge "$started" ] && [ "$((current - started))" -lt 90 ] || fail 'overall deadline; no further module/bind operation'
}
bounded() {
    budget
    operation=$((operation + 1))
    label=$1; shift
    output="$work/op-$operation.log"; status="$work/op-$operation.status"
    (set +e; "$@" > "$output" 2>&1; result=$?; printf '%s\n' "$result" > "$status") &
    child=$!
    attempts=0
    while [ ! -r "$status" ]; do
        attempts=$((attempts + 1))
        [ "$attempts" -lt 20 ] || fail "operation $label did not terminate; leave recovery to init timer"
        budget
        sleep 1
    done
    wait "$child" || fail 'operation status wrapper failed'
    OP_RC=$(cat "$status")
    case "$OP_RC" in ''|*[!0-9]*) fail 'invalid operation status';; esac
    [ "$OP_RC" -le 255 ] || fail 'invalid operation status'
    OP_LOG=$output
    printf '__NFC_OPERATION__%s %s %s\n' "$operation" "$label" "$OP_RC"
    cat "$output"
}
modules() {
    expected=$1
    awk 'NF && (NF < 6 || $5 != "Live") {exit 1}' "$root/proc/modules" || fail 'module state not Live'
    actual=$(awk 'NF {print $1}' "$root/proc/modules" | sort)
    wanted=$(for name in $expected; do printf '%s\n' "$name"; done | sort)
    [ "$actual" = "$wanted" ] || fail 'unexpected module set'
}
guard() {
    budget
    [ "$(value /proc/sys/kernel/tainted)" = 0 ] || fail 'kernel tainted'
    [ "$(value /sys/module/module/parameters/sig_enforce)" = Y ] || fail 'signature enforcement changed'
    [ "$(value /sys/module/cpufreq/parameters/default_governor)" = schedutil ] || fail 'default governor changed'
    [ "$(value /sys/devices/system/cpu/online)" = 0-3 ] || fail 'CPU topology changed'
    for p in "$root"/sys/devices/system/cpu/cpufreq/policy*; do [ ! -e "$p" ] || fail 'CPUfreq policy appeared'; done
    [ ! -e "$root/sys/kernel/debug/qcom_cpr/debug_info" ] || fail 'CPR provider appeared'
    awk 'NF && $3 !~ /^(rootfs|ramfs|tmpfs|devtmpfs|proc|sysfs|devpts|debugfs|configfs)$/ {exit 1}' "$root/proc/mounts" || fail 'unexpected filesystem mount'
    sensors=0
    for sensor in "$root"/sys/class/thermal/thermal_zone*/temp; do
        [ -f "$sensor" ] || continue
        temp=$(cat "$sensor")
        case "$temp" in -*) digits=${temp#-};; *) digits=$temp;; esac
        case "$digits" in ''|*[!0-9]*) fail 'invalid temperature';; esac
        [ "$temp" -ge -40000 ] && [ "$temp" -lt 60000 ] || fail 'temperature outside bounds'
        printf '__NFC_TEMPERATURE__%s=%s\n' "${sensor#"$root"}" "$temp"
        sensors=$((sensors + 1))
    done
    [ "$sensors" -eq 2 ] || fail 'expected two temperatures'
}
node="$root/sys/firmware/devicetree/base/soc/i2c@f9925000/nfc@28"
client=
for device in "$root"/sys/bus/i2c/devices/*-0028; do
    [ -d "$device" ] || continue
    [ "$(readlink -f "$device/of_node")" = "$node" ] || continue
    [ -z "$client" ] || fail 'duplicate NFC client'
    client=$device
done
[ -n "$client" ] || fail 'missing NFC client'
client_name=${client##*/}; client_real=$(readlink -f "$client")
driver="$root/sys/bus/i2c/drivers/nxp-nci_i2c"
write_binding() {
    case "$1" in bind|unbind) printf '%s\n' "$client_name" > "$driver/$1";; *) return 99;; esac
}
class_count() {
    count=0
    for device in "$root"/sys/class/nfc/nfc*; do
        [ -e "$device" ] || continue
        case "$(readlink -f "$device")" in "$client_real"/nfc/nfc[0-9]*) :;; *) fail 'NFC class parent mismatch';; esac
        count=$((count + 1))
    done
    [ "$count" -eq "$1" ] || fail 'unexpected NFC class count'
}
rfkill_count() {
    count=0
    for device in "$root"/sys/class/rfkill/rfkill*; do
        [ -r "$device/type" ] || continue
        [ "$(cat "$device/type")" = nfc ] || fail 'unexpected rfkill type'
        case "$(readlink -f "$device/device")" in "$client_real"/nfc/nfc[0-9]*) :;; *) fail 'rfkill parent mismatch';; esac
        printf '__NFC_RFKILL__%s soft=%s hard=%s\n' "${device#"$root"}" "$(cat "$device/soft")" "$(cat "$device/hard")"
        count=$((count + 1))
    done
    [ "$count" -eq "$1" ] || fail 'unexpected rfkill count'
}
snapshot() {
    label=$1; bound=$2; configured=$3
    guard
    printf '__NFC_COLD_SNAPSHOT__%s\n' "$label"
    cat "$root/proc/sys/kernel/random/boot_id" "$root/proc/modules"
    cp "$root/sys/kernel/debug/clk/clk_summary" "$work/clocks"
    awk '$1 == "cxo_d1_pin" {n++; if ($2 != 0 || $3 != 0 || $4 != 0 || $5 != 19200000) bad=1; print} END {exit n != 1 || bad}' "$work/clocks" || fail 'cold reference-clock vote changed'
    cp "$root/sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins" "$work/pins"
    cp "$root/sys/kernel/debug/gpio" "$work/gpio"
    cp "$root/proc/interrupts" "$work/interrupts"
    if [ "$bound" = 1 ]; then
        [ -L "$client/driver" ] && [ "$(readlink -f "$client/driver")" = "$driver" ] || fail 'NFC driver not bound'
        class_count 1; rfkill_count 1
        for pin in 20 21 22; do
            awk -v p="$pin" -v owner="$client_name" '$1 == "pin" && $2 == p {n++; if ($4 != "device" || $5 != owner || $6 != "function" || $7 != "gpio" || $8 != "group" || $9 != "gpio"p) bad=1; print} END {exit n != 1 || bad}' "$work/pins" || fail 'NFC pinmux owner mismatch'
        done
        awk '$NF == "nxp-nci_i2c" {n++; for (i=2;i<=5;i++) {if ($i !~ /^[0-9]+$/) bad=1; total+=$i}; print} END {exit n != 1 || bad || total > 8}' "$work/interrupts" || fail 'missing or excessive NFC IRQ'
    else
        [ ! -L "$client/driver" ] && [ ! -e "$client/driver" ] || fail 'NFC driver remains bound'
        class_count 0; rfkill_count 0
        for pin in 20 21 22; do
            awk -v p="$pin" '$1 == "pin" && $2 == p {n++; if ($4 != "UNCLAIMED" || NF != 4) bad=1; print} END {exit n != 1 || bad}' "$work/pins" || fail 'NFC pin owner not released'
        done
        awk '$NF == "nxp-nci_i2c" {found=1} END {exit found}' "$work/interrupts" || fail 'NFC IRQ not released'
    fi
    if [ "$configured" = 1 ]; then
        for pin in 20 22; do
            drive=2mA; [ "$pin" != 22 ] || drive=8mA
            awk -v p="gpio$pin" -v drive="$drive" '$1 == p {n++; if ($2 != ":" || $3 != "out" || $4 != "low" || $5 != "func0" || $6 != drive || $7 != "no" || $8 != "pull" || NF != 8) bad=1; print} END {exit n != 1 || bad}' "$work/gpio" || fail 'enable/firmware GPIO not cold'
        done
        awk '$1 == "gpio21" {n++; if ($2 != ":" || $3 != "in" || ($4 != "low" && $4 != "high") || $5 != "func0" || $6 != "8mA" || $7 != "pull" || $8 != "down" || NF != 8) bad=1; print} END {exit n != 1 || bad}' "$work/gpio" || fail 'IRQ GPIO configuration changed'
    fi
}
modules ''; snapshot before 0 0
for control in unsigned badsig; do
    bounded "reject-$control" insmod "$root/modules/rfkill-$control.ko"
    [ "$OP_RC" -ne 0 ] || fail 'invalid signature unexpectedly accepted'
    grep -Eq 'Key was rejected by service|Required key not available' "$OP_LOG" || fail 'module rejection was not a key error'
    modules ''; guard
    printf '__NFC_SIGNATURE_REJECTED__%s\n' "$control"
done
loaded=
for file in rfkill nfc nci nxp-nci nxp-nci_i2c; do
    bounded "load-$file" insmod "$root/modules/$file.ko"
    [ "$OP_RC" -eq 0 ] || fail "module load failed: $file"
    name=$(printf '%s' "$file" | tr '-' '_'); loaded="$loaded $name"
    [ -d "$root/sys/module/$name" ] || fail 'module init missing'
    modules "$loaded"; guard
done
snapshot registered 1 1
for round in 1 2 3; do
    bounded "unbind-$round" write_binding unbind
    [ "$OP_RC" -eq 0 ] || fail 'NFC unbind failed'
    snapshot "unbound-$round" 0 1
    bounded "bind-$round" write_binding bind
    [ "$OP_RC" -eq 0 ] || fail 'NFC bind failed'
    snapshot "rebound-$round" 1 1
    sleep 1
    snapshot "quiet-$round" 1 1
done
for file in nxp-nci_i2c nxp-nci nci nfc rfkill; do
    name=$(printf '%s' "$file" | tr '-' '_')
    bounded "unload-$file" rmmod "$name"
    [ "$OP_RC" -eq 0 ] || fail "module unload failed: $name"
    [ ! -e "$root/sys/module/$name" ] || fail 'module remains after unload'
    loaded=$(printf '%s\n' "$loaded" | awk -v remove="$name" '{for (i=1;i<=NF;i++) if ($i != remove) printf "%s ", $i}')
    modules "$loaded"; guard
done
modules ''; snapshot finished 0 1
printf 'NFC_COLD_LIFECYCLE_PASS\n'
