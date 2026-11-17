# SPDX-License-Identifier: GPL-2.0-only
"""Generate the two DSI headers with the exact current Kbuild generator command."""
from pathlib import Path
import hashlib,json,subprocess,sys
C=Path(sys.argv[1]);O=Path(sys.argv[2]);base=C/'drivers/gpu/drm/msm/registers';dst=O/'drivers/gpu/drm/msm/generated';dst.mkdir(parents=True);rows=[]
for name in ['dsi','dsi_phy_28nm']:
 command=[sys.executable,str(base/'gen_header.py'),'--no-validate','--rnn',str(base),'--xml',str(base/'display'/(name+'.xml')),'c-defines'];output=dst/(name+'.xml.h')
 with output.open('xb') as stream:subprocess.run(command,check=True,stdout=stream)
 rows.append(dict(command=command,output_SHA256=hashlib.sha256(output.read_bytes()).hexdigest()))
(O/'DSI-generator.json').write_text(json.dumps(dict(exact_Kbuild_generator=True,rows=rows,phone_access=False),indent=2)+'\n')
