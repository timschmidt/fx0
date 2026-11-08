"""Package export integrity and refusal checks; never builds or accesses USB."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import prepare_kernel_package as PACKAGE


class PackageExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root/'base.tar.gz'
        self.archive.write_bytes(b'pinned archive fixture')
        self.archive_hash = hashlib.sha512(self.archive.read_bytes()).hexdigest()
        self.config = self.root/'config'
        self.config.write_text('CONFIG_LOCALVERSION="-fixture"\n')
        self.manifest_path = self.root/'manifest.json'
        self.manifest = {'schema': 1, 'base': {'commit': 'a'*40,
                         'repository': 'https://github.com/timschmidt/fx0-linux.git'},
                         'profiles': {'cpr': {'patches': ['second.diff', 'first.diff']}},
                         'sha256': {}}
        for name in self.manifest['profiles']['cpr']['patches']:
            p = self.root/name
            p.write_text('diff --git a/file b/file\n' + name + '\n')
            self.manifest['sha256'][name] = hashlib.sha256(p.read_bytes()).hexdigest()
        self.output = self.root/'port'
        self.template = ROOT/'configs/linux-postmarketos-qcom-msm8226.APKBUILD.in'

    def export(self):
        self.manifest_path.write_text(json.dumps(self.manifest))
        return PACKAGE.export(self.manifest_path, 'cpr', self.config, self.template,
                              self.archive, self.archive_hash, self.output, 53,
                              root=self.root)

    def test_shell_recipe_preserves_series_order_and_every_checksum(self):
        report = self.export()
        subprocess.run(['sh', '-n', str(self.output/'APKBUILD')], check=True)
        shell = 'arch=armv7; . "$1"; printf "%s\\n" "$pkgrel" "$_commit" "$source"; printf "__SUMS__\\n%s\\n" "$sha512sums"'
        actual = subprocess.run(['sh', '-c', shell, 'sh', str(self.output/'APKBUILD')],
                                check=True, capture_output=True, text=True).stdout
        self.assertTrue(actual.startswith('53\n' + 'a'*40 + '\n'))
        sources, sums = actual.split('__SUMS__\n')
        self.assertLess(sources.index('second.patch'), sources.index('first.patch'))
        lines = [l.split() for l in sums.splitlines() if l.strip()]
        self.assertEqual(len(lines), 4)
        for wanted, name in lines:
            path = self.archive if name.startswith('linux-fx0-') else self.output/name
            self.assertEqual(hashlib.sha512(path.read_bytes()).hexdigest(), wanted)
        self.assertEqual(report['patch_order'], ['second.patch', 'first.patch'])

    def test_corrupt_archive_never_creates_output(self):
        self.archive.write_bytes(b'corrupted archive')
        with self.assertRaisesRegex(ValueError, 'Source archive checksum'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_prepare_copies_config_before_normalizing_capabilities(self):
        self.export()
        work = self.root/'build'
        work.mkdir()
        binary = self.root/'bin'
        binary.mkdir()
        make = binary/'make'
        make.write_text('#!/bin/sh\nset -eu\ntest -s .config\nprintf "%s\\n" "$@" > make-arguments\n')
        make.chmod(0o755)
        shell = ('arch=armv7; srcdir="$1"; PATH="$2:$PATH"; '
                 '. "$srcdir/APKBUILD"; default_prepare() { :; }; prepare')
        subprocess.run(['sh', '-c', shell, 'sh', str(self.output), str(binary)],
                       cwd=work, check=True)
        self.assertEqual((work/'.config').read_bytes(), self.config.read_bytes())
        self.assertEqual((work/'make-arguments').read_text().splitlines(),
                         ['ARCH=arm', 'LLVM=1', 'LOCALVERSION=', 'olddefconfig'])

    def test_corrupt_patch_never_creates_output(self):
        (self.root/'first.diff').write_text('changed patch')
        with self.assertRaisesRegex(ValueError, 'Patch checksum'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_path_escape_and_duplicate_never_create_output(self):
        for patches in [['../outside.diff'], ['first.diff', 'first.diff']]:
            self.manifest['profiles']['cpr']['patches'] = patches
            with self.assertRaises(ValueError):
                self.export()
            self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output/'keep'
        sentinel.write_text('retained')
        with self.assertRaisesRegex(ValueError, 'Output already exists'):
            self.export()
        self.assertEqual(sentinel.read_text(), 'retained')

    def test_wrong_repository_cannot_silently_use_template_url(self):
        self.manifest['base']['repository'] = 'https://example.invalid/another-kernel.git'
        with self.assertRaisesRegex(ValueError, 'Unsupported source repository'):
            self.export()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
