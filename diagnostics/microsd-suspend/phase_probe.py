#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe SD card-detect IRQs around owned-file I/O; never format/repair."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,threading,time,uuid
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();os.umask(0o077);a.output.mkdir(parents=True,exist_ok=False);out=a.output;media='/dev/mmcblk1p1';mount=out/'mount';mount.mkdir()
assert Path('/sys/class/block/mmcblk1/device/type').read_text().strip()=='SD'
assert subprocess.run(['findmnt','-rn','-S',media],capture_output=True).returncode==1
assert subprocess.check_output(['blkid','-s','TYPE','-o','value',media],text=True).strip()=='vfat'
def run(args):
 r=subprocess.run(args,capture_output=True,text=True,timeout=90)
 if r.returncode:raise RuntimeError(f'{args[0]} failed: {r.stderr}')
 return r.stdout
r=subprocess.run(['fsck.fat','-n',media],capture_output=True,text=True,timeout=90);(out/'fsck-before.log').write_text(r.stdout+r.stderr);assert r.returncode==0
stop=threading.Event();rows=[];phase='initial';mounted=False;owned=mount/('.fx0-cd-'+uuid.uuid4().hex);file=owned/'payload.bin';result={'status':'running','phases':[]}
def sample():
 irq={}
 for line in Path('/proc/interrupts').read_text().splitlines():
  if 'f98a4900' in line:
   c=line.split();irq[c[0].rstrip(':')]=sum(int(v) for v in c[1:5])
 return {'boottime':time.clock_gettime(time.CLOCK_BOOTTIME),'phase':phase,'IRQ_counts':irq}
def observe():
 while not stop.is_set():rows.append(sample());stop.wait(0.05)
def start(name):
 global phase
 phase=name;rows.append(sample());(out/(name+'-wake-before.txt')).write_text(Path('/sys/kernel/debug/wakeup_sources').read_text())
def end():
 rows.append(sample());(out/(phase+'-wake-after.txt')).write_text(Path('/sys/kernel/debug/wakeup_sources').read_text());result['phases'].append(phase);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',phase,flush=True)
t=threading.Thread(target=observe);t.start()
try:
 start('idle');time.sleep(3);end()
 start('mount');run(['mount','-t','vfat','-o','rw,nosuid,nodev,noexec',media,str(mount)]);mounted=True;assert os.statvfs(mount).f_bavail*os.statvfs(mount).f_frsize>134217728;owned.mkdir();end()
 payload=os.urandom(4194304);expected=hashlib.sha256(payload).hexdigest()
 start('write-buffered')
 with file.open('xb',buffering=0) as f:
  f.write(payload);end();start('fsync');os.fsync(f.fileno());end()
 start('sync');os.sync();end()
 start('read-discard-cache')
 with file.open('rb') as f:
  os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED);actual=hashlib.file_digest(f,'sha256').hexdigest()
 assert actual==expected;end();result['sha256_match']=True
 start('idle-after-io');time.sleep(6);end()
 start('remove-unmount');file.unlink();owned.rmdir();os.sync();run(['umount',str(mount)]);mounted=False;end()
 start('idle-after-unmount');time.sleep(3);end();result['status']='I/O observation passed'
finally:
 if mounted:
  file.unlink(missing_ok=True)
  if owned.exists():owned.rmdir()
  os.sync();run(['umount',str(mount)]);mounted=False
 stop.set();t.join();(out/'samples.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');(out/'gpio.txt').write_text(Path('/sys/kernel/debug/gpio').read_text());(out/'kernel-after.log').write_text(run(['dmesg']))
r=subprocess.run(['fsck.fat','-n',media],capture_output=True,text=True,timeout=90);(out/'fsck-after.log').write_text(r.stdout+r.stderr);assert r.returncode==0
result['final_fsck_exit']=0;result['unmounted_after']=subprocess.run(['findmnt','-rn','-S',media],capture_output=True).returncode==1;assert result['unmounted_after'];(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
