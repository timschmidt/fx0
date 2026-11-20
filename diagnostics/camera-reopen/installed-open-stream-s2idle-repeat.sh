#!/bin/sh
# Repeated open-stream s2idle cycles on the installed kernel, one camera process per camera.
set -u
CYCLES=${CYCLES:-10}
out=/run/fx0-r4-cam-repeat; rm -rf $out; mkdir -p $out
frames() { grep -c 'seq:' "$1"; }
for name in "Internal front camera" "Internal back camera"; do
  tag=$(echo "$name" | awk '{print $2}')
  idx=$(cam -l 2>/dev/null | grep -F "$name" | sed -E 's/^([0-9]+):.*/\1/' | head -1)
  [ -n "$idx" ] || { echo "$tag no-camera" >> $out/result; continue; }
  log=$out/$tag.log
  cam -c "$idx" -C100000 -s role=raw > $log 2>&1 &
  pid=$!
  n=0; while [ $n -lt 60 ] && [ "$(frames $log)" -lt 8 ]; do sleep 0.5; n=$((n+1)); done
  ok=0; i=1
  while [ $i -le $CYCLES ]; do
    b=$(frames $log); s0=$(cat /sys/power/suspend_stats/success)
    rtcwake -m freeze -s 10 >/dev/null 2>&1; rc=$?
    s1=$(cat /sys/power/suspend_stats/success)
    n=0; while [ $n -lt 20 ] && [ "$(frames $log)" -lt $((b+8)) ]; do sleep 0.5; n=$((n+1)); done
    a=$(frames $log); alive=no; kill -0 $pid 2>/dev/null && alive=yes
    echo "$tag cycle=$i rc=$rc suspended=$((s1-s0)) before=$b after=$a alive=$alive" >> $out/cycles
    [ $rc -eq 0 ] && [ $((s1-s0)) -eq 1 ] && [ $a -ge $((b+8)) ] && [ $alive = yes ] && ok=$((ok+1))
    i=$((i+1))
  done
  kill -INT $pid 2>/dev/null; wait $pid 2>/dev/null
  echo "$tag idx=$idx cycles=$CYCLES passed=$ok total_frames=$(frames $log)" >> $out/result
  sleep 2
done
journalctl -k -b --since "-15min" --no-pager -o cat | grep -iE 'camss|vfe|csid|imx1|stopping|restart capture|iommu|fault' > $out/kernel.txt
grep -c 'PM: suspend entry' /dev/null >/dev/null
journalctl -k -b --since "-15min" --no-pager -o cat | grep -c 'PM: suspend exit' > $out/suspend_exits
echo done >> $out/result
