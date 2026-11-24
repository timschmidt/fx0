#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# One bounded NCI up/down; no polling, vendor, secure-element or firmware request.
set -eu
root=${FX0_NFC_TEST_ROOT:-}
fail() { printf 'NFC_CONTROLLER_STARTUP_FAIL: %s\n' "$*" >&2; exit 1; }
value() { cat "$root$1" 2>/dev/null; }
[ "$(value /etc/fx0-nfc-controller)" = alpine-r58-controller-startup ] || fail 'lifecycle permit missing'
"$root/bin/nfc-startup-check" || fail 'qualified startup guard'
[ -r "$root/etc/fx0-nfc-controller.sha256" ] || fail 'module manifest missing'
(cd "${root:-/}" && sha256sum -c etc/fx0-nfc-controller.sha256) || fail 'module payload digest'
uptime_seconds() {
    awk 'NR == 1 && $1 ~ /^[0-9]+([.][0-9]+)?$/ {print int($1); ok=1} END {if (!ok) exit 1}' "$root/proc/uptime"
}
started=$(uptime_seconds) || fail 'monotonic clock unavailable'
work="$root/tmp/nfc-controller-startup"
mkdir -m 700 "$work" || fail 'lifecycle already attempted or workspace unavailable'
operation=0
budget() {
    current=$(uptime_seconds) || fail 'monotonic clock unavailable'
    [ "$current" -ge "$started" ] && [ "$((current - started))" -lt 110 ] || fail 'overall deadline; no further module/bind operation'
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
        [ "$attempts" -lt 35 ] || fail "operation $label did not terminate; leave recovery to init timer"
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
    label=$1; bound=$2; configured=$3; active=${4:-0}
    case "$active" in 0|1) :;; *) fail 'invalid active-state selector';; esac
    guard
    printf '__NFC_CONTROLLER_SNAPSHOT__%s\n' "$label"
    cat "$root/proc/sys/kernel/random/boot_id" "$root/proc/modules"
    cp "$root/sys/kernel/debug/clk/clk_summary" "$work/clocks"
    awk -v active="$active" '$1 == "cxo_d1_pin" {n++; if ($2 != active || $3 != active || $4 != 0 || $5 != 19200000) bad=1; print} END {exit n != 1 || bad}' "$work/clocks" || fail 'reference-clock vote does not match controller state'
    cp "$root/sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins" "$work/pins"
    cp "$root/sys/kernel/debug/gpio" "$work/gpio"
    cp "$root/proc/interrupts" "$work/interrupts"
    if [ "$bound" = 1 ]; then
        [ -L "$client/driver" ] && [ "$(readlink -f "$client/driver")" = "$driver" ] || fail 'NFC driver not bound'
        class_count 1; rfkill_count 1
        for pin in 20 21 22; do
            awk -v p="$pin" -v owner="$client_name" '$1 == "pin" && $2 == p {n++; if ($4 != "device" || $5 != owner || $6 != "function" || $7 != "gpio" || $8 != "group" || $9 != "gpio"p) bad=1; print} END {exit n != 1 || bad}' "$work/pins" || fail 'NFC pinmux owner mismatch'
        done
        awk '$NF == "nxp-nci_i2c" {n++; for (i=2;i<=5;i++) {if ($i !~ /^[0-9]+$/) bad=1; total+=$i}; print} END {exit n != 1 || bad || total > 64}' "$work/interrupts" || fail 'missing or excessive NFC IRQ'
        NFC_IRQ_TOTAL=$(awk '$NF == "nxp-nci_i2c" {for (i=2;i<=5;i++) total+=$i} END {print total+0}' "$work/interrupts")
        [ "$active" != 1 ] || [ "$NFC_IRQ_TOTAL" -gt 0 ] || fail 'active controller without IRQ activity'
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
            drive=2mA; level=low
            if [ "$pin" = 22 ]; then drive=8mA; elif [ "$active" = 1 ]; then level=high; fi
            awk -v p="gpio$pin" -v drive="$drive" -v level="$level" '$1 == p {n++; if ($2 != ":" || $3 != "out" || $4 != level || $5 != "func0" || $6 != drive || $7 != "no" || $8 != "pull" || NF != 8) bad=1; print} END {exit n != 1 || bad}' "$work/gpio" || fail 'enable/firmware GPIO does not match controller state'
        done
        awk '$1 == "gpio21" {n++; if ($2 != ":" || $3 != "in" || ($4 != "low" && $4 != "high") || $5 != "func0" || $6 != "8mA" || $7 != "pull" || $8 != "down" || NF != 8) bad=1; print} END {exit n != 1 || bad}' "$work/gpio" || fail 'IRQ GPIO configuration changed'
    fi
}

