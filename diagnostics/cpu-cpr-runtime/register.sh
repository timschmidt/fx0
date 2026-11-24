#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Pinned, module-registration-only trial in the moduleless Fx0 RAM environment.
set -eu
fail() { echo "CPR_REGISTRATION_FAILED: $*" >&2; exit 1; }
[ "$(uname -r)" = 6.18.59-fx0-cpr-observe ] || fail 'unexpected kernel'
[ "$(cat /etc/fx0-cpr-trial)" = registration-only ] || fail 'missing RAM trial marker'
[ "$(cat /sys/module/module/parameters/sig_enforce)" = Y ] || fail 'module signature enforcement is off'
[ "$(cat /sys/module/cpufreq/parameters/default_governor)" = userspace ] || fail 'unexpected default governor'
[ ! -d /sys/devices/system/cpu/cpufreq/policy0 ] || fail 'CPUfreq policy already exists'
[ -z "$(cat /proc/modules)" ] || fail 'expected an initially moduleless kernel'
sha256sum -c /etc/fx0-cpr-modules.sha256 || fail 'module payload digest'
check_bootstrap() {
    [ "$(cat /proc/sys/kernel/tainted)" = 0 ] || fail 'kernel tainted'
    cp /sys/kernel/debug/qcom_cpr/debug_info /tmp/cpr-registration-check.txt
    grep -qx 'corner_voltage_applied = 0' /tmp/cpr-registration-check.txt || fail 'performance request already applied'
    grep -qx 'feedback_allowed = 0' /tmp/cpr-registration-check.txt || fail 'feedback unexpectedly allowed'
    grep -qx 'apc_target = 1150000 uV' /tmp/cpr-registration-check.txt || fail 'boot APC target changed'
    ctl=$(awk '/^rbcpr_ctl = / {print $3}' /tmp/cpr-registration-check.txt)
    case "$ctl" in 0x*|0X*) ;; *) fail 'missing control readback' ;; esac
    [ "$((ctl & 1))" = 0 ] || fail 'feedback loop enabled'
    rate=$(awk '$1 == "a53mux@f9011000" {print $5}' /sys/kernel/debug/clk/clk_summary)
    [ "$rate" = 300000000 ] || fail 'CPU mux not at 300 MHz'
}
check_bootstrap
echo '__CPR_REGISTRATION_BEFORE__'
cat /tmp/cpr-registration-check.txt
insmod /modules/cpufreq_userspace.ko
[ -d /sys/module/cpufreq_userspace ] || fail 'userspace governor module absent'
# A successful userspace init registers the governor. Do not load the driver
# after a failed/missing init: CPUFreq would fall back to built-in schedutil.
insmod /modules/cpufreq-dt.ko
[ -d /sys/module/cpufreq_dt ] || fail 'CPUfreq driver module absent'
policy=/sys/devices/system/cpu/cpufreq/policy0
[ "$(cat "$policy/scaling_governor")" = userspace ] || fail 'governor fallback'
[ "$(cat "$policy/scaling_cur_freq")" = 300000 ] || fail 'unexpected initial frequency'
[ "$(cat "$policy/scaling_available_frequencies")" = '300000 384000 600000 787200 998400 1094400 1190400 ' ] || fail 'unexpected eligible OPP list'
check_bootstrap
echo '__CPR_REGISTRATION_AFTER__'
cat /tmp/cpr-registration-check.txt
cat "$policy/scaling_governor" "$policy/scaling_cur_freq" "$policy/scaling_available_frequencies"
cat /proc/modules
echo 'CPR_REGISTRATION_PASS: userspace and cpufreq-dt loaded; 300 MHz boot target retained; no positive pstate applied'
