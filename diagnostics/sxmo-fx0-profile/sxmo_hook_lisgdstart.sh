#!/bin/sh
# SPDX-License-Identifier: MIT
# configversion: 32e953d311555ad8dd7b4c13d5a0fff4
. /usr/local/bin/sxmo_deviceprofile_lg,madai.sh
unset SXMO_DEBUG
exec /usr/share/sxmo/default_hooks/sxmo_hook_lisgdstart.sh -r 25 "$@"
