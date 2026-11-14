#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise debug setting ownership, real flock exclusion, restoration and recovery."""
import importlib.util
import json
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location('irq_debug', Path(__file__).with_name('irq_debug.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def body(flags='_', extra=''):
    return '# filename:lineno [module]function flags format\n' + module.PREFIX + 'vfe_isr =' + flags + ' ' + module.FORMAT + '\nother.c:7 [other]fn =_ "unrelated"\n' + extra


class ModelIO(module.NativeIO):
    def __init__(self, condition='normal'):
        self.condition, self.commands = condition, []

    def write(self, path, value):
        self.commands.append(value)
        assert value in [module.SELECTOR + ' +p\n', module.SELECTOR + ' -p\n']
        if value.endswith('+p\n') and self.condition == 'fail-before':
            raise OSError('injected write failure before change')
        text = path.read_text()
        old, new = ('=_ ', '=p ') if value.endswith('+p\n') else ('=p ', '=_ ')
        lines = [line.replace(old, new) if line.startswith(module.PREFIX) else line for line in text.splitlines()]
        path.write_text('\n'.join(lines) + '\n')
        if value.endswith('+p\n') and self.condition == 'fail-after':
            raise OSError('injected write failure after change')


cases = []
for condition in ['normal', 'body-exception', 'fail-before', 'fail-after']:
    with tempfile.TemporaryDirectory(prefix='fx0-debug-lease-') as tmp:
        root = Path(tmp);control = root / 'control';control.write_text(body())
        io = ModelIO(condition);before = module.snapshot(control, io)
        lease = module.DebugLease(root / 'claim.json', control, root / 'lock', io)
        try:
            with lease:
                assert module.snapshot(control, io)['target_flags'] == 'p'
                if condition == 'body-exception':raise RuntimeError('injected body failure')
        except (RuntimeError, OSError):
            assert condition != 'normal'
        else:assert condition == 'normal'
        assert module.snapshot(control, io) == before
        assert lease.cleanup['target_disabled'] and lease.cleanup['all_debug_settings_unchanged']
        assert lease.fd is None
        cases.append(condition + ': exact restoration and lock released')

for condition in ['already-enabled', 'extra-flags', 'duplicate', 'missing', 'metadata']:
    with tempfile.TemporaryDirectory(prefix='fx0-debug-reject-') as tmp:
        root=Path(tmp);control=root/'control';text=body()
        if condition=='already-enabled':text=body('p')
        elif condition=='extra-flags':text=body('f')
        elif condition=='duplicate':text=body(extra=module.PREFIX+'vfe_isr =_ '+module.FORMAT+'\n')
        elif condition=='missing':text=text.replace(':903 ',':904 ')
        else:text=text.replace('status0 =','status_other =')
        control.write_text(text);io=ModelIO()
        try:
            with module.DebugLease(root/'claim.json',control,root/'lock',io):raise AssertionError('bad entry accepted')
        except ValueError:pass
        assert control.read_text()==text and not io.commands
        assert not (root/'claim.json').exists()
        cases.append(condition+' rejected before writes')

with tempfile.TemporaryDirectory(prefix='fx0-debug-exclusive-') as tmp:
    root=Path(tmp);control=root/'control';control.write_text(body());io=ModelIO()
    with module.DebugLease(root/'first.json',control,root/'lock',io):
        try:
            with module.DebugLease(root/'second.json',control,root/'lock',io):raise AssertionError('second owner entered')
        except BlockingIOError:pass
        assert len(io.commands)==1 and not (root/'second.json').exists()
    cases.append('real flock excludes a second lease without writes')

with tempfile.TemporaryDirectory(prefix='fx0-debug-recover-') as tmp:
    root=Path(tmp);control=root/'control';control.write_text(body());io=ModelIO()
    lease=module.DebugLease(root/'claim.json',control,root/'lock',io);lease.__enter__();lease._unlock()
    record=json.loads(lease.claim.read_text());bad=record|{'inode':record['inode']+1}
    module.private_json(lease.claim,bad)
    try:module.recover_debug(lease.claim,control,root/'lock',io)
    except ValueError:pass
    else:raise AssertionError('changed inode accepted')
    assert module.snapshot(control,io)['target_flags']=='p' and len(io.commands)==1
    module.private_json(lease.claim,record)
    result=module.recover_debug(lease.claim,control,root/'lock',io)
    assert result['target_disabled'] and result['all_debug_settings_unchanged']
    assert module.recover_debug(lease.claim,control,root/'lock',io)==result
    cases.append('inode-guarded abandoned recovery; mismatched inode rejected; closed recovery idempotent')

with tempfile.TemporaryDirectory(prefix='fx0-debug-other-') as tmp:
    root=Path(tmp);control=root/'control';control.write_text(body());io=ModelIO()
    lease=module.DebugLease(root/'claim.json',control,root/'lock',io);lease.__enter__()
    control.write_text(control.read_text().replace('[other]fn =_','[other]fn =p'))
    try:lease.close()
    except ValueError:pass
    else:raise AssertionError('changed other site accepted')
    assert module.snapshot(control,io)['target_flags']=='_' and '[other]fn =p' in control.read_text()
    assert lease.cleanup=={'target_disabled':True,'all_debug_settings_unchanged':False} and lease.fd is None
    cases.append('external other-site change detected after restoring owned flag, never overwritten')

with tempfile.TemporaryDirectory(prefix='fx0-debug-flags-') as tmp:
    root=Path(tmp);control=root/'control';control.write_text(body());io=ModelIO()
    lease=module.DebugLease(root/'claim.json',control,root/'lock',io);lease.__enter__()
    control.write_text(control.read_text().replace('vfe_isr =p','vfe_isr =pf'))
    try:lease.close()
    except ValueError:pass
    else:raise AssertionError('external target flags accepted')
    assert 'vfe_isr =pf' in control.read_text() and len(io.commands)==1 and lease.fd is None
    cases.append('external target flag ownership change rejected without overwrite')
print(json.dumps({'debug_lease_cases':len(cases),'cases':cases,'real_kernel_settings_modified':False},indent=2))
