#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check four-family core correlation, owner removal and RAW10 sample decoding."""
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
frames = [{'frames_timed': []}]
for index in range(24):
    when = 1_050_000_999 + index * 70_000_000
    frames[0]['frames_timed'].append({'timestamp_ns':when-999, 'sequence':index, 'bytesused':10})
    for event in ['vb2_qbuf', 'vb2_buf_queue', 'vb2_buf_done', 'vb2_dqbuf']:
        raw.append({'trace_ns':when+1000, 'event':event, 'timestamp_ns':when,
                    'owner_private':'private-token', 'type':9, 'bytesused':10})
raw.append({'trace_ns': 3_000_000_000, 'event': 'tracing_mark_write', 'marker': 'CASE_0_END'})
rows = worker.alias_rows(raw)
assert 'private-token' not in json.dumps(rows) and 'owner_private' not in json.dumps(rows)
assert {r['owner_alias'] for r in rows if 'owner_alias' in r} == {'owner1'}
assert raw[1]['owner_private'] == 'private-token'
cases.append('private owner tokens removed without altering input')
assert worker.session_evidence(rows, frames)[0]['delivered_frames_matched'] == 24
cases.append('24 buffers match unique core done/dequeue timestamps and sizes; no unused V4L2 events required')
for condition in ['missing-marker', 'duplicate-marker', 'reversed-markers', 'missing-event',
                  'wrong-timestamp', 'wrong-size', 'duplicate-done', 'short-delivery']:
    bad, delivered = copy.deepcopy(rows), copy.deepcopy(frames)
    index = next(i for i,r in enumerate(bad) if r['event']=='vb2_buf_done')
    if condition=='missing-marker':bad=bad[:-1]
    elif condition=='duplicate-marker':bad.append(dict(bad[-1]))
    elif condition=='reversed-markers':bad[-1]['trace_ns']=0
    elif condition=='missing-event':bad.pop(index)
    elif condition=='wrong-timestamp':bad[index]['timestamp_ns']+=1
    elif condition=='wrong-size':bad[index]['bytesused']+=1
    elif condition=='duplicate-done':bad.append(dict(bad[index]))
    else:delivered[0]['frames_timed'].pop()
    try:worker.session_evidence(bad, delivered)
    except ValueError:cases.append(condition+' rejected')
    else:raise AssertionError(condition+' accepted')
for condition in ['unused-event', 'type']:
    bad=copy.deepcopy(raw)
    if condition=='unused-event':bad[1]={'trace_ns':1_100_000_000,'event':'vb2_v4l2_buf_done','minor':0}
    else:bad[1]['type']=1
    try:worker.alias_rows(bad)
    except ValueError:cases.append(condition+' rejected')
    else:raise AssertionError(condition+' accepted')

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
print(json.dumps({'switching_evidence_cases':len(cases),'cases':cases,'hardware_accessed':False},indent=2))
