#!/bin/sh
# SPDX-License-Identifier: MIT
# Fx0 stock-kernel RAM diagnostic; the host must verify the selected unit first.
set -eu
case "${1-}" in ''|--debug) ;; *) exit 2 ;; esac

battery=/sys/class/power_supply/battery
bms=/sys/class/power_supply/bms
charge=$bms/charge
spmi=/sys/kernel/debug/spmi/spmi-0

printf 'PREFLIGHT_KERNEL '; uname -r
printf 'PREFLIGHT_UPTIME '; cat /proc/uptime
for supply in battery bms usb; do
    for key in present status health temp charge voltage_now current_now; do
        file=/sys/class/power_supply/$supply/$key
        if test -f "$file"; then
            printf 'PREFLIGHT_%s/%s=' "$supply" "$key"
            cat "$file"
        fi
    done
done
if test -f "$charge"; then
    printf 'PREFLIGHT_CHARGE_MODE='; stat -c '%a' "$charge"
else
    printf 'PREFLIGHT_CHARGE_ATTRIBUTE_ABSENT\n'
fi

case "$(uname -r)" in 3.4.0*) ;; *) exit 1 ;; esac
if grep -Eq '^/dev/' /proc/mounts; then exit 1; fi
test -f "$charge"
test -f "$spmi/data_raw"
test "$(cat "$battery/present")" = 1
test "$(cat "$battery/status")" = Charging
test "$(cat "$battery/health")" = Good
test "$(cat "$charge")" = 1
boot_seconds=$(cut -d. -f1 /proc/uptime)
test "$boot_seconds" -lt 55

old_address=$(cat "$spmi/address")
old_count=$(cat "$spmi/count")
old_mode=$(stat -c '%a' "$charge")
control_changed=0
debug_restore=

read_control()
{
    echo 0x1049 >"$spmi/address"
    echo 1 >"$spmi/count"
    printf 'CONTROL_SELECTOR_ADDRESS=' >&2; cat "$spmi/address" >&2
    printf 'CONTROL_SELECTOR_COUNT=' >&2; cat "$spmi/count" >&2
    dd if="$spmi/data_raw" bs=64 count=1 2>/dev/null | tr -d ' \r\n'
}

restore_allowed()
{
    test "$(cat "$battery/present")" = 1 &&
    test "$(cat "$battery/health")" = Good &&
    test "$(cat "$battery/temp")" -ge 0 &&
    test "$(cat "$battery/temp")" -lt 450
}

cleanup()
{
    set +e
    if test "$control_changed" = 1; then
        if restore_allowed; then
            echo 1 >"$charge"
            printf 'CLEANUP_CHARGER_CONTROL=%s\n' "$(read_control)"
        else
            printf 'CLEANUP_CHARGING_LEFT_DISABLED_SENSOR_GUARD\n'
        fi
    fi
    chmod "$old_mode" "$charge"
    echo "$old_address" >"$spmi/address"
    echo "$old_count" >"$spmi/count"
    if test -n "$debug_restore"; then
        while IFS= read -r query; do
            echo "$query" > /sys/kernel/debug/dynamic_debug/control
        done < "$debug_restore"
        rm -f "$debug_restore"
    fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if test "${1-}" = --debug; then
    debug_control=/sys/kernel/debug/dynamic_debug/control
    test -f "$debug_control"
    debug_restore=/tmp/fx0-bms-dyndbg-restore.$$
    selected=/tmp/fx0-bms-dyndbg-selected.$$
    grep -E '\](read_soc_params_raw|recalculate_soc|batfet_status_check|charging_ended|battery_status_check|qpnp_iadc_calibrate_for_trim|qpnp_check_pmic_temp|reset_cc) ' \
        "$debug_control" > "$selected"
    test -s "$selected"
    awk '{ split($1, at, ":"); flag = ($3 ~ /p/) ? "+p" : "-p"; print "file " at[1] " line " at[2] " " flag }' \
        "$selected" > "$debug_restore"
    awk '{ split($1, at, ":"); print "file " at[1] " line " at[2] " +p" }' \
        "$selected" | while IFS= read -r query; do
            echo "$query" > "$debug_control"
        done
    printf 'DEBUG_SELECTED_CALLSITES='; wc -l < "$selected"
    rm -f "$selected"
fi

original_control=$(read_control)
printf 'PREFLIGHT_CHARGER_CONTROL=%s\n' "$original_control"
test "$((original_control & 128))" -eq 128
test "$((original_control & 1))" -eq 0
restore_allowed
# The stock visibility callback removes owner-write despite a factory store hook.
chmod u+w "$charge"

take()
{
    printf 'SAMPLE %s\n' "$1"
    if test "${debug_restore:-}" != ''; then
        echo "<6>fx0_bms_capture $1" > /dev/kmsg
    fi
    printf 'UPTIME '; cat /proc/uptime
    for spec in 1010:1 1049:1 1209:1 1210:1 1310:1 1344:1 \
                4008:1 4040:1 4042:1 4043:1 405a:1 4061:1 \
                3848:2 385b:1 4098:2 408a:5 40a8:5 36f2:4; do
        address=${spec%:*}
        count=${spec#*:}
        echo "0x$address" >"$spmi/address"
        echo "$count" >"$spmi/count"
        printf 'REGISTER_0x%s\n' "$address"
        cat "$spmi/data_raw"
    done
    for supply in battery bms usb; do
        printf 'SUPPLY %s\n' "$supply"
        for key in present online status health charge charging_enabled \
                   voltage_now current_now temp charge_counter \
                   charge_counter_shadow current_max input_current_max; do
            file=/sys/class/power_supply/$supply/$key
            if test -f "$file"; then
                printf '%s=' "$key"
                cat "$file"
            fi
        done
    done
    for adc in /sys/bus/spmi/devices/*; do
        if test -f "$adc/external_rsense"; then
            printf 'ADC_EXTERNAL_RSENSE\n'
            cat "$adc/external_rsense"
        fi
    done
    restore_allowed
}

printf 'ORIGINAL_CHARGER_CONTROL=%s\n' "$original_control"
take charging-before-0
sleep 2
take charging-before-2

control_changed=1
echo 0 >"$charge"
disabled_control=$(read_control)
printf 'DISABLED_CHARGER_CONTROL=%s\n' "$disabled_control"
test "$((disabled_control & 128))" -eq 0
test "$((disabled_control & 1))" -eq 0
take stopped-0
sleep 1
take stopped-1
sleep 4
take stopped-5
sleep 10
take stopped-15
sleep 10
take stopped-25

restore_allowed
echo 1 >"$charge"
restored_control=$(read_control)
printf 'RESTORED_CHARGER_CONTROL=%s\n' "$restored_control"
test "$restored_control" = "$original_control"
control_changed=0
sleep 2
take restarted-2
sleep 3
take restarted-5
printf 'CAPTURE_COMPLETED\n'
