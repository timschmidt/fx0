# SPDX-License-Identifier: MIT
import hashlib,json,os,sys,time
from pathlib import Path
os.umask(0o077)
role,case,mode=sys.argv[1:4]
case=Path(case)
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
    (case/'serial-observation.json').write_text(json.dumps({'candidate_seen':True,'worker_attempted':True,'worker_result':{'passed':mode!='worker-failed'}}))
    raise SystemExit(7 if mode=='observer-error' else 0)
elif role=='normal-reboot':
    raise SystemExit(0)
else:
    raise SystemExit(2)
