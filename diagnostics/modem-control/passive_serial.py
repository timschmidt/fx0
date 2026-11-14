# SPDX-License-Identifier: MIT
"""Fixed read-only probe and one-shot worker framing for the owned RAM trial."""
import re

RELEASE='6.18.63-fx0-vibrator-alpine'
NOTES='05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
TOKEN='fx0.native_trial=r1-rmtfs-passive-01'


def checked_nonce(nonce):
    if re.fullmatch('[a-f0-9]{16}',nonce) is None:
        raise ValueError('Invalid trial framing nonce')
    return nonce


def probe_command(nonce):
    checked_nonce(nonce)
    return ("printf '\\nPROBE_"+nonce+"_BEGIN\\n'; "
            "printf 'RELEASE='; /bin/busybox uname -r; "
            "printf 'BOOT='; /bin/busybox cat /proc/sys/kernel/random/boot_id; "
            "printf 'CMD='; /bin/busybox cat /proc/cmdline; "
            "printf 'NOTES='; /bin/busybox sha256sum /sys/kernel/notes; "
            "printf 'UPTIME='; /bin/busybox cat /proc/uptime; "
            "printf 'PROBE_"+nonce+"_END\\n'\n").encode()


def lines(data):
    if len(data)>256*1024:
        raise ValueError('RAM console capture limit')
    return data.decode('utf-8',errors='replace').replace('\r\n','\n').splitlines()


def parse_probe(data,nonce,previous_boot):
    checked_nonce(nonce);rows=lines(data)
    begin='PROBE_'+nonce+'_BEGIN';end='PROBE_'+nonce+'_END'
    if begin not in rows or end not in rows:
        return None
    if rows.count(begin)!=1 or rows.count(end)!=1 or rows.index(begin)>=rows.index(end):
        raise ValueError('Ambiguous probe frame')
    fields={}
    for row in rows[rows.index(begin)+1:rows.index(end)]:
        key,separator,value=row.partition('=')
        if not separator or key in fields:
            raise ValueError('Malformed probe fields')
        fields[key]=value
    if set(fields)!={'RELEASE','BOOT','CMD','NOTES','UPTIME'}:
        raise ValueError('Incomplete probe identity')
    if fields['RELEASE']!=RELEASE or fields['NOTES'].split()!=[NOTES,'/sys/kernel/notes']:
        raise ValueError('Wrong linked RAM kernel')
    if re.fullmatch('[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}',fields['BOOT']) is None or fields['BOOT']==previous_boot:
        raise ValueError('RAM boot identity not new')
    tokens=fields['CMD'].split()
    if tokens.count(TOKEN)!=1 or [word for word in tokens if word.startswith('fx0.native_trial=')]!=[TOKEN] or 'module.sig_enforce=1' not in tokens:
        raise ValueError('Wrong RAM token or signature mode')
    uptime=float(fields['UPTIME'].split()[0])
    if not 0<=uptime<90:
        raise ValueError('Insufficient worker time before return')
    return {'boot_id':fields['BOOT'],'kernel':fields['RELEASE'],'notes_SHA256':NOTES,'uptime':uptime}


def worker_command(nonce):
    checked_nonce(nonce)
    return ("printf '\\nRUN_"+nonce+"_BEGIN\\n'; /bin/rmtfs-passive; "
            "fx0_result=$?; printf '\\nRUN_"+nonce+"_RC=%s\\n' \"$fx0_result\"\n").encode()


def parse_result(data,nonce,boot_id):
    checked_nonce(nonce);rows=lines(data);begin='RUN_'+nonce+'_BEGIN';prefix='RUN_'+nonce+'_RC='
    statuses=[(index,row) for index,row in enumerate(rows) if row.startswith(prefix)]
    if not statuses:
        return None
    if rows.count(begin)!=1 or len(statuses)!=1 or rows.index(begin)>=statuses[0][0]:
        raise ValueError('Ambiguous worker frame')
    value=statuses[0][1][len(prefix):]
    if re.fullmatch('[0-9]{1,3}',value) is None or int(value)>255:
        raise ValueError('Malformed worker exit status')
    body=rows[rows.index(begin)+1:statuses[0][0]]
    markers=[row for row in body if row.startswith(('RMTFS_PASSIVE_BEGIN ','RMTFS_LOCAL_SERVICE_','RMTFS_RFSA_OPEN ','RMTFS_PASSIVE_PASS'))]
    expected=['RMTFS_PASSIVE_BEGIN '+boot_id,'RMTFS_LOCAL_SERVICE_ABSENT','RMTFS_LOCAL_SERVICE_PRESENT','RMTFS_RFSA_OPEN /dev/qcom_rmtfs_mem1','RMTFS_LOCAL_SERVICE_ABSENT','RMTFS_PASSIVE_PASS']
    passed=int(value)==0 and markers==expected and not any('RMTFS_PASSIVE_FAIL' in row for row in body)
    return {'complete':True,'passed':passed,'returncode':int(value),'observed_markers':markers,'expected_markers':expected}


class Once:
    def __init__(self):
        self.attempted=False

    def send(self,writer,command):
        if self.attempted:
            raise RuntimeError('Serial command already attempted; do not retry')
        self.attempted=True
        if writer(command)!=len(command):
            raise RuntimeError('Short serial write; outcome uncertain; do not retry')
