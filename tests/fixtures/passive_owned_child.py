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
    boot='00000000-0000-4000-8000-000000000003'
    markers=['RMTFS_PASSIVE_BEGIN '+boot,'RMTFS_LOCAL_SERVICE_ABSENT','RMTFS_LOCAL_SERVICE_PRESENT','RMTFS_RFSA_OPEN /dev/qcom_rmtfs_mem1','RMTFS_LOCAL_SERVICE_ABSENT','RMTFS_PASSIVE_PASS']
    (case/'serial-observation.json').write_text(json.dumps({'state':'terminal','console_closed':True,'candidate_seen':True,'worker_attempted':True,'returned_native_USB':True,'native_return_USB_generation':'202','RAM_identity':{'boot_id':boot,'kernel':'6.18.63-fx0-vibrator-alpine','notes_SHA256':'05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377','uptime':10},'worker_result':{'complete':True,'passed':mode!='worker-failed','returncode':0,'observed_markers':markers,'expected_markers':markers}}))
    if mode=='observer-parent-deadline':
        import signal
        signal.signal(signal.SIGTERM,lambda signum,frame:sys.exit(0))
        (case/'observer-ready').write_text('ready');time.sleep(3)
    raise SystemExit(7 if mode=='observer-error' else 0)
elif role=='normal-reboot':
    raise SystemExit(0)
else:
    raise SystemExit(2)
