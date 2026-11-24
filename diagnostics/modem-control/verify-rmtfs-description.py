#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host-only verification of a separate unbooted Fx0 RMTFS description."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('modem_description', HERE/'verify-description.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
NODE = '/reserved-memory/rmtfs@fd80000'


def properties(path):
    MOD.Fdt(path)  # Check the complete FDT before parsing tokens.
    raw = path.read_bytes()
    header = struct.unpack_from('>10I', raw)
    offset, strings = header[2], header[3]
    stack, result = [], {}
    while True:
        token = struct.unpack_from('>I', raw, offset)[0]; offset += 4
        if token == 1:
            end = raw.index(0, offset); stack.append(raw[offset:end].decode())
            offset = (end + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, nameoff = struct.unpack_from('>II', raw, offset); offset += 8
            end = raw.index(0, strings + nameoff)
            key = ('/' + '/'.join(stack[1:]), raw[strings+nameoff:end].decode())
            assert key not in result
            result[key] = raw[offset:offset+size]; offset = (offset+size+3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            return result
        else:
            raise ValueError('Invalid FDT token')


def check(path):
    tree = MOD.Fdt(path)
    assert tree.cells('/reserved-memory/reserved@fb00000', 'reg') == [0x0fb00000, 0x280000]
    assert tree.cells(NODE, 'reg') == [0x0fd80000, 0x180000]
    assert tree.strings(NODE, 'compatible') == ['qcom,rmtfs-mem']
    assert tree.cells(NODE, 'qcom,client-id') == [1]
    assert tree.prop(NODE, 'no-map') == b'' and tree.prop(NODE, 'status') is None
    assert tree.prop(NODE, 'qcom,vmid') is None and tree.prop(NODE, 'qcom,use-guard-pages') is None
    assert tree.cells('/reserved-memory/smem@fa00000', 'reg') == [0x0fa00000, 0x100000]
    assert tree.strings('/soc/remoteproc@fc880000', 'status') == ['disabled']
    # The two replacement intervals exactly partition the prior 4 MiB range.
    assert 0x0fb00000 + 0x280000 == 0x0fd80000
    assert 0x0fd80000 + 0x180000 == 0x0fb00000 + 0x400000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'stock-dtb', 'patch', 'schema', 'schema-tools', 'output']:
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    env = os.environ | {'PYTHONDONTWRITEBYTECODE':'1', 'XDG_CACHE_HOME':str(output/'cache')}
    stock = MOD.Fdt(args.stock_dtb)
    assert stock.cells('/', 'qcom,board-id') == [150, 0]
    assert stock.cells('/soc/rmtfs_sharedmem', 'reg') == [0x0fd80000, 0x180000]
    assert stock.strings('/soc/rmtfs_sharedmem', 'compatible') == ['qcom,sharedmem-uio']
    board = 'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts'
    scratch = output/'source'; (scratch/board).parent.mkdir(parents=True)
    shutil.copy2(source/board, scratch/board)
    for dry in [True, False]:
        command = ['patch', '--batch', '--fuzz=0', '-p1', '-i', str(args.patch.resolve())]
        if dry: command.append('--dry-run')
        result = subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True)
        (output/('patch-dry-run.log' if dry else 'patch-apply.log')).write_text(result.stdout + result.stderr)
        result.check_returncode()
    for name, path in [('baseline', source/board), ('candidate', scratch/board)]:
        with (output/(name+'.dts')).open('wb') as stream:
            subprocess.run(['cpp','-nostdinc','-undef','-D__DTS__','-x','assembler-with-cpp',
                            '-I'+str(source/'include'),'-I'+str(source/'arch/arm/boot/dts'),
                            '-I'+str(source/'arch/arm/boot/dts/qcom'),str(path)],env=env,stdout=stream,check=True)
        with (output/(name+'-dtc.log')).open('w') as log:
            subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(output/(name+'.dtb')),str(output/(name+'.dts'))],env=env,stderr=log,check=True)
    baseline, candidate = output/'baseline.dtb', output/'candidate.dtb'
    assert MOD.Fdt(baseline).cells('/reserved-memory/reserved@fb00000', 'reg') == [0x0fb00000, 0x400000]
    check(candidate)
    old, new = properties(baseline), properties(candidate)
    differences = [key for key in set(old)|set(new) if old.get(key) != new.get(key)]
    expected = [('/reserved-memory/reserved@fb00000','reg')] + [(NODE,key) for key in ['compatible','reg','no-map','qcom,client-id']]
    assert set(differences) == set(expected), differences
    def warnings(name):
        return [row.split(': Warning ',1)[1] for row in (output/(name+'-dtc.log')).read_text().splitlines() if ': Warning ' in row]
    assert warnings('baseline') == warnings('candidate')
    controls = []
    for mode, node, prop, values in [
        ('wrong-base', NODE, 'reg', [0xfd00000,0x180000]),
        ('wrong-client', NODE, 'qcom,client-id', [2]),
        ('reservation-overlap', '/reserved-memory/reserved@fb00000','reg',[0xfb00000,0x400000]),
        ('reservation-gap', '/reserved-memory/reserved@fb00000','reg',[0xfb00000,0x200000])]:
        path = output/(mode+'.dtb'); shutil.copy2(candidate,path)
        subprocess.run(['fdtput','-t','x',str(path),node,prop,*[hex(value) for value in values]],check=True,env=env)
        try:check(path)
        except AssertionError:controls.append(mode)
        else:raise AssertionError('Invalid description accepted')
    def validate(path, name):
        result = subprocess.run([str(args.schema_tools/'dt-validate'),'-s',str(args.schema),'-l','qcom,rmtfs-mem',str(path)],env=env,capture_output=True,text=True,check=True)
        log = result.stdout+result.stderr; (output/(name+'-schema.log')).write_text(log); return log
    assert validate(candidate,'candidate') == ''
    missing = output/'missing-client.dtb'; shutil.copy2(candidate,missing)
    subprocess.run(['fdtput','-d',str(missing),NODE,'qcom,client-id'],check=True,env=env)
    assert 'qcom,client-id' in validate(missing,'missing-client')
    sha = lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'stock_RMTFS_base':0x0fd80000,'stock_RMTFS_size':0x180000,'client_id':1,
              'prior_no_map_reserved_union_exactly_preserved':True,'overlap_or_gap_introduced':False,
              'other_property_paths_and_bytes_unchanged':True,'property_differences':sorted(differences),
              'DTC_new_warnings':0,'DTC_inherited_warnings':len(warnings('baseline')),
              'actual_RMTFS_schema_diagnostics':0,'missing_client_schema_control_rejected':True,
              'negative_controls_rejected':controls,'board_source_sha256':sha(source/board),
              'candidate_board_sha256':sha(scratch/board),'baseline_DTB_sha256':sha(baseline),
              'candidate_DTB_sha256':sha(candidate),'patch_sha256':sha(args.patch),
              'MSS_stays_disabled':True,'candidate_booted_or_packaged':False,
              'scope':'Host-only separate candidate; built-in RMTFS driver would map this region if booted. No physical memory/driver/firmware qualification.'}
    (output/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':main()
