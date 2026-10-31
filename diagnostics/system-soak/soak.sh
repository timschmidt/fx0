#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# System soak: one JSON line per minute in LOGDIR; a 25 MB Wi-Fi download every 30 minutes.
# Usage: soak.sh HOURS LOGDIR
hours=${1:-24}; dir=${2:-/var/log/fx0-system-soak}; mkdir -p "$dir"; log="$dir/soak-$(date +%Y%m%dT%H%M%S).jsonl"
end=$(( $(date +%s) + hours * 3600 )); n=0
bat=$(grep -l "^Battery$" /sys/class/power_supply/*/type 2>/dev/null | head -1); bat=${bat%/type}
while [ "$(date +%s)" -lt "$end" ]; do
	n=$((n + 1)); t=$(date +%s)
	state=$(nmcli -g GENERAL.STATE device show wlan0 2>/dev/null | cut -d' ' -f1)
	gw=$(nmcli -g IP4.GATEWAY device show wlan0 2>/dev/null)
	ping=$( [ -n "$gw" ] && ping -I wlan0 -c 3 -W 2 "$gw" 2>/dev/null | grep -oE '[0-9]+ (packets )?received' | grep -oE '^[0-9]+')
	dns=$(getent ahostsv4 kernel.org >/dev/null 2>&1 && echo 1 || echo 0)
	dl=""; if [ $((n % 30)) -eq 1 ]; then dl=$(curl --interface wlan0 -sS -o /dev/null --max-time 120 -w '%{http_code} %{size_download} %{speed_download}' 'https://speed.cloudflare.com/__down?bytes=25000000' 2>/dev/null); fi
	mem=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
	load=$(cut -d' ' -f1 /proc/loadavg)
	temps=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1)
	cap=$(cat "$bat/voltage_now" 2>/dev/null); bst=$(cat "$bat/status" 2>/dev/null)
	rproc=$(cat /sys/class/remoteproc/*/state 2>/dev/null | grep -c running)
	sway=$(pgrep -x sway >/dev/null && echo 1 || echo 0)
	pw=$(pgrep -f "^/usr/bin/pipewire$" >/dev/null && echo 1 || echo 0)
	failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
	rootfree=$(df -k / | awk 'NR==2{print $4}')
	kwarn=$(journalctl -k -b --since "-61 s" --no-pager 2>/dev/null | grep -ciE 'WARNING:|BUG:|Oops|hung task|wcn36xx.*(error|fail|timeout)|gpu fault|hangcheck')
	printf '{"n":%d,"t":%d,"wifi":"%s","ping_replies":"%s","dns":%s,"download":"%s","mem_available_kb":%s,"load1":%s,"max_temp_mC":"%s","battery_uV_status":"%s %s","remoteprocs_running":%s,"sway":%s,"pipewire":%s,"failed_units":%s,"root_free_kb":%s,"kernel_warnings_last_min":%s,"taint":%s}\n' \
		"$n" "$t" "$state" "$ping" "$dns" "$dl" "$mem" "$load" "$temps" "$cap" "$bst" "$rproc" "$sway" "$pw" "$failed" "$rootfree" "$kwarn" "$(cat /proc/sys/kernel/tainted)" >> "$log"
	sleep $(( 60 - ($(date +%s) - t) > 0 ? 60 - ($(date +%s) - t) : 1 ))
done
