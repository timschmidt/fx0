"""Parse APK's width-padded action counters without weakening exact selection checks."""
from collections import Counter
import re

ACTION=re.compile(r'^\s*\(\s*([0-9]+)\s*/\s*([0-9]+)\s*\)\s+'
    r'(Upgrading|Installing|Purging|Replacing|Downgrading|Reinstalling)\s+'
    r'([A-Za-z0-9+_.-]+)\s+\(([A-Za-z0-9+_.~:<>= -]+)\)\s*$')
DOWNLOAD=re.compile(r'^\s*\(\s*([0-9]+)\s*/\s*([0-9]+)\)\s+Downloading ([A-Za-z0-9+_.~:-]+)\s*$')
def parse(text):
    result=[];downloads=[]
    for line in text.splitlines():
        if not re.match(r'^\s*\(\s*[0-9]+\s*/',line):continue
        transfer=DOWNLOAD.fullmatch(line)
        if transfer:
            downloads.append((int(transfer[1]),int(transfer[2]),transfer[3]));continue
        m=ACTION.fullmatch(line);assert m,'Unexpected APK action format'
        result.append(dict(index=int(m[1]),total=int(m[2]),action=m[3],package=m[4],versions=m[5]))
    assert result and all(row['index']==i and row['total']==len(result) for i,row in enumerate(result,1)), 'Incomplete or inconsistent APK action sequence'
    if downloads:
        assert all(index==i and total==len(downloads) for i,(index,total,name) in enumerate(downloads,1)), 'Incomplete download progress'
        changed=Counter(r['package']+'-'+r['versions'].split(' -> ')[-1] for r in result if r['action']!='Purging')
        fetched=Counter(name for _,_,name in downloads)
        assert all(count==1 and count<=changed[name] for name,count in fetched.items()), 'Download outside exact transaction cohort'
    return result
def equivalent(expected_text,actual_text):
    key=lambda rows:Counter((r['action'],r['package'],r['versions']) for r in rows)
    expected=parse(expected_text);actual=parse(actual_text)
    assert len(expected)==len(actual) and key(expected)==key(actual),'APK action selection differs from the pinned cohort'
    return len(actual)
