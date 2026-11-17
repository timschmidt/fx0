# SPDX-License-Identifier: GPL-2.0-only
"""Run exactly the selected CPU stack models with audited compiler modes."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
B = Path(__file__).resolve().parent
O = a.output.resolve()
O.mkdir(mode=0o700)
(O / 'tmp').mkdir()
compiler_log = O / 'compiler-modes.jsonl'
expected = json.loads((B / 'source-current.json').read_text())['source_files']
for name, digest in expected.items():
    assert hashlib.sha256((a.source.resolve() / name).read_bytes()).hexdigest() == digest, name
os.environ.update(TMPDIR=str(O / 'tmp'), FX0_KERNEL_SOURCE=str(a.source.resolve()),
                  ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                  UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
                  FX0_MODEL_COMPILER_LOG=str(compiler_log),
                  PATH=str(B / 'compiler-bin') + os.pathsep + os.environ['PATH'])
tempfile.tempdir = str(O / 'tmp')
sys.path.insert(0, str(B / 'fixtures/tests'))
names = json.loads((B / 'test-modules.json').read_text())
assert len(names) == 19 and all('slimbus' not in n and 'audio' not in n for n in names)
suite = unittest.TestLoader().loadTestsFromNames(names)
with (O / 'methods.log').open('x') as log:
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
builds = [json.loads(line) for line in compiler_log.read_text().splitlines()]
assert builds and all(b['sanitizers'] == (not b['shared']) for b in builds)
record = dict(passed=result.wasSuccessful(), tests=result.testsRun,
              failures=len(result.failures), errors=len(result.errors),
              skipped=len(result.skipped), failure_cases=[str(x[0]) for x in result.failures],
              error_cases=[str(x[0]) for x in result.errors],
              standalone_sanitizer_builds=sum(not b['shared'] for b in builds),
              unsanitized_shared_numeric_oracle_builds=sum(b['shared'] for b in builds),
              compiler_modes_verified=True, normal_LSan_enabled=True,
              pinned_modified_source_inputs_verified=True,
              all_model_sources_under_private_tmp=all(Path(s).is_relative_to(O / 'tmp') for b in builds for s in b['source_files']),
              physical_or_concurrent_kernel_acceptance=False, phone_access=False)
(O / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
assert result.wasSuccessful() and result.testsRun == 44 and not result.skipped
assert record['standalone_sanitizer_builds'] and record['all_model_sources_under_private_tmp']
