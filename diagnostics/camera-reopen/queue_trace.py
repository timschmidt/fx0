#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Owned tracefs instance and private vb2 trace decoding for the pinned camera tests."""
import hashlib
from collections import Counter
import json
import os
from pathlib import Path
import re
import time

EVENTS = {
    'vb2/vb2_qbuf': 'type == 9', 'vb2/vb2_dqbuf': 'type == 9',
    'vb2/vb2_buf_queue': 'type == 9', 'vb2/vb2_buf_done': 'type == 9',
}
IRQ_EVENTS = {'irq/irq_handler_entry': 'irq == 95', 'irq/irq_handler_exit': 'irq == 95'}
FUNCTION_COUNTS = {'vfe_isr': 8, 'vfe_isr_reg_update': 2, 'vfe_isr_wm_done': 2}
# Observe the unused V4L2 settings too, without enabling those uncalled events.
OBSERVED_EVENTS = dict(EVENTS, **IRQ_EVENTS, **{
    'v4l2/vb2_v4l2_buf_queue': 'minor == 0', 'v4l2/vb2_v4l2_buf_done': 'minor == 0'})
ROOT = Path('/sys/kernel/tracing')


def require(value, message):
    if not value:
        raise ValueError(message)


class NativeIO:
    def read(self, path):
        return path.read_text().strip()

    def write(self, path, value):
        path.write_text(value)

    def mkdir(self, path):
        path.mkdir()

    def rmdir(self, path):
        path.rmdir()


def private_json(path, value):
    temporary = path.with_name(path.name + '.new')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    temporary.replace(path)


def settings(root, io, exclude=None):
    def one(directory):
        values = {name: io.read(directory / name) for name in
                  ['tracing_on', 'current_tracer', 'trace_clock', 'buffer_size_kb', 'buffer_subbuf_size_kb',
                   'set_ftrace_filter', 'set_ftrace_notrace', 'set_ftrace_pid', 'set_ftrace_notrace_pid', 'trace_options']}
        for event in OBSERVED_EVENTS:
            for name in ['enable', 'filter']:
                path = directory / 'events' / event / name
                values['events/' + event + '/' + name] = io.read(path)
        return values
    result = {'global': one(root), 'other_instances': {}}
    for directory in sorted((root / 'instances').iterdir()):
        if directory.name != exclude and directory.is_dir():
            require(not directory.is_symlink(), 'unexpected instance symlink')
            result['other_instances'][directory.name] = one(directory)
    return result


def counters(directory, io):
    result = {}
    for path in sorted((directory / 'per_cpu').glob('cpu*/stats')):
        values = {}
        for line in io.read(path).splitlines():
            if ':' in line:
                name, value = line.split(':', 1)
                if value.strip().isdigit():
                    values[name.strip()] = int(value)
        require(all(name in values for name in ['overrun', 'commit overrun', 'dropped events']),
                'missing per-CPU trace loss counters')
        result[path.parent.name] = values
    require(result, 'no per-CPU trace statistics')
    return result


def no_loss(before, after):
    require(before.keys() == after.keys(), 'trace CPU inventory changed')
    return all(after[cpu][name] == before[cpu][name]
               for cpu in before for name in ['overrun', 'commit overrun', 'dropped events'])


def validate_buffer_sizing(sizing):
    # Pinned kernel: DIV_ROUND_UP(request, subbuffer payload capacity),
    # then ring_buffer_size() >> 10. Header bytes reduce payload capacity.
    # Thus integer-KiB readback is >= request and < request + subbuffer KiB.
    # Require the Fx0's default 4-KiB subbuffer and equal per-CPU readbacks.
    require(sizing['requested_kib'] == 256, 'unexpected trace buffer request')
    require(sizing['subbuffer_kib_readback'] == '4', 'unexpected trace subbuffer size')
    value = sizing['capacity_kib_readback']
    require(re.fullmatch(r'[0-9]+', value) is not None, 'invalid trace capacity readback')
    require(256 <= int(value) < 260, 'trace capacity outside page-rounding bound')
    cpus = sizing['per_cpu_capacity_kib_readback']
    require(cpus and all(re.fullmatch(r'cpu[0-9]+', cpu) and capacity == value
                         for cpu, capacity in cpus.items()), 'unequal/missing per-CPU trace capacities')


