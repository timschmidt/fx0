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
                                            ROOT / 'tests/test_nxp_nci_open_teardown.py')
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)


def model(source):
    """Adapt only clock-related model state; keep all actual callbacks intact."""
    driver = source / 'drivers/nfc/nxp-nci'
    assert 'ref_clk' not in (driver / 'i2c.c').read_text()
    code = SHARED.harness(source)
    obsolete = [
        'static struct clk clock_model;\n',
        SHARED.function(code, 'clk_prepare_enable'),
        SHARED.function(code, 'clk_disable_unprepare'),
        SHARED.block(code, r'^static struct clk \*devm_clk_get_optional\('),
        SHARED.block(code, r'^static int dev_err_probe\('),
        '   if (strstr(argv[1], "no_clock")) phy.ref_clk = NULL;\n',
    ]
    for text in obsolete:
        assert code.count(text) == 1, text
        code = code.replace(text, '')
    old = ' CHECK(!clock_model.votes && !phy.ref_clk_enabled && !en.value && !fw.value);'
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


@unittest.skipUnless((SOURCE / 'drivers/nfc/nxp-nci/i2c.c').is_file(),
                     'Set FX0_NFC_REMOVE_SOURCE to a current fixes checkout')
class NxpNciRemoveUpstreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        retained = os.environ.get('FX0_NFC_REMOVE_OUTPUT')
        cls.temporary = None
        if retained:
            cls.output = Path(retained)
            cls.output.mkdir(parents=True)
        else:
            cls.temporary = tempfile.TemporaryDirectory()
            cls.output = Path(cls.temporary.name)
        cls.records = []
        cls.code = model(SOURCE)
        cls.binary = cls.compile('candidate', cls.code)

    @classmethod
    def compile(cls, label, code):
        source = cls.output / (label + '.c')
        source.write_text(code)
        binary = cls.output / label
        args = shlex.split(os.environ.get('CC', 'clang'))
        args += ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                 '-Wno-unused-parameter', '-Wno-sign-compare', '-fsanitize=address,undefined',
                 '-fno-omit-frame-pointer', str(source), '-o', str(binary)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        (cls.output / (label + '-build.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise AssertionError(result.stderr)
        return binary

    def invoke(self, label, binary, mode, succeeds):
        result = subprocess.run([str(binary), mode], capture_output=True, text=True,
                                timeout=5, env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=0'})
        (self.output / (label + '-' + mode + '.log')).write_text(result.stdout + result.stderr)
        self.records.append(dict(label=label, mode=mode, returncode=result.returncode,
                                 expected_success=succeeds, stdout=result.stdout.strip()))
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, 'Broken ordering was accepted: ' + label)
            self.assertNotIn('AddressSanitizer:DEADLYSIGNAL', result.stderr)
        return result

    def test_open_reset_response_precedes_receive_drain(self):
        for mode in ['open', 'open_pending_irq', 'open_data_exchange']:
            with self.subTest(mode=mode):
                self.invoke('candidate', self.binary, mode, True)

    def test_cold_and_serialized_firmware_state_are_drained_before_free(self):
        for mode in ['cold', 'cold_pending_irq', 'firmware_pending_irq']:
            with self.subTest(mode=mode):
                self.invoke('candidate', self.binary, mode, True)

    def test_failed_IRQ_request_does_not_release_unowned_IRQ(self):
        self.invoke('candidate', self.binary, 'probe_irq_failure', True)

    def test_optional_transport_callback(self):
        self.invoke('candidate', self.binary, 'core_legacy', True)

    def test_missing_response_still_closes_and_drains(self):
        self.invoke('candidate', self.binary, 'open_timeout_pending_irq', True)

    def test_ordering_lock_wiring_and_ownership_controls_are_rejected(self):
        code = self.code
        stop = '\tif (info->phy_ops->stop_rx)\n\t\tinfo->phy_ops->stop_rx(info->phy_id);'
        unregister = '\tnci_unregister_device(ndev);'
        self.assertEqual(code.count(stop), 1)
        self.assertEqual(code.count(unregister), 1)
        without_stop = code.replace(stop, '')
        locked_unregister = code.replace(unregister, '\tmutex_lock(&info->info_lock);\n' +
                                         unregister + '\n\tmutex_unlock(&info->info_lock);')
        # Let the actual close callback reach its recursive mutex acquisition.
        # The normal rfkill model also checks unlocked context earlier.
        early_check = 'CHECK(dev == &ndev && !info.info_lock.held); rfkill_removed++;'
        self.assertEqual(locked_unregister.count(early_check), 1)
        locked_unregister = locked_unregister.replace(early_check,
                                                      'CHECK(dev == &ndev); rfkill_removed++;')
        controls = [
            ('unregister-under-lock', locked_unregister, 'open'),
            ('drain-before-reset', without_stop.replace(unregister, stop + '\n' + unregister), 'open'),
            ('drain-after-free', without_stop.replace('\tnci_free_device(ndev);',
                                                    '\tnci_free_device(ndev);\n' + stop), 'cold_pending_irq'),
            ('lock-during-drain', code.replace(stop, '\tmutex_lock(&info->info_lock);\n' + stop +
                                              '\n\tmutex_unlock(&info->info_lock);'), 'cold_pending_irq'),
            ('missing-stop-wiring', code.replace('\t.stop_rx = nxp_nci_i2c_stop_rx,', ''), 'cold'),
            ('unowned-IRQ-release', code.replace('\tif (!phy->irq_requested)\n\t\treturn;\n', ''),
             'probe_irq_failure'),
        ]
        for label, broken, mode in controls:
            with self.subTest(control=label):
                self.assertNotEqual(broken, code)
                # An unwired callback intentionally becomes an unused function.
                # Preserve Werror by removing only that now-unused definition.
                if label == 'missing-stop-wiring':
                    broken = broken.replace(SHARED.function(broken, 'nxp_nci_i2c_stop_rx'), '')
                    broken = broken.replace(SHARED.function(broken, 'free_irq'), '')
                    broken = broken.replace('static void free_irq(int irq, void *data);\n', '')
                binary = self.compile(label, broken)
                result = self.invoke(label, binary, mode, False)
                if label == 'unregister-under-lock':
                    self.assertIn('!m->held', result.stderr)

    @classmethod
    def tearDownClass(cls):
        report = dict(actual_driver_and_NCI_callback_bodies_preserved=True,
                      clock_feature_included=False, host_ASan_UBSan=True,
                      modeled_positive_cases=9, independent_regression_controls=6,
                      real_kernel_or_hardware_operations=False,
                      concurrent_firmware_timing_modeled=False,
                      fixture_sha256=hashlib.sha256(cls.code.encode()).hexdigest(),
                      results=cls.records)
        (cls.output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        if cls.temporary:
            cls.temporary.cleanup()


if __name__ == '__main__':
    unittest.main()
