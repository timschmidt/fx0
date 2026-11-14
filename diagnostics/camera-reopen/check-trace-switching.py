#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check alias removal, delivered-buffer correlation, and RAW10 pattern decoding."""
import copy
import importlib.util
import json
from pathlib import Path

source = Path(__file__).with_name('trace-switching.py')
spec = importlib.util.spec_from_file_location('switching', source)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
cases = []
raw = [{'trace_ns': 1_000_000_000, 'event': 'tracing_mark_write', 'marker': 'CASE_0_BEGIN'}]
for event in ['vb2_qbuf', 'vb2_dqbuf', 'vb2_buf_queue', 'vb2_buf_done', 'vb2_v4l2_buf_queue', 'vb2_v4l2_buf_done']:
    row = {'trace_ns': 1_100_000_000, 'event': event, 'timestamp_ns': 1_050_000_999, 'sequence': 7}
    if event.startswith('vb2_v4l2_'):
        row['minor'] = 0
    else:
        row.update(owner_private='private-token', type=9)
    raw.append(row)
raw.append({'trace_ns': 2_000_000_000, 'event': 'tracing_mark_write', 'marker': 'CASE_0_END'})
rows = worker.alias_rows(raw)
assert 'private-token' not in json.dumps(rows) and 'owner_private' not in json.dumps(rows)
assert {row['owner_alias'] for row in rows if 'owner_alias' in row} == {'owner1'}
assert raw[1]['owner_private'] == 'private-token'
cases.append('owner tokens removed without modifying private input')
frames = [{'frames_timed': [{'timestamp_ns': 1_050_000_000, 'sequence': 7}]}]
assert worker.session_evidence(rows, frames)[0]['delivered_frames_matched'] == 1
cases.append('microsecond truncation matches delivered timestamp and sequence')
for condition in ['missing-marker', 'duplicate-marker', 'reversed-markers', 'missing-event', 'wrong-sequence', 'wrong-timestamp', 'duplicate-done']:
    bad = copy.deepcopy(rows)
    if condition == 'missing-marker': bad = bad[:-1]
    elif condition == 'duplicate-marker': bad.append(dict(bad[-1]))
    elif condition == 'reversed-markers': bad[-1]['trace_ns'] = 0
    elif condition == 'missing-event': bad = [row for row in bad if row['event'] != 'vb2_buf_queue']
    elif condition == 'wrong-sequence': bad[-2]['sequence'] += 1
    elif condition == 'wrong-timestamp': bad[-2]['timestamp_ns'] += 1
    elif condition == 'duplicate-done': bad.append(dict(bad[-2]))
    try:
        worker.session_evidence(bad, frames)
    except ValueError:
        cases.append(condition + ' rejected')
    else:
        raise AssertionError(condition + ' accepted')
for condition in ['minor', 'type']:
    bad = copy.deepcopy(raw)
    target = next(row for row in bad if condition in row)
    target[condition] += 1
    try:
        worker.alias_rows(bad)
    except ValueError:
        cases.append('unexpected filtered ' + condition + ' rejected')
    else:
        raise AssertionError('bad filter accepted')

width, height, stride = 64, 8, 84
expected = ((1, 1, 0, 0, 1, 1, 0, 0), (1, 1, 1, 1, 0, 0, 0, 0),
            (1, 1, 1, 1, 0, 0, 0, 0), (1, 0, 1, 0, 1, 0, 1, 0))
frame = bytearray(height * stride)
for y in range(height):
    for x in range(width):
        plane = (y % 2) * 2 + x % 2
        value = 1000 if expected[plane][x // 8] else 0
        group, index = divmod(x, 4)
        offset = y * stride + group * 5
        frame[offset + index] = value >> 2
        frame[offset + 4] |= (value & 3) << (index * 2)
assert len(worker.bars(frame, width, height, stride)) == 3
cases.append('packed RAW10 pattern decoded with padded stride')
try:
    worker.bars(bytes(height * stride), width, height, stride)
except ValueError:
    cases.append('flat invalid pattern rejected')
else:
    raise AssertionError('flat frame accepted')
print(json.dumps({'switching_evidence_cases': len(cases), 'cases': cases,
                  'hardware_accessed': False}, indent=2))
