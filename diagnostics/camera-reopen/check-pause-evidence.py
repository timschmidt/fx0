#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check pause-window correlation without assuming that an IRQ cause is proven."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('pause_camera', Path(__file__).with_name('pause-queue-test.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
events = [{'name': name, 'monotonic_ns': value * 1000} for name, value in [
    ('pause_request', 1100), ('pause_acknowledged', 1200), ('resume_request', 1450), ('resume_acknowledged', 1500)]]
frames = [{'timestamp_ns': value * 1000, 'sequence': i} for i, value in enumerate([1000, 1300, 1600])]
cases = []
for when, expected in [
    (1050, 'before pause request'), (1150, 'stop acknowledgement pending'),
    (1350, 'client confirmed stopped'), (1475, 'resume acknowledgement pending'),
    (1550, 'after resume acknowledged'),
]:
    row = {'monotonic_usec': when, 'priority': 3, 'message': 'qcom-camss: Missing ready buf 1 4!'}
    actual = worker.correlate_pause(row, frames, 1700 * 1000, events)
    assert actual['client_pause_phase'] == expected
    assert actual['phase'] == 'between delivered buffers'
    cases.append(expected)
row = {'monotonic_usec': 1350, 'priority': 3, 'message': 'qcom-camss: diagnostic'}
assert worker.correlate_pause(row, frames, 1700 * 1000, events[:2])['client_pause_phase'] == 'pause timing incomplete'
cases.append('incomplete pause acknowledgement evidence stays incomplete')
assert worker.correlate_pause(row, frames, 1700 * 1000,
                              [{'name': 'unpaused_control', 'monotonic_ns': 1200 * 1000}])['client_pause_phase'] == 'unpaused control'
cases.append('unpaused control is distinct')
print(json.dumps({'pause_evidence_cases': len(cases), 'cases': cases, 'hardware_access': False}, indent=2))
