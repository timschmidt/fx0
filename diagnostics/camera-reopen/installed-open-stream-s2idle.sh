#!/bin/sh
# Open-stream s2idle test on the installed kernel: one camera at a time.
set -u
out=/run/fx0-r4-cam-sleep; rm -rf $out; mkdir -p $out
for name in "Internal front camera" "Internal back camera"; do
  tag=$(echo "$name" | awk '{print $2}')
  idx=$(cam -l 2>/dev/null | grep -F "$name" | sed -E 's/^([0-9]+):.*/\1/' | head -1)
  [ -n "$idx" ] || { echo "$tag no-camera" >> $out/result; continue; }
  log=$out/$tag.log
  cam -c "$idx" -C400 -s role=raw > $log 2>&1 &
  pid=$!
  n=0; while [ $n -lt 60 ]; do c=$(grep -c 'seq:' $log); [ "$c" -ge 8 ] && break; sleep 0.5; n=$((n+1)); done
  before=$(grep -c 'seq:' $log)
  s0=$(cat /sys/power/suspend_stats/success)
  rtcwake -m freeze -s 12 > $out/$tag.rtc 2>&1; rc=$?
  s1=$(cat /sys/power/suspend_stats/success)
  sleep 4
  after=$(grep -c 'seq:' $log)
  alive=no; kill -0 $pid 2>/dev/null && alive=yes
  kill -INT $pid 2>/dev/null; wait $pid 2>/dev/null
  echo "$tag idx=$idx before=$before after=$after rtcwake_rc=$rc suspend_success_delta=$((s1-s0)) cam_alive_after_wake=$alive" >> $out/result
  sleep 2
done
grep -iE 'camss|vfe|csid|imx1|stopping|Failed to restart' /dev/kmsg >/dev/null 2>&1 &
journalctl -k -b --since "-3min" --no-pager -o cat | grep -iE 'camss|vfe|csid|imx1|stopping|restart capture|PM: suspend' > $out/kernel.txt
echo done >> $out/result
