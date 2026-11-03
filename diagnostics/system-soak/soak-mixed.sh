#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Mixed-use soak: one JSON line per minute in LOGDIR.
# Adds to soak.sh: IMU/magnetometer reads and CPU idle entries every minute,
# a CPU burst every 10 minutes, a speaker play every 30 minutes and a few
# frames from each camera every 60 minutes.
# Usage: soak-mixed.sh HOURS LOGDIR
hours=${1:-24}; dir=${2:-/var/log/fx0-system-soak}; mkdir -p "$dir"; log="$dir/mixed-$(date +%Y%m%dT%H%M%S).jsonl"
end=$(( $(date +%s) + hours * 3600 )); n=0
uid=$(id -u user 2>/dev/null || echo 10000); rt=/run/user/$uid
python3 -c "
import math,struct,wave
w=wave.open('/tmp/fx0-soak-tone.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
a=int(32767*0.5); w.writeframes(b''.join(struct.pack('<hh',*(2*[int(a*math.sin(2*math.pi*880*i/48000))])) for i in range(48000))); w.close()"
iio() { for d in /sys/bus/iio/devices/iio:device*; do [ "$(cat $d/name 2>/dev/null)" = "$1" ] && echo $d; done | head -1; }
imu=$(iio mpu6515); mag=$(iio hscdtd008a)
while [ "$(date +%s)" -lt "$end" ]; do
	n=$((n + 1)); t=$(date +%s)
	state=$(nmcli -g GENERAL.STATE device show wlan0 2>/dev/null | cut -d' ' -f1)
	gw=$(nmcli -g IP4.GATEWAY device show wlan0 2>/dev/null)
	ping=$( [ -n "$gw" ] && ping -I wlan0 -c 3 -W 2 "$gw" 2>/dev/null | grep -oE '[0-9]+ (packets )?received' | grep -oE '^[0-9]+')
	dns=$(getent ahostsv4 kernel.org >/dev/null 2>&1 && echo 1 || echo 0)
	dl=""; if [ $((n % 30)) -eq 1 ]; then dl=$(curl --interface wlan0 -sS -o /dev/null --max-time 120 -w '%{http_code} %{size_download} %{speed_download}' 'https://speed.cloudflare.com/__down?bytes=25000000' 2>/dev/null); fi
	imu_ok=$(cat $imu/in_accel_z_raw >/dev/null 2>&1 && echo 1 || echo 0)
	mag_ok=$(cat $mag/in_magn_z_raw >/dev/null 2>&1 && echo 1 || echo 0)
	idle=$(cat /sys/devices/system/cpu/cpu*/cpuidle/state1/usage 2>/dev/null | awk '{s+=$1} END {print s+0}')
	burst=""; if [ $((n % 10)) -eq 5 ]; then s0=$(date +%s%N); head -c 67108864 /dev/zero | sha256sum >/dev/null; burst=$(( ($(date +%s%N) - s0) / 1000000 )); fi
	play=""; if [ $((n % 30)) -eq 15 ]; then play=$(su user -s /bin/sh -c "XDG_RUNTIME_DIR=$rt timeout 10 pw-play /tmp/fx0-soak-tone.wav" >/dev/null 2>&1 && echo 0 || echo 1); fi
	camr=""; if [ $((n % 60)) -eq 45 ]; then
		for name in back front; do i=$(cam -l 2>/dev/null | grep -i "$name camera" | cut -d: -f1)
			rm -rf /tmp/fx0-soak-cam; mkdir -p /tmp/fx0-soak-cam
			timeout 40 cam -c "$i" -C5 -s role=raw -F/tmp/fx0-soak-cam/ >/dev/null 2>&1
			camr="$camr$name:$(ls /tmp/fx0-soak-cam | wc -l) "; done; rm -rf /tmp/fx0-soak-cam; fi
	mem=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
	load=$(cut -d' ' -f1 /proc/loadavg)
	temps=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1)
	rproc=$(cat /sys/class/remoteproc/*/state 2>/dev/null | grep -c running)
	sway=$(pgrep -x sway >/dev/null && echo 1 || echo 0)
	pw=$(pgrep -f "^/usr/bin/pipewire$" >/dev/null && echo 1 || echo 0)
	failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
	rootfree=$(df -k / | awk 'NR==2{print $4}')
	kwarn=$(journalctl -k -b --since "-61 s" --no-pager 2>/dev/null | grep -ciE 'WARNING:|BUG:|[^m]Oops|hung task|rcu.*stall|timer handling|wcn36xx.*(error|fail|timeout)|gpu fault|hangcheck')
	printf '{"n":%d,"t":%d,"wifi":"%s","ping_replies":"%s","dns":%s,"download":"%s","imu":%s,"mag":%s,"cpuidle_entries":%s,"burst_ms":"%s","speaker_play_rc":"%s","camera_frames":"%s","mem_available_kb":%s,"load1":%s,"max_temp_mC":"%s","remoteprocs_running":%s,"sway":%s,"pipewire":%s,"failed_units":%s,"root_free_kb":%s,"kernel_warnings_last_min":%s,"taint":%s}\n' \
		"$n" "$t" "$state" "$ping" "$dns" "$dl" "$imu_ok" "$mag_ok" "$idle" "$burst" "$play" "$camr" "$mem" "$load" "$temps" "$rproc" "$sway" "$pw" "$failed" "$rootfree" "$kwarn" "$(cat /proc/sys/kernel/tainted)" >> "$log"
	sleep $(( 60 - ($(date +%s) - t) > 0 ? 60 - ($(date +%s) - t) : 1 ))
done
