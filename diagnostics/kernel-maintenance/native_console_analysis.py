# SPDX-License-Identifier: MIT
"""Summarize known kernel console signals without reproducing raw log lines."""
import base64
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT/'manifests/display-handoff-trace-sites.json'
RELEASES = ('6.18.63-fx0-vibrator-alpine', '6.18.63-fx0-handoff-trace-alpine')
SENSITIVE = re.compile(r'command line|cmdline|password|credential|PRIVATE KEY|ssh-|serialno=', re.I)


def summarize(body, *, full_record=True):
    text = body.decode('utf-8', errors='replace')
    catalog = json.loads(CATALOG.read_text())
    counts = {site['id']: 0 for site in catalog['sites']}
    events, releases, last_time, faults, panics, checks, armed = [], set(), None, 0, 0, 0, 0
    ignored = 0
    patterns = []
    for site in catalog['sites']:
        fmt = site['format'].rstrip('\n')
        chunks = re.split(r'(%[du])', fmt)
        expression = ''.join(r'(-?\d{1,10})' if part == '%d' else r'(\d{1,10})' if part == '%u'
                             else re.escape(part) for part in chunks)
        patterns.append((site['id'], re.compile(expression + r'(?=\s|$)'),
                         [part for part in chunks if part in ('%d', '%u')]))
    for line in text.splitlines():
        if SENSITIVE.search(line):
            ignored += 1
            continue
        stamp = re.search(r'\[\s*([0-9]{1,9}(?:\.[0-9]{1,9})?)\]', line)
        timestamp = float(stamp.group(1)) if stamp else None
        if timestamp is not None:
            last_time = timestamp
        for release in RELEASES:
            if re.search(r'Linux version ' + re.escape(release) + r'(?=\s|$)', line):
                releases.add(release)
        faults += bool(re.search(r'Unhandled context fault:', line))
        panics += bool(re.search(r'Kernel panic(?: - not syncing)?:', line))
        checks += bool(re.search(r'FX0_NATIVE_RETURN_CHECK status=0(?=\s|$)', line))
        armed += bool(re.search(r'FX0_NATIVE_RETURN_ARMED PID=[0-9]+(?=\s|$)', line))
        matches = []
        for site_id, pattern, types in patterns:
            for match in pattern.finditer(line):
                values = list(map(int, match.groups()))
                if not all((-2**31 <= value < 2**31) if kind == '%d' else
                           (0 <= value < 2**32) for kind, value in zip(types, values)):
                    continue
                matches.append((match.start(), site_id))
        for _, site_id in sorted(matches):
            counts[site_id] += 1
            if len(events) < 512:
                events.append({'site': site_id, 'seconds': timestamp})
    return {'full_record': full_record, 'bytes': len(body),
            'SHA256': hashlib.sha256(body).hexdigest(),
            'recognized_kernel_releases': sorted(releases), 'last_timestamp_seconds': last_time,
            'known_trace_counts': counts, 'known_trace_events': events,
            'event_list_limit': 512, 'context_fault_messages': faults, 'panic_messages': panics,
            'return_helper_check_messages': checks, 'return_helper_armed_messages': armed,
            'sensitive_lines_omitted_from_analysis': ignored,
            'raw_lines_included': False, 'missing_trace_is_inconclusive': True,
            'release_banner_is_not_exact_image_identity': True,
            'candidate_boot_attribution_proven': False, 'reset_cause_proven': False}


def compare(before, after):
    """Digest changes describe records, not a proven candidate boot or cause."""
    records = {}
    for path in sorted(set(before['records']) | set(after['records'])):
        old, new = before['records'].get(path), after['records'].get(path)
        valid_old = old and old['state'] == 'captured' and old.get('stable') is True
        valid_new = new and new['state'] == 'captured' and new.get('stable') is True
        if valid_old and valid_new:
            change = 'unchanged' if old['SHA256'] == new['SHA256'] else 'changed'
        elif valid_new and old and old['state'] == 'missing':
            change = 'new-record'
        elif valid_old and new and new['state'] == 'missing':
            change = 'record-disappeared'
        elif old and new and old['state'] == new['state'] == 'missing':
            change = 'missing-both'
        else:
            change = 'inconclusive'
        row = {'change': change}
        if valid_new:
            body = base64.b64decode(new['content_base64'], validate=True)
            if len(body) != new['bytes'] or hashlib.sha256(body).hexdigest() != new['SHA256']:
                raise ValueError('Console body differs from captured digest')
            row['analysis'] = summarize(body)
        records[path] = row
    return {'records': records, 'same_native_boot': before['boot_id'] == after['boot_id'],
            'changed_record_is_not_candidate_boot_proof': True,
            'candidate_boot_attribution_proven': False, 'reset_cause_proven': False,
            'raw_console_or_command_lines_included': False}
