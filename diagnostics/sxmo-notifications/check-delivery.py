#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import hashlib,json,os,signal,subprocess,tempfile,time,shutil
from pathlib import Path
import argparse
import pwd
parser=argparse.ArgumentParser(description="Reproduce Sxmo partial-write loss using real inotify and mocked desktop hooks")
parser.add_argument('--original',required=True,type=Path)
parser.add_argument('--candidate',required=True,type=Path)
parser.add_argument('--runtime-dir',required=True,type=Path)
args=parser.parse_args()
ORIGINAL=args.original.read_text()
CANDIDATE=args.candidate.read_text()
BOOT=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
uid,gid=args.runtime_dir.stat().st_uid,args.runtime_dir.stat().st_gid
assert uid != 0 and os.geteuid()==0, 'Run as root against the login user runtime directory'
base=Path(tempfile.mkdtemp(prefix='fx0-notification-fixture-',dir=args.runtime_dir))
os.chown(base,uid,gid)
results=[]
def wait_for(check,seconds=2):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if check():return True
  time.sleep(.02)
 return check()
def fixture(label,source):
 folder=base/label;folder.mkdir();os.chown(folder,uid,gid)
 bins=folder/'bin';bins.mkdir();os.chown(bins,uid,gid)
 notifs=folder/'notifications';notifs.mkdir();os.chown(notifs,uid,gid)
 log=folder/'calls';hooklog=folder/'hooks';errors=folder/'errors'
 for name in ['sxmo_hook_icons.sh','sxmo_hook_notifications.sh','sxmo_hook_statusbar.sh']:
  path=bins/name;path.write_text('#!/bin/sh\n:\n');path.chmod(0o755)
 (bins/'sxmo_common.sh').write_text('sxmo_log() { printf \"%s\\n\" \"$*\" >&2; }\n')
 (bins/'dunstify').write_text('#!/bin/sh\ncase "$2" in "Fx0 fixture "*) printf "%s\\n" "$*" >> "$CALLS";; *) exit 1;; esac\n');(bins/'dunstify').chmod(0o755)
 (bins/'sxmo_hook_notification.sh').write_text('#!/bin/sh\n[ -f "$1" ] && [ "$(wc -l < "$1")" -ge 3 ] || exit 1\ncase "$(tail -n+3 "$1")" in "Fx0 fixture "*) printf "%s\\n" "$1" >> "$HOOKS";; *) exit 1;; esac\n');(bins/'sxmo_hook_notification.sh').chmod(0o755)
 script=folder/'sxmo_notifs.sh';script.write_text(source);script.chmod(0o755)
 env=dict(PATH=str(bins)+':/usr/bin:/bin',HOME=pwd.getpwuid(uid).pw_dir,LC_ALL='C',SXMO_NOTIFDIR=str(notifs),CALLS=str(log),HOOKS=str(hooklog))
 def count(path):return len(path.read_text().splitlines()) if path.exists() else 0
 with errors.open('w') as output:
  monitor=subprocess.Popen(['sh',str(script),'monitor'],env=env,user=uid,group=gid,stdout=output,stderr=output,start_new_session=True)
  try:
   def watcher():
    for p in Path('/proc').glob('[0-9]*'):
     try:
      cmd=p.joinpath('cmdline').read_bytes().split(b'\0')
      if b'inotifywait' in b' '.join(cmd[:2]) and str(notifs).encode() in cmd:return True
     except (OSError,ProcessLookupError):pass
    return False
   assert wait_for(watcher),'real inotify watcher absent'
   path=notifs/'slow'
   with path.open('w') as file:
    os.chown(path,uid,gid)
    file.write('fx0-fixture\n:');file.flush();time.sleep(.15)
    # chown emits ATTRIB; the original can consume an incomplete record.
    before_close=count(log)
    file.write('\nFx0 fixture slow writer\n');file.flush();time.sleep(.15)
    assert count(log)==before_close
   wait_for(lambda:count(log)>0,.8)
   slow_count=count(log);slow_hook_count=count(hooklog)
   if label=='original':
    assert slow_count==0 and slow_hook_count==0
   else:
    assert slow_count==slow_hook_count==1 and before_close==0
    for i in range(5):
     p=subprocess.run(['sh',str(script),'new','-i','new'+str(i),'-g','fx0-fixture',':','Fx0 fixture '+str(i)],env=env,user=uid,group=gid,capture_output=True,text=True,timeout=3)
     assert p.returncode==0
     assert wait_for(lambda:count(log)==i+2),'normal new writer delivery missing'
    temp=folder/'atomic';temp.write_text('fx0-fixture\n:\nFx0 fixture atomic move\n');os.chown(temp,uid,gid)
    temp.rename(notifs/'atomic')
    assert wait_for(lambda:count(log)==7)
    assert wait_for(lambda:count(hooklog)==7)
    assert not errors.read_text(),errors.read_text()
   results.append(dict(variant=label,source_sha256=hashlib.sha256(source.encode()).hexdigest(),slow_writer_before_close=before_close,slow_writer_notifications=slow_count,slow_writer_hooks=slow_hook_count,total_notifications=count(log),total_hooks=count(hooklog),error_text=errors.read_text()))
  finally:
   os.killpg(monitor.pid,signal.SIGTERM)
   try:monitor.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(monitor.pid,signal.SIGKILL);monitor.wait()
try:
 fixture('original',ORIGINAL)
 fixture('candidate',CANDIDATE)
finally:shutil.rmtree(base)
print(json.dumps(dict(boot_id=BOOT,real_native_inotify=True,desktop_bus_and_hardware_mocked=True,results=results,temporary_files_removed=not base.exists())))
