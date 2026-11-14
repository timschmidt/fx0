# SPDX-License-Identifier: MIT
"""Read-only probe shape and observer entry barriers; no device access."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_native_probe',ROOT/'diagnostics/modem-control/passive_native_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class ProbeObserverTests(unittest.TestCase):
    def setup_probe(self,count):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        directory=Path(temporary.name)
        for number in range(count):(directory/('fixture'+str(number)+'.ko')).touch()
        texts={'/proc/sys/kernel/random/boot_id':'fixture boot','/proc/sys/kernel/osrelease':'fixture kernel',
               '/proc/sys/kernel/tainted':'0','/proc/cmdline':'root=fixture fx0.native_trial=fixture',
               '/proc/uptime':'10.0 20.0'}
        def path(value):
            value=str(value)
            if value=='/usr/lib/modules/6.18.63-fx0-vibrator-alpine':return directory
            if value not in texts:raise AssertionError('Unexpected native path request')
            return types.SimpleNamespace(read_text=lambda:texts[value])
        def output(*command):
            values={('findmnt','-n','-o','FSTYPE','-T','/usr/lib/modules'):'ext4',
                    ('systemctl','is-system-running'):'running',('pgrep','-x','sway'):'10',('pgrep','-x','lisgd'):'20'}
            return values[command]
        return path,output

    def test_native_probe_membership_shape_and_no_raw_command_line(self):
        path,output=self.setup_probe(478)
        with mock.patch.object(probe,'Path',side_effect=path),mock.patch.object(probe,'output',side_effect=output),mock.patch.object(probe,'sha',side_effect=lambda p:hashlib.sha256(str(p).encode()).hexdigest()):
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):probe.main()
        result=json.loads(stream.getvalue())
        self.assertTrue(result['trial']);self.assertEqual(result['modules_FSType'],'ext4')
        self.assertEqual(len(result['module_tree_digest']),64)
        self.assertNotIn('cmdline',result);self.assertNotIn('root=fixture',stream.getvalue())

    def test_native_probe_missing_membership_rejects_before_block_device_read(self):
        path,output=self.setup_probe(477)
        seen=[]
        def sha(value):seen.append(str(value));return '0'*64
        with mock.patch.object(probe,'Path',side_effect=path),mock.patch.object(probe,'output',side_effect=output),mock.patch.object(probe,'sha',side_effect=sha):
            with self.assertRaises(RuntimeError):probe.main()
        self.assertFalse(any(name.startswith('/dev/') for name in seen))

    def test_observer_requires_private_claim_and_rejects_optimization(self):
        source=ROOT/'diagnostics/modem-control/passive_observer.py'
        with tempfile.TemporaryDirectory() as directory:
            for flags in [[],['-O']]:
                result=subprocess.run([sys.executable,'-B',*flags,str(source),'--workspace',directory,'--usb-port','1-7'],capture_output=True,text=True,timeout=5)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('claim required' if not flags else 'Optimized Python',result.stderr)
            self.assertFalse((Path(directory)/'serial-observation.json').exists())


if __name__=='__main__':unittest.main()
