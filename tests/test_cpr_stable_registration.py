"""Exercise the exact stable CPR registration shell and reject older families."""
from pathlib import Path
import unittest

import test_cpr_alpine_registration as alpine

ROOT = Path(__file__).resolve().parents[1]


class StableRegistrationTests(alpine.AlpineRegistrationTests):
    SCRIPT = ROOT/'diagnostics/cpu-cpr-runtime/register-stable.sh'
    KERNEL = '6.18.63-fx0-cpr-nfc-alpine'
    MARKER = 'stable-6.18.63-r3-registration'
    PASS_MARKER = 'STABLE_CPR_REGISTRATION_PASS'

    def test_previous_stable_and_Alpine_CPR_families_rejected_before_load(self):
        for kernel in ['6.18.59-fx0-cpr-observe-alpine',
                       '6.18.63-fx0-vibrator-alpine',
                       '6.18.63-fx0-nfc-alpine']:
            with self.subTest(kernel=kernel):
                result, calls = self.run_case(kernel=kernel)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unexpected kernel', result.stderr)
                self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
