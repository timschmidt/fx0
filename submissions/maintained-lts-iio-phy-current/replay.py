#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay pinned IIO and PHY source against synthetic services; no devices."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'};expected=json.loads((P/'expected-fixtures.json').read_text());j=dict(passed=False,state='prepared',stages=[],manifest_verified_before_execution=True,source_head=manifest['source_head'],normal_LSan_and_failfast_ASan_UBSan=True,phone_access=False,real_hardware_execution=False);child=None;save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
tasks=[]
def add(label,script,args,negative=False):
 tasks.append((label,[P/script,*args],negative))
add('IADC','harness/IIO/check-iadc.py',[P/'source/drivers/iio/adc/qcom-spmi-iadc.c',O/'IADC'])
add('calibbias','harness/IIO/check-calibbias.py',[P/'source',O/'calibbias'])
add('scan-before','harness/IIO/check-scan.py',[P/'before',O/'scan-before','--documented-ABI'],True)
add('scan-after','harness/IIO/check-scan.py',[P/'source',O/'scan-after','--documented-ABI'])
for label,tree in [('PHY-before','before'),('PHY-after','source')]:
 add(label,'harness/PHY/check-usb.py',[P/tree/'drivers/phy/qualcomm/phy-qcom-usb-hs.c',O/label])
for kind in ['transport','packet','lifecycle','recovery','smd']:
 label='DMP-'+kind;add(label,'harness/IIO/check-dmp.py',[P/'source',O/label,kind])
for script,mutations,source in [('scan',['legacy-reader','end-offset','missing-cache'],P/'source'),('iadc',['unsigned-difference','missing-units','missing-range'],P/'source/drivers/iio/adc/qcom-spmi-iadc.c'),('calibbias',['gyro-stride','missing-put'],P/'source')]:
 for mutation in mutations:
  label=script+'-'+mutation;add(label,'harness/IIO/check-'+script+'.py',[source,O/label,'--mutation',mutation],True)
for mutation in ['zero-sentinel','no-odd-check','short-count']:
 label='PHY-'+mutation;add(label,'harness/PHY/check-usb.py',[P/'source/drivers/phy/qualcomm/phy-qcom-usb-hs.c',O/label,'--mutation',mutation],True)
for kind,mutation in [('transport','cursor'),('packet','packet-error'),('recovery','restore-flag'),('smd','status-bit'),('smd','suspended-bus')]:
 label='DMP-'+mutation;add(label,'harness/IIO/check-dmp.py',[P/'source',O/label,kind,'--mutation',mutation],True)
add('header','check-header.py',['--source',P/'source','--output',O/'header'])
add('reader','check-reader.py',['--source',P/'reader-example.py','--output',O/'reader'])
assert len(tasks)==29

try:
 for label,args,negative in tasks:
  with (O/(label+'.stdout')).open('xb') as stdout,(O/(label+'.stderr')).open('xb') as stderr:
   child=subprocess.Popen([sys.executable,'-B',*map(str,args)],env=env,stdout=stdout,stderr=stderr,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=120)
  assert code==0,label
  assert not (O/(label+'.stderr')).read_bytes(),label
  receipt=json.loads((O/label/'qualification.json').read_text())
  assert not receipt.get('sanitizer_diagnostics',False),label
  failures=receipt.get('failures',int(not receipt.get('passed',True)))
  assert failures>0 if negative else failures==0,(label,receipt)
  j['stages'].append(dict(label=label,returncode=code));save()
 for f,want in expected.items():assert sha(O/f)==want,f
 assert json.loads((O/'scan-before/qualification.json').read_text())['timestamp_offset']==24
 assert json.loads((O/'scan-after/qualification.json').read_text())['timestamp_offset']==16
 assert sum(json.loads((O/('DMP-'+kind)/'qualification.json').read_text())['checks'] for kind in ['transport','packet','lifecycle','recovery','smd'])==876382
 assert sum(json.loads((O/label/'qualification.json').read_text())['cases'] for label in ['IADC','calibbias','scan-after','PHY-after','reader'])==19529
 assert json.loads((O/'header/qualification.json').read_text())['usage_arrays']==4
 assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success',suites=29,qualified_fixtures=len(expected),all_generated_fixtures_match=True);print(json.dumps(dict(passed=True,suites=29,qualified_fixtures=len(expected))))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
