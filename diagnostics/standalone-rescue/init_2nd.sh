#!/bin/busybox ash
# SPDX-License-Identifier: MIT
# Fx0 development rescue: stay in this initramfs, with internal eMMC read-only.
. /init_functions.sh
. /init_functions_2nd.sh
trap 'halt -f' USR1
trap 'poweroff -f' USR2
trap 'reboot -f' TERM

# These are the modules embedded in this image, not those in the installed root.
load_modules /lib/modules/initramfs.load
setup_udev
for attempt in $(seq 1 30); do
    [ -b /dev/mmcblk0 ] && break
    sleep 1
done
if [ ! -b /dev/mmcblk0 ]; then
    echo 'Fx0 rescue: internal eMMC missing' >/dev/kmsg
else
    for node in /dev/mmcblk0 /dev/mmcblk0p* /dev/mmcblk0boot*; do
        [ -b "$node" ] || continue
        blockdev --setro "$node" || exit 1
    done
fi

setup_usb_network_configfs skip_udc
setup_usb_acm_configfs
echo 500 >"$CONFIGFS/g1/configs/c.1/MaxPower"
cat >/README <<'EOF'
Fx0 standalone development rescue
All tools/modules are in RAM; the installed root is not mounted.
Internal eMMC is read-only. No automatic root discovery, resizing or switch_root.
The USB serial shell and USB-only telnet shell run as root.
Use reboot -f to return to lk2nd; no normal OS startup is provided here.
EOF
cat >/sbin/pmos_getty <<'EOF'
#!/bin/sh
exec /bin/sh -l
EOF
chmod 755 /sbin/pmos_getty
printf '%s\n' 'cat /README' >/etc/profile
run_getty ttyGS0
setup_usb_configfs_udc
start_unudhcpd
mount -t debugfs none /sys/kernel/debug || true
mount -t pstore pstore /sys/fs/pstore || true
telnetd -b "${HOST_IP}:23" -l /sbin/pmos_getty &
cat /README >/dev/tty1
mkdir -p /run
echo 'Fx0 standalone rescue ready' >/run/fx0-standalone-rescue-ready
# The initial display holds are deliberately retained in this rescue environment.
while :; do sleep 60; done
