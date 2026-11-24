#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Resolve the fixed update's file collisions before selecting recovery writes.

This implements APK 3.0.8/3.0.9's apk_pkg_replaces_file rules for collisions
with unselected installed packages. Versioned replacement dependencies and
collisions between selected packages deliberately require separate qualification.
Inputs must come from authenticated package controls and the captured database.
"""
from pathlib import PurePosixPath
import re


def canonical(name):
    path = PurePosixPath(name)
    assert path.is_absolute() and '..' not in path.parts and path != PurePosixPath('/')
    if path.parts[1] in {'bin', 'sbin', 'lib'}:
        path = PurePosixPath('/usr') / path.relative_to('/')
    return str(path)


def installed_ownership(text):
    packages, owners = {}, {}
    for paragraph in text.split('\n\n'):
        header = {}
        for line in paragraph.splitlines():
            if line.startswith('F:'):
                break
            if len(line) > 1 and line[1] == ':':
                assert line[0] not in header, 'Repeated package header'
                header[line[0]] = line[2:]
        if 'P' not in header:
            continue
        name = header['P']
        assert name not in packages
        packages[name] = dict(version=header['V'], checksum=header['C'],
                              origin=header.get('o', ''), replaces=header.get('r', '').split(),
                              priority=int(header.get('q', '0')))
        directory = None
        for line in paragraph.splitlines():
            if line.startswith('F:'):
                directory = line[2:]
            elif line.startswith('R:'):
                assert directory is not None
                assert not directory.startswith('/') and '/' not in line[2:]
                path = canonical(str(PurePosixPath('/') / directory / line[2:]))
                owners.setdefault(path, set()).add(name)
    return packages, {p: sorted(names) for p, names in owners.items()}


def replacement_priority(package, other):
    dependencies = package.get('replaces', [])
    assert all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*', d) for d in dependencies), \
        'Versioned/negated replacement dependencies need separate qualification'
    priority = package.get('priority', 0)
    assert type(priority) is int and 0 <= priority <= 65535
    return priority if other in dependencies else -1


def retained_payloads(installed_text, candidates, incoming):
    packages, owners = installed_ownership(installed_text)
    retained = {}
    for path, payload in candidates.items():
        assert canonical(path) == path
        if payload['expected']['kind'] == 'directory' or path not in owners:
            continue
        providers = payload['packages']
        assert len(providers) == 1, ('Multiple candidate providers need qualification', path)
        provider = providers[0]
        assert provider in incoming
        assert len(owners[path]) == 1, ('Multiple installed file owners', path)
        owner = owners[path][0]
        if owner == provider:
            continue
        assert owner not in incoming, ('Selected owner collision needs qualification', path)
        old, new = packages[owner], incoming[provider]
        a_priority = replacement_priority(old, provider)
        b_priority = replacement_priority(new, owner)
        if a_priority > b_priority:
            retained[path] = dict(owner=owner,
                owner_identity={k: old[k] for k in ['version', 'checksum']},
                incoming_package=provider,
                incoming_identity={k: new[k] for k in ['version', 'checksum']},
                owner_replaces=old['replaces'], owner_priority=a_priority,
                incoming_replaces=new.get('replaces', []), incoming_priority=b_priority)
        else:
            assert b_priority >= 0 or (old['origin'] and old['origin'] == new.get('origin')), \
                ('Unresolved package file conflict', path, owner, provider)
    return retained
