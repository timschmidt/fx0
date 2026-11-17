#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay selected source-only host suites; no live hardware or network access."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);a=parser.parse_args();O=a.output.resolve();assert not O.exists();O.mkdir(mode=0o700);(O/'tmp').mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());H=P/'harness';C=P/'source';resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
commands=[('control',[H/'diagnostics/smbb-charging-policy/check-control.py',C]),('lifetime',[H/'diagnostics/smbb-charging-policy/check-lifetime.py',C,'--negative-controls']),('model',[H/'diagnostics/smbb-charging-policy/check-model.py',C,P/'vendor-source']),('USB-input',[H/'diagnostics/smbb-charging-policy/check-usb-input.py','--driver',C/'drivers/power/supply/qcom_smbb.c','--output',O/'USB-input']),('USB-budget',[H/'diagnostics/smbb-charging-policy/check-usb-gadget-budget.py','--driver',C/'drivers/usb/chipidea/udc.c','--output',O/'USB-budget']),('VADC-units',[H/'diagnostics/vadc-battery-units/check.py',C]),('VADC-metadata',[H/'diagnostics/vadc-battery-units/check-channel-metadata.py',C,'--before-driver',P/'before-vadc.c'])]
j=dict(passed=False,source_head=manifest['source_head'],manifest_verified=True,normal_LSan_and_failfast_ASan_UBSan=True,stages=[],phone_access=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n');child=None
try:
 for label,args in commands:
  with (O/(label+'.stdout')).open('xb') as out,(O/(label+'.stderr')).open('xb') as err:
   child=subprocess.Popen([sys.executable,'-B',*map(str,args)],cwd=H,env=env,stdout=out,stderr=err,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=180)
  assert code==0 and not (O/(label+'.stderr')).read_bytes(),label;j['stages'].append(dict(label=label,returncode=code));save()
 assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success');print(json.dumps(dict(passed=True,suites=7)))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
