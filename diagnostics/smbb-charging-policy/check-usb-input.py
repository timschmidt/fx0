#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the candidate SMBB USB input callbacks with instrumented SPMI I/O."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT/'tests/smbb-usb-input-harness.c'
EXTRACTOR = ROOT/'tests/test_lk2nd_download_framing.py'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(mode=0o700, exist_ok=False)
    source = args.driver.read_text()
    spec = importlib.util.spec_from_file_location('extractor', EXTRACTOR)
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    names = r'SMBB_\w+|STATUS_\w+|USB_TYPE_CHGPTH|USB_SUBTYPE_SMBP|USB_SUSPEND_EN|PRES_STATUS_BAT_PRES'
    macros = re.findall(r'^#define (?:'+names+r')\s+[^\n]+$', source, re.MULTILINE)
    enum = source[source.index('enum smbb_attr {'):source.index('struct smbb_charger {')]
    (out/'driver-definitions.h').write_text('\n'.join(macros)+'\n'+enum)
    limits = source[source.index('static int smbb_vbat_weak_fn('):source.index('static int smbb_charger_attr_read(')]
    functions = ['smbb_usb_input_supported', 'smbb_usb_input_suspend', 'smbb_usb_input_get_limit',
                 'smbb_usb_input_set_limit', 'smbb_usbin_get_property', 'smbb_usbin_set_property',
                 'smbb_charger_writable_property', 'smbb_usbin_writable_property']
    (out/'driver-functions.c').write_text(limits+''.join(extractor.function(source, name) for name in functions))
    binary = out/'usb-input-harness'
    command = ['clang', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-sign-compare',
               '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie', '-pthread',
               '-I'+str(out), str(HARNESS), '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=env)
    (out/'run.log').write_text(run.stdout+run.stderr)
    run.check_returncode()
    match = re.fullmatch(r'USB_INPUT_CASES (\d+)\n', run.stdout)
    assert match
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'cases': int(match[1]), 'failed': 0, 'compiler': command, 'binary_sha256': sha(binary),
              'driver_sha256': sha(args.driver), 'harness_sha256': sha(HARNESS), 'extractor_sha256': sha(EXTRACTOR),
              'scope': 'Extracted candidate driver callbacks with simulated register and power-supply I/O under ASan/UBSan.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({key: record[key] for key in ['cases', 'failed', 'scope']}))


if __name__ == '__main__':
    main()
