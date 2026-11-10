#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check normal lk2nd download and upload framing at both descriptor limits."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT/'tests/lk2nd-fastboot-td-harness.c'
EXTRACTOR = ROOT/'tests/test_lk2nd_download_framing.py'
SIZES = [64, 16384, 16385, 32768, 32769, 66048, 6330368, 6809600]
MAIN = r'''
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    length = (unsigned)strtoul(argv[1], NULL, 10);
    CHECK(length > 0 && length <= sizeof(payload));
    snprintf(expected_frame, sizeof(expected_frame), "DATA%08x", length);
    char argument[9];
    snprintf(argument, sizeof(argument), "%08x", length);
    fastboot_state = STATE_COMMAND;
    download_base = payload;
    download_max = sizeof(payload);
    usb_if.usb_read = hsusb_usb_read;
    usb_if.usb_write = hsusb_usb_write;
    cmd_download(argument, NULL, 0);
    CHECK(fastboot_state == STATE_COMMAND && download_size == length && okay == 1);
    cmd_upload("", download_base, download_size);
    CHECK(fastboot_state == STATE_COMMAND && okay == 2 && frames == 2);
    CHECK(bytes[0] == length && bytes[1] == length && count[0] == count[1]);
    CHECK(max_descriptors[0] == max_descriptors[1]);
    printf("%u %u %u %u\n", length, count[0], count[1], max_descriptors[0]);
    return 0;
}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limit(source, name):
    match = re.search(r'^#define\s+'+name+r'\s+\((\d+)\s*\*\s*1024\)', source, re.MULTILINE)
    if not match:
        raise ValueError(f'Missing source limit {name}')
    return int(match[1])*1024


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['control', 'candidate', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    out.mkdir(mode=0o700, exist_ok=False)
    spec = importlib.util.spec_from_file_location('framing_extractor', EXTRACTOR)
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    cases = {}
    for label, root, expected in [('control', args.control, 32768), ('single_td', args.candidate, 16384)]:
        fastboot = root/'app/aboot/fastboot.c'
        hsusb = root/'platform/msm_shared/hsusb.c'
        fastboot_text = fastboot.read_text()
        transfer_limit = limit(fastboot_text, 'MAX_USBFS_BULK_SIZE')
        descriptor_limit = limit(hsusb.read_text(), 'MAX_TD_XFER_SIZE')
        assert transfer_limit == expected and descriptor_limit == 16384
        # The existing extractor accepts static functions. Preserve the public helper body.
        source = fastboot_text.replace('\nvoid fastboot_write_data(', '\nstatic void fastboot_write_data(', 1)
        functions = ['hex2unsigned', 'req_complete', 'hsusb_usb_read', 'hsusb_usb_write',
                     'cmd_download', 'fastboot_write_data', 'cmd_upload']
        declarations = (f'#define MAX_USBFS_BULK_SIZE {transfer_limit}\n'
                        f'#define MAX_TD_XFER_SIZE {descriptor_limit}\n')
        unit = out/(label+'.c')
        unit.write_text(declarations+HARNESS.read_text()+'\n'+''.join(extractor.function(source, name)
                        for name in functions)+MAIN)
        binary = out/(label+'-framing')
        command = ['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                   '-O2', str(unit), '-o', str(binary)]
        run = subprocess.run(command, capture_output=True, text=True)
        (out/(label+'-build.log')).write_text(run.stdout+run.stderr)
        run.check_returncode()
        results = []
        for size in SIZES:
            run = subprocess.run([str(binary), str(size)], capture_output=True, text=True, check=True, timeout=10)
            count = (size+transfer_limit-1)//transfer_limit
            max_td = (min(size, transfer_limit)+descriptor_limit-1)//descriptor_limit
            assert list(map(int, run.stdout.split())) == [size, count, count, max_td]
            results.append({'bytes': size, 'download_requests': count, 'upload_requests': count,
                            'max_descriptors_per_data_request': max_td, 'passed': True})
        cases[label] = {'cases': results, 'compiler_command': command, 'fastboot_sha256': sha(fastboot),
                        'hsusb_sha256': sha(hsusb), 'compiled_source_sha256': sha(unit),
                        'binary_sha256': sha(binary), 'request_limit': transfer_limit,
                        'driver_descriptor_limit': descriptor_limit}
    record = {'variants': cases, 'harness_sha256': sha(HARNESS), 'extractor_sha256': sha(EXTRACTOR),
              'total_cases': 2*len(SIZES), 'failed': 0,
              'scope': 'Actual fastboot framing with mocked synchronous UDC completion. Descriptor count is derived from the driver limit. USB DMA and physical transport are outside this check.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({key: record[key] for key in ['total_cases', 'failed', 'scope']}))


if __name__ == '__main__':
    main()
