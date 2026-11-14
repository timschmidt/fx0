#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Associate sole VFE41 IRQ log records with complete mono-clock IRQ spans."""
from collections import Counter
from irq_evidence import decode_irq, WARNING
from queue_trace import require


def analyze_callbacks(report, rows, ring):
    require(report['trace_capture']['no_lost_events'], 'callback analysis requires lossless trace')
    require(len(report['captures']) == len(report['session_trace_evidence']) == 5, 'full five-session workload required')
    require(all(case['delivered_frames_matched'] == 24 for case in report['session_trace_evidence']),
            'core frame validation incomplete')
    require(sum(row['event'] == 'vb2_buf_done' for row in rows) == 120, 'core completion count differs')
    require(all('owner_private' not in row for row in rows), 'private owner token in analysis input')
    require(not ring['overrun_during_read'], 'kernel log read overran')
    records = ring['records']
    seq = [row['kernel_sequence'] for row in records]
    require(seq and seq == list(range(seq[0], seq[0] + len(seq))), 'kernel sequence gap or disorder')
    journal = {}
    for row in report['kernel_messages']:
        key = (row['source_printk_usec'], row['message'])
        require(key not in journal, 'ambiguous source journal record')
        journal[key] = row
    require(len(records) == len(journal) and all((row['kernel_monotonic_usec'], row['message']) in journal for row in records),
            'kernel/journal source records differ')
    irqs = [row | {'decoded': decode_irq(row['message'])} for row in records if decode_irq(row['message']) is not None]
    order = [(row['trace_ns'], row['trace_order']) for row in rows]
    require(order == sorted(order), 'trace rows out of emission order')
    spans, active = [], None
    for row in rows:
        event = row['event']
        if event == 'irq_handler_entry':
            require(active is None, 'overlapping VFE IRQ spans cannot be ordered uniquely')
            active = {'entry': row, 'events': [row]}
        elif event == 'irq_handler_exit':
            require(active is not None and active['entry']['cpu'] == row['cpu'], 'unmatched IRQ exit or CPU change')
            active['events'].append(row)
            active['exit'] = row
            spans.append(active)
            active = None
        elif event == 'function':
            require(active is not None and active['entry']['cpu'] == row['cpu'], 'selected callback outside VFE IRQ')
            active['events'].append(row)
        elif active is not None and row['cpu'] == active['entry']['cpu'] and event == 'vb2_buf_done':
            active['events'].append(row)
    require(active is None, 'unterminated VFE IRQ span')
    require(len(irqs) == len(spans) and irqs, 'IRQ print/span counts differ; no association allowed')
    # Sole VFE41 handler prints once at entry. Complete, serial streams permit
    # ordinal association without converting between printk and mono clocks.
    by_sequence = {}
    for index, (irq, span) in enumerate(zip(irqs, spans)):
        functions = [row for row in span['events'] if row['event'] == 'function']
        counts = Counter(row['function'] for row in functions)
        require(counts['vfe_isr'] == 1, 'IRQ lacks one selected handler entry')
        require(all(row['caller'] == 'vfe_isr' for row in functions if row['function'] != 'vfe_isr'),
                'callback caller differs from sole VFE41 handler')
        expected = {'vfe_isr': 1, 'vfe_isr_reg_update': len(irq['decoded']['reg_update_lines']),
                    'vfe_isr_wm_done': len(irq['decoded']['wm_done_indices'])}
        require(all(counts[name] == count for name, count in expected.items()),
                'callback counts disagree with saved raw-capture IRQ bits')
        span['ordinal'] = index
        span['IRQ_record'] = irq
        by_sequence[irq['kernel_sequence']] = span
    contexts = []
    for record in records:
        warning = WARNING.fullmatch(record['message'])
        if warning is None:
            continue
        previous = [irq for irq in irqs if irq['kernel_sequence'] < record['kernel_sequence']]
        require(previous, 'warning has no preceding VFE41 IRQ print')
        irq = previous[-1]
        span = by_sequence[irq['kernel_sequence']]
        containing = [i for i, case in enumerate(report['session_trace_evidence'])
                      if case['start_trace_ns'] <= span['entry']['trace_ns'] <= span['exit']['trace_ns'] <= case['end_trace_ns']]
        require(len(containing) == 1, 'warning-associated IRQ not wholly inside one session')
        case_index = containing[0]
        wm = [row for row in span['events'] if row.get('function') == 'vfe_isr_wm_done']
        reg = [row for row in span['events'] if row.get('function') == 'vfe_isr_reg_update']
        done = [row for row in span['events'] if row['event'] == 'vb2_buf_done']
        last_timestamp = report['captures'][case_index]['frames_timed'][-1]['timestamp_ns']
        final_done = [row for row in done if 0 <= row['timestamp_ns'] - last_timestamp < 1000]
        position = {id(row): i for i, row in enumerate(span['events'])}
        final_before_wm = (len(reg) == len(wm) == len(final_done) == 1 and
                           position[id(reg[0])] < position[id(final_done[0])] < position[id(wm[0])])
        events = []
        for row in span['events']:
            item = {'event': row.get('function', row['event']),
                    'relative_trace_usec': (row['trace_ns'] - span['entry']['trace_ns']) / 1000,
                    'trace_order': row['trace_order']}
            if row['event'] == 'vb2_buf_done':
                item.update(index=row['index'], queued_count=row['queued_count'], owned_by_driver=row['owned_by_driver'])
            events.append(item)
        contexts.append({'message': record['message'], 'reported_output_state': int(warning[2]),
                         'case': case_index, 'camera': report['captures'][case_index]['camera'],
                         'IRQ_ordinal': span['ordinal'], 'IRQ_kernel_sequence': irq['kernel_sequence'],
                         'warning_kernel_sequence': record['kernel_sequence'], 'saved_status': irq['decoded'],
                         'IRQ_to_warning_printk_usec': record['kernel_monotonic_usec'] - irq['kernel_monotonic_usec'],
                         'final_core_done_between_reg_update_and_wm_entry': final_before_wm,
                         'events_in_mono_clock': events})
    return {'IRQ_spans': len(spans), 'VFE41_IRQ_prints': len(irqs),
            'all_spans_have_one_handler_entry': True, 'saved_bits_match_callback_counts': True,
            'complete_serial_streams_associated_by_ordinal': True, 'warning_contexts': contexts,
            'warning_count': len(contexts), 'cross_clock_timestamp_conversion_used': False,
            'contract': 'One debug print at sole VFE41 handler entry; complete serial IRQ95 spans; lossless trace; contiguous and matched kernel/journal records.',
            'limitations': 'Callback entries, core completions and IRQ boundaries are traced; VFE memory state and MMIO writes are not directly traced.'}
