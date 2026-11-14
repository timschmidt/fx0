#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Decode pinned VFE41 status bits and correlate private journal/trace evidence."""
import re
from queue_trace import require

IRQ = re.compile(r'^qcom-camss fda0ac00\.camss: VFE: status0 = 0x([0-9a-fA-F]{8}), status1 = 0x([0-9a-fA-F]{8})$')
WARNING = re.compile(r'^qcom-camss fda0ac00\.camss: Missing ready buf ([01]) ([0-9]+)!$')


def decode_irq(message):
    match = IRQ.fullmatch(message)
    if match is None:
        return None
    value0, value1 = (int(word, 16) for word in match.groups())
    # camss-vfe-4-1.c: line REG_UPDATE is PIX bit4 or RDI(n) bit(n+5);
    # image-master ping/pong completion is bit(n+8), n=0..6.
    return {'status0_hex': f'0x{value0:08x}', 'status1_hex': f'0x{value1:08x}',
            'reg_update_lines': [name for name, bit in [('PIX', 4), ('RDI0', 5), ('RDI1', 6), ('RDI2', 7)] if value0 & (1 << bit)],
            'wm_done_indices': [index for index in range(7) if value0 & (1 << (index + 8))]}



def analyze_irqs(report, trace_rows, logs):
    """Use printk timestamps for log order; never mix them with trace mono time."""
    require(report['trace_capture']['no_lost_events'], 'analysis requires lossless core trace')
    require(not logs['kernel_ring_overrun_during_read'], 'kernel-ring read overran')
    require(len(report['captures']) == len(report['session_trace_evidence']) == 5, 'full workload required')
    require(all('owner_private' not in row for row in trace_rows), 'raw owner tokens in input')
    records = logs['kernel_ring_rows']
    sequences = [row['kernel_sequence'] for row in records]
    require(sequences and sequences == list(range(sequences[0], sequences[0] + len(sequences))),
            'kernel sequence gap or disorder')
    journal = {}
    for row in logs['journal_rows']:
        require('_SOURCE_MONOTONIC_TIMESTAMP' in row, 'missing original kernel timestamp')
        key = (int(row['_SOURCE_MONOTONIC_TIMESTAMP']), row['MESSAGE'])
        require(key not in journal, 'ambiguous journal source record')
        journal[key] = row
    require(len(journal) == len(records), 'journal/kernel window counts differ')
    require(all((row['kernel_monotonic_usec'], row['message']) in journal for row in records),
            'journal source timestamps/messages do not match kernel records')
    irqs, warnings = [], []
    for record in records:
        decoded = decode_irq(record['message'])
        if decoded is not None:
            irqs.append(decoded | {'kernel_sequence': record['kernel_sequence'],
                                   'printk_timestamp_usec': record['kernel_monotonic_usec']})
        elif WARNING.fullmatch(record['message']):
            warning = WARNING.fullmatch(record['message'])
            require(irqs, 'warning has no preceding IRQ status record')
            preceding = irqs[-1]
            source = journal[(record['kernel_monotonic_usec'], record['message'])]
            reception_ns = int(source['__MONOTONIC_TIMESTAMP']) * 1000
            containing = [i for i, bound in enumerate(report['session_trace_evidence'])
                          if bound['start_trace_ns'] <= reception_ns <= bound['end_trace_ns']]
            require(len(containing) <= 1, 'overlapping camera windows')
            warnings.append({'message': record['message'], 'reported_output_state': int(warning[2]),
                             'missing_index': int(warning[1]), 'kernel_sequence': record['kernel_sequence'],
                             'printk_timestamp_usec': record['kernel_monotonic_usec'],
                             'preceding_IRQ': preceding,
                             'adjacent_kernel_records': preceding['kernel_sequence'] + 1 == record['kernel_sequence'],
                             'IRQ_to_warning_printk_usec': record['kernel_monotonic_usec'] - preceding['printk_timestamp_usec'],
                             'reg_update_and_wm_done_bits_in_saved_status': bool(preceding['reg_update_lines'] and preceding['wm_done_indices']),
                             'case_by_journal_reception': containing[0] if containing else None})
    counts, tails = [], []
    for index, (capture, bound) in enumerate(zip(report['captures'], report['session_trace_evidence'])):
        selected = [row for row in trace_rows if bound['start_trace_ns'] <= row['trace_ns'] <= bound['end_trace_ns']]
        done = [row for row in selected if row['event'] == 'vb2_buf_done']
        require(len(done) == 24 and bound['delivered_frames_matched'] == 24, 'core session incomplete')
        last = max(done, key=lambda row: row['trace_ns'])
        require(0 <= last['timestamp_ns'] - capture['frames_timed'][-1]['timestamp_ns'] < 1000, 'final core frame mismatch')
        tails.append({'case': index, 'camera': capture['camera'],
                      'last_four_core_owned_counts': [row['owned_by_driver'] for row in done[-4:]],
                      'last_core_done_queued_count': last['queued_count'],
                      'last_core_done_buffer_index': last['index']})
        messages = [row for row in logs['journal_rows'] if decode_irq(row['MESSAGE']) is not None
                    and bound['start_trace_ns'] <= int(row['__MONOTONIC_TIMESTAMP']) * 1000 <= bound['end_trace_ns']]
        require(messages, 'no received IRQ messages within case')
        counts.append(len(messages))
    return {'IRQ_status_messages': len(irqs), 'IRQ_messages_by_journal_reception_case': counts,
            'matched_journal_and_kernel_records': len(records), 'kernel_sequence_contiguous': True,
            'warning_count': len(warnings), 'warning_contexts': warnings, 'core_tails': tails,
            'cross_clock_microsecond_ordering_claimed': False,
            'clock_basis': 'Printk source timestamps and sequences for kernel log order; CLOCK_MONOTONIC for core trace; journal reception only for coarse session assignment.',
            'limitations': 'Saved status bits do not directly trace VFE state transitions or WM-to-line mappings; printk can perturb timing.'}