write_debug() {
    case "$1" in nci_core_reset_rsp_packet|nci_core_init_rsp_packet\*|nci_rf_disc_map_rsp_packet|nci_core_reset_ntf_packet) :;; *) return 99;; esac
    printf 'module nci func %s +p\n' "$1" > "$root/sys/kernel/debug/dynamic_debug/control"
}
check_debug() {
    cp "$root/sys/kernel/debug/dynamic_debug/control" "$work/debug-control"
    awk -v selector="$1" '
    BEGIN {prefix="[nci]"selector; wildcard=(substr(prefix,length(prefix))=="*"); if(wildcard) prefix=substr(prefix,1,length(prefix)-1)}
    (wildcard && index($2,prefix)==1) || (!wildcard && $2==prefix) {n++; if(index($3,"p")==0) bad=1; print}
    END {exit n==0 || bad}' "$work/debug-control" || fail 'targeted NCI debug not enabled'
}
state_result() {
    [ "$(wc -l < "$OP_LOG")" -eq 1 ] || fail 'unexpected controller helper output'
    grep -Fq '{"ok":true,"action":"'"$1"'","index":'"$index"',' "$OP_LOG" || fail 'wrong controller action/index'
    grep -Fq '"name":"'"$nfc_name"'","protocols":126,"powered_before":'"$2"',"powered_after":'"$3"',"rf_mode":2,' "$OP_LOG" || fail 'wrong powered state or active RF mode'
}
responses() {
    phase=$1
    dmesg > "$work/responses-$phase" || fail 'kernel log read failed'
    awk '/nci_core_reset_rsp_packet: status / || /nci_core_init_rsp_packet_v[12]: status / || /nci_rf_disc_map_rsp_packet: status / {status=$NF; sub(/^0x/,"",status); if(status !~ /^0+$/) bad=1} END {exit bad}' "$work/responses-$phase" || fail 'NCI response reports failure'
    resets=$(awk '/nci_core_reset_rsp_packet: status 0x0$/ {n++} END {print n+0}' "$work/responses-$phase")
    required=1; [ "$phase" != closed ] || required=2
    [ "$resets" -ge "$required" ] || fail 'reset response missing'
    grep -Eq 'nci_core_init_rsp_packet_v[12]: status (0x)?0$' "$work/responses-$phase" || fail 'core init response missing'
    grep -Eq 'nci_rf_disc_map_rsp_packet: status 0x0$' "$work/responses-$phase" || fail 'RF mapping response missing'
    grep -Eq 'nci_core_reset_(rsp|ntf)_packet: nci_ver 0x[12][0-9a-f],' "$work/responses-$phase" || fail 'supported NCI version missing'
    grep -Eq 'nci_core_init_rsp_packet: manufact_id 0x[1-9a-f][0-9a-f]*$' "$work/responses-$phase" || fail 'manufacturer ID missing'
    grep -Eq 'nci_core_init_rsp_packet: manufact_specific_info 0x[0-9a-f]+$' "$work/responses-$phase" || fail 'manufacturer information missing'
    printf '__NFC_CONTROLLER_RESPONSES__%s\n' "$phase"
    grep -E 'nci_core_(reset_(rsp|ntf)_packet|init_rsp_packet)|nci_rf_disc_map_rsp_packet' "$work/responses-$phase"
}
modules ''; snapshot before 0 0 0
loaded=
for file in rfkill nfc nci nxp-nci nxp-nci_i2c; do
    bounded "load-$file" insmod "$root/modules/$file.ko"
    [ "$OP_RC" -eq 0 ] || fail "module load failed: $file"
    name=$(printf '%s' "$file" | tr '-' '_'); loaded="$loaded $name"
    [ -d "$root/sys/module/$name" ] || fail 'module init missing'
    modules "$loaded"; guard
done
snapshot registered 1 1 0
set -- "$root"/sys/class/nfc/nfc[0-9]*
[ "$#" -eq 1 ] && [ -e "$1" ] || fail 'expected one NFC interface'
nfc_name=${1##*/}; index=${nfc_name#nfc}
case "$index" in ''|*[!0-9]*) fail 'invalid NFC index';; esac
for function in nci_core_reset_rsp_packet nci_core_init_rsp_packet\* nci_rf_disc_map_rsp_packet nci_core_reset_ntf_packet; do
    bounded "debug-$function" write_debug "$function"
    [ "$OP_RC" -eq 0 ] || fail 'targeted NCI debug write failed'
    check_debug "$function"; guard
done
bounded observe-before "$root/bin/nfc-state" get "$index"
[ "$OP_RC" -eq 0 ] || fail 'controller baseline query failed'
state_result get 0 0
bounded controller-up "$root/bin/nfc-state" up "$index"
[ "$OP_RC" -eq 0 ] || fail 'controller up did not complete successfully'
state_result up 0 1
snapshot active 1 1 1
responses initialized
sleep 1
bounded observe-active "$root/bin/nfc-state" get "$index"
[ "$OP_RC" -eq 0 ] || fail 'active controller query failed'
state_result get 1 1
snapshot active-quiet 1 1 1
bounded controller-down "$root/bin/nfc-state" down "$index"
[ "$OP_RC" -eq 0 ] || fail 'controller down did not complete successfully'
state_result down 1 0
snapshot returned-cold 1 1 0
responses closed
last_irq=$NFC_IRQ_TOTAL
sleep 1
bounded observe-cold "$root/bin/nfc-state" get "$index"
[ "$OP_RC" -eq 0 ] || fail 'cold controller query failed'
state_result get 0 0
snapshot cold-quiet 1 1 0
[ "$NFC_IRQ_TOTAL" -eq "$last_irq" ] || fail 'IRQ activity continues in cold mode'
for file in nxp-nci_i2c nxp-nci nci nfc rfkill; do
    name=$(printf '%s' "$file" | tr '-' '_')
    bounded "unload-$file" rmmod "$name"
    [ "$OP_RC" -eq 0 ] || fail "module unload failed: $name"
    [ ! -e "$root/sys/module/$name" ] || fail 'module remains after unload'
    loaded=$(printf '%s\n' "$loaded" | awk -v remove="$name" '{for(i=1;i<=NF;i++) if($i!=remove) printf "%s ",$i}')
    modules "$loaded"; guard
done
modules ''; snapshot finished 0 1 0
printf 'NFC_CONTROLLER_STARTUP_PASS\n'
