#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare actual systemd dependency graphs; never execute clock or fsck jobs."""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('repository', type=Path)
parser.add_argument('baseline')
parser.add_argument('workspace', type=Path, help='New empty output directory')
args = parser.parse_args()
args.workspace.mkdir(exist_ok=False)
unit_path = 'systemd/swclock-offset-boot.service.in'
baseline = subprocess.check_output(['git', '-C', str(args.repository), 'show', args.baseline + ':' + unit_path], text=True)
candidate = (args.repository / unit_path).read_text()
report = {'baseline': args.baseline, 'services_executed': False, 'system_time_changed': False, 'variants': {}}
for variant, source in [('baseline', baseline), ('fixed', candidate)]:
    units = args.workspace / (variant + '-units')
    units.mkdir()
    # Keep actual dependency instructions. The placeholder command only avoids
    # requiring installation of swclock-offset on the graph-checking host.
    (units / 'swclock-offset-boot.service').write_text(source.replace('SWCLOCK_PATH/swclock-offset-boot', '/usr/bin/true'))
    for name in ['systemd-fsck@.service', 'systemd-fsck-root.service', 'local-fs-pre.target']:
        shutil.copyfile(Path('/usr/lib/systemd/system') / name, units / name)
    for name in ['sysinit.target', 'basic.target', 'sockets.target', 'shutdown.target', 'emergency.target',
                 'local-fs.target', 'reboot.target', 'poweroff.target', 'halt.target', 'kexec.target']:
        (units / name).write_text('[Unit]\nDescription=Offline graph fixture\nDefaultDependencies=no\n')
    env = os.environ.copy()
    env.update(SYSTEMD_UNIT_PATH=str(units.resolve()), SYSTEMD_LOG_LEVEL='debug', SYSTEMD_COLORS='0')
    command = ['systemd-analyze', 'verify', '--man=no', '--generators=no',
               str(units / 'swclock-offset-boot.service'), 'systemd-fsck@dev-first.service',
               'systemd-fsck@dev-second.service', 'local-fs-pre.target']
    child = subprocess.run(command, env=env, capture_output=True, text=True)
    log = child.stdout + child.stderr
    (args.workspace / (variant + '-manager.txt')).write_text(log)
    assert child.returncode == 0, log
    graph = {}
    for block in re.split(r'(?:^|\n)\s*→ Unit ', log)[1:]:
        first, _, rest = block.partition('\n')
        properties = {}
        for line in rest.splitlines():
            match = re.match(r'\s+(Before|After|Wants):\s+(\S+)', line)
            if match:
                properties.setdefault(match[1], []).append(match[2])
        graph[first.rstrip(':').strip()] = properties
    clock = graph['swclock-offset-boot.service']
    assert 'systemd-fsck-root.service' in clock['Before']
    for name in ['systemd-fsck@dev-first.service', 'systemd-fsck@dev-second.service']:
        assert 'local-fs-pre.target' in graph[name]['After']
    if variant == 'baseline':
        assert 'systemd-fsck@swclock-offset-boot.service' in clock['Before']
        assert 'local-fs-pre.target' not in clock.get('Before', [])
    else:
        assert 'local-fs-pre.target' in clock['Before'] and 'local-fs-pre.target' in clock['Wants']
        assert 'systemd-fsck@swclock-offset-boot.service' not in log
        assert 'local-fs-pre.target: Installed new job local-fs-pre.target/start' in log
    report['variants'][variant] = {'verify_returncode': child.returncode, 'dependency_graph': graph}
(args.workspace / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print('Baseline spurious instance and fixed explicit clock/fsck barrier verified; no services executed.')
