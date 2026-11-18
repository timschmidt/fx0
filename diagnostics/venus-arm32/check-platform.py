# SPDX-License-Identifier: GPL-2.0-only
"""Run focused host controls over the maintained Venus and IOMMU helpers."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('linux', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('kernel_helpers', here / 'check-aperture.py')
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)

    media = args.linux / 'drivers/media/platform/qcom/venus'
    iommu = args.linux / 'drivers/iommu/arm/arm-smmu/qcom_iommu.c'
    targets = {
        media / 'core.h': ('venus_wrapper_addr',),
        media / 'core.c': ('venus_assign_register_offsets', 'venus_map_registers'),
        media / 'hfi_venus.c': ('venus_set_registers',),
        media / 'pm_helpers.c': ('mbs_to_bw', 'load_scale_bw'),
        iommu: ('qcom_iommu_select_wrapper_clk', 'qcom_iommu_resume',
                'qcom_iommu_attach_dev', 'qcom_iommu_identity_attach',
                'qcom_iommu_tlb_inv_range_nosync'),
    }
    functions = {name: extract.function(path.read_text(), name)
                 for path, names in targets.items() for name in names}
    registers = (media / 'hfi_venus_io.h').read_text()
    offsets = []
    for name in ('VBIF_BASE', 'CPU_BASE', 'CPU_CS_BASE', 'CPU_IC_BASE', 'CPU_BASE_V6',
                 'CPU_CS_BASE_V6', 'CPU_IC_BASE_V6', 'WRAPPER_BASE', 'WRAPPER_BASE_V6',
                 'WRAPPER_TZ_BASE_V6', 'AON_BASE_V6'):
        offsets.append(re.search(r'^#define\s+' + name + r'\s+[^\n]+', registers, re.M)[0])
    smmu_registers = iommu.with_name('arm-smmu.h').read_text()
    for name in ('ARM_SMMU_CB_SCTLR', 'ARM_SMMU_CB_S1_TLBIVA', 'ARM_SMMU_CB_S1_TLBIVAL'):
        offsets.append(re.search(r'^#define\s+' + name + r'\s+[^\n]+', smmu_registers, re.M)[0])

    core = (media / 'core.c').read_text()
    tables = {}
    for name, kind in (('msm8226_reg_preset', 'reg_val'), ('msm8226_bw_enc', 'bw_tbl'),
                       ('msm8226_bw_dec', 'bw_tbl')):
        table = re.search(r'static const struct ' + kind + ' ' + name + r'\[\] = \{.*?\n\};',
                          core, re.S)
        tables[name] = table[0]

    fixture = (here / 'platform-fixture.c').read_text()
    marker = '/* insert actual kernel code */'
    assert fixture.count(marker) == 1
    generated = '\n'.join([*offsets, *tables.values(), *functions.values()])
    args.output.mkdir()
    program = args.output / 'platform-fixture.c'
    executable = args.output / 'platform-fixture'
    program.write_text(fixture.replace(marker, generated))
    subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-missing-field-initializers', '-Wno-unused-parameter', '-fsanitize=undefined',
                    '-fno-sanitize-recover=all', str(program), '-o', str(executable)],
                   check=True, timeout=30)
    result = json.loads(subprocess.check_output([str(executable.resolve())], text=True, timeout=10))
    assert result['passed']
    result['kernel_fragments_sha256'] = {name: hashlib.sha256(data.encode()).hexdigest()
                                         for name, data in (functions | tables).items()}
    result['UBSan'] = True
    result['hardware_exercised'] = False
    (args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
