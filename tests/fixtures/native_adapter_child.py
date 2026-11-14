# SPDX-License-Identifier: MIT
import hashlib,json,os,sys,time
from pathlib import Path
os.umask(0o077)
role,case,mode=sys.argv[1:4]
case=Path(case)
if mode=='spawn-persistence-fault':
    (case/(role+'-started')).write_text('owned child started');time.sleep(5);raise SystemExit(0)
if role=='transfer':
    output=case/'transfer';output.mkdir()
    if mode in ['usb-timeout','other-transfer-error','parent-deadline']:
        (output/'result.json').write_text(json.dumps({'state':'failed','last_IO':{'errno':110 if mode!='other-transfer-error' else 5}}))
        if mode=='parent-deadline':
            (case/'transfer-ready').write_text('ready');time.sleep(3)
        raise SystemExit(4)
    payload=Path(sys.argv[4]).read_bytes()
    if mode=='bad-readback':payload=payload[:-1]+bytes([payload[-1]^1])
    (output/'readback.bin').write_bytes(payload)
    (output/'result.json').write_text(json.dumps({'state':'verified','readback_sha256':hashlib.sha256(payload).hexdigest()}))
elif role=='observer':
    if mode=='dead-observer':raise SystemExit(3)
    time.sleep(.12)
    candidate='00000000-0000-4000-8000-000000000003'
    returned='00000000-0000-4000-8000-000000000002'
    (case/'native-observation.json').write_text(json.dumps({'candidate_seen':True,'candidate_boot_id':candidate,'candidate_health_passed':mode!='worker-failed','returned':True,'native_return':{'boot_id':returned}}))
    health={'boot_id':candidate,'systemd':'running','taint':0,'serious_kernel_pattern_counts':{'BUG:':0}}
    for name in ['exact_r2_notes_verified','all478_new_module_metadata_files_verified','early_static_helper_alive_and_exact_binary','primary_return_timer_active','four_cpus_schedutil_787200_max','touch_device_open','package_DB_world_and_raw_boot_unchanged','read_only']:health[name]=True
    (case/'candidate-ready.json').write_text(json.dumps(health))
    if mode=='observer-parent-deadline':
        import signal
        signal.signal(signal.SIGTERM,lambda signum,frame:sys.exit(0))
        (case/'observer-ready').write_text('ready');time.sleep(3)
    raise SystemExit(7 if mode=='observer-error' else 0)
elif role=='normal-reboot':
    raise SystemExit(0)
else:
    raise SystemExit(2)
