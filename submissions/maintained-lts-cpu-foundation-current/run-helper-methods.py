# SPDX-License-Identifier: GPL-2.0-only
"""Run only the four synthetic calibration/planning fixture modules."""
from pathlib import Path
import argparse
import json
import os
import sys
import tempfile
import unittest

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
B = Path(__file__).resolve().parent
O = a.output.resolve()
O.mkdir(mode=0o700)
(O / 'tmp').mkdir()
os.environ.update(TMPDIR=str(O / 'tmp'), FX0_KERNEL_SOURCE=str(a.source.resolve()),
                  ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                  UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
tempfile.tempdir = str(O / 'tmp')
sys.path.insert(0, str(B / 'harness/fixtures/tests'))
names = ['test_msm8926_calibration', 'test_msm8926_voltage_plan',
         'test_msm8926_corner', 'test_msm8926_fuses']
suite = unittest.TestLoader().loadTestsFromNames(names)
with (O / 'methods.log').open('x') as log:
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
record = dict(passed=result.wasSuccessful(), tests=result.testsRun,
              failures=len(result.failures), errors=len(result.errors),
              skipped=len(result.skipped), selected_modules=names,
              ctypes_shared_oracles_unsanitized=True,
              standalone_fuse_loader_ASan_UBSan_LSan=True,
              all_data_synthetic=True, phone_access=False)
(O / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
assert result.wasSuccessful() and result.testsRun == 16 and not result.skipped
