#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate completed observer/native-return artifacts; no device access or actions."""
import argparse
import hashlib
import json
from pathlib import Path
import re

IMAGE='e7ae8e67f9d97ffa02576447c23af2d0c72853d98d61d8033e4405a11f400659'
NOTES='cb8ff4d80009dbd0b4542ce5d28d7ce10e4d84e0db4e332c749ff8ae18a08269'
BOOT='3790f14d537107221529b21d07a98c62fbf1603a81f3cdd77c76140581135921'
NATIVE='c3ac8f04-888e-493c-bb5d-a1729a275f7d'
ORDER=['qcom_pil_info','qcom_common','qcom_q6v5','mdt_loader','qcom_q6v5_mss']
REGISTERS={'0x1740':1,'0x1741':115,'0x2001':2,'0x2004':3,'0x2005':8,'0x2040':0,'0x2041':62,'0x2045':64,'0x2046':0}


def verify(base):
    def load(name):
        return json.loads((base/name).read_text())
    image=load('image-verification.json')
    assert image['image_sha256']==IMAGE and image['kernel_notes_sha256']==NOTES
    handoff=load('boot-request.json')
    assert handoff['image_sha256']==IMAGE
    assert handoff['state'] in ['acknowledged','uncertain or failed; never retry BOOT']
    transfer=load('transfer/result.json');assert transfer['state']=='verified' and transfer['readback_sha256']==IMAGE
    for name in ['transfer','observer','network']:
        assert load(name+'-controller.json')['returncode']==0
    observation=load('observation.json')
    assert observation.get('RAM_detached_UTC') and observation['serial']['state']=='terminal'
    assert observation['serial'].get('error') is None
    assert any(row.get('RAM') is True for row in observation['USB'])
    text=(base/'serial-kmsg.txt').read_text(errors='replace').replace('\r\n','\n')
    assert len(re.findall(r'^MODEM_PROBE_PASS\r?$',text,re.M))==1
    assert re.findall(r'^__MODEM_PROBE_EXIT__(\d+)\r?$',text,re.M)==['0']
    boot_ids=re.findall(r'^__MODEM_PROBE_BEGIN__([0-9a-f-]+)\r?$',text,re.M)
    assert len(boot_ids)==1 and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot_ids[0])
    ram_id=boot_ids[0];assert ram_id!=NATIVE
    operations=re.findall(r'^__MODEM_OPERATION__(\d+) ([a-z0-9_-]+) (\d+)\r?$',text,re.M)
    expected=[(str(i+1),'load-'+name,'0') for i,name in enumerate(ORDER)]
    expected += [(str(i+6),'unload-'+name,'0') for i,name in enumerate(reversed(ORDER))]
    assert operations==expected
    states=re.findall(r'^__MODEM_STATE__offline (/sys/class/remoteproc/remoteproc\d+)\r?$',text,re.M)
    assert len(states)>=2 and len(set(states))==1
    match=re.search(r'^__KERNEL_NOTES__\n(.*?)^__BOOT_HASH__\n',text,re.M|re.S);assert match
    tokens=match.group(1).split();assert len(tokens)==84 and all(re.fullmatch(r'[0-9a-f]{2}',token) for token in tokens)
    assert hashlib.sha256(bytes.fromhex(' '.join(tokens))).hexdigest()==NOTES
    assert re.search(r'^__BOOT_HASH__\n'+BOOT+r'\s+/dev/mmcblk0p15\n__FX0_CHECK_END__\n',text,re.M)
    assert 'Linux version 6.18.59-fx0-dmp ' in text
    def kmsg_time(message):
        values=re.findall(r'^\d+,\d+,(\d+),[^;]*;'+re.escape(message)+r'\r?$',text,re.M)
        assert len(values)==1,(message,values)
        return int(values[0])/1000000
    started=kmsg_time('Fx0 RAM diagnostic init started')
    returned=kmsg_time('Returning to lk2nd for diagnostic retrieval')
    assert 180<=returned-started<190
    irq_rows=re.findall(r'^\s*\d+:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+[^\n]*q6v5 (wdog|fatal|ready|handover|stop)\r?$',text,re.M)
    assert len(irq_rows)==5 and {row[4] for row in irq_rows}=={'wdog','fatal','ready','handover','stop'}
    total=sum(int(value) for row in irq_rows for value in row[:4]);assert total<=8
    post=load('postflight-verification/native.json')
    assert post['phase']=='postflight' and post['boot_id'] not in [NATIVE,ram_id]
    assert re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',post['boot_id'])
    pre=load('entry-preflight/native.json')
    assert pre['phase']=='preflight' and pre['boot_id']==NATIVE
    assert post['files_sha256']==pre['files_sha256'] and len(post['files_sha256'])==10
    assert post['CPU_policy']==pre['CPU_policy'] and post['NFC']==pre['NFC']
    assert post['remoteprocs']==pre['remoteprocs']
    assert post['Sway_PID']>1 and post['ModemManager_PID']>1
    assert len(post['temperatures_mC'])==2 and all(-40000<=value<60000 for value in post['temperatures_mC'])
    assert post['kernel']=='6.18.59-fx0-dmp' and post['kernel_taint']==0 and post['raw_boot_sha256']==BOOT
    assert post['registers']==REGISTERS
    assert post['systemd']=='running' and post['pending_jobs']==post['failed_units']==[]
    assert post['native_MSS_disabled_and_unloaded'] and post['ModemManager_objects']==[]
    assert post['packages']['linux-postmarketos-qcom-msm8226']['version']=='6.18.59-r50'
    for name in ['upower','upower-lang','upower-systemd']:
        assert post['packages'][name]['version']=='99991.91.0-r5'
    assert len(post['UPower_samples'])==3
    assert len({sample['PID'] for sample in post['UPower_samples']})==1 and post['UPower_samples'][0]['PID']>1
    for sample in post['UPower_samples']:
        assert sample['display']=={'IsPresent':False,'State':0,'WarningLevel':1,'Percentage':0.0} and sample['OnBattery'] is False
    restored=load('postflight-verification/host-restoration.json')
    assert restored['own_volatile_profile_removed'] and restored['host_routes_resolver_and_protected_index_unchanged']
    health=load('native-health-controller.json');assert health['state']=='terminal' and health['returncode']==0
    return {'image_sha256':IMAGE,'RAM_boot_id':ram_id,'native_return_boot_id':post['boot_id'],
            'worker_exit':0,'ten_module_operations_and_offline_states_verified':True,
            'kernel_notes_and_original_raw_boot_hash_verified':True,'timer_seconds_after_init':returned-started,
            'modem_IRQ_total':total,'native_r50_r5_and_APC_S5_raw_controls_restored':True,
            'host_network_restored':True,'BOOT_reply_acknowledged':handoff['state']=='acknowledged',
            'physical_display_touch_confirmed_by_this_validator':False,
            'scope':'Offline driver probe and native return evidence only; physical UI, firmware start, radio/GNSS and wider bringup separate'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();assert not args.output.exists()
    result=verify(args.trial)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
