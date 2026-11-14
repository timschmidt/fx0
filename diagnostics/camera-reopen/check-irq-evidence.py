#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check IRQ bit decoding and keep printk/trace clock domains separate."""
import copy
import json
from irq_evidence import analyze_irqs, decode_irq

cases = []
for bits, lines, masters in [(0x10,['PIX'],[]),(0x20,['RDI0'],[]),(0x40,['RDI1'],[]),
                             (0x80,['RDI2'],[]),(0x100,[],[0]),(0x4000,[],[6]),(0x120,['RDI0'],[0])]:
    row=decode_irq(f'qcom-camss fda0ac00.camss: VFE: status0 = 0x{bits:08x}, status1 = 0x00000000')
    assert row['reg_update_lines']==lines and row['wm_done_indices']==masters
    cases.append('pinned status bits '+hex(bits))
assert decode_irq('qcom-camss: malformed VFE status') is None
cases.append('unrecognized debug payload not decoded')
report={'trace_capture':{'no_lost_events':True},'captures':[],'session_trace_evidence':[]}
trace=[];logs={'kernel_ring_overrun_during_read':False,'kernel_ring_rows':[],'journal_rows':[]}
sequence=100
for case in range(5):
    start=2_000_000_000+case*1_000_000_000
    frames=[]
    for index in range(24):
        when=start+500_000_000+index*1000
        trace.append({'event':'vb2_buf_done','trace_ns':when,'timestamp_ns':when,
                      'owned_by_driver':([3]*20+[3,2,1,0])[index],'queued_count':1,'index':index%4})
        frames.append({'timestamp_ns':when})
    report['captures'].append({'camera':'front' if case in [0,2] else 'back','frames_timed':frames})
    report['session_trace_evidence'].append({'start_trace_ns':start,'end_trace_ns':start+900_000_000,'delivered_frames_matched':24})
    for warning in ([False,True] if case==2 else [False]):
        stamp=case*1_000_000+1000+(156 if warning else 0)
        message=('qcom-camss fda0ac00.camss: Missing ready buf 1 4!' if warning else
                 'qcom-camss fda0ac00.camss: VFE: status0 = 0x00000120, status1 = 0x20000000')
        logs['kernel_ring_rows'].append({'kernel_sequence':sequence,'kernel_monotonic_usec':stamp,'message':message});sequence+=1
        logs['journal_rows'].append({'_SOURCE_MONOTONIC_TIMESTAMP':str(stamp),'__MONOTONIC_TIMESTAMP':str(stamp+2_000_000),'MESSAGE':message})
result=analyze_irqs(report,trace,logs)
assert result['warning_count']==1 and result['warning_contexts'][0]['IRQ_to_warning_printk_usec']==156
assert result['warning_contexts'][0]['case_by_journal_reception']==2
assert result['cross_clock_microsecond_ordering_claimed'] is False
cases.append('two-second clock offset does not contaminate raw printk warning interval')
late=copy.deepcopy(logs)
for row in late['journal_rows']:row['__MONOTONIC_TIMESTAMP']=str(int(row['__MONOTONIC_TIMESTAMP'])+400_000)
assert analyze_irqs(report,trace,late)['warning_contexts']==result['warning_contexts']
cases.append('journal reception delay cannot change same-clock IRQ-to-warning interval')
for condition in ['trace-loss','kernel-overrun','sequence-gap','journal-source-mismatch','raw-owner','last-frame-mismatch','missing-case-IRQ']:
    p,t,l=copy.deepcopy(report),copy.deepcopy(trace),copy.deepcopy(logs)
    if condition=='trace-loss':p['trace_capture']['no_lost_events']=False
    elif condition=='kernel-overrun':l['kernel_ring_overrun_during_read']=True
    elif condition=='sequence-gap':l['kernel_ring_rows'][1]['kernel_sequence']+=1
    elif condition=='journal-source-mismatch':l['journal_rows'][0]['_SOURCE_MONOTONIC_TIMESTAMP']='0'
    elif condition=='raw-owner':t[0]['owner_private']='fixture-token'
    elif condition=='last-frame-mismatch':p['captures'][0]['frames_timed'][-1]['timestamp_ns']+=5000
    else:
        l['kernel_ring_rows'][0]['message']='other normal message';l['journal_rows'][0]['MESSAGE']='other normal message'
    try:analyze_irqs(p,t,l)
    except ValueError:cases.append(condition+' rejected')
    else:raise AssertionError(condition+' accepted')
print(json.dumps({'IRQ_evidence_cases':len(cases),'cases':cases,'hardware_accessed':False},indent=2))
