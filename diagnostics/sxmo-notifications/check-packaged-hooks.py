#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the real Sxmo environment loader and hook precedence with mocked vibration."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--control-init', required=True, type=Path)
args = parser.parse_args()
source = args.source.resolve()
results = []
with tempfile.TemporaryDirectory(prefix='fx0-packaged-hooks-') as temporary:
    base = Path(temporary)
    home = base / 'home'
    config = home / '.config'
    runtime = base / 'runtime'
    binary = base / 'bin'
    share_local, share_system = base / 'local/share', base / 'system/share'
    for folder in [config / 'sxmo/hooks/lg,madai', runtime, binary,
                   share_local / 'sxmo/default_hooks',
                   share_system / 'sxmo/default_hooks/lg,madai']:
        folder.mkdir(parents=True, exist_ok=True)
    def program(path, text):
        path.write_text(text)
        path.chmod(0o755)
    program(binary / 'xrandr', '#!/bin/sh\nexit 1\n')
    program(binary / 'sxmo_vibrate', '#!/bin/sh\nprintf "%s %s\\n" "$1" "$2" >> "$FIXTURE_CALLS"\n')
    generic = share_local / 'sxmo/default_hooks/sxmo_hook_notification.sh'
    program(generic, '#!/bin/sh\nprintf "generic\\n" >> "$FIXTURE_CALLS"\n')
    board = share_system / 'sxmo/default_hooks/lg,madai/sxmo_hook_notification.sh'
    shutil.copyfile(source / 'configs/default_hooks/lg,madai/sxmo_hook_notification.sh', board)
    board.chmod(0o755)
    def check(label, init, device, selected, calls, mute=False):
        log = base / 'calls'
        log.unlink(missing_ok=True)
        flag = config / 'sxmo/.novibrate'
        flag.unlink(missing_ok=True)
        if mute:
            flag.touch()
        environment = dict(PATH=':'.join([str(binary), str(source / 'scripts/core'),
                                         str(source / 'scripts/deviceprofiles'), '/usr/bin', '/bin']),
                           HOME=str(home), XDG_CONFIG_HOME=str(config),
                           XDG_RUNTIME_DIR=str(runtime), SXMO_DEVICE_NAME=device,
                           XDG_DATA_DIRS=str(share_local) + ':' + str(share_system),
                           FIXTURE_CALLS=str(log), LANG='C')
        script = '. "$1"; _sxmo_load_environments >/dev/null; command -v sxmo_hook_notification.sh; printf "%s\\n" "$PATH"; sxmo_hook_notification.sh'
        p = subprocess.run(['sh', '-c', script, 'fixture', str(init)], env=environment,
                           capture_output=True, text=True, timeout=5)
        assert p.returncode == 0, (label, p.stderr)
        lines = p.stdout.splitlines()
        assert lines[0] == str(selected), (label, lines)
        assert all(lines[1].split(':')), (label, 'empty PATH entry', lines[1])
        actual = log.read_text().splitlines() if log.exists() else []
        assert actual == calls, (label, actual)
        results.append(dict(case=label, selected_hook=str(selected.relative_to(base)), calls=actual,
                            no_empty_PATH_entry=True))
    candidate_init = source / 'configs/profile.d/sxmo_init.sh'
    check('original-misses-packaged-board-hook', args.control_init, 'lg,madai', generic, ['generic'])
    check('packaged-board-before-generic', candidate_init, 'lg,madai', board, ['300 39168'])
    check('packaged-board-respects-mute', candidate_init, 'lg,madai', board, [], mute=True)
    user_generic = config / 'sxmo/hooks/sxmo_hook_notification.sh'
    program(user_generic, '#!/bin/sh\nprintf "user-generic\\n" >> "$FIXTURE_CALLS"\n')
    check('user-generic-before-packaged-board', candidate_init, 'lg,madai', user_generic, ['user-generic'])
    user_board = config / 'sxmo/hooks/lg,madai/sxmo_hook_notification.sh'
    program(user_board, '#!/bin/sh\nprintf "user-board\\n" >> "$FIXTURE_CALLS"\n')
    check('user-board-before-user-generic', candidate_init, 'lg,madai', user_board, ['user-board'])
    user_board.unlink()
    user_generic.unlink()
    local_board = share_local / 'sxmo/default_hooks/lg,madai/sxmo_hook_notification.sh'
    local_board.parent.mkdir()
    program(local_board, '#!/bin/sh\nprintf "local-board\\n" >> "$FIXTURE_CALLS"\n')
    check('XDG-data-priority', candidate_init, 'lg,madai', local_board, ['local-board'])
    check('other-device-keeps-generic', candidate_init, 'desktop', generic, ['generic'])
print(json.dumps(dict(real_environment_loader=True,hardware_mocked=True,cases=results,
                      temporary_files_removed=not base.exists()), indent=2))
