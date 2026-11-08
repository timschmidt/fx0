#!/usr/bin/env python3
"""Stage, read back and RAM-boot a checked Fx0 Android image through lk2nd.

Linux only. Uses fastboot stage/get_staged with persistent logs and no transfer
kill deadline, then sends only the standard boot command. Never flashes. Keep
output in ignored private storage. Device observation/recovery is separate.
"""
import argparse
import ctypes as c
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

class Bulk(c.Structure):
 _fields_=[('endpoint',c.c_uint),('length',c.c_uint),('timeout',c.c_uint),('data',c.c_void_p)]
lib=c.CDLL(None,use_errno=True);lib.ioctl.argtypes=[c.c_int,c.c_ulong,c.c_void_p];lib.ioctl.restype=c.c_int
BULK=0xc0005502 | (c.sizeof(Bulk)<<16);CLAIM=0x8004550f;RELEASE=0x80045510

def ioctl(fd,command,arg):
 result=lib.ioctl(fd,command,c.byref(arg))
 if result<0:raise OSError(c.get_errno(),os.strerror(c.get_errno()))
 return result

def transfer(fd,endpoint,data=None):
 buffer=c.create_string_buffer(data if data is not None else 64)
 size=len(data) if data is not None else 64
 request=Bulk(endpoint,size,5000,c.addressof(buffer))
 size=ioctl(fd,BULK,request)
 return size if data is not None else buffer.raw[:size]

def command(fd,output,input_,payload):
 if payload not in [b'getvar:product',b'getvar:lk2nd:version',b'boot']:raise ValueError('Command not permitted')
 if transfer(fd,output,payload)!=len(payload):raise RuntimeError('Short command write')
 responses=[]
 for _ in range(32):
  packet=transfer(fd,input_);responses.append(packet.decode(errors='replace'))
  if packet[:4]==b'OKAY':return responses
  if packet[:4]==b'FAIL':raise RuntimeError(str(responses))
  if packet[:4]!=b'INFO' and packet:raise RuntimeError('Unexpected fastboot response '+repr(packet))
 raise RuntimeError('Too many fastboot responses')

def require(condition,message):
 if not condition:raise ValueError(message)

def read(path):
 try:return path.read_text().strip()
 except OSError:return None

def device(serial):
 ports=[p for p in Path('/sys/bus/usb/devices').iterdir()
        if read(p/'idVendor')=='18d1' and read(p/'idProduct')=='d00d' and read(p/'serial')==serial]
 require(len(ports)==1,'Expected exactly one matching lk2nd USB device')
 port=ports[0];data=(port/'descriptors').read_bytes();interfaces=[];current=None;offset=0
 while offset<len(data):
  require(offset+2<=len(data),'Truncated USB descriptor')
  length,kind=data[offset],data[offset+1]
  require(length>=2 and offset+length<=len(data),'Invalid USB descriptor length')
  item=data[offset:offset+length]
  if kind==4:
   require(length>=9,'Truncated interface descriptor')
   current={'number':item[2],'class':item[5:8],'endpoints':[]};interfaces.append(current)
  elif kind==5 and current is not None:
   require(length>=7,'Truncated endpoint descriptor')
   if item[3]&3==2:current['endpoints'].append(item[2])
  offset+=length
 matches=[v for v in interfaces if v['class']==bytes([255,66,3])]
 require(len(matches)==1,'Expected exactly one fastboot interface')
 interface=matches[0];outs=[e for e in interface['endpoints'] if not e&128];ins=[e for e in interface['endpoints'] if e&128]
 require(len(outs)==len(ins)==1,'Expected one bulk endpoint per direction')
 node=Path('/dev/bus/usb')/f'{int(read(port/"busnum")):03d}'/f'{int(read(port/"devnum")):03d}'
 return node,interface['number'],outs[0],ins[0]

def query(serial,boot=False):
 node,number,out,input_=device(serial);fd=os.open(node,os.O_RDWR);index=c.c_uint(number);claimed=False
 try:
  ioctl(fd,CLAIM,index);claimed=True
  product=command(fd,out,input_,b'getvar:product')
  require(product[-1].rstrip('\0')=='OKAYlk2nd-msm8226','Unexpected bootloader product')
  result={'product':product,'lk2nd_version':command(fd,out,input_,b'getvar:lk2nd:version')}
  if boot:result['boot_response']=command(fd,out,input_,b'boot')
  return result
 finally:
  if claimed:
   try:ioctl(fd,RELEASE,index)
   except OSError:pass
  os.close(fd)

def checked_transfer(image,expected,serial,output,probe=query,runner=subprocess.run):
 image=Path(image).resolve();output=Path(output)
 require(re.fullmatch('[0-9a-f]{64}',expected) is not None,'Expected a lower-case SHA-256')
 data=image.read_bytes();require(data[:8]==b'ANDROID!','Expected an Android boot image')
 require(hashlib.sha256(data).hexdigest()==expected,'Image checksum mismatch')
 report={'started_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_sha256':expected,'phase':'identity probe'}
 def save():(output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  report['identity']=probe(serial);report['phase']='staging';save()
  with (output/'fastboot.log').open('w') as log:
   for args in [['stage',str(image)],['get_staged',str(output/'readback.img')]]:
    r=runner(['fastboot','-v','-s',serial,*args],stdout=log,stderr=log,text=True)
    require(r.returncode==0,'Fastboot transfer failed; inspect its log and current device state')
  received=(output/'readback.img').read_bytes()
  require(received==data,'RAM readback differs; no boot command sent')
  report['readback_sha256']=hashlib.sha256(received).hexdigest();report['readback_bytes']=len(received)
  report['phase']='boot requested';save()
  report['handoff']=probe(serial,boot=True);report['phase']='boot acknowledged'
 except Exception as error:
  report['error']=str(error).replace(serial,'<serial>');save();raise
 report['finished_UTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();return report

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--serial',required=True);p.add_argument('--image',type=Path,required=True)
 p.add_argument('--sha256',required=True);p.add_argument('--output',type=Path,required=True)
 args=p.parse_args();args.output.mkdir(parents=True,mode=0o700)
 result=checked_transfer(args.image,args.sha256,args.serial,args.output)
 print('RAM boot acknowledged after exact image readback; observe the device and its return path.')

if __name__=='__main__':main()
