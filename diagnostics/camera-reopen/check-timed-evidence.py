#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the actual timed parser and correlation on malformed and delayed evidence."""
import argparse
import importlib.util
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--worker', type=Path, default=Path(__file__).with_name('timed-queue-test.py'))
source = parser.parse_args().worker
spec = importlib.util.spec_from_file_location('timed_camera', source)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def fixture(times=(1_000_000, 1_033_333, 1_066_666, 1_133_332), sequences=(0, 1, 2, 3), size=10112256):
    return '\n'.join(f'{ts // 1_000_000}.{ts % 1_000_000:06d} (30.00 fps) stream0 seq: {seq:06d} bytesused: {size}'
                     for ts, seq in zip(times, sequences))


frames = worker.parse_frames(fixture(), 10112256, 4)
assert frames[-1]['timestamp_ns'] - frames[-2]['timestamp_ns'] == 66_666_000
cases = ['valid gap retained in timestamps']
for name, text in [
    ('missing record', fixture(sequences=(0, 1, 2))),
    ('sequence gap', fixture(sequences=(0, 1, 4, 5))),
    ('wrong bytes', fixture(size=1)),
    ('backward timestamp', fixture(times=(1_000_000, 1_033_333, 1_030_000, 1_133_332))),
    ('damaged timestamp syntax', fixture().replace('1.000000', '1.badtime')),
]:
    try:
        worker.parse_frames(text, 10112256, 4)
    except ValueError:
        cases.append(name + ' rejected')
    else:
        raise AssertionError(name + ' accepted')

for when, phase in [
    (999_999, 'before first delivered buffer'),
    (1_080_000, 'between delivered buffers'),
    (1_140_000, 'after last delivered buffer, before cam exit observed'),
    (1_160_000, 'after cam exit observed'),
]:
    result = worker.correlate({'monotonic_usec': when, 'priority': 3, 'message': 'qcom-camss: warning'},
                              frames, 1_150_000_000)
    assert result['phase'] == phase
    if phase == 'between delivered buffers':
        assert (result['previous_sequence'], result['next_sequence'], result['bracketing_interval_ns']) == (2, 3, 66_666_000)
    cases.append(phase)

for message, priority, expected in [
    ('qcom-camss fda0ac00.camss: Missing ready buf 1 4!', 3, True),
    ('qcom-camss: unrecognized diagnostic', 4, True),
    ('qcom-camss: ordinary information', 6, False),
    ('other-driver: failure', 3, True),
]:
    assert bool(worker.issues([{'message': message, 'priority': priority}])) is expected
    cases.append(message)
print(json.dumps({'timed_evidence_cases': len(cases), 'cases': cases, 'hardware_access': False}, indent=2))
