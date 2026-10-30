#!/bin/sh
# SPDX-License-Identifier: MIT
# Fx0 bringup: observed input identifiers and tested display scale.
export SXMO_POWER_BUTTON="0:0:pm8941_pwrkey"
export SXMO_VOLUME_BUTTON="1:1:gpio-keys"
export SXMO_SWAY_SCALE="1.5"
# Measured contact trajectories need a 60px swipe and a 120px edge band.
export SXMO_LISGD_THRESHOLD="60"
export LISGD_EDGE_SIZE="2.4"
