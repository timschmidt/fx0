#!/bin/sh
# Like dual-sleep.sh but traces per-device PM callbacks, arms wakeup_count and uses a 40 s RTC alarm.
set -u
R=/run/fx0-csid1; T=/run/fx0-csid1.sh; L=$R/trace-log; TR=/sys/kernel/tracing
log() { echo "$(date +%T.%N | cut -c1-12) $*" >> $L; }
WP() { su user -c "XDG_RUNTIME_DIR=/run/user/10000 systemctl --user $1 wireplumber" >> $L 2>&1; }
restore() {
  echo 0 > $TR/tracing_on; echo 0 > $TR/events/power/enable 2>/dev/null; echo 0 > /sys/class/rtc/rtc0/wakealarm
  for i in 1 2 3 4 5; do [ -e /sys/module/qcom_camss ] || break; rmmod qcom_camss >> $L 2>&1 && break; sleep 1; done
  modprobe qcom_camss >> $L 2>&1; sleep 3; WP start
  log "restored wireplumber=$(su user -c 'XDG_RUNTIME_DIR=/run/user/10000 systemctl --user is-active wireplumber') taint=$(cat /proc/sys/kernel/tainted)"
  echo done > $R/trace-state
}
trap restore EXIT
echo running > $R/trace-state; : > $L
[ -d $TR/events ] || mount -t tracefs nodev $TR
WP stop
for i in $(seq 20); do [ "$(cat /sys/module/qcom_camss/refcnt)" = 0 ] && break; sleep 0.5; done
rmmod qcom_camss >> $L 2>&1 || { log rmmod-failed; exit 1; }
insmod ${KO:-$R/qcom-camss-csid1.ko} >> $L 2>&1 || { log insmod-failed; exit 1; }
for i in $(seq 30); do media-ctl -d /dev/media0 -p 2>/dev/null | grep -q imx132 && media-ctl -d /dev/media0 -p | grep -q imx179 && break; sleep 1; done
dmesg -C
echo 0 > $TR/tracing_on; : > $TR/trace; echo 8192 > $TR/buffer_size_kb; echo mono > $TR/trace_clock
echo 1 > $TR/events/power/device_pm_callback_start/enable; echo 1 > $TR/events/power/device_pm_callback_end/enable; echo 1 > $TR/events/power/suspend_resume/enable
media-ctl -d /dev/media0 -r
RESET=0 timeout 200 sh $T imx179 0 0 0 1500 trace-back & a=$!
sleep 1
RESET=0 timeout 200 sh $T imx132 1 1 1 700 trace-front & b=$!
sleep 8
cnt() { grep -o '<' /run/fx0-csid-test/$1/stream.log 2>/dev/null | wc -l; }
irq() { grep pm8xxx_rtc_alarm /proc/interrupts | awk '{print $2}'; }
mi() { awk '/^(Dirty|Writeback):/{printf "%s%s ", $1, $2}' /proc/meminfo; }
log "pre-sync $(mi)"; t0=$(cut -d' ' -f1 /proc/uptime); sync; t1=$(cut -d' ' -f1 /proc/uptime); log "sync_from=$t0 sync_to=$t1 $(mi)"
echo 1 > $TR/tracing_on
echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +40 > /sys/class/rtc/rtc0/wakealarm
wc=$(cat /sys/power/wakeup_count); echo $wc > /sys/power/wakeup_count; wrc=$?
r0=$(cat /sys/class/rtc/rtc0/since_epoch)
log "before back=$(cnt trace-back) front=$(cnt trace-front) irq=$(irq) wakeup_count_rc=$wrc alarm=$(cat /sys/class/rtc/rtc0/wakealarm) rtc=$r0"
echo freeze > /sys/power/state; src=$?
r1=$(cat /sys/class/rtc/rtc0/since_epoch)
log "after state_rc=$src rtc_elapsed=$((r1-r0)) irq=$(irq) back=$(cnt trace-back) front=$(cnt trace-front) succ=$(cat /sys/power/suspend_stats/success) fail=$(cat /sys/power/suspend_stats/fail)"
echo 0 > $TR/tracing_on
cp $TR/trace $R/pm-trace.txt
wait $a; ra=$?; wait $b; rb=$?
log "wait rc back=$ra front=$rb final back=$(cnt trace-back) front=$(cnt trace-front)"
dmesg | grep -v "Fixed dependency" | tail -n 40 > $R/trace-dmesg.txt
