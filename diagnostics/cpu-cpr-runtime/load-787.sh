#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Repeated transitions and bounded four-core load; no request above 787.2 MHz.
set -eu
fail() { echo "CPR_LOAD_FAILED: $*" >&2; exit 1; }
[ "$(cat /etc/fx0-cpr-load-step)" = 787-repeat-load ] || fail 'missing load permit'
/bin/cpr-register || fail 'registration gate'
policy=/sys/devices/system/cpu/cpufreq/policy0
printf '787200\n' > "$policy/scaling_max_freq"
printf '300000\n' > "$policy/scaling_min_freq"
limits_ready=0
for i in $(seq 1 30); do
    if [ "$(cat "$policy/scaling_max_freq")" = 787200 ] &&
       [ "$(cat "$policy/scaling_min_freq")" = 300000 ]; then limits_ready=1; break; fi
    sleep 0.1
done
[ "$limits_ready" = 1 ] || fail 'limits did not settle'
irq_total() {
    awk '$NF == "cpr" { n++; for (i=2;i<=5;i++) { if ($i !~ /^[0-9]+$/) exit 1; total+=$i } }
         END { if (n != 1) exit 1; printf "%.0f\n", total }' /proc/interrupts
}
check_temperatures() {
    temperatures=; sensor_count=0
    for sensor in /sys/class/thermal/thermal_zone*/temp; do
        temp=$(cat "$sensor") || return 1
        case "$temp" in ''|*[!0-9-]*) return 1 ;; esac
        [ "$temp" -ge -40000 ] && [ "$temp" -lt 60000 ] || return 1
        temperatures="${temperatures}${temperatures:+,}${temp}"
        sensor_count=$((sensor_count + 1))
    done
    [ "$sensor_count" = 2 ]
}
check_point() {
    rate=$1
    [ "$(cat /proc/sys/kernel/tainted)" = 0 ] || return 1
    [ "$(cat /sys/devices/system/cpu/online)" = 0-3 ] || return 1
    [ "$(cat "$policy/scaling_governor")" = userspace ] || return 1
    [ "$(cat "$policy/scaling_max_freq")" = 787200 ] || return 1
    [ "$(cat "$policy/scaling_min_freq")" = 300000 ] || return 1
    [ "$(cat "$policy/scaling_cur_freq")" = "$rate" ] || return 1
    cp /sys/kernel/debug/clk/clk_summary /tmp/cpr-load-clocks.txt || return 1
    actual=$(awk '$1 == "a53mux@f9011000" {print $5}' /tmp/cpr-load-clocks.txt)
    pll_rate=$(awk '$1 == "a53pll@f9016000" {print $5}' /tmp/cpr-load-clocks.txt)
    pll_enabled=$(awk '$1 == "a53pll@f9016000" {print $2}' /tmp/cpr-load-clocks.txt)
    if [ "$rate" = 787200 ]; then
        [ "$pll_rate" = 787200000 ] && [ "$pll_enabled" = 1 ] || return 1
    else
        [ "$pll_enabled" = 0 ] || return 1
    fi
    [ "$actual" = "$((rate * 1000))" ] || return 1
    cp /sys/kernel/debug/qcom_cpr/debug_info /tmp/cpr-load-check.txt || return 1
    grep -qx 'corner_voltage_applied = 1' /tmp/cpr-load-check.txt || return 1
    grep -qx 'feedback_allowed = 1' /tmp/cpr-load-check.txt || return 1
    apc=$(awk '/^apc_target = / {print $3}' /tmp/cpr-load-check.txt)
    cached=$(awk '/^corner, cached_volt = / {print $4}' /tmp/cpr-load-check.txt)
    planned=$(awk '/^corner, planned_volt = / {print $4}' /tmp/cpr-load-check.txt)
    case "$apc:$cached:$planned" in *[!0-9:]*|::*|:*|*:) return 1 ;; esac
    [ -n "$apc" ] && [ -n "$cached" ] && [ -n "$planned" ] || return 1
    [ "$apc" = "$cached" ] || return 1
    ctl=$(awk '/^rbcpr_ctl = / {print $3}' /tmp/cpr-load-check.txt)
    result=$(awk '/^rbcpr_result_0 = / {print $3}' /tmp/cpr-load-check.txt)
    case "$ctl" in 0x*|0X*) ;; *) return 1 ;; esac
    if [ "$rate" = 600000 ] || [ "$rate" = 787200 ]; then
        [ "$((ctl & 1))" = 1 ] || return 1
        [ "$apc" -ge 1080000 ] && [ "$apc" -le 1180000 ] || return 1
        [ "$planned" -ge 1080000 ] && [ "$planned" -le 1180000 ] || return 1
        [ "$((apc % 10000))" = 0 ] && [ "$((planned % 10000))" = 0 ] || return 1
    else
        [ "$rate" = 300000 ] && [ "$((ctl & 1))" = 0 ] || return 1
        [ "$apc" = 1080000 ] && [ "$planned" = 1080000 ] || return 1
    fi
    check_temperatures
}
[ "$(cat "$policy/scaling_governor")" = userspace ] || fail 'governor changed'
[ "$(cat /proc/sys/kernel/tainted)" = 0 ] || fail 'kernel tainted before request'
[ "$(cat /sys/devices/system/cpu/online)" = 0-3 ] || fail 'CPU topology changed'
check_temperatures || fail 'temperature outside trial bounds before request'
sha256sum -c /etc/fx0-cpr-load.sha256 || fail 'worker payload digest'
[ "$(/bin/cpr-sha256 --digest 1048576)" = fbbab289f7f94b25736c58be46a994c441fd02552cc6022352e3d86d2fab7c83 ] || fail 'worker self-check'
pids=
cleanup() {
    for pid in $pids; do kill "$pid" 2>/dev/null || true; done
    for pid in $pids; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
irq_before=$(irq_total) || fail 'cannot identify CPR IRQ row'
irq_previous=$irq_before
response=0
adjustment=0
floor_response=0
ceiling_response=0
echo "__CPR_LOAD_IRQ_BEFORE__${irq_before}"
sample_point() {
    check_point "$1" || fail 'clock, voltage, loop, CPU, policy or temperature guard'
    irq=$(irq_total) || fail 'CPR IRQ row disappeared'
    [ "$irq" -ge "$irq_previous" ] && [ "$((irq - irq_before))" -le 10000 ] || fail 'IRQ count decreased or storm'
    irq_previous=$irq
    if [ "$1" = 787200 ]; then
        if [ "$apc" != "$planned" ]; then adjustment=1; response=1; fi
        if [ "$((ctl & 64))" != 0 ]; then floor_response=1; response=1; fi
        if [ "$((ctl & 251658240))" = 251658240 ]; then ceiling_response=1; response=1; fi
    fi
    printf 'CPR_LOAD_SAMPLE phase=%s n=%s rate=%s apc=%s cached=%s planned=%s ctl=%s result=%s irq=%s temperatures=%s pll_rate=%s pll_enabled=%s\n' "$2" "$3" "$1" "$apc" "$cached" "$planned" "$ctl" "$result" "$irq" "$temperatures" "$pll_rate" "$pll_enabled"
}
request_point() {
    check_temperatures || fail 'temperature before request'
    [ "$(cat /proc/sys/kernel/tainted)" = 0 ] || fail 'taint before request'
    [ "$(cat /sys/devices/system/cpu/online)" = 0-3 ] || fail 'CPU topology before request'
    [ "$(cat "$policy/scaling_governor")" = userspace ] || fail 'governor before request'
    [ "$(cat "$policy/scaling_max_freq")" = 787200 ] || fail 'maximum before request'
    [ "$(cat "$policy/scaling_min_freq")" = 300000 ] || fail 'minimum before request'
    case "$1" in 300000|600000|787200) ;; *) fail 'unqualified request' ;; esac
    echo "__CPR_LOAD_REQUEST__${1}"
    printf '%s\n' "$1" > "$policy/scaling_setspeed" || fail 'frequency request rejected'
    settled=0
    for attempt in $(seq 1 30); do
        if check_point "$1"; then settled=1; break; fi
        sleep 0.1
    done
    [ "$settled" = 1 ] || fail 'requested point did not settle'
    sample_point "$1" "$2" 0
}
for cycle in $(seq 1 3); do
    request_point 787200 "repeat-${cycle}-pll-entry"
    hold=3
    [ "$cycle" != 1 ] || hold=10
    for sample in $(seq 1 "$hold"); do sample_point 787200 "repeat-${cycle}-pll-entry" "$sample"; sleep 0.2; done
    request_point 600000 "repeat-${cycle}-aux"
    for sample in $(seq 1 3); do sample_point 600000 "repeat-${cycle}-aux" "$sample"; sleep 0.2; done
    request_point 787200 "repeat-${cycle}-pll-reentry"
    for sample in $(seq 1 3); do sample_point 787200 "repeat-${cycle}-pll-reentry" "$sample"; sleep 0.2; done
    request_point 300000 "repeat-${cycle}-low"
    for sample in $(seq 1 3); do sample_point 300000 "repeat-${cycle}-low" "$sample"; sleep 0.2; done
