import copy
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile
import subprocess
import signal
import sys
import tracemalloc
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'diagnostics' / 'stable-update'
sys.path.insert(0, str(SOURCE))
from stream_restore import StreamRollback


class StreamRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'private'
        self.root.mkdir()
        self.uid, self.gid = os.getuid(), os.getgid()
        self.rows = {'/data':self.directory(), '/data/keep':self.file(b'kept',2),
                     '/data/alias':dict(self.file(b'kept',2),hardlink_to='/data/keep'),
                     '/data/change':self.file(b'new'),
                     '/data/link':dict(self.directory(),kind='symlink',mode=0o777,target='change'),
                     '/data/absent':dict(kind='absent')}
        self.rows['/data/keep']['data_source'] = dict(base_archive_member='data/keep')
        self.rows['/data/change']['data_source'] = dict(delta_archive_member='data/change')
        self.manifest = dict(format='fx0-stable-file-delta-v2',paths=self.rows,
                             directory_membership={'/data':['alias','change','keep','link']})
        self.archives({'data/keep':b'kept'},{'data/change':b'new'})

    def directory(self):
        return dict(kind='directory',mode=0o755,uid=self.uid,gid=self.gid,mtime_ns=1234567890123456789,xattrs={})

    def file(self, data, links=1):
        return dict(kind='file',mode=0o640,uid=self.uid,gid=self.gid,mtime_ns=1234567890123456789,
                    xattrs={},size=len(data),sha256=hashlib.sha256(data).hexdigest(),nlink=links)

    def archives(self, base, delta):
        for name, bodies in [('base.tar.gz',base),('delta.tar.gz',delta)]:
            with tarfile.open(self.base / name,'w:gz') as archive:
                for path, data in bodies.items():
                    info = tarfile.TarInfo(path)
                    info.size = len(data)
                    archive.addfile(info,io.BytesIO(data))
        self.manifest['base_archive_sha256'] = hashlib.sha256((self.base/'base.tar.gz').read_bytes()).hexdigest()
        self.delta_sha = hashlib.sha256((self.base/'delta.tar.gz').read_bytes()).hexdigest()

    def open(self, **kwargs):
        return StreamRollback(self.root,self.manifest,self.base/'base.tar.gz',self.base/'delta.tar.gz',self.delta_sha,
                              skip_selinux_for_host_fixture=True,**kwargs)

    def test_complete_restore_modes_ns_mtimes_links_xattrs_and_membership(self):
        self.rows['/data/change']['xattrs'] = {'user.fx0':'74657374'}
        with self.open() as restore:
            restore.restore()
            restore.verify()
        self.assertEqual((self.root/'data/change').read_bytes(),b'new')
        self.assertEqual(os.getxattr(self.root/'data/change','user.fx0'),b'test')
        self.assertEqual((self.root/'data/keep').stat().st_ino,(self.root/'data/alias').stat().st_ino)

    def test_interruption_and_resume_match_complete_capture(self):
        with self.open() as restore:
            with self.assertRaises(InterruptedError):
                restore.restore(stop_after=2)
        with self.open() as restore:
            restore.restore()
            restore.verify()
        self.assertFalse(list(self.root.rglob('.fx0-stream-restore-*')))

    def test_corrupt_referenced_body_refused_before_any_write(self):
        self.archives({'data/keep':b'kept'},{'data/change':b'bad'})
        with self.assertRaisesRegex(AssertionError,'Archived body differs'):
            self.open()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_changed_archive_after_validation_refused_before_restore(self):
        with self.open() as restore:
            with (self.base/'delta.tar.gz').open('ab') as output:
                output.write(b'x')
            with self.assertRaisesRegex(AssertionError,'Source archive changed'):
                restore.restore()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_parent_symlink_cannot_escape_private_root(self):
        outside = self.base/'outside'
        outside.mkdir()
        (outside/'keep').write_bytes(b'outside must survive')
        (self.root/'data').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(AssertionError,'Symlink in canonical parent'):
            self.open()
        self.assertEqual((outside/'keep').read_bytes(),b'outside must survive')

    def test_external_hardlink_refused_before_restore(self):
        (self.root/'data').mkdir()
        (self.base/'outside').write_bytes(b'old')
        os.link(self.base/'outside',self.root/'data/change')
        with self.open() as restore:
            with self.assertRaisesRegex(AssertionError,'Existing hardlink crosses'):
                restore.restore()
        self.assertEqual((self.base/'outside').read_bytes(),b'old')

    def test_wrong_internal_hardlink_group_is_split(self):
        # Two independently captured equal bodies must remain separate inodes.
        self.rows['/data/first'] = dict(self.file(b'new'),data_source=dict(base_archive_member='data/first'))
        self.manifest['directory_membership']['/data'].append('first')
        self.manifest['directory_membership']['/data'].sort()
        self.archives({'data/keep':b'kept','data/first':b'new'},{'data/change':b'new'})
        (self.root/'data').mkdir()
        (self.root/'data/first').write_bytes(b'new')
        os.link(self.root/'data/first',self.root/'data/change')
        with self.open() as restore:
            restore.restore()
            restore.verify()
        self.assertNotEqual((self.root/'data/first').stat().st_ino,(self.root/'data/change').stat().st_ino)

    def test_unknown_directory_entry_preserved_and_verification_refuses(self):
        (self.root/'data').mkdir()
        (self.root/'data/unknown').write_bytes(b'preserve')
        with self.open() as restore:
            restore.restore()
            with self.assertRaisesRegex(AssertionError,'Directory membership differs'):
                restore.verify()
        self.assertEqual((self.root/'data/unknown').read_bytes(),b'preserve')

    def test_live_root_refused(self):
        with self.assertRaises(AssertionError):
            StreamRollback('/',self.manifest,self.base/'base.tar.gz',self.base/'delta.tar.gz',self.delta_sha)

    def test_large_bodies_do_not_accumulate_in_memory(self):
        data = b'fx0-stream-memory-probe\n' * (12*1024**2//24)
        self.rows['/data/keep'].update(self.file(data,2))
        self.rows['/data/alias'].update(self.file(data,2))
        self.rows['/data/change'].update(self.file(data))
        self.archives({'data/keep':data},{'data/change':data})
        tracemalloc.start()
        try:
            with self.open() as restore:
                restore.restore()
                restore.verify()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak,8*1024**2)

    def test_authenticated_partial_copy_is_resumed(self):
        (self.root/'data').mkdir()
        with self.open() as restore:
            partial = restore.partial_path('/data/change')
        partial.write_bytes(b'n')
        partial.chmod(0o600)
        with self.open() as restore:
            restore.restore()
            restore.verify()
        self.assertFalse(partial.exists())

    def test_unrecognised_partial_prefix_is_preserved_before_any_write(self):
        (self.root/'data').mkdir()
        with self.open() as restore:
            partial = restore.partial_path('/data/change')
        partial.write_bytes(b'x')
        partial.chmod(0o600)
        with self.assertRaisesRegex(AssertionError,'not an authenticated body prefix'):
            self.open()
        self.assertEqual(partial.read_bytes(),b'x')
        self.assertEqual(list((self.root/'data').iterdir()),[partial])

    def test_partial_symlink_cannot_redirect_a_copy(self):
        (self.root/'data').mkdir()
        with self.open() as restore:
            partial = restore.partial_path('/data/change')
        outside = self.base/'outside'
        outside.write_bytes(b'preserve')
        partial.symlink_to(outside)
        with self.assertRaisesRegex(AssertionError,'Unrecognised private restore partial'):
            self.open()
        self.assertEqual(outside.read_bytes(),b'preserve')

    def test_actual_owned_process_SIGKILL_before_rename_can_resume(self):
        import json
        manifest_path = self.base/'manifest.json'
        manifest_path.write_text(json.dumps(self.manifest))
        script = r'''import json,os,signal,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from stream_restore import StreamRollback
base=Path(sys.argv[2]);original=os.fsync
def terminate_before_rename(fd):
 if '.fx0-stream-restore-' in os.readlink('/proc/self/fd/'+str(fd)):
  os.kill(os.getpid(),signal.SIGKILL)
 original(fd)
os.fsync=terminate_before_rename
with StreamRollback(base/'private',json.loads((base/'manifest.json').read_text()),base/'base.tar.gz',base/'delta.tar.gz',sys.argv[3],skip_selinux_for_host_fixture=True) as restore:
 restore.restore()
'''
        result = subprocess.run([sys.executable,'-B','-c',script,str(SOURCE),str(self.base),self.delta_sha],
                                capture_output=True,timeout=20)
        self.assertEqual(result.returncode,-signal.SIGKILL,result.stderr.decode())
        self.assertTrue(list(self.root.rglob('.fx0-stream-restore-*')))
        with self.open() as restore:
            restore.restore()
            restore.verify()
        self.assertFalse(list(self.root.rglob('.fx0-stream-restore-*')))


if __name__ == '__main__':
    unittest.main()
