#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract/validate embedded FDTs and report selected Fx0 CPU properties.

Input and extracted blobs should remain private. No device access or writes
outside a newly created output directory; libfdt validates each candidate.
"""
import argparse,ctypes as c,ctypes.util,hashlib,json,struct,subprocess
from pathlib import Path

def inspect(data, output, dtc=None):
    library = ctypes.util.find_library('fdt')
    if not library:
        raise RuntimeError('Host libfdt is required')
    f = c.CDLL(library)
    f.fdt_check_full.argtypes = [c.c_void_p,c.c_size_t];f.fdt_check_full.restype=c.c_int
    f.fdt_node_offset_by_phandle.argtypes=[c.c_void_p,c.c_uint32];f.fdt_node_offset_by_phandle.restype=c.c_int
    f.fdt_next_node.argtypes=[c.c_void_p,c.c_int,c.POINTER(c.c_int)];f.fdt_next_node.restype=c.c_int
    f.fdt_get_path.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_int];f.fdt_get_path.restype=c.c_int
    f.fdt_getprop.argtypes=[c.c_void_p,c.c_int,c.c_char_p,c.POINTER(c.c_int)];f.fdt_getprop.restype=c.c_void_p
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    reports=[];position=0
    while True:
        start=data.find(b'\xd0\x0d\xfe\xed',position)
        if start<0:break
        position=start+4
        if start+40>len(data):continue
        size=struct.unpack_from('>I',data,start+4)[0]
        if size<40 or start+size>len(data):continue
        raw=bytes(data[start:start+size]);buf=c.create_string_buffer(raw)
        if f.fdt_check_full(buf,size):continue
        def prop(offset,name):
            length=c.c_int();ptr=f.fdt_getprop(buf,offset,name.encode(),c.byref(length))
            return c.string_at(ptr,length.value) if ptr and length.value>=0 else None
        def values(offset,name):
            raw=prop(offset,name)
            if raw is None:return None
            if name in ['model','compatible','reg-names','regulator-name']:
                return raw.rstrip(b'\0').decode().split('\0')
            if len(raw)%4:raise ValueError('Unexpected non-cell property: '+name)
            return list(struct.unpack('>'+str(len(raw)//4)+'I',raw))
        report={'offset':start,'bytes':size,'sha256':hashlib.sha256(raw).hexdigest(),'root':{},'nodes':{}}
        for name in ['model','compatible','qcom,msm-id','qcom,board-id']:
            value=values(0,name)
            if value is not None:report['root'][name]=value
        depth=c.c_int();offset=-1
        props=['phandle','linux,phandle','compatible','reg','reg-names','cpu-vdd-supply','vdd-apc-supply','vdd-mx-supply','regulator-name','regulator-min-microvolt','regulator-max-microvolt','qcom,cpr-corner-map','qcom,cpr-corner-frequency-map','qcom,cpr-speed-bin-max-corners','qcom,pvs-version-fuse-sel','qcom,cpufreq-table','qcom,saw2-cfg','qcom,saw2-spm-dly','qcom,saw2-spm-ctl','qcom,saw2-pmic-data0','qcom,saw2-pmic-data1','qcom,vctl-timeout-us','qcom,vctl-port','qcom,L2-spm-is-apcs-master']
        props += ['qcom,speed-bin-fuse-sel','qcom,pvs-fuse-redun-sel','qcom,pvs-fuse','qcom,pvs-fuse-redun',
                  'qcom,pvs-voltage-table','qcom,cpr-voltage-floor','qcom,cpr-voltage-ceiling',
                  'qcom,vdd-mx-vmax','qcom,vdd-mx-vmin-method','qcom,cpr-ref-clk',
                  'qcom,cpr-timer-delay','qcom,cpr-timer-cons-up','qcom,cpr-timer-cons-down',
                  'qcom,cpr-irq-line','qcom,cpr-step-quotient','qcom,cpr-idle-clocks',
                  'qcom,cpr-gcnt-time','qcom,vdd-apc-step-up-limit','qcom,vdd-apc-step-down-limit',
                  'qcom,cpr-apc-volt-step','qcom,cpr-fuse-redun-sel','qcom,cpr-fuse-row',
                  'qcom,cpr-fuse-bp-cpr-disable','qcom,cpr-fuse-bp-scheme',
                  'qcom,cpr-fuse-target-quot','qcom,cpr-fuse-ro-sel',
                  'qcom,cpr-fuse-redun-row','qcom,cpr-fuse-redun-target-quot',
                  'qcom,cpr-fuse-redun-ro-sel','qcom,cpr-enable',
                  'qcom,cpr-fuse-cond-min-volt-sel','qcom,cpr-cond-min-voltage',
                  'qcom,cpr-fuse-uplift-sel','qcom,cpr-uplift-voltage','qcom,cpr-uplift-quotient',
                  'qcom,cpr-uplift-max-volt','qcom,cpr-uplift-speed-bin',
                  'qcom,cpr-quotient-adjustment','qcom,cpr-up-threshold',
                  'qcom,cpr-down-threshold','qcom,cpr-quot-adjust-scaling-factor-max']
        props += [f'qcom,speed{speed}-bin-v{version}' for speed in range(8) for version in range(4)]
        while True:
            offset=f.fdt_next_node(buf,offset,c.byref(depth))
            if offset<0:break
            path=c.create_string_buffer(4096)
            if f.fdt_get_path(buf,offset,path,len(path)):raise ValueError('Node path too long')
            name=path.value.decode()
            if 'clock-a7@' not in name and not any(name.endswith(s) for s in ['regulator@f9018000','spm-regulator@1700','msm-cpufreq@0','spm@f9012000']):continue
            report['nodes'][name]={k:v for k in props if (v:=values(offset,k)) is not None}
        supply_links=[]
        for node,properties in list(report['nodes'].items()):
            for key in ['cpu-vdd-supply','vdd-apc-supply','vdd-mx-supply']:
                if key not in properties:continue
                cells=properties[key]
                if len(cells)!=1:raise ValueError('Unexpected supply specifier')
                provider=f.fdt_node_offset_by_phandle(buf,cells[0])
                if provider<0:raise ValueError('Unresolved CPU supply phandle')
                path=c.create_string_buffer(4096)
                if f.fdt_get_path(buf,provider,path,len(path)):raise ValueError('Supply path too long')
                provider_name=path.value.decode()
                supply_links.append({'consumer':node,'property':key,'provider':provider_name})
                if provider_name not in report['nodes']:
                    report['nodes'][provider_name]={k:v for k in props if (v:=values(provider,k)) is not None}
        report['resolved_supply_links']=supply_links
        target=output/f'fdt-{len(reports):02d}.dtb';target.write_bytes(raw)
        if dtc:
            result=subprocess.run([str(dtc),'-I','dtb','-O','dts','-o',str(target.with_suffix('.dts')),str(target)],capture_output=True,text=True)
            target.with_suffix('.dtc.log').write_text(result.stderr)
            if result.returncode:raise ValueError('dtc rejected a libfdt-valid blob')
            report['dtc_decompile_exit']=0
        reports.append(report)
    if not reports:raise ValueError('No valid FDT found')
    (output/'cpu-properties.json').write_text(json.dumps(reports,indent=2)+'\n')
    return reports

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--dtc',type=Path);a=p.parse_args()
    reports=inspect(a.input.read_bytes(),a.output,a.dtc)
    print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
