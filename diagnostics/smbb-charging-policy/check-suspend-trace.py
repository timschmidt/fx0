"""Verify the PM8226 register ordering in a captured RTC suspend trace."""
import re


CHARGE_CTRL = 0x1049
BTC_CTRL = 0x1249
ADC_CHANNEL = 0x3148
ADC_RESULT = 0x3160
BAT_TEMP_STATUS = 0x1209
USB_STATUS = 0x1310
CONTROL_AND_ADC = (CHARGE_CTRL, BTC_CTRL, ADC_CHANNEL, ADC_RESULT)
REGISTERS = CONTROL_AND_ADC + (BAT_TEMP_STATUS, USB_STATUS)
MASKS = {CHARGE_CTRL: 0x81, BTC_CTRL: 0x83}


def decode(raw):
    count = re.search(r'entries-in-buffer/entries-written:\s*(\d+)/(\d+)', raw)
    assert count and count[1] == count[2], 'lost trace entries'
    markers = {}
    transfers = []
    pending = {}
    for index, line in enumerate(raw.splitlines()):
        mark = re.search(r': (suspend_resume: machine_suspend\[1\] (?:begin|end)|smbb_pm_(?:suspend|resume)_(?:enter|exit):)(.*)', line)
        if mark:
            name, rest = mark.groups()
            if name.endswith('_exit:'):
                assert 'result=0' in rest.split(), 'charger callback returned an error'
            assert name not in markers, f'duplicate {name}'
            markers[name] = index
        match = re.search(r'-(\d+)\s+\[.*: spmi_(write_begin|write_end|read_end): .* sid=00 addr=0x([0-9a-f]+)\b(.*)', line)
        if not match:
            assert ': spmi_' not in line, 'unparsed SPMI transfer'
            continue
        pid, kind, address, fields = match.groups()
        pid, address = int(pid), int(address, 16)
        assert address in REGISTERS
        key = pid, address
        if kind == 'write_end':
            start, data = pending.pop(key)
        else:
            payload = re.search(r'len=(\d+) buf=0x\[([0-9a-f-]+)\]', fields)
            assert payload, 'invalid SPMI payload'
            data = bytes.fromhex(payload[2].replace('-', ' '))
            assert len(data) == int(payload[1])
            if kind == 'write_begin':
                assert key not in pending
                pending[key] = index, data
                continue
            start = index
        assert 'ret=0' in fields.split(), 'SPMI transaction failed'
        transfers.append(dict(start=start, end=index, pid=pid, address=address,
                              write=kind == 'write_end', data=list(data)))
    assert not pending, 'incomplete SPMI write'
    return markers, transfers


def value(event):
    assert len(event['data']) == 1
    return event['data'][0] & MASKS.get(event['address'], 0xff)


def matching(events, address, expected, write, start=-1):
    for event in events:
        if (event['address'] == address and event['write'] == write and event['start'] > start
                and value(event) == expected):
            return event
    raise AssertionError(f'missing {"write" if write else "readback"} {address:#x}={expected:#x}')


def readback(events, action):
    return matching([event for event in events if event['pid'] == action['pid']],
                    action['address'], value(action), False, action['end'])


def verify(raw, user_inhibit):
    marks, events = decode(raw)
    names = ('smbb_pm_suspend_enter:', 'smbb_pm_suspend_exit:',
             'suspend_resume: machine_suspend[1] begin', 'suspend_resume: machine_suspend[1] end',
             'smbb_pm_resume_enter:', 'smbb_pm_resume_exit:')
    missing = set(names) - marks.keys()
    assert not missing, 'missing suspend or charger callback markers: ' + ', '.join(sorted(missing))
    positions = [marks[name] for name in names]
    assert positions == sorted(positions)
    suspend, suspended, start, end, resume, _ = positions
    controls = [event for event in events if event['address'] in MASKS]
    assert all(not value(event) & 1 for event in controls if event['address'] == CHARGE_CTRL)
    assert all(value(event) & 0x80 for event in controls if event['address'] == BTC_CTRL)
    assert not any(event['write'] and event['start'] < end and event['end'] > start for event in controls)
    quiesce = [event for event in controls if event['start'] > suspend and event['end'] < suspended]
    disabled = matching(quiesce, CHARGE_CTRL, 0, True)
    verified_disable = readback(quiesce, disabled)
    if user_inhibit:
        conservative_verified = matching(quiesce, BTC_CTRL, 0x81, False, verified_disable['end'])
    else:
        conservative = matching(quiesce, BTC_CTRL, 0x81, True, verified_disable['end'])
        conservative_verified = readback(quiesce, conservative)
    still_disabled = [event for event in controls if event['write'] and event['start'] > disabled['end']
                      and event['end'] < start and event['address'] == CHARGE_CTRL]
    assert all(value(event) == 0 for event in still_disabled)
    still_conservative = [event for event in controls if event['write'] and event['address'] == BTC_CTRL
                          and conservative_verified['end'] < event['start'] < end]
    assert all(value(event) == 0x81 for event in still_conservative)
    after = [event for event in events if event['start'] > end]
    enables = [event for event in after if event['address'] == CHARGE_CTRL and event['write'] and value(event) == 0x80]
    samples = []
    if user_inhibit:
        assert not enables
        assert all(value(event) == (0 if event['address'] == CHARGE_CTRL else 0x81) for event in controls)
        repeated_disable = matching(after, CHARGE_CTRL, 0, True, resume)
        readback(after, repeated_disable)
    else:
        assert enables and enables[0]['start'] > resume
        enabled = enables[0]
        worker = [event for event in after if event['pid'] == enabled['pid'] and event['end'] < enabled['start']]
        previous = resume
        for channel in (0x30, 0x06):
            selected = matching(worker, ADC_CHANNEL, channel, True, previous)
            sample = next((event for event in worker if event['address'] == ADC_RESULT and not event['write']
                           and len(event['data']) == 2 and event['start'] > selected['end']), None)
            assert sample, f'missing fresh VADC result for channel {channel:#x}'
            samples.append(dict(channel=channel, conversion=sample['data']))
            previous = sample['end']
        stock = matching(worker, BTC_CTRL, 0x82, True, previous)
        readback(worker, stock)
        readback(after, enabled)
    return dict(suspend_inhibit_and_readback=True, control_writes_during_sleep=0,
                enable_writes_after_wake=len(enables), post_wake_ADC_before_enable=samples,
                control_and_VADC_transfers=sum(event['address'] in CONTROL_AND_ADC for event in events),
                lost_trace_entries=0)


