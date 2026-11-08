"""Reader restoration against IIO's exclusive scan-mask semantics."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('native_reader', Path(__file__).resolve().parents[1] /
    'diagnostics/imu-dmp-native/read_quaternion.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Attribute:
    def __init__(self, name, state):
        self.name, self.state = name, state
        self.fail = False

    def write_text(self, value):
        if self.fail:
            raise OSError('injected failure')
        value = value.strip()
        if value == '1' and self.name in ('raw', 'quat'):
            other = 'quat' if self.name == 'raw' else 'raw'
            if self.state[other] == '1':
                raise OSError('invalid exclusive scan mask')
        self.state[self.name] = value

    def __str__(self):
        return self.name


class ReaderRestore(unittest.TestCase):
    def test_saved_raw_scan_restored_after_quaternion_capture(self):
        state = {'raw': '0', 'quat': '1', 'stamp': '1', 'length': '64'}
        paths = {name: Attribute(name, state) for name in state}
        saved = {paths['raw']: '1', paths['quat']: '0', paths['stamp']: '0', paths['length']: '8'}
        reader.restore_configuration(saved, [paths[k] for k in ('raw', 'quat', 'stamp')])
        self.assertEqual(state, {'raw': '1', 'quat': '0', 'stamp': '0', 'length': '8'})

    def test_restore_failure_reported_and_remaining_attributes_attempted(self):
        state = {'raw': '0', 'quat': '1', 'stamp': '1', 'length': '64'}
        paths = {name: Attribute(name, state) for name in state}
        paths['raw'].fail = True
        saved = {paths['raw']: '1', paths['quat']: '0', paths['stamp']: '0', paths['length']: '8'}
        with self.assertRaisesRegex(RuntimeError, 'injected failure'):
            reader.restore_configuration(saved, [paths[k] for k in ('raw', 'quat', 'stamp')])
        self.assertEqual(state['quat'], '0')
        self.assertEqual(state['length'], '8')


if __name__ == '__main__':
    unittest.main()