done
request_point 787200 preload
for cpu in 0 1 2 3; do
    /bin/cpr-sha256 --worker "$cpu" > "/tmp/cpr-worker-${cpu}.txt" 2>&1 &
    pid=$!; pids="$pids $pid"; printf '%s\n' "$pid" > "/tmp/cpr-worker-${cpu}.pid"
done
echo '__CPR_LOAD_WORKERS_STARTED__'
complete=0
for sample in $(seq 1 80); do
    sample_point 787200 load "$sample"
    count=0
    for cpu in 0 1 2 3; do
        if grep -q '^CPR_LOAD_WORKER ' "/tmp/cpr-worker-${cpu}.txt"; then
            count=$((count + 1))
        else
            pid=$(cat "/tmp/cpr-worker-${cpu}.pid")
            kill -0 "$pid" 2>/dev/null || fail 'worker exited without a result'
        fi
    done
    if [ "$count" = 4 ]; then complete=1; break; fi
    sleep 0.5
done
[ "$complete" = 1 ] || fail 'workers exceeded observation deadline'
for pid in $pids; do wait "$pid" || fail 'worker failure'; done
pids=
for cpu in 0 1 2 3; do
    read -r tag cpu_field hashes_field bytes_field cpu_ms_field wall_ms_field affinity_field extra < "/tmp/cpr-worker-${cpu}.txt" || fail 'worker result missing'
    [ "$tag" = CPR_LOAD_WORKER ] && [ "$cpu_field" = "cpu=${cpu}" ] && [ "$affinity_field" = "affinity=${cpu}" ] && [ -z "$extra" ] || fail 'worker identity or affinity'
    [ "$bytes_field" = bytes_per_hash=1048576 ] || fail 'worker buffer size'
    case "$hashes_field:$cpu_ms_field:$wall_ms_field" in hashes=*:cpu_ms=*:wall_ms=*) ;; *) fail 'worker result fields' ;; esac
    hashes=${hashes_field#hashes=}; cpu_ms=${cpu_ms_field#cpu_ms=}; wall_ms=${wall_ms_field#wall_ms=}
    case "$hashes:$cpu_ms:$wall_ms" in *[!0-9:]*|::*|:*|*:) fail 'worker numeric fields' ;; esac
    [ -n "$hashes" ] && [ -n "$cpu_ms" ] && [ -n "$wall_ms" ] || fail 'empty worker numeric field'
    [ "$hashes" -gt 0 ] && [ "$cpu_ms" -ge 25000 ] && [ "$cpu_ms" -le 35000 ] && [ "$wall_ms" -ge 30000 ] && [ "$wall_ms" -le 35000 ] && [ "$cpu_ms" -le "$((wall_ms + 10))" ] || fail 'worker accounting outside bounds'
    cat "/tmp/cpr-worker-${cpu}.txt"
