"""Check current NXP removal ordering without the separate clock feature.

This runs extracted callbacks against modeled services. It never opens NFC
hardware or a kernel netlink endpoint. Set FX0_NFC_REMOVE_SOURCE to the fixes
checkout; FX0_NFC_REMOVE_OUTPUT optionally retains the generated host artifacts.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FX0_NFC_REMOVE_SOURCE',
                             ROOT / 'worktrees/linux-nfc-remove-upstream'))
SPEC = importlib.util.spec_from_file_location('nxp_remove_shared',
                                            Path(__file__).with_name('fixtures') / 'test_nxp_nci_open_teardown.py')
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)


def model(source):
    """Adapt only clock-related model state; keep all actual callbacks intact."""
    driver = source / 'drivers/nfc/nxp-nci'
    has_clock = 'ref_clk' in (driver / 'i2c.c').read_text()
    code = SHARED.harness(source)
    obsolete = [
        'static struct clk clock_model;\n',
        SHARED.function(code, 'clk_prepare_enable'),
        SHARED.function(code, 'clk_disable_unprepare'),
        SHARED.block(code, r'^static struct clk \*devm_clk_get_optional\('),
        SHARED.block(code, r'^static int dev_err_probe\('),
        '   if (strstr(argv[1], "no_clock")) phy.ref_clk = NULL;\n',
    ]
    for text in ([] if has_clock else obsolete):
        assert code.count(text) == 1, text
        code = code.replace(text, '')
    old = ' CHECK(!clock_model.votes && !phy.ref_clk_enabled && !en.value && !fw.value);'
    if not has_clock:
        assert code.count(old) == 1
        code = code.replace(old, ' CHECK(!en.value && !fw.value);')
    actual = {
        'drivers/nfc/nxp-nci/i2c.c': ['nxp_nci_i2c_set_mode', 'nxp_nci_i2c_write',
                                    'nxp_nci_i2c_nci_read', 'nxp_nci_i2c_irq_thread_fn',
                                    'nxp_nci_i2c_probe', 'nxp_nci_i2c_remove'],
        'drivers/nfc/nxp-nci/core.c': ['nxp_nci_open', 'nxp_nci_close', 'nxp_nci_send',
                                     'nxp_nci_remove'],
        'net/nfc/nci/core.c': ['nci_reset_req', 'nci_close_device', 'nci_unregister_device',
                             'nci_recv_frame'],
        'net/nfc/nci/rsp.c': ['nci_core_reset_rsp_packet'],
    }
    if 'static void nxp_nci_i2c_stop_rx(' in (driver / 'i2c.c').read_text():
        actual['drivers/nfc/nxp-nci/i2c.c'].append('nxp_nci_i2c_stop_rx')
    for name, functions in actual.items():
        text = (source / name).read_text()
        for function in functions:
            assert SHARED.function(code, function) == SHARED.function(text, function), function
    return code



if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--baseline', action='store_true')
    a = p.parse_args()
    assert not a.output.exists()
    a.output.mkdir()
    code = model(a.source)
    path = a.output / 'model.c'; path.write_text(code)
    binary = a.output / 'model'
    cmd = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-Wno-unused-parameter', '-Wno-sign-compare', '-fsanitize=address,undefined',
           '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(path), '-o', str(binary)]
    c = subprocess.run(cmd, capture_output=True, text=True)
    (a.output / 'build.log').write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    modes = ['open', 'open_pending_irq', 'open_data_exchange', 'cold', 'cold_pending_irq',
             'firmware_pending_irq', 'probe_irq_failure', 'core_legacy', 'open_timeout_pending_irq']
    if 'ref_clk' in (a.source / 'drivers/nfc/nxp-nci/i2c.c').read_text():
        modes.append('open_no_clock')
    records = []
    for mode in modes:
        r = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=10,
                           env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                                             'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
        (a.output / (mode + '.log')).write_text(r.stdout + r.stderr)
        assert not any(s in r.stderr for s in ['ERROR: AddressSanitizer', 'runtime error:', 'LeakSanitizer', 'DEADLYSIGNAL']), (mode, r.stderr)
        records.append(dict(mode=mode, returncode=r.returncode, stdout=r.stdout.strip(), assertion=r.stderr.strip()))
    failures = sum(r['returncode'] != 0 for r in records)
    report = dict(actual_driver_and_NCI_callback_bodies_preserved=True,
                  clock_feature_included=len(modes)==10, host_ASan_UBSan_normal_LSan_failfast=True,
                  modeled_cases=len(modes), failures=failures, results=records,
                  real_kernel_or_hardware_operations=False, concurrent_firmware_timing_modeled=False,
                  fixture_SHA256=hashlib.sha256(code.encode()).hexdigest())
    (a.output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert failures > 0 if a.baseline else failures == 0, report
    print(json.dumps(dict(cases=len(modes), failures=failures, baseline=a.baseline)))
