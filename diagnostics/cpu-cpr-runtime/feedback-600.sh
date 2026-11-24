#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# First variable-corner feedback trial; no explicit request above 600 MHz.
set -eu
fail() { echo "CPR_FEEDBACK_FAILED: $*" >&2; exit 1; }
[ "$(cat /etc/fx0-cpr-feedback-step)" = 300-600 ] || fail 'missing feedback permit'
/bin/cpr-register || fail 'registration gate'
policy=/sys/devices/system/cpu/cpufreq/policy0
printf '600000\n' > "$policy/scaling_max_freq"
printf '300000\n' > "$policy/scaling_min_freq"
limits_ready=0
for i in $(seq 1 30); do
    if [ "$(cat "$policy/scaling_max_freq")" = 600000 ] &&
       [ "$(cat "$policy/scaling_min_freq")" = 300000 ]; then limits_ready=1; break; fi
    sleep 0.1
done
[ "$limits_ready" = 1 ] || fail 'limits did not settle'
irq_total() {
    awk '$NF == "cpr" { n++; for (i=2;i<=5;i++) { if ($i !~ /^[0-9]+$/) exit 1; total+=$i } }
         END { if (n != 1) exit 1; printf "%.0f\n", total }' /proc/interrupts
}
check_temperatures() {
    for sensor in /sys/class/thermal/thermal_zone*/temp; do
        temp=$(cat "$sensor") || return 1
        case "$temp" in ''|*[!0-9-]*) return 1 ;; esac
        [ "$temp" -ge -40000 ] && [ "$temp" -lt 60000 ] || return 1
    done
}
check_point() {
    rate=$1
    [ "$(cat /proc/sys/kernel/tainted)" = 0 ] || return 1
    [ "$(cat /sys/devices/system/cpu/online)" = 0-3 ] || return 1
    [ "$(cat "$policy/scaling_governor")" = userspace ] || return 1
    [ "$(cat "$policy/scaling_max_freq")" = 600000 ] || return 1
    [ "$(cat "$policy/scaling_min_freq")" = 300000 ] || return 1
    [ "$(cat "$policy/scaling_cur_freq")" = "$rate" ] || return 1
    actual=$(awk '$1 == "a53mux@f9011000" {print $5}' /sys/kernel/debug/clk/clk_summary)
    [ "$actual" = "$((rate * 1000))" ] || return 1
    cp /sys/kernel/debug/qcom_cpr/debug_info /tmp/cpr-feedback-check.txt || return 1
    grep -qx 'corner_voltage_applied = 1' /tmp/cpr-feedback-check.txt || return 1
    grep -qx 'feedback_allowed = 1' /tmp/cpr-feedback-check.txt || return 1
    apc=$(awk '/^apc_target = / {print $3}' /tmp/cpr-feedback-check.txt)
    cached=$(awk '/^corner, cached_volt = / {print $4}' /tmp/cpr-feedback-check.txt)
    planned=$(awk '/^corner, planned_volt = / {print $4}' /tmp/cpr-feedback-check.txt)
    case "$apc:$cached:$planned" in *[!0-9:]*|::*|:*|*:) return 1 ;; esac
    [ -n "$apc" ] && [ -n "$cached" ] && [ -n "$planned" ] || return 1
    [ "$apc" = "$cached" ] || return 1
    ctl=$(awk '/^rbcpr_ctl = / {print $3}' /tmp/cpr-feedback-check.txt)
    result=$(awk '/^rbcpr_result_0 = / {print $3}' /tmp/cpr-feedback-check.txt)
    case "$ctl" in 0x*|0X*) ;; *) return 1 ;; esac
    if [ "$rate" = 600000 ]; then
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
irq_before=$(irq_total) || fail 'cannot identify the four-CPU CPR IRQ row'
echo "__CPR_FEEDBACK_IRQ_BEFORE__${irq_before}"
echo '__CPR_FEEDBACK_REQUEST__600000'
printf '600000\n' > "$policy/scaling_setspeed" || fail '600 MHz request rejected'
settled=0
for i in $(seq 1 30); do
    if check_point 600000; then settled=1; break; fi
    sleep 0.1
done
[ "$settled" = 1 ] || fail '600 MHz / voltage bounds / loop state did not settle'
response=0
for sample in $(seq 1 50); do
    check_point 600000 || fail 'feedback observation outside qualified bounds'
    irq=$(irq_total) || fail 'CPR IRQ row disappeared'
    [ "$irq" -ge "$irq_before" ] && [ "$((irq - irq_before))" -le 10000 ] || fail 'unexpected IRQ count or storm'
    # A cache/plan difference or an ISR clamp flag proves a handled response.
    if [ "$apc" != "$planned" ] || [ "$((ctl & 64))" != 0 ] ||
       [ "$((ctl & 251658240))" = 251658240 ]; then response=1; fi
    printf 'CPR_FEEDBACK_SAMPLE n=%s apc=%s cached=%s planned=%s ctl=%s result=%s irq=%s\n' "$sample" "$apc" "$cached" "$planned" "$ctl" "$result" "$irq"
    sleep 0.2
done
irq_after=$(irq_total) || fail 'cannot read final IRQ count'
[ "$irq_after" -ge "$irq_before" ] && [ "$((irq_after - irq_before))" -le 10000 ] || fail 'final IRQ count outside bounds'
echo "__CPR_FEEDBACK_IRQ_AFTER__${irq_after}"
echo '__CPR_FEEDBACK_OBSERVED__600000'
cat /tmp/cpr-feedback-check.txt
cat /sys/kernel/debug/regulator/regulator_summary
cat /sys/kernel/debug/clk/clk_summary
cat /proc/interrupts
echo '__CPR_FEEDBACK_REQUEST__300000'
printf '300000\n' > "$policy/scaling_setspeed" || fail '300 MHz return rejected'
settled=0
for i in $(seq 1 30); do
    if check_point 300000; then settled=1; break; fi
    sleep 0.1
done
[ "$settled" = 1 ] || fail 'fixed-corner return did not settle'
echo '__CPR_FEEDBACK_OBSERVED__300000'
cat /tmp/cpr-feedback-check.txt
cat /sys/kernel/debug/regulator/regulator_summary
cat /sys/kernel/debug/clk/clk_summary
if [ "$irq_after" -le "$irq_before" ] || [ "$response" != 1 ]; then
    echo 'CPR_FEEDBACK_INCONCLUSIVE: valid bounded 600 MHz state and 300 MHz return, but no handled feedback response proved'
    exit 2
fi
echo 'CPR_FEEDBACK_PASS: bounded 600 MHz loop and handled CPR response; fixed-corner 300 MHz return verified'
