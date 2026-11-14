#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Analyze preserved four-event core data from the failed first switching trace."""
from pathlib import Path
import argparse,os
import hashlib,json,statistics
from collections import Counter
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('observation',type=Path)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
source=args.observation
observation=json.loads(source.read_text())
report=observation['result'];rows=observation['decoded_alias_rows']
assert report is not None and rows is not None
assert not any('owner_private' in row for row in rows)
assert report['worker_error']=='ValueError: session trace event family missing'
assert observation['unit_before_stop']['ExecMainStatus']=='1'
# Post-hoc analysis of retained data; never overwrite or accept failed worker report.
bounds_by_case=[]
matched_frames=0
for index,capture in enumerate(report['captures']):
    starts=[r for r in rows if r.get('marker')==f'CASE_{index}_BEGIN']
    ends=[r for r in rows if r.get('marker')==f'CASE_{index}_END']
    assert len(starts)==len(ends)==1 and starts[0]['trace_ns']<ends[0]['trace_ns']
    start,finish=starts[0]['trace_ns'],ends[0]['trace_ns']
    selected=[r for r in rows if start<=r['trace_ns']<=finish]
    counts=Counter(r['event'] for r in selected)
    assert all(counts[event]==24 for event in ['vb2_qbuf','vb2_dqbuf','vb2_buf_queue','vb2_buf_done'])
    for frame in capture['frames_timed']:
        for event in ['vb2_buf_done','vb2_dqbuf']:
            matches=[r for r in selected if r['event']==event and 0<=r['timestamp_ns']-frame['timestamp_ns']<1000 and r['bytesused']==frame['bytesused']]
            assert len(matches)==1
        matched_frames+=1
    bounds_by_case.append({'start_trace_ns':start,'end_trace_ns':finish,'event_counts':dict(counts)})
sessions=[]
for index, capture in enumerate(report['captures']):
    bounds=bounds_by_case[index]
    selected=[r for r in rows if bounds['start_trace_ns']<=r['trace_ns']<=bounds['end_trace_ns']]
    frames=capture['frames_timed']
    intervals=[b['timestamp_ns']-a['timestamp_ns'] for a,b in zip(frames,frames[1:])]
    median=statistics.median(intervals)
    gaps=[]
    for previous,following,interval in zip(frames,frames[1:],intervals):
        if interval<=median*1.5:continue
        def core_done(frame):
            matches=[r for r in selected if r['event']=='vb2_buf_done' and 0<=r['timestamp_ns']-frame['timestamp_ns']<1000]
            assert len(matches)==1
            return matches[0]
        first,last=core_done(previous),core_done(following)
        between=[r for r in selected if first['trace_ns']<=r['trace_ns']<=last['trace_ns']]
        queued=[r for r in selected if r['event']=='vb2_buf_queue' and r['trace_ns']>=first['trace_ns'] and r['index']==first['index'] and r['owner_alias']==first['owner_alias']]
        next_queue=min(queued,key=lambda r:r['trace_ns']) if queued else None
        driver=[r for r in between if 'owned_by_driver' in r]
        gaps.append({'previous_sequence':previous['sequence'],'next_sequence':following['sequence'],
                     'interval_ms':interval/1e6,'median_multiple':interval/median,
                     'previous_core_done':first,'next_core_done':last,
                     'same_buffer_next_driver_queue':next_queue,
                     'same_buffer_requeue_delay_ms':(next_queue['trace_ns']-first['trace_ns'])/1e6 if next_queue else None,
                     'minimum_core_owned_count_between':min((r['owned_by_driver'] for r in driver),default=None),
                     'core_zero_owned_snapshots_between':sum(r['owned_by_driver']==0 for r in driver),
                     'events_between':between})
    sessions.append({'case':index,'camera':capture['camera'],'geometry':[capture['width'],capture['height']],
                     'delivered_buffers':len(frames),'pattern_frames':capture['consecutive_pattern_frames'],
                     'median_interval_ms':median/1e6,'maximum_interval_ms':max(intervals)/1e6,
                     'intervals_over_1_5_median':len(gaps),'trace_counts':bounds['event_counts'],
                     'gaps':gaps})
warnings=[]
for warning in report['kernel_messages']:
    when=warning['monotonic_usec']*1000
    containing=[i for i,b in enumerate(bounds_by_case) if b['start_trace_ns']<=when<=b['end_trace_ns']]
    assert len(containing)==1
    index=containing[0];capture=report['captures'][index];bound=bounds_by_case[index]
    selected=[r for r in rows if bound['start_trace_ns']<=r['trace_ns']<=bound['end_trace_ns']]
    core=[r for r in selected if r['event']=='vb2_buf_done'];last=max(core,key=lambda r:r['trace_ns'])
    dequeues=[r for r in selected if r['event']=='vb2_dqbuf' and r['index']==last['index'] and r['timestamp_ns']==last['timestamp_ns']]
    assert len(dequeues)==1
    queued=[r for r in selected if r['event']=='vb2_buf_queue' and r['trace_ns']<=when]
    last_queue=max(queued,key=lambda r:r['trace_ns'])
    warnings.append({'message':warning['message'],'case':index,'camera':capture['camera'],'warning_ns':when,
                     'last_core_done':last,'last_core_dequeue':dequeues[0],
                     'warning_after_last_core_done_ms':(when-last['trace_ns'])/1e6,
                     'last_dequeue_after_warning_ms':(dequeues[0]['trace_ns']-when)/1e6,
                     'last_frame_timestamp_to_core_done_ms':(last['trace_ns']-last['timestamp_ns'])/1e6,
                     'warning_after_last_driver_queue_ms':(when-last_queue['trace_ns'])/1e6,
                     'driver_queue_events_after_warning':sum(r['event']=='vb2_buf_queue' and r['trace_ns']>when for r in selected),
                     'tail_core_counts':[{k:r[k] for k in ['event','trace_ns','index','queued_count','owned_by_driver']} for r in selected if r['event'] in ['vb2_buf_done','vb2_dqbuf']][-8:]})
result={'analysis_kind':'post-hoc core trace correlation; original worker remains failed',
        'matched_delivered_frames_by_core_timestamp_and_size':matched_frames,
        'warning_contexts':warnings,'observation_SHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'sessions':sessions,
        'vb2_count_semantics':'core snapshots only, not direct VFE internal state or proof of hardware frame counts',
        'new_kernel_messages':report['kernel_messages'],'original_warning_reproduced':any('Missing ready buf' in r['message'] for r in report['kernel_messages']),
        'original_warning_cause_resolved':False}
descriptor=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(descriptor,'w') as stream:stream.write(json.dumps(result,indent=2)+'\n')
for session in sessions:
    print(json.dumps({k:v for k,v in session.items() if k!='gaps'}))
    for gap in session['gaps']:
        print(json.dumps({k:v for k,v in gap.items() if k not in ['previous_core_done','next_core_done','same_buffer_next_driver_queue','events_between']}))
