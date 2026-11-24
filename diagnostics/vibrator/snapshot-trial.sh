#!/bin/sh
# SPDX-License-Identifier: MIT
# Independent read-only snapshot if the worker has not returned.
set -u
[ "$#" -eq 2 ] || exit 2
logdir=$1
procdir=$2
umask 077
{
    printf 'boot_id='
    cat "$procdir/sys/kernel/random/boot_id"
    printf 'uptime='
    cat "$procdir/uptime"
    printf 'taint='
    cat "$procdir/sys/kernel/tainted"
    printf '__MODULES_BEGIN__\n'
    cat "$procdir/modules"
    printf '__MODULES_END__\n'
    for path in "$procdir"/[0-9]*; do
        [ -r "$path/comm" ] || continue
        case "$(cat "$path/comm")" in
            vibrator-pulses|vibrator-ram)
                printf '__WORKER__ %s\n' "${path##*/}"
                cat "$path/status" "$path/wchan" "$path/stack" 2>/dev/null
                ;;
        esac
    done
} >"$logdir/vibrator-state.txt.tmp"
mv "$logdir/vibrator-state.txt.tmp" "$logdir/vibrator-state.txt"