def verify_prepared(raw):
    markers, events = decode(raw)
    charge, btc = CHARGE_CTRL, BTC_CTRL
    annotated = {}
    samples = []
    for index, line in enumerate(raw.splitlines()):
        marker = re.search(r'tracing_mark_write: fx0_charge_sleep_(prepare|quiet|release)\b', line)
        if marker:
            assert marker[1] not in annotated, 'duplicate preparation marker'
            annotated[marker[1]] = index
        worker = re.search(r'-(\d+)\s+\[.*: prepared_sample_start:', line)
        if worker:
            samples.append((int(worker[1]), index))
    start, quiet, release = (annotated[name] for name in ('prepare', 'quiet', 'release'))
    enter, asleep, slept, resume, resumed = (markers[name] for name in (
        'smbb_pm_suspend_enter:', 'suspend_resume: machine_suspend[1] begin',
        'suspend_resume: machine_suspend[1] end', 'smbb_pm_resume_enter:', 'smbb_pm_resume_exit:'))
    end = markers['smbb_pm_suspend_exit:']
    assert start < quiet < enter < end < asleep < slept < resume < resumed < release
    controls = [event for event in events if event['address'] in (charge, btc)]
    assert all(not value(event) & 1 for event in controls if event['address'] == charge)
    assert all(value(event) & 0x80 for event in controls if event['address'] == btc)
    prep = [event for event in controls if start < event['start'] and event['end'] < quiet]
    disabled = matching(prep, charge, 0, True)
    check = readback(prep, disabled)
    narrowed = matching(prep, btc, 0x81, True, check['end'])
    window = readback(prep, narrowed)
    while_held = [event for event in controls if window['end'] < event['start'] < release]
    assert all(value(event) == (0 if event['address'] == charge else 0x81) for event in while_held)
    assert not any(event['write'] and event['start'] < slept and event['end'] > asleep for event in controls)
    inside_suspend = [event for event in controls if enter < event['start'] and event['end'] < end]
    quiesce = readback(inside_suspend, matching(inside_suspend, charge, 0, True))
    matching(inside_suspend, btc, 0x81, False, quiesce['end'])
    enables = [event for event in controls if event['write'] and event['address'] == charge
               and value(event) == 0x80 and event['start'] > disabled['end']]
    assert enables and all(release < event['start'] for event in enables)
    enabled = enables[0]
    readback(controls, enabled)
    opened = matching(controls, btc, 0x82, True, release)
    assert readback(controls, opened)['end'] < enabled['start']
    pid, worker_start = next((pid, index) for pid, index in samples if resume < index < release)
    transactions = [event for event in events if event['pid'] == pid and
                    worker_start < event['start'] and event['end'] < release]
    before = worker_start
    measured = []
    for channel in (0x30, 0x06):
        select = matching(transactions, ADC_CHANNEL, channel, True, before)
        reading = next((event for event in transactions if event['address'] == ADC_RESULT
                        and not event['write'] and event['start'] > select['end'] and len(event['data']) == 2), None)
        assert reading, f'missing wake conversion for channel {channel:#x}'
        measured.append(dict(channel=channel, conversion=reading['data']))
        before = reading['end']
    return dict(inhibit_verified_before_RTC_entry=True, conservative_window_verified=True,
                charge_enable_before_release=False, control_writes_during_sleep=0,
                ADC_results_from_resume_worker_before_release=measured,
                automatic_charge_enable_readback_verified=True, trace_lost=0)


def main():
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--user-inhibit', action='store_true')
    mode.add_argument('--prepared', action='store_true')
    args = parser.parse_args()
    if not __debug__:
        parser.error('run with Python assertions enabled')
    raw = args.trace.read_text()
    result = verify_prepared(raw) if args.prepared else verify(raw, args.user_inhibit)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
