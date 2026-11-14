"""Portable record and fixed-sidecar rejection checks; no device or capture."""
from pathlib import Path
import tempfile,unittest
import clock_transaction as clock

class View:
    def __init__(self,path):self.path=path
    def target(self,name):
        assert name==clock.DB
        return self.path

class ClockGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name)/'installed'
        identities={**clock.OLD,**{n:dict(version='1-r0',checksum='fixture-'+n) for n in ['busybox','postmarketos-base-systemd','systemd','musl']}}
        self.records={name:('P:'+name,'V:'+value['version'],'C:'+value['checksum'],'T:original metadata') for name,value in identities.items()}
        self.write(self.records)
        self.ops=clock.ClockUpdate.__new__(clock.ClockUpdate);self.ops.snapshot=View(self.path)
        self.ops.before=clock.database(self.path.read_bytes());self.ops.before_records=clock.package_records(self.path.read_bytes())
    def write(self,rows):self.path.write_text('\n\n'.join('\n'.join(row) for row in rows.values())+'\n\n')
    def candidate(self):
        rows={**self.records}
        for name,new in clock.NEW.items():rows[name]=tuple('V:'+new['version'] if line.startswith('V:') else 'C:'+new['checksum'] if line.startswith('C:') else line for line in rows[name])
        return rows
    def test_original_exact_candidate_and_partial_recovery(self):
        self.ops.package_state(False);rows=self.candidate();self.write(rows);self.ops.package_state(True)
        rows['swclock-offset']=self.records['swclock-offset'];self.write(rows);self.ops.package_state()
        with self.assertRaises(AssertionError):self.ops.package_state(True)
        with self.assertRaises(AssertionError):self.ops.package_state(False)
    def test_unselected_metadata_and_missing_records_are_refused_without_writes(self):
        for change in ['metadata','missing']:
            with self.subTest(change=change):
                rows=self.candidate()
                if change=='metadata':rows['musl']=rows['musl']+('T:unowned modification',)
                else:rows.pop('musl')
                self.write(rows);before=self.path.read_bytes()
                with self.assertRaises((AssertionError,KeyError)):self.ops.package_state()
                self.assertEqual(self.path.read_bytes(),before)
    def test_only_script_failure_on_known_trigger_owners_is_recoverable(self):
        for name in clock.TRIGGER_OWNERS:
            rows=self.candidate();rows[name]=rows[name]+('f:s',);self.write(rows);self.ops.package_state()
            with self.assertRaises(AssertionError):self.ops.package_state(True)
        for name,flag in [('musl','s'),('busybox','f'),('systemd','x')]:
            rows=self.candidate();rows[name]=rows[name]+('f:'+flag,);self.write(rows)
            with self.subTest(name=name,flag=flag),self.assertRaises(AssertionError):self.ops.package_state()
        rows=self.candidate();rows['busybox']=rows['busybox']+('f:s','T:unknown extra metadata');self.write(rows)
        with self.assertRaises(AssertionError):self.ops.package_state()
    def test_unknown_selected_identity_is_refused(self):
        rows=self.candidate();rows['swclock-offset']=tuple('C:untrusted' if line.startswith('C:') else line for line in rows['swclock-offset']);self.write(rows)
        with self.assertRaises(AssertionError):self.ops.package_state()
    def test_fixed_sidecar_bounds_refuse_unowned_metadata(self):
        snapshot=clock.ClockSnapshot.__new__(clock.ClockSnapshot)
        row=dict(kind='file',nlink=1,uid=0,gid=0,mode=0o644,size=1048576,xattrs={})
        snapshot.transaction_row(clock.SIDEFILE,row);snapshot.transaction_row(clock.SIDEFILE,dict(kind='absent'))
        for key,value in [('nlink',2),('uid',1),('gid',1),('mode',0o666),('size',1048577),('xattrs',{'user.extra':'00'}),('kind','symlink')]:
            with self.subTest(key=key),self.assertRaises(AssertionError):snapshot.transaction_row(clock.SIDEFILE,{**row,key:value})
if __name__=='__main__':unittest.main()
