# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the actual ARM legacy aperture and Venus admission helpers."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def function(source, name):
    match = re.search(r'^.*\b' + name + r'\([^;]+?\)\n\{', source, re.M)
    if match is None:
        raise ValueError(f'unable to find {name}')
    start = match.end()
    depth = 1
    for end in range(start, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[match.start():end + 1] + '\n'
    raise ValueError(f'unterminated helper {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('linux', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    sources = {
        'arm_iommu_dma_aperture_within': 'arch/arm/mm/dma-mapping.c',
        'venus_reserve_iova_region': 'drivers/media/platform/qcom/venus/core.c',
        'venus_unreserve_iova_region': 'drivers/media/platform/qcom/venus/core.c',
    }
    extracted = {name: function((args.linux / path).read_text(), name)
                 for name, path in sources.items()}
    fixtures = Path(__file__).resolve().with_name('aperture-fixture.c')
    text = fixtures.read_text()
    marker = '/* kernel helpers */'
    if text.count(marker) != 1:
        raise ValueError('missing fixture insertion point')
    args.output.mkdir()
    c_file = args.output / 'aperture.c'
    program = args.output / 'aperture'
    c_file.write_text(text.replace(marker, '\n'.join(extracted.values())))
    subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-g',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all',
                    str(c_file), '-o', str(program)], check=True, timeout=30)
    counts = json.loads(subprocess.check_output([str(program.resolve())], text=True, timeout=10))
    if counts != {'passed': True, 'checks': 23}:
        raise ValueError(f'incomplete boundary test: {counts}')
    result = counts | {'actual_functions_sha256': {
        name: hashlib.sha256(source.encode()).hexdigest() for name, source in extracted.items()},
        'services': 'synthetic device, allocator and loaded-domain data',
        'UBSan': True, 'hardware_exercised': False}
    (args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
