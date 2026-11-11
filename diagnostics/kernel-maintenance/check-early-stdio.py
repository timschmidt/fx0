#!/usr/bin/env python3
"""Reproduce BusyBox background startup with absent/present early /dev/null."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('native_root',type=Path);p.add_argument('report',type=Path);a=p.parse_args();root=a.native_root.resolve();assert (root/'usr/bin/busybox').is_file() and (root/'qemu').is_file()
results={}
for present in [False,True]:
 cmd=['bwrap','--unshare-all','--die-with-parent','--clearenv','--ro-bind',str(root),'/','--ro-bind','/usr/bin/qemu-arm-static','/qemu','--tmpfs','/dev','--proc','/proc','--tmpfs','/tmp']
 if present:cmd+=['--dev-bind','/dev/null','/dev/null']
 cmd+=['/qemu','/usr/bin/busybox','ash','-c',"/qemu /usr/bin/busybox ash -c 'printf armed' & wait \"$!\""]
 result=subprocess.run(cmd,capture_output=True,text=True,timeout=15);results[str(present)]=dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
assert results['False']['returncode']==2 and "can't open '/dev/null'" in results['False']['stderr'],results
assert results['True']['returncode']==0 and results['True']['stdout']=='armed',results
record=dict(actual_native_ARM_BusyBox_used=True,missing_dev_null_background_launch_reproduced=True,present_dev_null_background_launch_succeeds=True,cases=results,phone_commands_or_reboot_requests=False);assert not a.report.exists();a.report.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
