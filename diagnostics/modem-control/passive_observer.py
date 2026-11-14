# SPDX-License-Identifier: MIT
from pathlib import Path
from datetime import datetime,timezone
import argparse,fcntl,importlib.util,json,os,re,secrets,select,stat,sys,termios,time
if sys.flags.optimize:raise RuntimeError('Optimized Python is forbidden for the observer')
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--usb-port',required=True);args=parser.parse_args()
if re.fullmatch(r'[0-9]+-[0-9]+(?:\.[0-9]+)*',args.usb_port) is None:raise RuntimeError('Invalid selected USB port')
root=Path(__file__).resolve().parents[2];base=args.workspace.resolve();os.umask(0o077)
if base.stat().st_uid!=os.getuid() or stat.S_IMODE(base.stat().st_mode)!=0o700:raise RuntimeError('Private owned observer workspace required')
if not (base/'attempt.claim').is_file():raise RuntimeError('Controller attempt claim required')
spec=importlib.util.spec_from_file_location('serial_protocol',root/'diagnostics/modem-control/passive_serial.py');protocol=importlib.util.module_from_spec(spec);spec.loader.exec_module(protocol)
before=json.loads((base/'before.json').read_text());port=Path('/sys/bus/usb/devices')/args.usb_port
def now():return datetime.now(timezone.utc).isoformat()
def read(path):
    try:return path.read_text().strip()
    except OSError:return None
def save(record):
    temporary=base/'serial-observation.tmp'
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as stream:
        stream.write(json.dumps(record,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(base/'serial-observation.json')
    directory=os.open(base,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
def native():return read(port/'idVendor')=='18d1' and read(port/'idProduct')=='d001'
def ram():return read(port/'idVendor')=='1d6b' and read(port/'idProduct')=='0104' and read(port/'serial')=='fx0-rmtfs-passive-r1' and read(port/'speed')=='480'
def tty():
    result=[];parent=port.resolve()
    for path in Path('/sys/class/tty').glob('ttyACM*'):
        if parent in (path/'device').resolve().parents:result.append(Path('/dev')/path.name)
    if len(result)!=1:raise RuntimeError('Expected one ACM console on selected RAM USB port')
    return result[0]
record={'started_UTC':now(),'state':'observing','candidate_seen':False,'worker_attempted':False,'worker_result':None,'returned_native_USB':False,'errors':[],'nonce':secrets.token_hex(8),'phone_partitions_written':False}
assert not (base/'serial-observation.json').exists();save(record)
probe_once=protocol.Once();worker_once=protocol.Once();capture=bytearray();descriptor=None;closed=False;probe=None;probe_sent=None;start=time.monotonic();generation=None
with (base/'serial-console.log').open('xb') as log:
    try:
        while time.monotonic()-start<360:
            if native() and read(port/'devnum')!=str(before['native_USB_generation']):
                record.update(returned_native_USB=True,native_return_USB_generation=read(port/'devnum'));break
            if ram() and not record['candidate_seen']:
                generation=read(port/'devnum');record.update(candidate_seen=True,RAM_USB_generation=generation);save(record)
            if record['candidate_seen'] and not closed and descriptor is None and ram():
                try:
                    node=tty();assert stat.S_ISCHR(node.stat().st_mode)
                    descriptor=os.open(node,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
                    fcntl.ioctl(descriptor,termios.TIOCEXCL)
                    settings=termios.tcgetattr(descriptor);settings[0]=settings[1]=settings[3]=0;settings[2]=termios.CS8|termios.CREAD|termios.CLOCAL;settings[4]=settings[5]=termios.B115200;settings[6][termios.VMIN]=0;settings[6][termios.VTIME]=0
                    termios.tcsetattr(descriptor,termios.TCSANOW,settings)
                    assert ram() and read(port/'devnum')==generation
                    probe_once.send(lambda data:os.write(descriptor,data),protocol.probe_command(record['nonce']));probe_sent=time.monotonic();record['probe_sent_UTC']=now();save(record)
                except BaseException as error:
                    record['errors'].append({'phase':'console-open-or-probe','type':type(error).__name__,'message':str(error)[:200]});closed=True
                    if descriptor is not None:os.close(descriptor);descriptor=None
                    save(record)
            if descriptor is not None:
                try:
                    if not ram() or read(port/'devnum')!=generation:raise RuntimeError('RAM USB generation changed; no console retry')
                    ready,_,_=select.select([descriptor],[],[],0.2)
                    if ready:
                        data=os.read(descriptor,8192)
                        if not data:raise RuntimeError('RAM console closed')
                        log.write(data);log.flush();capture.extend(data)
                        if len(capture)>256*1024:raise RuntimeError('RAM console capture bound')
                    if probe is None:
                        probe=protocol.parse_probe(bytes(capture),record['nonce'],before['boot_id'])
                        if probe is not None:
                            record['RAM_identity']=probe;record['worker_attempted']=True;record['worker_attempted_UTC']=now();save(record)
                            worker_once.send(lambda data:os.write(descriptor,data),protocol.worker_command(record['nonce']))
                            print('Exact passive-r1 RAM identity checked; worker command attempted once.',flush=True)
                        elif time.monotonic()-probe_sent>20:raise RuntimeError('Read-only RAM identity frame not observed; no worker command')
                    if record['worker_attempted'] and record['worker_result'] is None:
                        result=protocol.parse_result(bytes(capture),record['nonce'],probe['boot_id'])
                        if result is not None:
                            record['worker_result']=result;save(record);print('Passive worker result:',result['passed'],'exit',result['returncode'],'; observing independent return.',flush=True)
                except BaseException as error:
                    record['errors'].append({'phase':'console','type':type(error).__name__,'message':str(error)[:200]});closed=True
                    os.close(descriptor);descriptor=None;save(record)
            else:time.sleep(0.25)
        else:record['observation_deadline_reached']=True
    finally:
        if descriptor is not None:os.close(descriptor)
        record.update(state='terminal',finished_UTC=now(),console_closed=True);save(record)
print('Passive RAM observation terminal; native USB returned:',record['returned_native_USB'],flush=True)
raise SystemExit(0 if record['returned_native_USB'] else 1)
