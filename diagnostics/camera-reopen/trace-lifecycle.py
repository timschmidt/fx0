#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded empty tracefs-instance validation, before any camera capture."""
import argparse
import hashlib
import json
from pathlib import Path
import signal

from queue_trace import ROOT, TraceLease, parse_private_trace, private_json, recover_claim, settings, NativeIO, verify_markers

NAMES = ['fx0-camera-probe-normal-02', 'fx0-camera-probe-failure-02']


def identity(check_baseline=True):
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == 'e134d38d-f8b1-4115-8bff-8e91f69d1d01'
    assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() == '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
    if check_baseline:
        assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
        assert hashlib.sha256(Path('/lib/apk/db/installed').read_bytes()).hexdigest() == 'b106cfa76000084e240f6b1e40496a06b52f5d1820593364f8b13bfb54c9665f'


def recover(workspace):
    results = []
    for claim in sorted(workspace.glob('*.claim.json'), key=lambda p: not (ROOT / 'instances' / json.loads(p.read_text())['name']).exists()):
        assert json.loads(claim.read_text())['name'] in NAMES
        results.append(recover_claim(claim))
    assert all(not (ROOT / 'instances' / name).exists() for name in NAMES)
    private_json(workspace / 'stop-post.json', {'recovery': results, 'all_expected_instances_absent': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    identity(not args.recover)
    if args.recover:
        recover(args.workspace)
        return
    def stop(_signal, _frame):
        raise RuntimeError('owned lifecycle service stopped')
    signal.signal(signal.SIGTERM, stop)
    before = settings(ROOT, NativeIO())
    report = {'cases': [], 'camera_capture': False, 'before_settings': before, 'passed': False}
    try:
        for index, name in enumerate(NAMES):
            lease = TraceLease(name, args.workspace / (str(index) + '.claim.json'), fail_after_config=bool(index))
            try:
                with lease:
                    lease.start()
                    lease.marker('CLOCK_PROBE')
                    text, data = lease.stop_dump(args.workspace / 'empty.private.trace')
                    rows = parse_private_trace(text)
                    assert verify_markers(rows) == 1
                    assert len(rows) == 1 and rows[0]['event'] == 'tracing_mark_write'
                    assert data['no_lost_events']
                    report['cases'].append({'normal_empty_trace': data, 'marker_count': 1})
            except RuntimeError as error:
                assert index == 1 and str(error) == 'injected failure before event enable'
                report['cases'].append({'expected_setup_failure_rejected': True})
            assert lease.cleanup['instance_removed'] and lease.cleanup['global_and_other_settings_unchanged']
            report['cases'][-1]['cleanup'] = lease.cleanup
            report['cases'][-1]['buffer_sizing'] = lease.sizing
        report['after_settings'] = settings(ROOT, NativeIO())
        assert report['after_settings'] == before
        report['passed'] = True
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        private_json(args.workspace / 'result.json', report)
    print(json.dumps({'passed': True, 'cases': len(report['cases']), 'camera_capture': False}))


if __name__ == '__main__':
    main()
