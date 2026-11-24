#!/bin/sh
# SPDX-License-Identifier: MIT
root=${FX0_DIAG_ROOT:-/www}
not_found() {
    printf 'HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
    exit
}
IFS= read -r request || exit
set -- $request
case "$2" in
    /dmesg.txt) file="$root/dmesg.txt" ;;
    /status.txt) file="$root/status.txt" ;;
    /vibrator.log) file="$root/vibrator.log" ;;
    /vibrator-result.txt) file="$root/vibrator-result.txt" ;;
    /vibrator-state.txt) file="$root/vibrator-state.txt" ;;
    *) not_found ;;
esac
[ -r "$file" ] || not_found
while IFS= read -r header; do
    case "$header" in ''|"$(printf '\r')") break ;; esac
done
size=$(wc -c <"$file")
printf 'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %s\r\nConnection: close\r\n\r\n' "$size"
cat "$file"
