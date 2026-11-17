# SPDX-License-Identifier: GPL-2.0-only
"""Execute the actual LTS register generator with independent hash seeds."""
from pathlib import Path
import argparse,collections,hashlib,json,os,re,subprocess,sys
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();C=a.source.resolve();O=a.output.resolve();O.mkdir();source=C/'drivers/gpu/drm/msm/registers/gen_header.py';t=source.read_text();needle='for variant in sorted(self.variants):';assert t.count(needle)==1;mutant=O/'unsorted-gen_header.py';mutant.write_text(t.replace(needle,'for variant in self.variants:'));records=[];bodies={}
for label,script in [('current',source),('unsorted',mutant)]:
 hashes=[]
 for seed in ['1','2','42','77','123']:
  r=subprocess.run([sys.executable,'-B',str(script),'--rnn',str(source.parent),'--xml',str(source.parent/'adreno/a6xx.xml'),'c-defines'],env=os.environ|{'PYTHONHASHSEED':seed,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=60);(O/(label+'-'+seed+'.stderr')).write_bytes(r.stderr);assert r.returncode==0 and not r.stderr,r.stderr;p=O/(label+'-'+seed+'.h');p.write_bytes(r.stdout);hashes.append(hashlib.sha256(r.stdout).hexdigest());bodies[label+'-'+seed]=r.stdout.decode()
 records.append(dict(label=label,seeds=5,unique_headers=len(set(hashes)),SHA256=hashes))
assert records[0]['unique_headers']==1 and records[1]['unique_headers']>1
# Only ordering of complete usage-array declarations may differ.
pattern=r'template<> constexpr inline uint16_t \w+_REGS<[^>]+>\[\] = \{.*?\};\n'
reference=bodies['current-1'];arrays=re.findall(pattern,reference,re.S);assert arrays
for label,body in bodies.items():assert collections.Counter(re.findall(pattern,body,re.S))==collections.Counter(arrays) and re.sub(pattern,'',body,flags=re.S)==re.sub(pattern,'',reference,flags=re.S),label
j=dict(passed=True,records=records,usage_arrays=len(arrays),all_array_keys_registers_and_nonusage_declarations_preserved=True,source_SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),generator_executed_only_XML_and_header_output=True,phone_access=False);(O/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(passed=True,usage_arrays=len(arrays),current_unique=1,regressed_unique=records[1]['unique_headers'])))