done
echo '__CPR_LOAD_WORKERS_TERMINAL__'
sample_point 787200 postload 0
cat /tmp/cpr-load-check.txt
cat /sys/kernel/debug/regulator/regulator_summary
cat /sys/kernel/debug/clk/clk_summary
cat /proc/interrupts
request_point 600000 return-bridge
for sample in $(seq 1 3); do sample_point 600000 return-bridge "$sample"; sleep 0.2; done
request_point 300000 recovery
for sample in $(seq 1 10); do sample_point 300000 recovery "$sample"; sleep 0.5; done
echo '__CPR_LOAD_RETURN_VERIFIED__300000'
cat /tmp/cpr-load-check.txt
cat /sys/kernel/debug/regulator/regulator_summary
cat /sys/kernel/debug/clk/clk_summary
printf 'CPR_LOAD_RESPONSE adjustment=%s floor=%s ceiling=%s irq_before=%s irq_after=%s\n' "$adjustment" "$floor_response" "$ceiling_response" "$irq_before" "$irq_previous"
if [ "$irq_previous" -le "$irq_before" ] || [ "$response" != 1 ]; then
    echo 'CPR_LOAD_INCONCLUSIVE: transitions/load/return valid, handled feedback not proved'
    exit 2
fi
echo 'CPR_LOAD_PASS: three PLL/aux/PLL/fixed-corner cycles, four bounded 787.2 MHz checksum workers, guarded feedback and fixed-corner return'
