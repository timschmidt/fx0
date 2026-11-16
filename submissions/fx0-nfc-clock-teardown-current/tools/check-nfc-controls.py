from pathlib import Path
import os, subprocess, json, shlex, unittest, tempfile, hashlib
import importlib.util
B=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location("lifecycle", B/"check-nfc-lifecycle.py")
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
SHARED=M.SHARED
model=M.model
SOURCE=Path(os.environ["FX0_NFC_REMOVE_SOURCE"])
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
                 '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', str(source), '-o', str(binary)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        (cls.output / (label + '-build.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise AssertionError(result.stderr)
        return binary

    def invoke(self, label, binary, mode, succeeds):
        result = subprocess.run([str(binary), mode], capture_output=True, text=True,
                                timeout=5, env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
        (self.output / (label + '-' + mode + '.log')).write_text(result.stdout + result.stderr)
        self.records.append(dict(label=label, mode=mode, returncode=result.returncode,
                                 expected_success=succeeds, stdout=result.stdout.strip()))
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, 'Broken ordering was accepted: ' + label)
            self.assertNotIn('AddressSanitizer', result.stderr)
            self.assertNotIn('LeakSanitizer', result.stderr)
            self.assertNotIn('runtime error:', result.stderr)
            self.assertEqual(result.returncode, 1)
            self.assertTrue(result.stderr.strip())
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
                      clock_feature_included=True, host_ASan_UBSan_normal_LSan_failfast=True,
                      modeled_positive_cases=sum(r["expected_success"] for r in cls.records), independent_regression_controls=6,
                      real_kernel_or_hardware_operations=False,
                      concurrent_firmware_timing_modeled=False,
                      fixture_sha256=hashlib.sha256(cls.code.encode()).hexdigest(),
                      results=cls.records)
        (cls.output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        if cls.temporary:
            cls.temporary.cleanup()


if __name__ == '__main__':
    unittest.main()
