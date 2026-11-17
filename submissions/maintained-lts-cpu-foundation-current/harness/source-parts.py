# SPDX-License-Identifier: GPL-2.0-only
"""Extract unmodified functions and macros for host qualification."""
from pathlib import Path
import hashlib
import re


def function(text, name):
    m = re.search(r'^(?=[A-Za-z_*])[^\n]*?\b'+name+r'\(', text, re.M)
    assert m, name
    start = m.start()
    if text[start:].startswith(name) or text[start:].startswith('*'+name):
        previous = text[:start].rstrip('\n').rsplit('\n', 1)[-1]
        assert previous.startswith(('static ', 'const ', 'struct ', 'int ', 'void ')), (name, previous)
        start -= len(previous) + 1
    return text[start:text.index('\n}', m.start())+2]+'\n'


def macro(text, name):
    m = re.search(r'^#define '+name+r'\b', text, re.M)
    assert m, name
    lines = text[m.start():].splitlines(keepends=True)
    selected = []
    for line in lines:
        selected.append(line)
        if not line.rstrip().endswith('\\'):
            break
    return ''.join(selected)
