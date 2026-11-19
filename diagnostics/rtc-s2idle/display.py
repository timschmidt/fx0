#!/usr/bin/env python3
"""Check DRM vblank and RMI4 recovery during RTC-backed Fx0 system sleep."""
import argparse
import json
from pathlib import Path
import runpy
import signal


CYCLES = 3
TRACE_RETURNS = ('rmi_driver_suspend', 'rmi_driver_resume', 'rmi_i2c_panel_prepared')


def measure(rtc, display, boot_id, release, token, notes, report):
    rtc['guard'](boot_id, release, token, notes)
    before = display['preflight']()
    socket = display['display_session']()
    mode = before['sway']['current_mode']
    assert before['rtc_clear'] and mode and before['suspend'] == {'success': '0', 'fail': '0'}
    crtc = display['wait_for'](socket, True, mode)
    report['baseline_vblank_increment'] = display['vblank'](crtc)
    for _ in range(CYCLES):
        cycle = {}
        report['cycles'].append(cycle)
        with display['capture']() as (instance, unavailable):
            cycle['unavailable_probes'] = unavailable
            assert not unavailable, 'RMI4 tracing was unavailable before suspend'
            saved = rtc['probe'](boot_id, release, token, notes)
            cycle['rtc'] = saved
            assert saved['passed'] and saved['cleared_alarm']
            if 'trace' in saved:
                trace = saved['trace']
                assert trace['complete_s2idle_intervals'] == 1
                assert trace['wake_irqs_in_s2idle'] == [saved['before']['rtc_irq']]
            cycle['recovered_CRTC'] = display['wait_for'](socket, True, mode)
            assert cycle['recovered_CRTC'] == crtc
            cycle['vblank_increment'] = display['vblank'](crtc)
            cycle['RMI4_returns'] = display['trace_results'](instance)
            assert cycle['RMI4_returns'] == {key: [0] for key in TRACE_RETURNS}
        cycle['trace_cleanup_verified'] = (not instance.exists() and display['NAME'] not in
            display['read'](display['TRACE'] / 'kprobe_events'))
        assert cycle['trace_cleanup_verified']
        assert display['filters']() == before['processes']
    after = display['preflight']()
    assert after['suspend'] == {'success': str(CYCLES), 'fail': '0'} and after['rtc_clear']
    assert after['sway'] == before['sway'] and after['drm'] == before['drm']
    assert after['processes'] == before['processes']
    report.update(passed=True, cleared_alarm=True, same_session=True,
                  suspend_counts=after['suspend'], mode=mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('boot_id')
    parser.add_argument('release')
    parser.add_argument('token')
    parser.add_argument('notes_sha256')
    parser.add_argument('--rtc-probe', type=Path, default=Path(__file__).with_name('probe.py'))
    parser.add_argument('--display-probe', type=Path, default=Path(__file__).parent.parent /
                        'sxmo-fx0-profile/check-display-power.py')
    args = parser.parse_args()
    if not __debug__:
        parser.error('run with Python assertions enabled')
    rtc = runpy.run_path(str(args.rtc_probe))
    display = runpy.run_path(str(args.display_probe), init_globals={
        'EXPECTED_BOOT': args.boot_id, 'NOTES_SHA256': args.notes_sha256})
    signal.signal(signal.SIGTERM, rtc['interrupted'])
    report = dict(passed=False, boot_id=args.boot_id, cycles=[])
    try:
        measure(rtc, display, args.boot_id, args.release, args.token, args.notes_sha256, report)
    except Exception as error:
        report.update(error=type(error).__name__, detail=str(error).splitlines()[0][:120] if str(error) else '')
    print('FX0_S2IDLE_DISPLAY ' + json.dumps(report), flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