class TraceLease:
    def __init__(self, name, claim, root=ROOT, io=None, fail_after_config=False, callbacks=False):
        require(re.fullmatch(r'fx0-camera-[a-z0-9-]{1,40}', name), 'invalid owned instance name')
        self.root, self.name, self.claim = Path(root), name, Path(claim)
        self.path = self.root / 'instances' / name
        self.io = io or NativeIO()
        self.fail_after_config = fail_after_config
        self.callbacks = callbacks
        self.events = dict(EVENTS, **IRQ_EVENTS) if callbacks else EVENTS
        self.callback_config = None
        self.created = False
        self.cleanup = None
        self.sizing = None

    def _save(self, state):
        private_json(self.claim, {'state': state, 'name': self.name, 'device': self.device,
                                 'inode': self.inode, 'before_settings': self.before, 'buffer_sizing': self.sizing,
                                 'callbacks': self.callbacks, 'callback_config': self.callback_config})

    def _owned(self):
        require(self.created and self.path.is_dir() and not self.path.is_symlink(), 'owned instance missing')
        info = self.path.stat()
        require((info.st_dev, info.st_ino) == (self.device, self.inode), 'owned instance identity changed')

    def _write(self, relative, value):
        self._owned()
        self.io.write(self.path / relative, value)

    def __enter__(self):
        require(not self.path.exists(), 'owned instance already exists; never reuse it')
        require(not self.claim.exists(), 'trace claim already exists')
        require(self.claim.parent.is_dir() and not self.claim.parent.stat().st_mode & 0o077,
                'trace workspace must be private')
        self.before = settings(self.root, self.io)
        try:
            self.io.mkdir(self.path)
            self.created = True
            info = self.path.stat()
            self.device, self.inode = info.st_dev, info.st_ino
            self._save('created; no event enabled yet')
            self._write('tracing_on', '0')
            require(self.io.read(self.path / 'tracing_on') == '0', 'trace did not stop')
            self._write('current_tracer', 'nop')
            require(self.io.read(self.path / 'current_tracer') == 'nop', 'unexpected tracer')
            clocks = self.io.read(self.path / 'trace_clock')
            require('mono' in clocks.replace('[', '').replace(']', '').split(), 'monotonic trace clock unavailable')
            self._write('trace_clock', 'mono')
            require('[mono]' in self.io.read(self.path / 'trace_clock'), 'trace clock did not select mono')
            self._write('buffer_size_kb', '256')
            self.sizing = {
                'requested_kib': 256,
                'subbuffer_kib_readback': self.io.read(self.path / 'buffer_subbuf_size_kb'),
                'capacity_kib_readback': self.io.read(self.path / 'buffer_size_kb'),
                'per_cpu_capacity_kib_readback': {
                    path.parent.name: self.io.read(path)
                    for path in sorted((self.path / 'per_cpu').glob('cpu*/buffer_size_kb'))},
            }
            self._save('sizing captured; no event enabled yet')
            validate_buffer_sizing(self.sizing)
            for event, expression in self.events.items():
                text = self.io.read(self.path / 'events' / event / 'format')
                fields = (['irq', 'name'] if event.endswith('irq_handler_entry') else
                          ['irq', 'ret'] if event.endswith('irq_handler_exit') else
                          ['owner', 'queued_count', 'owned_by_drv_count', 'index', 'type', 'timestamp'])
                require(all(re.search(r'field:[^;]*\b' + field + r';', text) for field in fields),
                        'trace event format differs: ' + event)
                self._write('events/' + event + '/filter', expression)
                require(self.io.read(self.path / 'events' / event / 'filter') == expression, 'trace filter mismatch')
            if self.callbacks:
                self._configure_callbacks()
            if self.fail_after_config:
                raise RuntimeError('injected failure before event enable')
            for event in self.events:
                self._write('events/' + event + '/enable', '1')
                require(self.io.read(self.path / 'events' / event / 'enable') == '1', 'event enable mismatch')
            self._save('configured; stopped')
            return self
        except BaseException:
            if self.created:
                self.close()
            raise

    def _configure_callbacks(self):
        for field in ['set_ftrace_pid', 'set_ftrace_notrace_pid']:
            require(self.io.read(self.path / field) in ('', 'no pid'), 'unexpected own function PID filter')
        excluded = self.io.read(self.path / 'set_ftrace_notrace')
        require(not [line for line in excluded.splitlines() if line and not line.startswith('#')],
                'unexpected own function exclusion')
        selectors = '\n'.join(name + ':mod:qcom_camss' for name in FUNCTION_COUNTS) + '\n'
        self._write('set_ftrace_filter', selectors)
        selected = self.io.read(self.path / 'set_ftrace_filter').splitlines()
        names = []
        for line in selected:
            match = re.fullmatch(r'(vfe_isr(?:_reg_update|_wm_done)?) \[qcom_camss\]', line)
            require(match is not None, 'unexpected function selected')
            names.append(match[1])
        require(dict(Counter(names)) == FUNCTION_COUNTS, 'function selection count differs from pinned r1')
        # These are per-array formatting flags. Never write shared func_* flags.
        for option, value in [('print-parent', '1'), ('sym-offset', '0'), ('sym-addr', '0'), ('context-info', '1')]:
            self._write('options/' + option, value)
            require(self.io.read(self.path / 'options' / option) == value, 'own trace formatting mismatch')
        self._write('current_tracer', 'function')
        require(self.io.read(self.path / 'current_tracer') == 'function', 'function tracer did not select')
        function_flags = {}
        for option in ['func_stack_trace', 'func-no-repeats', 'func-args']:
            path = self.path / 'options' / option
            if path.is_file():
                function_flags[option] = self.io.read(path)
                require(function_flags[option] == '0', 'shared function flag configured; never alter it')
        self.callback_config = {'selected': selected, 'shared_function_flags_read_only': function_flags,
                                'tracer': 'function', 'irq_filter': 95}
        self._save('callbacks configured; stopped')

    def start(self):
        self._write('trace', '')
        self.before_counters = counters(self.path, self.io)
        self._write('tracing_on', '1')
        require(self.io.read(self.path / 'tracing_on') == '1', 'trace did not start')
        self._save('recording')

    def marker(self, label):
        require(re.fullmatch(r'[A-Z0-9_]{1,60}', label), 'invalid trace marker')
        now = time.monotonic_ns()
        self._write('trace_marker', 'FX0_CAMERA ' + label + ' mono_ns=' + str(now) + '\n')
        return now

    def stop_dump(self, destination):
        self._write('tracing_on', '0')
        require(self.io.read(self.path / 'tracing_on') == '0', 'trace did not stop')
        after = counters(self.path, self.io)
        text = self.io.read(self.path / 'trace') + '\n'
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(text)
        result = {'bytes': len(text.encode()), 'SHA256': hashlib.sha256(text.encode()).hexdigest(),
                  'before_counters': self.before_counters, 'after_counters': after,
                  'no_lost_events': no_loss(self.before_counters, after)}
        self._save('stopped; private trace retained')
        return text, result

    def close(self):
        if not self.created:
            return
        self._owned()
        errors = []
        for relative, value in [('tracing_on', '0')] + [('events/' + event + '/enable', '0') for event in self.events] + [('current_tracer', 'nop')]:
            try:
                self._write(relative, value)
            except OSError as error:
                errors.append(type(error).__name__ + ': ' + relative)
        try:
            self.io.rmdir(self.path)
        except OSError as error:
            errors.append(type(error).__name__ + ': remove owned instance')
        unchanged = settings(self.root, self.io, self.name) == self.before
        self.cleanup = {'instance_removed': not self.path.exists(), 'global_and_other_settings_unchanged': unchanged,
                        'errors': errors}
        if not self.path.exists():
            self.created = False
        private_json(self.claim, {'state': 'cleanup finished', 'name': self.name, 'device': self.device,
                                  'inode': self.inode, 'before_settings': self.before, 'buffer_sizing': self.sizing, 'callbacks': self.callbacks,
                                  'callback_config': self.callback_config, 'cleanup': self.cleanup})
        require(self.cleanup['instance_removed'] and unchanged and not errors, 'trace cleanup or configuration preservation failed')

    def __exit__(self, *_exception):
        self.close()


