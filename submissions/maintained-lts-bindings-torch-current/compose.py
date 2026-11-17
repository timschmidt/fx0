# SPDX-License-Identifier: GPL-2.0-only
"""Reconcile every binding/board/torch source path against its original parent."""
from pathlib import Path
import hashlib,json,re,subprocess
B=Path(__file__).resolve().parent;R=B.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';plan=json.loads((B/'prepared.json').read_text());receipt=B/'composition.json';j=json.loads(receipt.read_text()) if receipt.exists() else dict(base=plan['base'],completed=[],phone_access=False,published=False);sha=lambda b:hashlib.sha256(b).hexdigest();save=lambda:receipt.write_text(json.dumps(j,indent=2)+'\n')
def blob(h,p):
 r=subprocess.run(['git','show',h+':'+p],cwd=E,capture_output=True);return r.stdout if r.returncode==0 else b''
def block(data,anchor,semicolon=True):
 start=data.index(anchor);i=data.index(b'{',start)+1;depth=1
 while depth:depth+=(data[i]==123)-(data[i]==125);i+=1
 if semicolon:
  assert data[i:i+1]==b';';return data[start:i+1]
 return data[start:i]
def tokens(data):
 data=re.sub(rb'/\*.*?\*/|//[^\n]*',b'',data,flags=re.S);return re.findall(rb'"[^"\n]*"|[A-Za-z0-9_@,\.\-]+|[^\s]',data)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==plan['base'];assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=C)
for row in plan['origin_commits']:
 h=row['commit']
 if any(r['origin_commit']==h for r in j['completed']):continue
 outputs={};details=[]
 for p in row['paths']:
  source=C/p;ours=source.read_bytes() if source.exists() else b'';base=blob(h+'^',p);theirs=blob(h,p);folder=B/'stages'/h[:12]/p;folder.mkdir(parents=True,exist_ok=True)
  for name,data in [('ours',ours),('base',base),('theirs',theirs)]: (folder/name).write_bytes(data)
  note=[]
  if h.startswith('99339fb'):
   a=block(ours,b'pm8226_pon: pon@800');b=block(theirs,b'pm8226_pon: pon@800');assert tokens(a)==tokens(b);merged=ours;note.append('Existing LTS PON label and every node property match the incoming labeled node')
  elif h.startswith('3c4dcc'):
   a=block(ours,b'pm8226_flash: led-controller@d300');b=block(theirs,b'pm8226_flash: led-controller@d300');assert tokens(a)==tokens(b);assert b'status = "disabled";' in a;merged=ours;note.append('Complete disabled torch node already present and source-equivalent')
  elif h.startswith('38b038') and p.endswith('/qcom-msm8926-lg-madai.dts'):
   transformed=ours
   for anchor in [b'&pm8226_spmi_regulators {',b'&saw_l2 {']:
    chunk=block(transformed,anchor);assert transformed.count(chunk)==1;transformed=transformed.replace(chunk,b'')
   assert transformed.count(b'reg = <0xb0 0x8>;')==1;transformed=transformed.replace(b'reg = <0xb0 0x8>;',b'reg = <0xb0 0x4>;')
   assert tokens(transformed)==tokens(theirs),'Unexpected normal-board differences';merged=ours;note.append('Existing full LTS board contains every incoming board token, retaining its APC/SAW blocks and eight-byte CPU fuse cell; no normal-board rewrite')
  elif h.startswith('38b038') and p=='arch/arm/boot/dts/qcom/Makefile':
   assert ours.count(b'qcom-msm8926-lg-madai.dtb')==1;merged=ours;note.append('Normal board already registered once in the complete LTS board list; preserve CPU/suspend targets and unrelated boards')
  elif h.startswith('38b038') and p.endswith('qcom,wcnss-pil.yaml'):
   assert b'          - qcom,wcn3660a\n' in ours;merged=ours;note.append('Incoming WCN3660A enum entry already present; preserve LTS smem-state binding shape')
  elif h.startswith('e602641') and p.endswith('/leds-qcom-flash-v1.c'):
   old=block(ours,b'static int qcom_flash_v1_off(',False);new=block(theirs,b'static int qcom_flash_v1_off(',False)
   merged=ours.replace(old,new);assert merged==theirs
   note.append('Retain the complete existing driver; only its shutdown function changes, matching the attributed current implementation exactly')
  elif h.startswith('e602641') and p.endswith('/Makefile'):
   assert ours.count(b'obj-$(CONFIG_LEDS_QCOM_FLASH_V1)\t+= leds-qcom-flash-v1.o')==1;merged=ours;note.append('Existing matching first-generation driver object entry retained')
  elif h.startswith('e602641') and p.endswith('/Kconfig'):
   a=ours[ours.index(b'config LEDS_QCOM_FLASH_V1'):];a=a[:a.find(b'\nconfig ',1)] if b'\nconfig ' in a[1:] else a
   b=theirs[theirs.index(b'config LEDS_QCOM_FLASH_V1'):];b=b[:b.find(b'\nconfig ',1)] if b'\nconfig ' in b[1:] else b
   assert tokens(a)==tokens(b);merged=ours;note.append('Existing driver Kconfig block is token-equivalent; no duplicate added')
  elif h.startswith('8700b1c') and p=='MAINTAINERS':
   start=theirs.index(b'QUALCOMM PM8941 TORCH LED DRIVER\n');end=theirs.index(b'QUALCOMM SMB CHARGER DRIVER\n',start);entry=theirs[start:end]
   assert entry not in ours and ours.count(b'QUALCOMM SMB CHARGER DRIVER\n')==1
   merged=ours.replace(b'QUALCOMM SMB CHARGER DRIVER\n',entry+b'QUALCOMM SMB CHARGER DRIVER\n');note.append('Insert the exact attributed torch ownership entry next to the existing LTS charger entry; do not import the newer PAS service')
  elif ours==theirs or base==theirs:merged=ours;note.append('Already exact after-source or no incoming delta')
  elif ours==base:merged=theirs
  else:
   r=subprocess.run(['git','merge-file','--diff3','-p',str(folder/'ours'),str(folder/'base'),str(folder/'theirs')],capture_output=True);(folder/'merge.stdout').write_bytes(r.stdout);(folder/'merge.stderr').write_bytes(r.stderr)
   if r.returncode:j.update(state='needs reconciliation',origin=h,path=p);save();print(json.dumps(dict(origin=h,path=p,returncode=r.returncode)));raise SystemExit(2)
   merged=r.stdout;note.append('Three-way delta only, preserving unrelated LTS schema/API context')
  assert b'<<<<<<<' not in merged and b'>>>>>>>' not in merged;(folder/'after').write_bytes(merged);outputs[p]=merged;details.append(dict(path=p,before_SHA256=sha(ours),original_parent_SHA256=sha(base),original_after_SHA256=sha(theirs),after_SHA256=sha(merged),source_changed=ours!=merged,adjustments=note))
 for p,data in outputs.items():source=C/p;source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(data)
 j['completed'].append(dict(origin_commit=h,subject=row['subject'],files=details));j.update(state='composed '+h[:12]);save();print(h[:12],sum(f['source_changed'] for f in details),'changed paths')
j.update(passed=True,state='selected source closure composed');save()
