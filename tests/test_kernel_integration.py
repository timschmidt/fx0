"""Exercise preparation ordering and refusal paths against real Git/patch."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT/'scripts/prepare_kernel_integration.py')
PREPARE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PREPARE)


class KernelPreparationTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'local/kernel-preparation').mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'local/kernel-preparation')
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        self.source.mkdir()
        self.git('init', '-q')
        (self.source/'version').write_text('one\n')
        self.git('add', 'version')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'base')
        base = self.git('rev-parse', 'HEAD').strip()
        (self.root/'config').write_text('reference configuration\n')
        self.patch('first.diff','one','two')
        self.patch('second.diff','two','three')
        self.manifest = {
            'schema':1,'base':{'commit':base},
            'configuration':{'path':'config','sha256':PREPARE.digest(self.root/'config')},
            'profiles':{'r50':{'patches':['first.diff']},
                        'cpr':{'patches':['first.diff','second.diff']}},
            'sha256':{name:PREPARE.digest(self.root/name) for name in ['first.diff','second.diff']},
        }
        self.path = self.root/'manifest.json'

    def tearDown(self):
        self.temp.cleanup()

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.source,text=True,
                                       stderr=subprocess.PIPE)

    def patch(self,name,before,after,path='version'):
        (self.root/name).write_text(f'diff --git a/{path} b/{path}\n'
                                   f'--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n'
                                   f'-{before}\n+{after}\n')

    def prepare(self,profile='cpr'):
        self.path.write_text(json.dumps(self.manifest))
        return PREPARE.prepare(self.source,profile,self.path,self.root)

    def assert_pristine(self):
        self.assertEqual((self.source/'version').read_text(),'one\n')
        self.assertFalse(self.git('status','--porcelain').strip())

    def test_ordered_series_profile_and_receipt(self):
        report = self.prepare()
        self.assertEqual((self.source/'version').read_text(),'three\n')
        self.assertEqual(report['files_sha256']['version'],
                         hashlib.sha256(b'three\n').hexdigest())
        self.assertEqual(len(report['patches']),2)
        with self.assertRaisesRegex(ValueError,'no tracked changes'):
            self.prepare()
        self.assertEqual((self.source/'version').read_text(),'three\n')

    def test_mixed_patch_records_plain_unified_added_header(self):
        patch = self.root/'first.diff'
        patch.write_text(patch.read_text() +
                         '--- /dev/null\n+++ b/added-helper.h\n'
                         '@@ -0,0 +1,2 @@\n+#define FIXTURE_VALUE 7\n+\n')
        self.manifest['sha256']['first.diff'] = PREPARE.digest(patch)
        report = self.prepare('r50')
        self.assertEqual(set(report['files_sha256']), {'version', 'added-helper.h'})
        self.assertEqual(report['files_sha256']['added-helper.h'],
                         hashlib.sha256(b'#define FIXTURE_VALUE 7\n\n').hexdigest())
        self.assertEqual((self.source/'added-helper.h').read_bytes(),
                         b'#define FIXTURE_VALUE 7\n\n')

    def test_r50_profile_excludes_followup(self):
        report = self.prepare('r50')
        self.assertEqual((self.source/'version').read_text(),'two\n')
        self.assertEqual(list(report['patches']),['first.diff'])

    def test_checksum_failures_do_not_modify_source(self):
        for target in ['second.diff','config']:
            saved = (self.root/target).read_bytes()
            (self.root/target).write_bytes(saved+b'changed\n')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                self.prepare()
            self.assert_pristine()
            (self.root/target).write_bytes(saved)

    def test_second_patch_conflict_is_found_before_first_patch_is_applied(self):
        self.patch('second.diff','different','three')
        self.manifest['sha256']['second.diff'] = PREPARE.digest(self.root/'second.diff')
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assert_pristine()
        self.assertFalse(list((self.root/'local/kernel-preparation').iterdir()))

    def test_dirty_or_wrong_base_refused(self):
        (self.source/'untracked').write_text('keep me\n')
        with self.assertRaisesRegex(ValueError,'untracked files'):
            self.prepare()
        self.assertEqual((self.source/'untracked').read_text(),'keep me\n')
        (self.source/'untracked').unlink()
        self.manifest['base']['commit'] = '0'*40
        with self.assertRaisesRegex(ValueError,'pinned base'):
            self.prepare()
        self.assert_pristine()

    def test_unsafe_paths_and_duplicate_entries_refused(self):
        self.patch('second.diff','one','three','../../victim')
        self.manifest['sha256']['second.diff'] = PREPARE.digest(self.root/'second.diff')
        with self.assertRaisesRegex(ValueError,'Unsafe manifest path'):
            self.prepare()
        self.assert_pristine()
        self.manifest['profiles']['cpr']['patches'] = ['first.diff','first.diff']
        with self.assertRaisesRegex(ValueError,'Duplicate patch'):
            self.prepare()
        self.assert_pristine()


if __name__ == '__main__':
    unittest.main()
