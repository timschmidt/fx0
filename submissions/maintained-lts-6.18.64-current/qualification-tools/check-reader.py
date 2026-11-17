"""Run only decoder/restoration checks and reject swapped timestamp layouts."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import struct
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
N=args.output.resolve()
N.mkdir()
W=args.repo.resolve()
file=W/'diagnostics/imu-dmp-native/read_quaternion.py'
text=file.read_text()
tree=ast.parse(text)
names={'SCAN','LEGACY_R1_SCAN'}
selected=[node for node in tree.body if
    isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets)
    or isinstance(node,ast.FunctionDef) and node.name=='decode_scan']
assert len(selected)==3
capture=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capture')
calls=[n for n in ast.walk(capture) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='decode_scan']
assert len(calls)==1 and len(calls[0].keywords)==1
assert calls[0].keywords[0].arg=='legacy_r1_timestamp'
assert ast.unparse(calls[0].keywords[0].value)=='legacy_r1_timestamp'
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='unpack_from' for n in ast.walk(capture))
old=subprocess.check_output(['git','show','664b2a505706f2bad66a3ae25eae397092cfa1d1:diagnostics/imu-dmp-native/read_quaternion.py'],cwd=W,text=True)
before=ast.parse(old)
restore=lambda t:ast.dump(next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='restore_configuration'),include_attributes=False)
assert restore(before)==restore(tree)
result=subprocess.run(['python3','-B','tests/test_mpu_dmp_reader.py','-v'],cwd=W,capture_output=True,text=True,timeout=30)
(N/'reader-tests.log').write_text(result.stdout+result.stderr)
assert result.returncode==0 and 'Ran 7 tests' in result.stderr
code=ast.unparse(ast.Module(body=selected,type_ignores=[]))
values=[(0,0,0,0,0),(1<<30,0,0,0,123456789),(-(1<<30),1,-1,17,987654321),
    (2**31-1,-2**31,123,-456,2**63-1),(5,6,7,8,-2**63),(1,2,3,4,-1),
    (-1,-2,-3,-4,16),(123,456,789,1000,24),(111,-222,333,-444,31415926535)]
records=[]
for label,source,faulty in [('candidate',code,False),
    ('maintained-slot-reverted',code.replace("SCAN = struct.Struct('=iiiiq8x')","SCAN = struct.Struct('=iiii8xq')",1),True),
    ('legacy-slot-overwritten',code.replace("LEGACY_R1_SCAN = struct.Struct('=iiii8xq')","LEGACY_R1_SCAN = struct.Struct('=iiiiq8x')",1),True)]:
    namespace={'struct':struct,'__builtins__':{}}
    exec(compile(source,'<pure-scan-decoder>','exec'),namespace)
    failures=0
    for legacy,fmt in [(False,'=iiiiq8x'),(True,'=iiii8xq')]:
        for expected in values:
            data=bytearray(struct.pack(fmt,*expected))
            if legacy:data[16:24]=b'\x5a'*8
            else:data[24:]=b'\xa5'*8
            failures+=namespace['decode_scan'](data,legacy_r1_timestamp=legacy)!=expected
    assert (failures>0 if faulty else failures==0),(label,failures)
    records.append(dict(variant=label,records=18,failures=failures))
j=dict(passed=True,reader_SHA256=hashlib.sha256(file.read_bytes()).hexdigest(),tests=7,synthetic_decode_records=18,
    regression_controls=records[1:],maintained_timestamp_offset=16,legacy_timestamp_offset=24,scan_bytes=32,
    actual_capture_calls_decoder_and_forwards_layout_flag=True,restore_function_unchanged=True,
    capture_main_firmware_and_device_operations_not_executed=True,normal_package_deployment_qualified=False,
    phone_access=False)
(N/'reader-qualification.json').write_text(json.dumps(j,indent=2)+'\n')
print(json.dumps({k:j[k] for k in ['passed','tests','synthetic_decode_records','regression_controls']}))
