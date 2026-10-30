#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Model qcom_wcnss regulator selection from the real driver tables.

Extracts every wcnss_data table and the wcnss_init_regulators() branch
condition from a Linux tree, then evaluates which supplies are requested
for zero, one and two attached power domains. The expected result is
that every supply not represented by an attached power domain is
requested, and that the table is never indexed out of bounds.
"""
import re
import sys
from pathlib import Path

source = (Path(sys.argv[1]) / 'drivers/remoteproc/qcom_wcnss.c').read_text()

tables = {}
for name, body in re.findall(r'static const struct wcnss_data (\w+) = \{(.*?)\n\};', source, re.S):
    pd_names = re.findall(r'"(\w+)"', (re.search(r'\.pd_names = \{([^}]*)\}', body) or [None, ''])[1])
    vregs = re.findall(r'\{ *"(\w+)"', (re.search(r'\.vregs = .*?\{(.*?)\n\t\},', body, re.S) or [None, ''])[1])
    num_vregs = int(re.search(r'\.num_vregs = (\d+)', body)[1])
    m = re.search(r'\.num_pd_vregs = (\d+)', body)
    tables[name] = (pd_names, vregs, num_vregs, int(m[1]) if m else 0)
assert {'riva_data', 'pronto_v1_data', 'pronto_v2_data', 'pronto_v3_data'} <= set(tables), tables

function = re.search(r'static int wcnss_init_regulators\(.*?\n\}', source, re.S)[0]
condition = re.search(r'\tif \((.*?)\) \{\n\t\t/\* Do nothing', function)[1]
known = {'possible_pds >= num_vregs': 'old', '!data->num_pd_vregs': 'new'}
assert condition in known, condition


def select(pd_names, vregs, num_vregs, num_pd_vregs, num_pds, rule):
    possible_pds = len(pd_names)
    offset, count = 0, num_vregs
    skip = possible_pds >= num_vregs if rule == 'old' else not num_pd_vregs
    if skip:
        pass
    elif num_pds:
        offset = num_pds
        if num_pds < num_pd_vregs:
            count += num_pd_vregs - num_pds
    else:
        count += num_pd_vregs
    if offset + count > len(vregs):
        return None
    return vregs[offset:offset + count]


def expected(pd_names, vregs, num_pd_vregs, num_pds):
    # Table PD regulators are named vdd<pd>; attached domains replace them.
    attached = {'vdd' + pd for pd in pd_names[:num_pds]} if num_pd_vregs else set()
    return [v for v in vregs if v not in attached]


failures = 0
cases = 0
for name, (pd_names, vregs, num_vregs, num_pd_vregs) in sorted(tables.items()):
    assert len(vregs) == num_vregs + num_pd_vregs, name
    for num_pds in range(len(pd_names) + 1):
        cases += 1
        got = select(pd_names, vregs, num_vregs, num_pd_vregs, num_pds, known[condition])
        want = expected(pd_names, vregs, num_pd_vregs, num_pds)
        ok = got is not None and sorted(got) == sorted(want)
        failures += not ok
        print(f'{"ok  " if ok else "FAIL"} {name:15} pds={num_pds} requested={got} expected={want}')
print(f'{known[condition]} condition: {cases} cases, {failures} failures')
sys.exit(1 if failures else 0)
