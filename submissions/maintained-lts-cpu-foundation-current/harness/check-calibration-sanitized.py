# SPDX-License-Identifier: GPL-2.0-only
"""Actual decoder versus the independent compiled-vendor-array Python oracle."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,random,subprocess
b=Path(__file__).resolve().parent;root=b/'fixtures'
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--mutation',choices=['clock-selector','conditional-minimum','read-error']);a=p.parse_args();a.output.mkdir(mode=0o700)
spec=importlib.util.spec_from_file_location('vendor_oracle',root/'tests/test_msm8926_calibration.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
header=(a.source/'drivers/pmdomain/qcom/cpr-msm8926.h').read_text()
if a.mutation:
 changes={'clock-selector':('selector == 1 ?','selector == 2 ?'),'conditional-minimum':('result.minimum_override = !fuses->conditional_matches;','result.minimum_override = !!fuses->conditional_matches;'),'read-error':('if (fuses->read_status)','if (false && fuses->read_status)')}
 old,new=changes[a.mutation];assert old in header;header=header.replace(old,new)
linux=a.output/'linux';linux.mkdir()
(linux/'types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint64_t u64;typedef uint32_t u32;\n')
(linux/'errno.h').write_text('#define EINVAL 22\n#define EIO 5\n')
(linux/'minmax.h').write_text('#define min(a,b) ((a)<(b)?(a):(b))\n#define max(a,b) ((a)>(b)?(a):(b))\n#define clamp(x,l,h) min(max(x,l),h)\n')
(a.output/'cpr-msm8926.h').write_text(header)
vectors=[]
def add(row,primary,backup,matches,status=0,secure=0,ret=43):
 expected=oracle.reference(row,primary,backup,matches) if ret==43 else [0xdeadbeef]*43
 vectors.append((row,primary,backup,status,secure,matches,ret,[int(v) for v in expected]))
primary=700<<24|900<<12|1200|5<<54|3<<38|6<<41;backup=650<<24|850<<12|1300|7<<46|2<<36|4<<39
for selector in range(8):
 for pvs in range(32):
  for redundant in range(2):
   for matches in range(2):add(8|16|pvs<<6|selector<<24|(31-pvs)<<27,primary|redundant<<57,backup,matches)
for speed in range(8):
 for version in range(4):
  for valid in range(2):
   for upper in range(2):
    for flags in range(4):
     for matches in range(2):add(speed|valid<<3|version<<4|10<<6|upper<<53,700<<24|900<<12|1200|(flags&1)<<36|(flags>>1)<<37,0,matches)
for svs,normal,turbo in [(0,0,0),(900,800,1200),(700,900,950),(700,900,951),(4095,4095,4095),(0,1,4095)]:
 for redundant in range(2):
  row=svs<<24|normal<<12|turbo;add(24,row|redundant<<57,row,1)
rng=random.Random(8926)
for _ in range(2000):add(rng.getrandbits(64),rng.getrandbits(64),rng.getrandbits(64),rng.randrange(2))
for status,secure,matches,ret in [(-5,0,1,-5),(1,0,1,-5),(0,-517,1,-517),(0,4,1,-5),(0,0,-1,-22),(0,0,2,-22)]:add(24,0,0,matches,status,secure,ret)
text='struct vector { unsigned long long row22,row138,row139; int status,secure,matches,ret;unsigned out[43]; };\nstatic const struct vector vectors[]={\n'
for r,pr,ba,st,se,ma,re,ex in vectors:text+='{'+f'{r}ULL,{pr}ULL,{ba}ULL,{st},{se},{ma},{re},'+'{'+','.join(str(v)+'U' for v in ex)+'}},\n'
text+='};\n'
main=r'''
#include <stdio.h>
#include <string.h>
static unsigned checks,failures;
#define CHECK(c) do { checks++; if(!(c)) { failures++; if(failures<4) printf("FAIL %u %s\n",checks,#c); } } while(0)
int main(void) {
 for(unsigned i=0;i<sizeof(vectors)/sizeof(vectors[0]);i++) {
  const struct vector *v=&vectors[i];unsigned out[43];
  for(unsigned k=0;k<43;k++)out[k]=0xdeadbeef;
  int ret=decode(v->row22,v->row138,v->row139,v->status,v->secure,v->matches,out);
  CHECK(ret==v->ret);
  for(unsigned k=0;k<43;k++)CHECK(out[k]==v->out[k]);
 }
 struct cpr_msm8926_calibration c,before;struct cpr_msm8926_fuses f={0};
 memset(&c,0xa5,sizeof(c));memcpy(&before,&c,sizeof(c));
 CHECK(cpr_msm8926_decode(NULL,&c)==-EINVAL);CHECK(!memcmp(&before,&c,sizeof(c)));
 CHECK(cpr_msm8926_decode(&f,NULL)==-EINVAL);
 printf("{\"cases\":%zu,\"checks\":%u,\"failures\":%u}\n",sizeof(vectors)/sizeof(vectors[0])+2,checks,failures);
 return failures!=0;
}
'''
program=oracle.WRAPPER+text+main;(a.output/'model.c').write_text(program)
r=subprocess.run(['clang-21','-std=gnu11','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(a.output),str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,timeout=120)
(a.output/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
r=subprocess.run([str(a.output/'model')],capture_output=True,text=True,timeout=60)
(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=json.loads(r.stdout.splitlines()[-1]);j.update(returncode=r.returncode,mutation=a.mutation,sanitizer_diagnostics=bool(r.stderr),actual_header_SHA256=hashlib.sha256(header.encode()).hexdigest(),program_SHA256=hashlib.sha256(program.encode()).hexdigest(),independent_oracle='compiled vendor property arrays and Python sequence',all_fuse_vectors_synthetic=True,physical_calibration_acceptance=False)
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert r.returncode==(1 if a.mutation else 0) and not r.stderr
