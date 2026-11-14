#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check lease ownership/failure paths with a tracefs model and the real parser."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time

spec = importlib.util.spec_from_file_location('queue_trace', Path(__file__).with_name('queue_trace.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def populate(path):
    for name, text in {'tracing_on': '1', 'current_tracer': 'nop', 'trace_clock': '[local] mono boot',
                       'buffer_subbuf_size_kb': '4', 'buffer_size_kb': '1408', 'trace': '# tracer: nop\n', 'trace_marker': ''}.items():
        (path / name).write_text(text)
    for event in module.OBSERVED_EVENTS:
        folder = path / 'events' / event
        folder.mkdir(parents=True)
        (folder / 'enable').write_text('0')
        (folder / 'filter').write_text('none')
        names = ['minor', 'timestamp', 'sequence'] if event.startswith('v4l2/') else [
            'owner', 'queued_count', 'owned_by_drv_count', 'index', 'type', 'timestamp']
        (folder / 'format').write_text('\n'.join('field:int ' + name + ';' for name in names))
    stats = path / 'per_cpu/cpu0'
    stats.mkdir(parents=True)
    (stats / 'buffer_size_kb').write_text('1408')
    (stats / 'stats').write_text('entries: 0\noverrun: 0\ncommit overrun: 0\ndropped events: 0\n')


class ModelIO(module.NativeIO):
    def __init__(self, fail=None, capacity=None, cpu_capacity=None):
        self.fail = fail
        self.capacity = capacity
        self.cpu_capacity = cpu_capacity
        self.event_enables = 0

    def mkdir(self, path):
        path.mkdir()
        populate(path)

    def rmdir(self, path):
        shutil.rmtree(path)  # Model virtual files disappear when the instance is removed.

    def write(self, path, value):
        if path.name == 'enable' and value == '1':
            self.event_enables += 1
        if self.fail and path.as_posix().endswith(self.fail) and value == '1':
            raise OSError('injected event enable failure')
        if path.name == 'trace_clock':
            path.write_text('local [' + value + '] boot')
        elif path.name == 'buffer_size_kb':
            # Model ARM page payload, not ordinary-file echo of the request.
            capacity = 4096 - 16
            rounded = ((int(value) * 1024 + capacity - 1) // capacity * capacity) // 1024
            text = self.capacity if self.capacity is not None else str(rounded)
            path.write_text(text)
            (path.parent / 'per_cpu/cpu0/buffer_size_kb').write_text(
                self.cpu_capacity if self.cpu_capacity is not None else text)
        elif path.name == 'trace_marker':
            now = time.monotonic_ns()
            with (path.parent / 'trace').open('a') as stream:
                stream.write(f'worker-1 [000] .... {now // 1_000_000_000}.{now % 1_000_000_000:09d}: tracing_mark_write: {value}')
        else:
            path.write_text(value)


cases = []
for condition in ['success', 'setup-failure', 'enable-failure', 'body-failure', 'loss']:
    with tempfile.TemporaryDirectory(prefix='fx0-trace-model-') as tmp:
        root = Path(tmp)
        populate(root)
        (root / 'instances').mkdir()
        other = root / 'instances/other-trace'
        other.mkdir()
        populate(other)
        workspace = root / 'private'
        workspace.mkdir(mode=0o700)
        io = ModelIO(fail='vb2_buf_queue/enable' if condition == 'enable-failure' else None)
        before = module.settings(root, io)
        lease = module.TraceLease('fx0-camera-model', workspace / 'claim.json', root, io,
                                  fail_after_config=condition == 'setup-failure')
        try:
            with lease:
                lease.start()
                lease.marker('CLOCK_PROBE')
                if condition == 'body-failure':
                    raise RuntimeError('injected body failure')
                if condition == 'loss':
                    (lease.path / 'per_cpu/cpu0/stats').write_text('overrun: 1\ncommit overrun: 0\ndropped events: 0\n')
                text, result = lease.stop_dump(workspace / 'private.trace')
                rows = module.parse_private_trace(text)
                assert module.verify_markers(rows) == 1
                assert result['no_lost_events'] is (condition != 'loss')
                assert (workspace / 'private.trace').stat().st_mode & 0o077 == 0
        except (RuntimeError, OSError):
            assert condition in ['setup-failure', 'enable-failure', 'body-failure']
        else:
            assert condition in ['success', 'loss']
        assert not lease.path.exists() and module.settings(root, io) == before
        assert lease.cleanup['instance_removed'] and lease.cleanup['global_and_other_settings_unchanged']
        cases.append(condition + ': owned instance removed; other/global settings preserved')

for capacity, cpu_capacity, accepted in [
        ('256', None, True), ('257', None, True), ('258', None, True), ('259', None, True),
        ('255', None, False), ('260', None, False), ('X', None, False),
        ('258 (expanded: 1408)', None, False), ('258', '259', False)]:
    with tempfile.TemporaryDirectory(prefix='fx0-trace-sizing-') as tmp:
        root = Path(tmp)
        populate(root)
        (root / 'instances').mkdir()
        workspace = root / 'private'
        workspace.mkdir(mode=0o700)
        io = ModelIO(capacity=capacity, cpu_capacity=cpu_capacity)
        before = module.settings(root, io)
        lease = module.TraceLease('fx0-camera-sizing', workspace / 'claim.json', root, io)
        try:
            with lease:
                assert accepted
        except ValueError:
            assert not accepted
            assert io.event_enables == 0
        else:
            assert accepted
        assert not lease.path.exists() and module.settings(root, io) == before
        claim = json.loads(lease.claim.read_text())
        assert claim['buffer_sizing']['capacity_kib_readback'] == capacity
        cases.append('buffer rounding/readback: ' + repr((capacity, cpu_capacity, accepted)))

with tempfile.TemporaryDirectory(prefix='fx0-trace-collision-') as tmp:
    root = Path(tmp)
    populate(root)
    (root / 'instances').mkdir()
    existing = root / 'instances/fx0-camera-existing'
    existing.mkdir()
    populate(existing)
    workspace = root / 'private'
    workspace.mkdir(mode=0o700)
    before = module.settings(root, ModelIO())
    try:
        with module.TraceLease('fx0-camera-existing', workspace / 'claim.json', root, ModelIO()):
            raise AssertionError('existing instance entered')
    except ValueError:
        pass
    assert existing.is_dir() and module.settings(root, ModelIO()) == before
    cases.append('existing instance rejected without writes/removal')

for name in ['../global', '/absolute', 'fx0-camera-../escape', 'unowned-name']:
    try:
        module.TraceLease(name, Path('/tmp/not-created'))
    except ValueError:
        cases.append('invalid name rejected: ' + name)
    else:
        raise AssertionError('invalid name accepted')

with tempfile.TemporaryDirectory(prefix='fx0-trace-recovery-') as tmp:
    root = Path(tmp)
    populate(root)
    (root / 'instances').mkdir()
    workspace = root / 'private'
    workspace.mkdir(mode=0o700)
    io = ModelIO()
    lease = module.TraceLease('fx0-camera-recovery', workspace / 'claim.json', root, io)
    lease.__enter__()
    record = json.loads(lease.claim.read_text())
    bad = record | {'inode': record['inode'] + 1}
    module.private_json(lease.claim, bad)
    try:
        module.recover_claim(lease.claim, root, io)
    except ValueError:
        pass
    else:
        raise AssertionError('wrong recovery inode accepted')
    assert lease.path.is_dir()
    module.private_json(lease.claim, record)
    result = module.recover_claim(lease.claim, root, io)
    assert result['instance_removed'] and result['global_and_other_settings_unchanged']
    cases.append('abandoned owned lease recovered; mismatched inode rejected untouched')

text = '''# tracer: nop
cam-7 [001] .... 12.000001: vb2_buf_queue: owner = deadbeef, queued = 4, owned_by_drv = 1, index = 0, type = 9, bytesused = 10, timestamp = 12000000000
<idle>-0 [001] .... 12.033334: vb2_buf_done: owner = deadbeef, queued = 4, owned_by_drv = 0, index = 0, type = 9, bytesused = 10, timestamp = 12033333000
worker-1 [000] .... 12.040000: tracing_mark_write: FX0_CAMERA CLOCK_PROBE mono_ns=12040000123
'''
rows = module.parse_private_trace(text)
assert rows[0]['owned_by_driver'] == 1 and rows[1]['owned_by_driver'] == 0
assert module.verify_markers(rows) == 1
cases.append('queue/done/marker parsing and microsecond rounding')
for bad in [text.replace('owned_by_drv = 1', 'owned_by_drv = bad'), text + 'CPU 0: LOST EVENTS\n',
            text.replace('vb2_buf_done:', 'unknown_event:'), text.replace('mono_ns=12040000123', 'mono_ns=99999999999')]:
    try:
        module.verify_markers(module.parse_private_trace(bad))
    except ValueError:
        cases.append('malformed/unknown/lost/clock-mismatch evidence rejected')
    else:
        raise AssertionError('bad trace evidence accepted')
print(json.dumps({'trace_lease_model_and_parser_cases': len(cases), 'cases': cases,
                  'real_kernel_tracefs_modified': False, 'native_lifecycle_still_required': True}, indent=2))
