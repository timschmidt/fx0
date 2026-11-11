#!/bin/sh
# SPDX-License-Identifier: MIT
# Keep the full worker result in RAM, independently of /dev/kmsg rate limits.
set -u
[ "$#" -ge 3 ] || exit 2
logdir=$1
procdir=$2
shift 2
[ -d "$logdir" ] && [ ! -e "$logdir/vibrator.log" ] &&
    [ ! -e "$logdir/vibrator-result.txt" ] || exit 2
umask 077
"$@" >"$logdir/vibrator.log" 2>&1
result=$?
{
    printf 'exit_status=%s\n' "$result"
    printf 'boot_id='
    cat "$procdir/sys/kernel/random/boot_id"
    printf 'uptime='
    cut -d ' ' -f 1 "$procdir/uptime"
    printf 'taint='
    cat "$procdir/sys/kernel/tainted"
    printf '__MODULES_BEGIN__\n'
    cat "$procdir/modules"
    printf '__MODULES_END__\n'
} >"$logdir/vibrator-result.txt.tmp"
mv "$logdir/vibrator-result.txt.tmp" "$logdir/vibrator-result.txt"
printf 'VIBRATOR_RESULT exit=%s log=/www/vibrator.log\n' "$result"
exit "$result"
