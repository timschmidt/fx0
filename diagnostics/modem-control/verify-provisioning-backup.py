#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify private provisioning snapshots; emit a redacted report, no device I/O."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat

SPEC=importlib.util.spec_from_file_location('fx0_provisioning_capture',Path(__file__).with_name('capture-provisioning.py'))
CAPTURE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CAPTURE)


def verify(backup):
    backup=Path(backup)
    CAPTURE.require(backup.is_dir() and not backup.is_symlink() and not stat.S_IMODE(backup.stat().st_mode)&0o077,'Backup directory must be private')
    expected_names={'manifest.json','capture-controller.json'}|{name+'.img' for name in CAPTURE.PARTITIONS}
    CAPTURE.require({path.name for path in backup.iterdir()}==expected_names,'Unexpected or missing backup files')
    for path in backup.iterdir():
        CAPTURE.require(not path.is_symlink() and path.is_file() and not stat.S_IMODE(path.stat().st_mode)&0o077,'Backup files must be private regular files')
    manifest=json.loads((backup/'manifest.json').read_text())
    CAPTURE.require(manifest['schema']=='fx0-current-provisioning-v1' and manifest['complete'] is True,'Incomplete snapshot')
    CAPTURE.require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',manifest['native_boot_id']),'Invalid native boot identity')
    for key in ['source_devices_opened_read_only','source_set_stable_before_through_after','snapshot_files_fsynced_and_reread','native_state_unchanged']:
        CAPTURE.require(manifest[key] is True,'Missing capture acceptance')
    CAPTURE.require(manifest['firmware_partition_included'] is False,'Firmware partition must be excluded')
    controller=json.loads((backup/'capture-controller.json').read_text())
    CAPTURE.require(controller['state']=='terminal' and controller['returncode']==0 and controller['BOOT_or_restore_requested'] is False,'Capture not terminal successful')
    CAPTURE.require(set(manifest['partitions'])==set(CAPTURE.PARTITIONS),'Unexpected partition set')
    rows={}
    for name,(number,start,sectors) in CAPTURE.PARTITIONS.items():
        row=manifest['partitions'][name]
        CAPTURE.require(row['device']=='/dev/mmcblk0p'+str(number) and row['start_sector']==start and row['sectors']==sectors,'Source map mismatch')
        CAPTURE.require(row['file']==name+'.img' and row['bytes']==sectors*512,'Snapshot path/size mismatch')
        path=backup/(name+'.img')
        CAPTURE.require(path.stat().st_size==row['bytes'],'Snapshot file size mismatch')
        value=CAPTURE.digest(path)
        CAPTURE.require(value==row['sha256']==row['source_after_sha256'],'Snapshot/source reread digest mismatch')
        rows[name]={'bytes':row['bytes'],'verified':True}
    return {'verified':True,'partitions':rows,'total_bytes':sum(row['bytes'] for row in rows.values()),
            'manifest_sha256':hashlib.sha256((backup/'manifest.json').read_bytes()).hexdigest(),
            'current_capture_receipts_checked':True,'firmware_partition_excluded':True,
            'provisioning_payload_or_per_partition_digests_in_report':False,'restore_performed':False,
            'scope':'Private file bytes and recorded capture consistency only; no independent receipt authentication, physical restore or modem operation'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',required=True,type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=verify(args.backup)
    if args.output:
        with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
        args.output.chmod(0o600)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
