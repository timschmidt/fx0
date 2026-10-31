#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Wi-Fi soak: one JSON line per minute in $LOG; a 25 MB download every 10 minutes.
# Usage: soak.sh HOURS LOGDIR
hours=${1:-8}; dir=${2:-/var/log/fx0-wifi-soak}; mkdir -p "$dir"; log="$dir/soak-$(date +%Y%m%dT%H%M%S).jsonl"
end=$(( $(date +%s) + hours * 3600 )); n=0
while [ "$(date +%s)" -lt "$end" ]; do
	n=$((n + 1)); t=$(date +%s)
	state=$(nmcli -g GENERAL.STATE device show wlan0 2>/dev/null | cut -d' ' -f1)
	link=$(nmcli -t -f ACTIVE,CHAN,SIGNAL,RATE device wifi list ifname wlan0 --rescan no 2>/dev/null | grep '^yes' | cut -d: -f2-4 | tr ':' ' ')
	gw=$(nmcli -g IP4.GATEWAY device show wlan0 2>/dev/null)
	ping=$( [ -n "$gw" ] && ping -I wlan0 -c 5 -W 2 "$gw" 2>/dev/null | grep -oE '[0-9]+ (packets )?received' | grep -oE '^[0-9]+')
	dns=$(getent ahostsv4 kernel.org >/dev/null 2>&1 && echo 1 || echo 0)
	dl=""; if [ $((n % 10)) -eq 1 ]; then dl=$(curl --interface wlan0 -sS -o /dev/null --max-time 120 -w '%{http_code} %{size_download} %{speed_download}' 'https://speed.cloudflare.com/__down?bytes=25000000' 2>/dev/null); fi
	kerr=$(dmesg 2>/dev/null | grep -ciE 'wcn36xx.*(error|fail|timeout)|WARNING:|BUG:|Oops')
	scanfail=$(journalctl -u wpa_supplicant --since "-61 s" --no-pager 2>/dev/null | grep -c SCAN-FAILED)
	printf '{"n":%d,"t":%d,"state":"%s","link":"%s","ping_replies":"%s","dns":%s,"download":"%s","kernel_errors_total":%s,"scan_failed_last_min":%s,"taint":%s}\n' \
		"$n" "$t" "$state" "$link" "$ping" "$dns" "$dl" "$kerr" "$scanfail" "$(cat /proc/sys/kernel/tainted)" >> "$log"
	sleep $(( 60 - ($(date +%s) - t) > 0 ? 60 - ($(date +%s) - t) : 1 ))
done