LINE = re.compile(r'\[(?P<cpu>\d+)\]\s+.*?(?P<seconds>\d+)\.(?P<fraction>\d+):\s+(?P<body>.*)$')
EVENT_LINE = re.compile(r'(?:(?:vb2|v4l2|irq):)?(?P<event>[a-zA-Z0-9_]+):\s*(?P<payload>.*)$')
FUNCTION_LINE = re.compile(r'(vfe_isr(?:_reg_update|_wm_done)?)(?: \[qcom_camss\])?\s+<-(?P<caller>[a-zA-Z_][a-zA-Z0-9_.]*)(?: \[[a-zA-Z0-9_]+\])?$')
VB2 = re.compile(r'^owner\s*=\s*([^,]+),\s*queued\s*=\s*(\d+),\s*owned_by_drv\s*=\s*(-?\d+),\s*index\s*=\s*(\d+),\s*type\s*=\s*(\d+),\s*bytesused\s*=\s*(\d+),\s*timestamp\s*=\s*(\d+)$')


def parse_private_trace(text):
    rows = []
    allowed = {name.split('/')[1] for name in dict(EVENTS, **IRQ_EVENTS)}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = LINE.search(line)
        require(match is not None, 'unrecognized trace line ' + str(number))
        seconds, fraction = match.group('seconds', 'fraction')
        body = match['body']
        parsed = EVENT_LINE.fullmatch(body)
        function = FUNCTION_LINE.fullmatch(body) if parsed is None else None
        require(parsed is not None or function is not None, 'unexpected trace payload')
        event = parsed['event'] if parsed else 'function'
        payload = parsed['payload'] if parsed else body
        require(len(fraction) <= 9, 'unexpected trace timestamp precision')
        row = {'trace_ns': int(seconds) * 1_000_000_000 + int(fraction.ljust(9, '0')), 'event': event,
               'trace_resolution_ns': 10 ** (9 - len(fraction)), 'cpu': int(match['cpu']), 'trace_order': number}
        if event == 'function':
            row.update(function=function[1], caller=function['caller'])
        elif event == 'irq_handler_entry':
            entry = re.fullmatch(r'irq=95 name=fda0ac00\.camss_msm_vfe0', payload)
            require(entry is not None, 'unexpected IRQ entry')
            row.update(irq=95, handler='fda0ac00.camss_msm_vfe0')
        elif event == 'irq_handler_exit':
            require(payload == 'irq=95 ret=handled', 'unexpected IRQ exit')
            row.update(irq=95, handled=True)
        elif event == 'tracing_mark_write':
            marker = re.fullmatch(r'FX0_CAMERA ([A-Z0-9_]+) mono_ns=(\d+)', payload)
            require(marker is not None, 'unexpected instance marker')
            row.update(marker=marker[1], marker_mono_ns=int(marker[2]))
        elif event in allowed and event.startswith('vb2_v4l2_'):
            minor = re.search(r'\bminor=(\d+)\b', payload)
            timestamp = re.search(r'\btimestamp\s*=\s*(\d+)\b', payload)
            sequence = re.search(r'\bsequence\s*=\s*(\d+)\b', payload)
            require(minor and timestamp and sequence, 'unexpected V4L2 event payload')
            row.update(minor=int(minor[1]), timestamp_ns=int(timestamp[1]), sequence=int(sequence[1]))
        else:
            require(event in allowed, 'unexpected trace event')
            body = VB2.fullmatch(payload)
            require(body is not None, 'unexpected vb2 event payload')
            owner, queued, owned, index, kind, used, timestamp = body.groups()
            row.update(owner_private=owner.strip(), queued_count=int(queued), owned_by_driver=int(owned),
                       index=int(index), type=int(kind), bytesused=int(used), timestamp_ns=int(timestamp))
        rows.append(row)
    return sorted(rows, key=lambda row: (row['trace_ns'], row['trace_order']))


def verify_markers(rows):
    markers = [row for row in rows if row['event'] == 'tracing_mark_write']
    require(markers, 'trace markers missing')
    for row in markers:
        require(-row['trace_resolution_ns'] <= row['trace_ns'] - row['marker_mono_ns'] <= 100_000_000,
                'trace/monotonic clock mismatch')
    return len(markers)


def recover_claim(claim, root=ROOT, io=None):
    """Recover only an inode-matching instance described by a private owned claim."""
    claim = Path(claim)
    require(not claim.parent.stat().st_mode & 0o077 and not claim.is_symlink(), 'recovery claim must be private')
    record = json.loads(claim.read_text())
    lease = TraceLease(record['name'], claim, root, io, callbacks=record.get('callbacks', False))
    lease.before = record['before_settings']
    lease.sizing = record.get('buffer_sizing')
    lease.callback_config = record.get('callback_config')
    if lease.path.exists():
        lease.device, lease.inode = record['device'], record['inode']
        lease.created = True
        lease.close()
        return lease.cleanup
    unchanged = settings(lease.root, lease.io, lease.name) == lease.before
    require(unchanged, 'trace configuration differs after missing instance')
    return {'instance_removed': True, 'global_and_other_settings_unchanged': True, 'errors': []}
