#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the ChipIdea USB budget consumer with controlled work and supplier I/O."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'tests/chipidea-usb-budget-harness.c'
EXTRACTOR = ROOT / 'tests/test_lk2nd_download_framing.py'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    source = args.driver.read_text()
    spec = importlib.util.spec_from_file_location('extractor', EXTRACTOR)
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    begin = source.index('enum ci_vbus_draw_event {')
    end = source.index('/**\n * isr_reset_handler:', begin)
    callbacks = ['ci_udc_vbus_draw', 'isr_tr_complete_low']
    (output / 'driver-functions.c').write_text(
        source[begin:end] + ''.join(extractor.function(source, name) for name in callbacks))
    binary = output / 'usb-budget-harness'
    command = ['clang', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
               '-I' + str(output), str(HARNESS), '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (output / 'build.log').write_text(build.stdout + build.stderr)
    build.check_returncode()
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=env)
    (output / 'run.log').write_text(run.stdout + run.stderr)
    run.check_returncode()
    match = re.fullmatch(r'USB_BUDGET_CASES (\d+)\n', run.stdout)
    assert match

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    result = {'cases': int(match[1]), 'failed': 0, 'compiler': command,
              'driver_sha256': sha(args.driver), 'harness_sha256': sha(HARNESS),
              'binary_sha256': sha(binary),
              'scope': 'Actual ChipIdea budget callbacks with simulated device links, work and supplier I/O.'}
    (output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(run.stdout, end='')


if __name__ == '__main__':
    main()
