#!/bin/sh
# Install access rules for the Fx0 stock USB mode and lk2nd fastboot.
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo "Run through the host administrator authentication mechanism." >&2
    exit 1
fi
rule=/etc/udev/rules.d/70-fx0-development.rules
if [ -e "$rule" ]; then
    echo "Refusing to overwrite existing rule: $rule" >&2
    exit 1
fi
install -d -m 0755 /etc/udev/rules.d
cat > "$rule" <<'RULES'
# LG Fx0 LGL25 stock USB and lk2nd fastboot, for the active local user.
SUBSYSTEM=="usb", ATTR{idVendor}=="1004", ATTR{idProduct}=="6341", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="d00d", TAG+="uaccess"
RULES
chmod 0644 "$rule"
udevadm control --reload-rules
udevadm trigger --action=change --subsystem-match=usb --attr-match=idVendor=1004
udevadm trigger --action=change --subsystem-match=usb --attr-match=idVendor=18d1
udevadm settle
