#!/bin/sh
# Usage (as root, detached): KO=<module> TAG=<name> variant-test.sh
# Swap in KO, run back-first and front-first dual streams, record VFE IRQ rate, eMMC fsync time, frames; restore.
set -u
R=/run/fx0-var/$TAG; T=/run/fx0-csid1.sh; L=$R/log; mkdir -p $R; : > $L
log() { echo "$(date +%T) $*" >> $L; }
WP() { su user -c "XDG_RUNTIME_DIR=/run/user/10000 systemctl --user $1 wireplumber" >> $L 2>&1; }
restore() {
  pkill -INT v4l2-ctl; sleep 1; pkill -KILL v4l2-ctl; sleep 1
  for i in 1 2 3 4 5 6 7 8; do [ -e /sys/module/qcom_camss ] || break; rmmod qcom_camss >> $L 2>&1 && break; sleep 1; done
  modprobe qcom_camss >> $L 2>&1; sleep 3; WP start
  log "restored wireplumber=$(su user -c 'XDG_RUNTIME_DIR=/run/user/10000 systemctl --user is-active wireplumber') stock=$(grep -c 'camss_find_sleep_line$' /proc/kallsyms) taint=$(cat /proc/sys/kernel/tainted)"
  dmesg | grep -v "Fixed dependency" | grep -iE "camss|vfe|csid|ispif|rcu|BUG|WARN" | tail -n 20 > $R/dmesg.txt
  echo done > $R/state
}
trap restore EXIT
vfe() { grep camss_msm_vfe0 /proc/interrupts | awk '{print $2}'; }
up() { cut -d' ' -f1 /proc/uptime; }
frames() { grep -o '<' /run/fx0-csid-test/$1/stream.log 2>/dev/null | wc -l; }
WP stop
for i in $(seq 20); do [ "$(cat /sys/module/qcom_camss/refcnt)" = 0 ] && break; sleep 0.5; done
rmmod qcom_camss >> $L 2>&1 || { log rmmod-failed; exit 1; }
insmod $KO >> $L 2>&1 || { log insmod-failed; exit 1; }
for i in $(seq 30); do media-ctl -d /dev/media0 -p 2>/dev/null | grep -q imx132 && media-ctl -d /dev/media0 -p | grep -q imx179 && break; sleep 1; done
dmesg -C
pair() { # name firstargs secondargs
  media-ctl -d /dev/media0 -r
  RESET=0 timeout 40 sh $T $2 & p1=$!
  sleep 3
  RESET=0 timeout 40 sh $T $3 & p2=$!
  sleep 4
  a=$(vfe); t0=$(up); sleep 2; b=$(vfe); t1=$(up)
  f0a=$(frames ${2##* }); f0b=$(frames ${3##* })
  d0=$(up); timeout 60 dd if=/dev/zero of=/var/tmp/fx0-io bs=1M count=4 conv=fsync 2>/dev/null; d1=$(up); rm -f /var/tmp/fx0-io
  sleep 3; f1a=$(frames ${2##* }); f1b=$(frames ${3##* })
  log "$1 vfe_irqs=$((b-a)) over $t0..$t1 fsync4M=$d0..$d1 first_frames=$f0a->$f1a second_frames=$f0b->$f1b"
  pkill -INT v4l2-ctl; wait $p1; wait $p2; sleep 1
  for x in ${2##* } ${3##* }; do log "  $x: $(cat /run/fx0-csid-test/$x/result) $(grep -o 'VIDIOC[^<]*' /run/fx0-csid-test/$x/stream.log | head -1)"; done
}
pair back-first "imx179 0 0 0 100000 bf-back" "imx132 1 1 1 100000 bf-front"
pair front-first "imx132 1 1 1 100000 ff-front" "imx179 0 0 0 100000 ff-back"
