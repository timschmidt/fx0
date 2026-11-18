#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu

log_stage() {
    if [ -c /dev/kmsg ]; then
        printf '<2>%s\n' "$*" > /dev/kmsg && return
    fi
    printf '%s\n' "$*" >&2
}
abort_trial() {
    log_stage "FX0_VENUS_STAGE_FAIL $*"
    sync
    reboot -f
    while :; do sleep 60; done
}

release=6.18.64-fx0-venus-ram-alpine
[ "$(uname -r)" = "$release" ] || abort_trial release
case " $(cat /proc/cmdline) " in
    *' fx0.native_trial=venus-6.18.64-02 '*) : ;;
    *) abort_trial token ;;
esac
[ "$(cat /proc/sys/kernel/tainted)" = 0 ] || abort_trial taint
[ "$(cat /sys/module/module/parameters/sig_enforce)" = Y ] || abort_trial signatures
firmware_parameter=/sys/module/firmware_class/parameters/path
# The postmarketOS first stage selects this path before loading drivers.
[ "$(cat "$firmware_parameter")" = /lib/firmware/postmarketos ] || abort_trial 'initial firmware path'
[ -f /tmp/fx0-native-return-armed ] || abort_trial 'return helper'

early_modules=/usr/lib/modules
ram_modules=/fx0-ram-modules
[ -d "$early_modules/$release" ] && [ -d /sysroot/usr/lib/modules ] || abort_trial 'module paths'
(cd "$early_modules/$release" && sha256sum -c /etc/fx0-native-modules.sha256 >/dev/null) || abort_trial 'source modules'
mkdir "$ram_modules" || abort_trial 'module directory'
mount -t tmpfs -o size=96m,nodev,nosuid,mode=0755 tmpfs "$ram_modules" || abort_trial tmpfs
cp -a "$early_modules/$release" "$ram_modules/" || abort_trial 'module copy'
cp "$early_modules/initramfs.load" "$ram_modules/initramfs.load" || abort_trial 'early module list'
(cd "$ram_modules/$release" && sha256sum -c /etc/fx0-native-modules.sha256 >/dev/null) || abort_trial 'copied modules'
mount --move "$ram_modules" /sysroot/usr/lib/modules || abort_trial 'module mount move'

early_firmware=/usr/lib/firmware
ram_firmware=/run/fx0-venus-firmware
mkdir -p -m 700 "$ram_firmware/qcom/msm8226" || abort_trial 'firmware directory'
cp -a "$early_firmware"/qcom/msm8226/venus.* "$ram_firmware/qcom/msm8226/" || abort_trial 'firmware copy'
(cd "$ram_firmware" && sha256sum -c /etc/fx0-venus-firmware.sha256 >/dev/null) || abort_trial 'copied firmware'

mkdir -m 700 /run/fx0-native-trial || abort_trial 'trial status directory'
cp /tmp/fx0-native-return-armed /run/fx0-native-trial/return-armed || abort_trial 'return status'
mkdir -p /run/systemd/system/sysinit.target.wants || abort_trial 'return timer directory'
cp /etc/fx0-native-return.service /run/systemd/system/fx0-native-return.service || abort_trial 'return service'
cp /etc/fx0-native-return.timer /run/systemd/system/fx0-native-return.timer || abort_trial 'return timer'
ln -s ../fx0-native-return.timer /run/systemd/system/sysinit.target.wants/fx0-native-return.timer || abort_trial 'return timer enable'
# The verified copy is available on the /run mount carried into userspace.
printf '%s' "$ram_firmware" > "$firmware_parameter" || abort_trial 'firmware path switch'
[ "$(cat "$firmware_parameter")" = "$ram_firmware" ] || abort_trial 'verify firmware path'
log_stage "FX0_VENUS_STAGE_READY release=$release"
