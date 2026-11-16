# SPDX-License-Identifier: GPL-2.0-only
"""Run actual native Kconfig across CAMSS/provider tristate combinations."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('label')
p.add_argument('--architectures', nargs='+', default=['arm', 'arm64'])
p.add_argument('--fixed', action='store_true')
a = p.parse_args()
source = a.source.resolve()
base = Path(__file__).resolve().parent
record = base / (a.label + '.json')
assert not record.exists()
results = []
for arch in a.architectures:
    out = base / (a.label + '-' + arch + '-out')
    out.mkdir(mode=0o700)
    for consumer in ['y', 'm']:
        for provider in ['n', 'm', 'y']:
            label = arch + '-camss-' + consumer + '-phy-' + provider
            seed = out / (label + '.seed')
            config = {
                'MODULES': 'y', 'ARCH_QCOM': 'y', 'OF': 'y', 'PM': 'y',
                'CPU_FREQ': 'y', 'CPUFREQ_DT': 'y',
                'COMMON_CLK': 'y', 'IOMMU_SUPPORT': 'y',
                'MEDIA_SUPPORT': 'y', 'MEDIA_SUPPORT_FILTER': 'y',
                'MEDIA_CAMERA_SUPPORT': 'y', 'MEDIA_PLATFORM_SUPPORT': 'y',
                'MEDIA_PLATFORM_DRIVERS': 'y', 'VIDEO_DEV': 'y',
                'V4L_PLATFORM_DRIVERS': 'y', 'VIDEO_QCOM_CAMSS': consumer,
                'PHY_QCOM_MIPI_CSI2': provider,
            }
            if arch == 'arm':
                config.update(ARCH_MULTI_V7='y', MMU='y', ARM_SMMU='y')
            seed.write_text(''.join('CONFIG_' + k + '=' + v + '\n' if v != 'n'
                                    else '# CONFIG_' + k + ' is not set\n'
                                    for k, v in config.items()))
            command = ['make', 'O=' + str(out), 'ARCH=' + arch, 'LLVM=-21',
                       'KCONFIG_ALLCONFIG=' + str(seed), 'allnoconfig']
            r = subprocess.run(command, cwd=source, capture_output=True,
                               text=True, timeout=120)
            (out / (label + '.log')).write_text(r.stdout + r.stderr)
            assert r.returncode == 0, label
            assert 'warning:' not in (r.stdout + r.stderr).lower(), label
            text = (out / '.config').read_text()
            (out / (label + '.config')).write_text(text)
            def value(key):
                for line in text.splitlines():
                    if line.startswith('CONFIG_' + key + '='):
                        return line.split('=', 1)[1]
                return 'n'
            assert value('VIDEO_QCOM_CAMSS') == consumer, label
            assert value('PHY_QCOM_MIPI_CSI2') == provider, label
            assert value('COMPILE_TEST') == 'n', label
            helper = value('GENERIC_PHY_MIPI_DPHY')
            reachable = {'n': 0, 'm': 1, 'y': 2}[helper] >= {'m': 1, 'y': 2}[consumer]
            if a.fixed:
                assert reachable, label
            results.append(dict(profile=label, ARCH=arch,
                                CAMSS=consumer, optional_PHY=provider,
                                direct_timing_helper=helper,
                                link_dependency_satisfied=reachable,
                                config_SHA256=hashlib.sha256(text.encode()).hexdigest(),
                                COMPILE_TEST=False, diagnostics=0))
            record.write_text(json.dumps(dict(results=results, complete=False), indent=2) + '\n')
failures = sum(not r['link_dependency_satisfied'] for r in results)
assert failures == (0 if a.fixed else len(a.architectures) * 2)
report = dict(source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
              cwd=source, text=True).strip(), source_Kconfig_SHA256=hashlib.sha256(
              (source / 'drivers/media/platform/qcom/camss/Kconfig').read_bytes()).hexdigest(),
              native=True, COMPILE_TEST=False, complete=True, fixed=a.fixed,
              profiles=len(results), dependency_failures=failures, results=results,
              phone_access=False, full_build_separate=True)
record.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['fixed', 'profiles', 'dependency_failures']}))
