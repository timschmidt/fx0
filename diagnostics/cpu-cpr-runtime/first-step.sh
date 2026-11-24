#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Explicit first fixed-corner requests; registration-only images lack this permit.
set -eu
fail() { echo "CPR_FIRST_STEP_FAILED: $*" >&2; exit 1; }
[ "$(cat /etc/fx0-cpr-first-step)" = 300-384 ] || fail 'missing first-step permit'
/bin/cpr-register || fail 'registration gate'
policy=/sys/devices/system/cpu/cpufreq/policy0
printf '384000\n' > "$policy/scaling_max_freq"
printf '300000\n' > "$policy/scaling_min_freq"
limits_ready=0
for i in $(seq 1 30); do
    if [ "$(cat "$policy/scaling_max_freq")" = 384000 ] &&
       [ "$(cat "$policy/scaling_min_freq")" = 300000 ]; then limits_ready=1; break; fi
    sleep 0.1
done
[ "$limits_ready" = 1 ] || fail 'limits did not settle at 300-384 MHz'
[ "$(cat "$policy/scaling_governor")" = userspace ] || fail 'governor changed'
check_point() {
    rate=$1
    [ "$(cat /proc/sys/kernel/tainted)" = 0 ] || return 1
    [ "$(cat "$policy/scaling_governor")" = userspace ] || return 1
    [ "$(cat "$policy/scaling_max_freq")" = 384000 ] || return 1
    [ "$(cat "$policy/scaling_min_freq")" = 300000 ] || return 1
    [ "$(cat "$policy/scaling_cur_freq")" = "$rate" ] || return 1
    actual=$(awk '$1 == "a53mux@f9011000" {print $5}' /sys/kernel/debug/clk/clk_summary)
    [ "$actual" = "$((rate * 1000))" ] || return 1
    cp /sys/kernel/debug/qcom_cpr/debug_info /tmp/cpr-first-step-check.txt || return 1
    grep -qx 'corner_voltage_applied = 1' /tmp/cpr-first-step-check.txt || return 1
    grep -qx 'feedback_allowed = 1' /tmp/cpr-first-step-check.txt || return 1
    grep -qx 'apc_target = 1080000 uV' /tmp/cpr-first-step-check.txt || return 1
    grep -qx 'corner, cached_volt = 1080000 uV' /tmp/cpr-first-step-check.txt || return 1
    ctl=$(awk '/^rbcpr_ctl = / {print $3}' /tmp/cpr-first-step-check.txt)
    case "$ctl" in 0x*|0X*) ;; *) return 1 ;; esac
    [ "$((ctl & 1))" = 0 ] || return 1
}
for requested in 384000 300000; do
    case "$requested" in 300000|384000) ;; *) fail 'request outside first fixed corner' ;; esac
    echo "__CPR_FIRST_STEP_REQUEST__${requested}"
    printf '%s\n' "$requested" > "$policy/scaling_setspeed" || fail 'frequency request rejected'
    settled=0
    for i in $(seq 1 30); do
        if check_point "$requested"; then settled=1; break; fi
        sleep 0.1
    done
    [ "$settled" = 1 ] || fail "state did not settle at ${requested} kHz / 1.08 V / LOOP_EN=0"
    # Observe a bounded quiet hold, without issuing any additional requests.
    for i in $(seq 1 10); do
        check_point "$requested" || fail "state changed during ${requested} kHz hold"
        sleep 0.2
    done
    echo "__CPR_FIRST_STEP_OBSERVED__${requested}"
    cat /tmp/cpr-first-step-check.txt
    cat /sys/kernel/debug/regulator/regulator_summary
    cat /sys/class/thermal/thermal_zone*/temp
    cat /sys/kernel/debug/clk/clk_summary
done
echo 'CPR_FIRST_STEP_PASS: 300-384-300 MHz; fixed 1.08 V APC target applied; feedback loop remained disabled'
