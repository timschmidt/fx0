#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check complete ordinal IRQ association without timestamp-domain conversion."""
import copy
import json
from callback_evidence import analyze_callbacks

report={'trace_capture':{'no_lost_events':True},'captures':[],'session_trace_evidence':[],'kernel_messages':[]}
rows=[];ring={'overrun_during_read':False,'records':[]};sequence=100;order=0
for case in range(5):
    start=10_000_000_000+case*1_000_000_000;frames=[]
    report['session_trace_evidence'].append({'start_trace_ns':start-1,'end_trace_ns':start+100_000_000,'delivered_frames_matched':24})
    for frame in range(24):
        when=start+frame*1_000_000;frames.append({'timestamp_ns':when})
        events=['irq_handler_entry','vfe_isr','vfe_isr_reg_update']
        events+=['vb2_buf_done','vfe_isr_wm_done'] if frame==23 else ['vfe_isr_wm_done','vb2_buf_done']
        events+=['irq_handler_exit']
        for event in events:
            row={'event':event,'trace_ns':when,'trace_order':order,'cpu':0};order+=1
            if event.startswith('vfe_'):
                row.update(event='function',function=event,caller='__handle_irq_event_percpu' if event=='vfe_isr' else 'vfe_isr')
            elif event=='vb2_buf_done':row.update(timestamp_ns=when,index=frame%4,queued_count=1,owned_by_driver=0 if frame==23 else 3)
            rows.append(row)
        messages=['qcom-camss fda0ac00.camss: VFE: status0 = 0x00000120, status1 = 0x20000000']
        if case==2 and frame==23:messages.append('qcom-camss fda0ac00.camss: Missing ready buf 1 4!')
        for warning,message in enumerate(messages):
            stamp=case*1_000_000+frame*1000+warning*156
            ring['records'].append({'kernel_sequence':sequence,'kernel_monotonic_usec':stamp,'message':message});sequence+=1
            report['kernel_messages'].append({'source_printk_usec':stamp,'monotonic_usec':when//1000+400_000,'message':message})
    report['captures'].append({'camera':'front' if case in [0,2] else 'back','frames_timed':frames})
result=analyze_callbacks(report,rows,ring)
assert result['IRQ_spans']==result['VFE41_IRQ_prints']==120
assert result['warning_contexts'][0]['case']==2 and result['warning_contexts'][0]['IRQ_to_warning_printk_usec']==156
assert result['warning_contexts'][0]['final_core_done_between_reg_update_and_wm_entry']
assert result['cross_clock_timestamp_conversion_used'] is False
cases=['complete serial streams associate; equal-timestamp callback order preserved']
late=copy.deepcopy(report)
for row in late['kernel_messages']:row['monotonic_usec']+=50_000_000
assert analyze_callbacks(late,rows,ring)==result
cases.append('arbitrary journal reception delay cannot change callback association')
for condition in ['trace-loss','kernel-overrun','kernel-gap','source-mismatch','handler-missing',
                  'unmatched-exit','wrong-CPU','unscoped-callback','wrong-caller','IRQ-print-missing',
                  'saved-bits-mismatch','private-owner','short-core-count','core-validation-short','row-disorder']:
    p,t,k=copy.deepcopy(report),copy.deepcopy(rows),copy.deepcopy(ring)
    if condition=='trace-loss':p['trace_capture']['no_lost_events']=False
    elif condition=='kernel-overrun':k['overrun_during_read']=True
    elif condition=='kernel-gap':k['records'][-1]['kernel_sequence']+=1
    elif condition=='source-mismatch':p['kernel_messages'][0]['source_printk_usec']+=1
    elif condition=='handler-missing':t.pop(1)
    elif condition=='unmatched-exit':t.pop(0)
    elif condition=='wrong-CPU':t[5]['cpu']=1
    elif condition=='unscoped-callback':t.insert(0,t[1]|{'trace_order':-1})
    elif condition=='wrong-caller':t[2]['caller']='unexpected'
    elif condition=='IRQ-print-missing':
        k['records'].pop(0);p['kernel_messages'].pop(0)
    elif condition=='saved-bits-mismatch':
        k['records'][0]['message']=k['records'][0]['message'].replace('00000120','00000020')
        p['kernel_messages'][0]['message']=k['records'][0]['message']
    elif condition=='private-owner':t[0]['owner_private']='fixture-private'
    elif condition=='short-core-count':t.pop(next(i for i,r in enumerate(t) if r['event']=='vb2_buf_done'))
    elif condition=='core-validation-short':p['session_trace_evidence'][0]['delivered_frames_matched']=23
    else:t[0],t[1]=t[1],t[0]
    try:analyze_callbacks(p,t,k)
    except ValueError:cases.append(condition+' rejected')
    else:raise AssertionError(condition+' accepted')
print(json.dumps({'callback_evidence_cases':len(cases),'cases':cases,'hardware_accessed':False},indent=2))
