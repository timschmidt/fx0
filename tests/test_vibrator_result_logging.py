"""Actual RAM logger retains completion when all console output is lost."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOGGER = ROOT/'diagnostics/vibrator/log-trial.sh'
SERVER = ROOT/'diagnostics/vibrator/serve-results.sh'


class ResultLoggingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root/'www'
        self.output.mkdir()
        self.proc = self.root/'proc'
        (self.proc/'sys/kernel/random').mkdir(parents=True)
        (self.proc/'sys/kernel/random/boot_id').write_text('fixture-boot\n')
        (self.proc/'sys/kernel/tainted').write_text('4096\n')
        (self.proc/'uptime').write_text('12.34 20.00\n')
        (self.proc/'modules').write_text('')

    def tearDown(self):
        self.temp.cleanup()

    def worker(self, code):
        program = "import sys; print('line\\n'*14, end=''); print('WORKER_END'); sys.exit(%d)" % code
        return subprocess.run(
            ['sh', str(LOGGER), str(self.output), str(self.proc), sys.executable, '-c', program],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_complete_log_and_state_survive_discarded_console(self):
        self.assertEqual(self.worker(0).returncode, 0)
        self.assertEqual((self.output/'vibrator.log').read_text(), 'line\n'*14+'WORKER_END\n')
        self.assertEqual((self.output/'vibrator-result.txt').read_text(),
                         'exit_status=0\nboot_id=fixture-boot\nuptime=12.34\ntaint=4096\n'
                         '__MODULES_BEGIN__\n__MODULES_END__\n')
        self.assertEqual(self.worker(0).returncode, 2)
        self.assertEqual((self.output/'vibrator.log').read_text().count('WORKER_END'), 1)

    def test_failed_worker_also_records_exit_and_full_output(self):
        self.assertEqual(self.worker(7).returncode, 7)
        self.assertTrue((self.output/'vibrator-result.txt').read_text().startswith('exit_status=7\n'))
        self.assertTrue((self.output/'vibrator.log').read_text().endswith('WORKER_END\n'))

    def request(self, path):
        result = subprocess.run(['sh', str(SERVER)], input=f'GET {path} HTTP/1.0\r\n\r\n',
                                env=dict(os.environ, FX0_DIAG_ROOT=str(self.output)),
                                capture_output=True, text=True, check=True)
        return result.stdout

    def test_result_routes_return_exact_bodies(self):
        self.worker(0)
        for name in ['vibrator.log', 'vibrator-result.txt', 'vibrator-state.txt']:
            with self.subTest(name=name):
                if name=='vibrator-state.txt':
                    (self.output/name).write_text('snapshot\n')
                response = self.request('/'+name)
                self.assertTrue(response.startswith('HTTP/1.0 200 OK\n'))
                self.assertEqual(response.split('\n\n', 1)[1], (self.output/name).read_text())

    def test_missing_and_unlisted_paths_are_404(self):
        for path in ['/vibrator-result.txt', '/other', '/../modules']:
            with self.subTest(path=path):
                self.assertTrue(self.request(path).startswith('HTTP/1.0 404 Not Found\n'))


if __name__=='__main__':
    unittest.main()
