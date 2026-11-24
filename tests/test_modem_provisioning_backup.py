"""Synthetic file fixtures for bounded copy and private backup acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('provisioning_verify',ROOT/'diagnostics/modem-control/verify-provisioning-backup.py')
VERIFY=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(VERIFY)
CAPTURE=VERIFY.CAPTURE


class ProvisioningBackupTests(unittest.TestCase):
    def test_exact_copy_source_readonly_and_destination_private(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'source';target=base/'backup'
            payload=bytes(range(256))*32;source.write_bytes(payload);source.chmod(0o400)
            CAPTURE.copy_exact(source,target,len(payload),hashlib.sha256(payload).hexdigest())
            self.assertEqual(source.read_bytes(),payload)
            self.assertEqual(target.read_bytes(),payload)
            self.assertEqual(target.stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):
                CAPTURE.copy_exact(source,target,len(payload),hashlib.sha256(payload).hexdigest())
            self.assertEqual(target.read_bytes(),payload)

    def test_short_oversized_changed_and_nondevice_sources_rejected(self):
        for mode in ['short','oversized','wrong-hash','device-identity','source-symlink']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                base=Path(directory);source=base/'source';source.write_bytes(b'synthetic')
                target=base/'backup';size=len(b'synthetic');expected=hashlib.sha256(b'synthetic').hexdigest();rdev=None
                if mode=='short':size+=1
                if mode=='oversized':size-=1
                if mode=='wrong-hash':expected='0'*64
                if mode=='device-identity':rdev=0
                if mode=='source-symlink':
                    other=base/'real';source.rename(other);source.symlink_to(other)
                with self.assertRaises((ValueError,OSError)):
                    CAPTURE.copy_exact(source,target,size,expected,rdev)
                self.assertEqual(source.read_bytes(),b'synthetic')

    def fixture(self,directory):
        base=Path(directory);base.chmod(0o700)
        manifest={'schema':'fx0-current-provisioning-v1','complete':True,
                  'native_boot_id':'12345678-1234-1234-1234-123456789abc',
                  'source_devices_opened_read_only':True,'source_set_stable_before_through_after':True,
                  'snapshot_files_fsynced_and_reread':True,'native_state_unchanged':True,
                  'firmware_partition_included':False,'partitions':{}}
        for name,(number,start,sectors) in CAPTURE.PARTITIONS.items():
            path=base/(name+'.img')
            with path.open('wb') as stream:stream.truncate(sectors*512)
            path.chmod(0o600);value=CAPTURE.digest(path)
            manifest['partitions'][name]={'file':name+'.img','device':'/dev/mmcblk0p'+str(number),
                                          'start_sector':start,'sectors':sectors,'bytes':sectors*512,
                                          'sha256':value,'source_after_sha256':value}
        (base/'manifest.json').write_text(json.dumps(manifest));(base/'manifest.json').chmod(0o600)
        (base/'capture-controller.json').write_text(json.dumps({'state':'terminal','returncode':0,'BOOT_or_restore_requested':False}))
        (base/'capture-controller.json').chmod(0o600)
        return base,manifest

    def test_valid_snapshot_report_is_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            base,manifest=self.fixture(directory);report=VERIFY.verify(base)
            self.assertTrue(report['verified']);self.assertEqual(report['total_bytes'],43515904)
            self.assertFalse(report['restore_performed'])
            for row in manifest['partitions'].values():self.assertNotIn(row['sha256'],json.dumps(report))

    def test_bad_snapshot_metadata_files_permissions_and_controller_rejected(self):
        cases=['incomplete','unstable','source-writable','wrong-map','wrong-name','wrong-size','changed-file',
               'changed-digest','source-reread-mismatch','missing','symlink','world-readable','public-directory',
               'nonterminal','failed','restore-flag','firmware-included','extra-file']
        with tempfile.TemporaryDirectory() as directory:
            base,original=self.fixture(directory)
            manifest_path=base/'manifest.json';controller_path=base/'capture-controller.json'
            original_controller=controller_path.read_bytes();data_path=base/'fsc.img'
            for mode in cases:
                with self.subTest(mode=mode):
                    manifest=copy.deepcopy(original);controller=json.loads(original_controller)
                    if mode=='incomplete':manifest['complete']=False
                    if mode=='unstable':manifest['source_set_stable_before_through_after']=False
                    if mode=='source-writable':manifest['source_devices_opened_read_only']=False
                    if mode=='wrong-map':manifest['partitions']['fsc']['start_sector']+=1
                    if mode=='wrong-name':manifest['partitions']['fsc']['file']='../other'
                    if mode=='wrong-size':manifest['partitions']['fsc']['bytes']-=1
                    if mode=='changed-digest':manifest['partitions']['fsc']['sha256']='0'*64
                    if mode=='source-reread-mismatch':manifest['partitions']['fsc']['source_after_sha256']='0'*64
                    if mode=='changed-file':
                        with data_path.open('r+b') as stream:stream.write(b'X')
                    if mode=='missing':data_path.rename(base/'moved.img')
                    if mode=='symlink':data_path.rename(base/'moved.img');data_path.symlink_to(base/'moved.img')
                    if mode=='world-readable':data_path.chmod(0o644)
                    if mode=='public-directory':base.chmod(0o755)
                    if mode=='nonterminal':controller['state']='running'
                    if mode=='failed':controller['returncode']=1
                    if mode=='restore-flag':controller['BOOT_or_restore_requested']=True
                    if mode=='firmware-included':manifest['firmware_partition_included']=True
                    if mode=='extra-file':(base/'unexpected.img').write_bytes(b'')
                    manifest_path.write_text(json.dumps(manifest));controller_path.write_text(json.dumps(controller))
                    with self.assertRaises(ValueError):VERIFY.verify(base)
                    if mode in ['missing','symlink']:
                        if data_path.is_symlink():data_path.unlink()
                        (base/'moved.img').rename(data_path)
                    if mode=='changed-file':
                        with data_path.open('r+b') as stream:stream.write(b'\0')
                    if mode=='world-readable':data_path.chmod(0o600)
                    if mode=='public-directory':base.chmod(0o700)
                    if mode=='extra-file':(base/'unexpected.img').unlink()


if __name__=='__main__':unittest.main()
