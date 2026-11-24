# SPDX-License-Identifier: MIT
"""Input/refusal controls for the host-only locked passive image workflow."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'diagnostics/modem-control'
spec = importlib.util.spec_from_file_location('passive_image_inputs', HERE / 'build-passive-r1-image.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PassiveImageInputs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.output = self.base / 'output'

    def invoke(self, tool, arguments, optimize=False):
        command = [sys.executable, '-B'] + (['-O'] if optimize else [])
        result = subprocess.run(command + [str(HERE / tool), *map(str, arguments)],
                                capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists(), result.stdout + result.stderr)
        return result

    def test_locked_file_rejects_changed_size_digest_symlink_and_other_writes(self):
        path = self.base / 'material'
        path.write_bytes(b'body')
        expected = {'bytes': 4, 'SHA256': builder.sha(b'body')}
        path.chmod(0o600)
        self.assertEqual(builder.locked_file(path, expected), b'body')
        for value in (b'longer', b'edit'):
            with self.subTest(value=value):
                path.write_bytes(value)
                with self.assertRaises(ValueError):
                    builder.locked_file(path, expected)
        path.write_bytes(b'body')
        link = self.base / 'link'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            builder.locked_file(link, expected)
        path.chmod(0o622)
        with self.assertRaises(ValueError):
            builder.locked_file(path, expected)
        self.assertEqual(path.read_bytes(), b'body')

    def test_material_roster_rejected_without_output(self):
        materials = self.base / 'materials'
        materials.mkdir()
        for name in (None, 'unexpected-file'):
            with self.subTest(name=name):
                if name:
                    (materials / name).write_bytes(b'extra')
                result = self.invoke('build-passive-r1-image.py',
                                     ['--materials', materials, '--output-dir', self.output])
                self.assertIn(b'roster differs', result.stderr)

    def test_all_launchers_reject_optimized_python_before_output(self):
        for tool, arguments in {
            'build-passive-r1-image.py': ['--materials', self.base],
            'build-passive-r1-helpers.py': ['--native-root', self.base, '--target-root', self.base],
            'build-passive-r1-dtb.py': ['--kernel-source', self.base],
            'prepare-passive-r1-materials.py': ['--apk-dir', self.base, '--helpers', self.base,
                                                 '--passive-dtb', self.base / 'missing'],
        }.items():
            with self.subTest(tool=tool):
                result = self.invoke(tool, [*arguments, '--output-dir', self.output], optimize=True)
                self.assertIn(b'Optimized Python is forbidden', result.stderr)

    def test_wrong_archive_rejected_before_unpack_or_output(self):
        import json
        lock = json.loads((ROOT / 'manifests/passive-r1-materials.json').read_text())
        for name in lock['archives']:
            (self.base / name).write_bytes(b'not a gzip archive')
        result = self.invoke('prepare-passive-r1-materials.py',
                             ['--apk-dir', self.base, '--helpers', self.base,
                              '--passive-dtb', self.base / 'missing', '--output-dir', self.output])
        self.assertIn(b'Input size differs from lock', result.stderr)

    def test_wrong_root_inventory_rejected_before_compiler_or_output(self):
        database = self.base / 'lib/apk/db/installed'
        database.parent.mkdir(parents=True)
        database.write_bytes(b'wrong inventory')
        result = self.invoke('build-passive-r1-helpers.py',
                             ['--native-root', self.base, '--target-root', self.base,
                              '--output-dir', self.output])
        self.assertIn(b'Root database differs', result.stderr)

    def test_wrong_board_rejected_before_patch_or_output(self):
        board = self.base / 'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts'
        board.parent.mkdir(parents=True)
        board.write_bytes(b'wrong source')
        result = self.invoke('build-passive-r1-dtb.py',
                             ['--kernel-source', self.base, '--output-dir', self.output])
        self.assertIn(b'Board source differs', result.stderr)


if __name__ == '__main__':
    unittest.main()
