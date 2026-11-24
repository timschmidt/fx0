#!/bin/sh
# SPDX-License-Identifier: MIT
# Fx0: one bounded pulse for a completed Sxmo notification.
[ ! -f "${XDG_CONFIG_HOME:-$HOME/.config}/sxmo/.novibrate" ] || exit 0
exec sxmo_vibrate 300 "${SXMO_VIBRATE_STRENGTH:-1}"
