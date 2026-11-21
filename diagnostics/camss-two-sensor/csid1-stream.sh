#!/bin/sh
# Stream one sensor through a chosen CSID/ISPIF/RDI path using raw media-ctl/v4l2-ctl.
# Usage: csid1-stream.sh [sensor=imx132] [csid=1] [ispif=1] [rdi=0] [frames=24] [tag=front]
# Expected on 6.18.64 r7 (no fix) with csid>=1: csid_set_power -EINVAL (STREAMON fails).
# Expected with fx0-linux development/fx0-camss-csid-without-vfe-01: frames arrive.
set -u
SN=${1:-imx132}; CS=${2:-1}; IS=${3:-1}; RD=${4:-0}; N=${5:-24}; TAG=${6:-$SN}
out=/run/fx0-csid-test/$TAG; rm -rf $out; mkdir -p $out
M=$(for m in /dev/media*; do media-ctl -d $m -p 2>/dev/null | grep -q msm_csid1 && echo $m; done | head -1)
[ -n "$M" ] || { echo "no camss media device" > $out/result; exit 1; }
[ "${RESET:-1}" = 1 ] && media-ctl -d $M -r
S=$(media-ctl -d $M -p | sed -n "s/.*entity [0-9]*: \($SN [^ ]*\) .*/\1/p" | head -1)
P=$(media-ctl -d $M -p | grep -A12 "entity.*$S" | sed -n 's/.*-> "\(msm_csiphy[0-9]\)".*/\1/p' | head -1)
case $SN in imx132) F=SRGGB10_1X10/1976x1200; W=1976; H=1200;; imx179) F=SRGGB10_1X10/3280x2464; W=3280; H=2464;; esac
media-ctl -d $M -l "'$P':1->'msm_csid$CS':0[1],'msm_csid$CS':1->'msm_ispif$IS':0[1],'msm_ispif$IS':1->'msm_vfe0_rdi$RD':0[1]" > $out/links.log 2>&1
media-ctl -d $M -V "'$S':0[fmt:$F],'$P':0[fmt:$F],'msm_csid$CS':0[fmt:$F],'msm_ispif$IS':0[fmt:$F],'msm_vfe0_rdi$RD':0[fmt:$F]" > $out/fmt.log 2>&1
V=$(media-ctl -d $M -e msm_vfe0_video$RD)
v4l2-ctl -d $V --set-fmt-video=width=$W,height=$H,pixelformat=pRAA --stream-mmap=4 --stream-count=$N --stream-to=/dev/null > $out/stream.log 2>&1; rc=$?
echo "media=$M sensor=$S phy=$P csid=$CS ispif=$IS rdi=$RD video=$V stream_rc=$rc" > $out/result
