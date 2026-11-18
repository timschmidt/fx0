# SPDX-License-Identifier: GPL-2.0-only
"""Run focused host controls over the maintained Venus and IOMMU helpers."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import resource
import signal
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
        iommu: ('qcom_iommu_ctx_tlb_sync', 'qcom_iommu_tlb_lock',
                'qcom_iommu_tlb_unlock', 'qcom_iommu_tlb_sync',
                'qcom_iommu_tlb_inv_context', 'qcom_iommu_tlb_inv_range_nosync',
                'qcom_iommu_tlb_sync_online', 'qcom_iommu_tlb_flush_walk',
                'qcom_iommu_tlb_add_page', 'qcom_iommu_fault', 'qcom_iommu_halt',
                'qcom_iommu_unhalt', 'qcom_iommu_rearm_venus_ctx',
                'qcom_iommu_venus_forget_domain', 'qcom_iommu_domain_free',
                'qcom_iommu_attach_dev', 'qcom_iommu_identity_attach',
                'qcom_iommu_unmap', 'qcom_iommu_sync_domain', 'qcom_iommu_flush_iotlb_all',
                'qcom_iommu_iotlb_sync', 'qcom_iommu_select_wrapper_clk',
                'qcom_iommu_resume_venus', 'qcom_iommu_resume', 'qcom_iommu_suspend'),
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
    for name in ('ARM_SMMU_CB_SCTLR', 'ARM_SMMU_CB_TLBSYNC', 'ARM_SMMU_CB_TLBSTATUS',
                 'ARM_SMMU_CB_S1_TLBIASID', 'ARM_SMMU_CB_S1_TLBIVA', 'ARM_SMMU_CB_S1_TLBIVAL',
                 'ARM_SMMU_CB_FSR', 'ARM_SMMU_CB_FSYNR0', 'ARM_SMMU_CB_FAR',
                 'ARM_SMMU_CB_RESUME', 'ARM_SMMU_RESUME_TERMINATE'):
        offsets.append(re.search(r'^#define\s+' + name + r'\s+[^\n]+', smmu_registers, re.M)[0])
    iommu_source = iommu.read_text()
    for name in ('QCOM_IOMMU_IMPL_DEF', 'QCOM_IOMMU_MICRO_MMU_CTRL', 'MICRO_MMU_CTRL_HALT_REQ',
                 'MICRO_MMU_CTRL_IDLE'):
        offsets.append(re.search(r'^#define\s+' + name + r'\s+[^\n]+', iommu_source, re.M)[0])

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
    generated_fixture = fixture.replace(marker, generated)
    program.write_text(generated_fixture)
    compiler = ['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                '-Wno-missing-field-initializers', '-Wno-unused-parameter', '-fsanitize=undefined',
                '-fno-sanitize-recover=all']
    subprocess.run([*compiler, str(program), '-o', str(executable)], check=True, timeout=30)
    result = json.loads(subprocess.check_output([str(executable.resolve())], text=True, timeout=10))
    assert result['passed']
    result['kernel_fragments_sha256'] = {name: hashlib.sha256(data.encode()).hexdigest()
                                         for name, data in (functions | tables).items()}
    result['UBSan'] = True
    result['hardware_exercised'] = False
    controls = {
        'offline_register_access': (
            'qcom_iommu_tlb_lock', 'if (iommu->ctx_online)', 'if (true)',
            'enables > disables && ctx_writes'),
        'missing_resume_invalidation': (
            'qcom_iommu_rearm_venus_ctx', 'iommu_writel(ctx, ARM_SMMU_CB_S1_TLBIASID, ctx->asid);',
            '', 'ctx_writes == 3 && ctx_trace[0].reg'),
        'published_failed_resume': (
            'qcom_iommu_resume_venus', 'if (!ret)', 'if (true)',
            '!iommu.ctx_online && !ctx_writes'),
        'whole_tlb_flush_only_waits': (
            'qcom_iommu_flush_iotlb_all', 'qcom_iommu_sync_domain(domain, true);',
            'qcom_iommu_sync_domain(domain, false);', 'ctx_writes == 2 && ctx_trace[0].reg'),
        'freed_domain_remains_visible': (
            'qcom_iommu_venus_forget_domain', 'WRITE_ONCE(ctx->domain, NULL);',
            'WRITE_ONCE(ctx->domain, &domain->domain);', '!ctx.domain && !ctx_writes'),
        'interrupt_while_clocks_are_off': (
            'qcom_iommu_fault', 'if (iommu->wrapper_clk_sel && pm_runtime_get_if_active(parent) <= 0)',
            'if (false && iommu->wrapper_clk_sel && pm_runtime_get_if_active(parent) <= 0)',
            'ctx && enables > disables'),
    }
    _, hard_core_limit = resource.getrlimit(resource.RLIMIT_CORE)
    resource.setrlimit(resource.RLIMIT_CORE, (0, hard_core_limit))
    for control, (helper, old, new, expected) in controls.items():
        original = functions[helper]
        assert original.count(old) == 1 and generated_fixture.count(original) == 1, control
        control_source = args.output / f'{control}.c'
        control_executable = args.output / control
        control_source.write_text(generated_fixture.replace(original, original.replace(old, new)))
        subprocess.run([*compiler, str(control_source), '-o', str(control_executable)],
                       check=True, timeout=30)
        run = subprocess.run([str(control_executable.resolve())], capture_output=True, text=True,
                             timeout=10)
        assert run.returncode == -signal.SIGABRT and expected in run.stderr, (control, run.stderr)
    result['negative_controls_detected'] = list(controls)
    (args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
