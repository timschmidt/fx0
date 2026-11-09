#!/usr/bin/env python3
"""Add validity probes to a pristine isolated checkout; do not change C code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = 'd8e650c3180db30b4c7df59caadefae9c2ff2866'
BACKPORT = '1ddb4275a13932db1a64d8549182947066c57fb0'


def prepare(source, report, base=BASE):
    source = source.resolve()
    if report.exists():
        raise ValueError('Report already exists')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                   text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'])
    if base not in [BASE, BACKPORT] or head != base or dirty:
        raise ValueError('Use a pristine isolated checkout at ' + base)
    path = source / 'src/linux/integration-test.py'
    original = path.read_text()
    marker = '    def test_tool_device_enumeration_failure(self):'
    if original.count(marker) != 1 or original.count('import os\n') != 1:
        raise ValueError('Unexpected integration-test layout')
    fragment = (Path(__file__).parent / 'fixtures.fragment.py').read_text()
    text = original.replace('import os\n', 'import os\nimport json\n', 1)
    text = text.replace(marker, fragment + '\n' + marker)
    compile(text, str(path), 'exec')
    c_files = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((source / 'src').rglob('*.c'))}
    path.write_text(text)
    record = {'base': head, 'only_modified_file': 'src/linux/integration-test.py',
              'integration_test_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'production_C_files_sha256': c_files,
              'source_C_changed': False, 'built_or_executed': False}
    report.write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--base', choices=[BASE, BACKPORT], default=BASE)
    args = parser.parse_args()
    result = prepare(args.source, args.report, args.base)
    print('Prepared 12 probes; production C unchanged')
