#!/usr/bin/env python3
"""Temporarily address only an identified Fx0 RAM USB gadget.

Waits for the selected physical port plus the diagnostic VID/PID, serial and
host MAC. Creates an in-memory, non-autoconnect NetworkManager profile without
gateway or DNS, and deletes only that profile when the gadget detaches. Uses
existing NetworkManager permissions; does not change Wi-Fi or other profiles.
"""
import argparse,datetime,hashlib,json,subprocess,time,uuid
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--usb-port',required=True,help='Physical USB path component, for example 1-14')
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--wait',type=int,default=600,help='Maximum observation duration in seconds')
args=parser.parse_args()
if not 30<=args.wait<=1800:parser.error('--wait must be 30 through 1800 seconds')
if args.report.exists():parser.error('Report already exists')
args.report.parent.mkdir(parents=True,exist_ok=True)
STATE=args.report
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def run(args):return subprocess.run(args,capture_output=True,text=True,check=True)
def parent(p):
 for a in [p,*p.parents]:
  if (a/'idVendor').exists():return a
 return None
def value(p):
 try:return p.read_text().strip()
 except OSError:return None
report={'started_UTC':now(),'state':'waiting for matching RAM USB gadget','connection_UUID':None,'host_default_routes_before':json.loads(run(['ip','-j','route','show','default']).stdout),'resolver_sha256_before':hashlib.sha256(Path('/etc/resolv.conf').read_bytes()).hexdigest()}
def save():
 STATE.write_text(json.dumps(report,indent=2)+'\n');STATE.chmod(0o600)
save();created=None;deadline=time.monotonic()+args.wait
try:
 while time.monotonic()<deadline:
  found=[]
  for p in Path('/sys/class/net').iterdir():
   u=parent((p/'device').resolve())
   if u and u.name==args.usb_port and value(u/'idVendor')=='1d6b' and value(u/'idProduct')=='0104' and value(u/'serial')=='fx0-diagnostic' and value(p/'address')=='02:46:58:30:00:02':found.append((p.name,u))
  if found:break
  time.sleep(1)
 else:raise RuntimeError('No matching RAM gadget appeared')
 if len(found)!=1:raise RuntimeError('Expected exactly one matching RAM gadget')
 interface,usb=found[0];name='fx0-ram-'+uuid.uuid4().hex[:12]
 # Know our unique UUID before add, including if its reply or a later step fails.
 created=str(uuid.uuid4())
 report.update({'state':'adding RAM-only volatile connection','interface':interface,'connection_name':name,'connection_UUID':created,'USB_port':str(usb)});save()
 r=run(['nmcli','connection','add','save','no','type','ethernet','ifname',interface,'con-name',name,'connection.uuid',created,'802-3-ethernet.mac-address','02:46:58:30:00:02','connection.autoconnect','no','ipv4.method','manual','ipv4.addresses','172.16.42.2/24','ipv4.never-default','yes','ipv4.ignore-auto-dns','yes','ipv6.method','disabled','ipv6.never-default','yes'])
 r=run(['nmcli','--wait','15','connection','up','uuid',created,'ifname',interface]);report.update({'state':'active','active_UTC':now(),'activation':r.stdout});save()
 print('Temporary RAM USB address active',flush=True)
 while time.monotonic()<deadline and value(usb/'serial')=='fx0-diagnostic':time.sleep(1)
except Exception as error:report['error']=str(error)
finally:
 if created:
  r=subprocess.run(['nmcli','connection','delete','uuid',created],capture_output=True,text=True);report['cleanup']={'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
 report['finished_UTC']=now();report['state']='terminal';report['host_default_routes_after']=json.loads(run(['ip','-j','route','show','default']).stdout);report['resolver_sha256_after']=hashlib.sha256(Path('/etc/resolv.conf').read_bytes()).hexdigest();save();print(json.dumps({'state':report['state'],'error':report.get('error'),'cleanup_returncode':report.get('cleanup',{}).get('returncode')}),flush=True)

if report.get("error") or report.get("cleanup",{}).get("returncode",0):raise SystemExit(1)
