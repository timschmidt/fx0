#!/bin/sh
# SPDX-License-Identifier: MIT
# mkinitfs cleanup hook, after udev has had a chance to bind native DRM.
if ! grep -Fq 'lg,madai' /sys/firmware/devicetree/base/compatible; then
    exit 0
fi
if [ "$(cat /sys/class/graphics/fb0/name 2>/dev/null)" != msmdrmfb ]; then
    echo 'Fx0 native framebuffer absent; temporary display holds retained' >/dev/kmsg
    exit 1
fi
for dev in fd928000.iommu fd900000.display-subsystem; do
    echo auto >"/sys/bus/platform/devices/$dev/power/control" || exit 1
done
echo 'Fx0 native framebuffer bound; initial display holds released' >/dev/kmsg
