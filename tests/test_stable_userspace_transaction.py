"""Filesystem safety checks; actual APK/controller qualification runs on ARM."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'diagnostics/stable-update/stable_transaction.py'
SPEC=importlib.util.spec_from_file_location('stable_transaction',SOURCE)
controller=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(controller)


class RecoveryGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='stable-controller-guard-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.a='/usr/bin/owned';self.b='/usr/bin/owned-alias';self.new='/usr/bin/new-owned'
        self.protected='/usr/lib/modules/protected.ko'
        contents={self.a:b'original signed software',controller.LOCK:b'',controller.WORLD:b'exact original world',
                  '/usr/bin/unselected':b'preserve unrelated executable',self.protected:b'preserve kernel module'}
        for name,body in contents.items():
            path=self.target(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
            path.chmod(0o600 if name==controller.LOCK else 0o644)
        os.link(self.target(self.a),self.target(self.b))
        self.target(controller.EXECUTOR).mkdir(parents=True)
        names={'/'+str(p.relative_to(self.root)) for p in self.root.rglob('*')}
        rows={}
        for name in names:
            path=self.target(name);st=path.lstat()
            row=dict(kind='directory' if path.is_dir() else 'file',mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,
                mtime_ns=st.st_mtime_ns,xattrs={k:os.getxattr(path,k).hex() for k in os.listxattr(path)})
            if row['kind']=='file':row.update(size=st.st_size,sha256=controller.sha(path),nlink=st.st_nlink)
            rows[name]=row
        rows[self.b]['hardlink_to']=self.a;rows[self.new]=dict(kind='absent')
        self.manifest=dict(paths=rows,directory_membership={n:sorted(p.name for p in self.target(n).iterdir()) for n,r in rows.items() if r['kind']=='directory'})
        self.body=b'new authenticated candidate bytes'
        expected=dict(kind='file',mode=0o644,uid=os.getuid(),gid=os.getgid(),mtime_ns=1794000000000000000,
            xattrs={},size=len(self.body),sha256=hashlib.sha256(self.body).hexdigest(),nlink=2)
        self.scope=dict(mutable_files=[self.a,self.b,self.new],mutable_directories=['/usr/bin',controller.EXECUTOR],
            candidate_payloads={self.a:dict(expected=expected),self.b:dict(expected=dict(expected,hardlink_to=self.a)),
                self.new:dict(expected=dict(expected,nlink=1))},config_paths=[],config_sidecars=[],config_upstream_unchanged=[],
            mutable_state_files=[],new_file_xattrs={self.new:rows[self.a]['xattrs']},directory_candidate_acl={},known_executor_scripts={})
        self.snapshot=controller.Snapshot(self.root,self.manifest,self.scope,{self.a:contents[self.a]})

    def target(self,name):return self.root/name.lstrip('/')

    def candidate(self):
        controller.atomic(self.target(self.a),self.body,0o644)
        self.target(self.b).unlink();os.link(self.target(self.a),self.target(self.b))
        self.target(self.new).write_bytes(self.body);self.target(self.new).chmod(0o644)
        for name in [self.a,self.b,self.new]:os.utime(self.target(name),ns=(1794000000000000000,1794000000000000000))

    def test_recovers_hardlinks_metadata_and_namespace_without_touching_protected_inode(self):
        lock=self.target(controller.LOCK).stat().st_ino;protected=self.target(self.protected).stat().st_ino
        self.candidate()
        with self.snapshot.locked():
            self.assertTrue(self.snapshot.verify_candidate())
            self.snapshot.restore(hooks_terminal=True)
            self.assertEqual(self.snapshot.verify(),[]);self.snapshot.locks()
        self.assertEqual(self.target(self.a).read_bytes(),b'original signed software')
        self.assertEqual(self.target(self.a).stat().st_ino,self.target(self.b).stat().st_ino)
        self.assertEqual(self.target(controller.LOCK).stat().st_ino,lock)
        self.assertEqual(self.target(self.protected).stat().st_ino,protected)
        self.assertFalse(self.target(self.new).exists())

    def test_unselected_change_refuses_before_any_restore_write(self):
        self.candidate();self.target('/usr/bin/unselected').write_bytes(b'external change')
        with self.snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Unowned state changed'):self.snapshot.restore(hooks_terminal=True)
        self.assertEqual(self.target(self.a).read_bytes(),self.body);self.assertTrue(self.target(self.new).exists())

    def test_unknown_owned_bytes_are_preserved(self):
        self.candidate();self.target(self.a).write_bytes(b'unknown external bytes')
        with self.snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Unrecognised owned payload'):self.snapshot.restore(hooks_terminal=True)
        self.assertEqual(self.target(self.a).read_bytes(),b'unknown external bytes')

    def test_active_hooks_refuse_recovery(self):
        self.candidate()
        with self.snapshot.locked():
            with self.assertRaises(AssertionError):self.snapshot.restore(hooks_terminal=False)
        self.assertEqual(self.target(self.a).read_bytes(),self.body)

    def test_out_of_scope_hardlink_refuses_recovery(self):
        self.candidate();os.link(self.target(self.a),self.root/'outside-scope-alias')
        with self.snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'out-of-scope hardlink'):self.snapshot.restore(hooks_terminal=True)
        self.assertEqual(self.target(self.a).read_bytes(),self.body)

    def test_lock_reopen_is_detected_as_lost_posix_lock(self):
        with self.assertRaisesRegex(AssertionError,'Both real APK lock types'):
            with self.snapshot.locked():
                fd=os.open(self.target(controller.LOCK),os.O_RDONLY);os.close(fd)

    def test_lock_and_kernel_paths_cannot_enter_recovery_write_set(self):
        for name in [controller.LOCK,self.protected,'/usr/bin/treescan','/etc/ssh/ssh_host_ed25519_key']:
            scope=dict(self.scope,mutable_files=self.scope['mutable_files']+[name])
            with self.assertRaises(AssertionError):controller.Snapshot(self.root,self.manifest,scope,{self.a:b'original signed software'})
        with self.assertRaisesRegex(AssertionError,'Live root requires'):controller.Snapshot('/',self.manifest,self.scope,{})

    def test_symlink_ancestor_is_refused(self):
        (self.root/'redirect').symlink_to('/tmp')
        with self.assertRaisesRegex(AssertionError,'Symlink ancestor'):self.snapshot.target('/redirect/outside')

    def test_unknown_executor_preserves_known_and_unknown_entries(self):
        directory=self.target(controller.EXECUTOR);known=b'known signed software script'
        (directory/'000-unknown').write_bytes(b'unknown');(directory/'known.trigger').write_bytes(known)
        ops=controller.StableUpdate.__new__(controller.StableUpdate);ops.snapshot=self.snapshot
        ops.scope=dict(known_executor_scripts={'known.trigger':dict(size=len(known),sha256=hashlib.sha256(known).hexdigest())})
        ops.hooks_terminal=lambda:True
        with self.snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Unknown executor'):ops.cleanup_executor()
        self.assertEqual(sorted(p.name for p in directory.iterdir()),['000-unknown','known.trigger'])

    def retained_snapshot(self):
        name='/usr/bin/unselected'
        original_db=(b'P:distro-release\nV:1-r0\nC:original-distro-control\n'
                     b'r:alpine-release\nF:usr/bin\nR:unselected\n\n')
        self.target(controller.DB).write_bytes(original_db)
        self.manifest['paths'][controller.DB]=self.snapshot.row(controller.DB)
        self.manifest['paths']['/usr/lib/apk/db']=self.snapshot.row('/usr/lib/apk/db')
        self.manifest['directory_membership']['/usr/lib/apk/db'].append('installed')
        spec=importlib.util.spec_from_file_location('ownership',SOURCE.with_name('apk_payload_ownership.py'))
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        incoming={'alpine-release':dict(version='2-r0',checksum='candidate-control',origin='alpine-base',replaces=[],priority=0)}
        candidates=dict(self.scope['candidate_payloads'])
        candidates[name]=dict(packages=['alpine-release'],expected=dict(candidates[self.a]['expected']))
        # The remaining candidate paths belong to their current package, so the
        # ownership resolver need only decide the genuinely colliding path.
        retained=helper.retained_payloads(original_db.decode(),{name:candidates[name]},incoming)
        for path in [self.a,self.b,self.new]:candidates[path]['packages']=['alpine-release']
        scope=dict(self.scope,mutable_files=self.scope['mutable_files']+[controller.DB],
                   mutable_state_files=[controller.DB],candidate_payloads=candidates,
                   retained_owner_payloads=retained,incoming_ownership=incoming,
                   ownership_helper_sha256=controller.sha(SOURCE.with_name('apk_payload_ownership.py')))
        snapshot=controller.Snapshot(self.root,self.manifest,scope,
            {self.a:b'original signed software',controller.DB:original_db})
        return snapshot,name

    def test_retained_distro_payload_is_checked_as_immutable_not_as_incoming_bytes(self):
        snapshot,name=self.retained_snapshot();self.candidate()
        before=self.target(name).read_bytes()
        with snapshot.locked():
            self.assertTrue(snapshot.verify_candidate())
            snapshot.restore(hooks_terminal=True)
        self.assertEqual(self.target(name).read_bytes(),before)
        self.assertNotIn(name,snapshot.files)

    def test_retained_distro_payload_change_refuses_before_recovery_writes(self):
        snapshot,name=self.retained_snapshot();self.candidate()
        self.target(name).write_bytes(b'candidate or external replacement of distro file')
        with snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Unowned state changed'):
                snapshot.restore(hooks_terminal=True)
        self.assertEqual(self.target(self.a).read_bytes(),self.body)

    def test_retained_owner_database_change_fails_even_with_original_file_bytes(self):
        snapshot,name=self.retained_snapshot();self.candidate()
        self.target(controller.DB).write_bytes(self.target(controller.DB).read_bytes().replace(b'P:distro-release',b'P:alpine-release'))
        with snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Retained file owner changed'):
                snapshot.verify_candidate()

    def test_retained_owner_replacement_rule_change_refuses_recovery_writes(self):
        snapshot,name=self.retained_snapshot();self.candidate()
        path=self.target(controller.DB)
        path.write_bytes(path.read_bytes().replace(b'r:alpine-release',b'r:other-package'))
        with snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Retained owner replacement metadata changed'):
                snapshot.restore(hooks_terminal=True)
        self.assertEqual(self.target(self.a).read_bytes(),self.body)

    def symlink_snapshot(self):
        self.candidate()
        self.target(self.new).unlink();self.target(self.new).symlink_to('owned')
        expected=dict(kind='symlink',target='owned',mode=0o777,uid=os.getuid(),gid=os.getgid(),
                      mtime_ns=1794000000000000000)
        candidates=dict(self.scope['candidate_payloads']);candidates[self.new]=dict(expected=expected)
        snapshot=controller.Snapshot(self.root,self.manifest,dict(self.scope,candidate_payloads=candidates),
                                     {self.a:b'original signed software'})
        now=time.time_ns();snapshot.install_window=(now-2_000_000_000,now+2_000_000_000)
        return snapshot

    def test_apk_symlink_creation_time_is_bound_to_owned_upgrade_not_archive_header(self):
        snapshot=self.symlink_snapshot()
        self.assertNotEqual(self.target(self.new).lstat().st_mtime_ns,snapshot.candidates[self.new]['mtime_ns'])
        with snapshot.locked():self.assertTrue(snapshot.verify_candidate())

    def test_symlink_timestamp_outside_owned_upgrade_is_rejected(self):
        snapshot=self.symlink_snapshot();stamp=snapshot.install_window[0]-1_000_000_000
        os.utime(self.target(self.new),ns=(stamp,stamp),follow_symlinks=False)
        with snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Candidate payload differs'):
                snapshot.verify_candidate()

    def test_missing_or_reversed_owned_timestamp_window_is_rejected(self):
        snapshot=self.symlink_snapshot()
        for window,error in [(None,'Missing owned APK timestamp window'),
                             ((2,1),'Invalid owned APK timestamp window')]:
            snapshot.install_window=window
            with snapshot.locked():
                with self.assertRaisesRegex(AssertionError,error):snapshot.verify_candidate()

    def test_symlink_target_is_still_exact_inside_valid_upgrade_window(self):
        snapshot=self.symlink_snapshot()
        self.target(self.new).unlink();self.target(self.new).symlink_to('not-the-signed-target')
        with snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Unrecognised owned payload'):
                snapshot.verify_candidate()

    def test_regular_file_still_requires_exact_signed_archive_timestamp(self):
        snapshot=self.symlink_snapshot();stamp=time.time_ns()
        os.utime(self.target(self.a),ns=(stamp,stamp))
        with snapshot.locked():
            with self.assertRaisesRegex(AssertionError,'Candidate payload differs'):
                snapshot.verify_candidate()


if __name__=='__main__':unittest.main()
