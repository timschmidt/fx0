"""Exercise actual NVMEM keepout code and candidate match data with fake MMIO."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
TREE=KERNEL

def block(source,needle):
    start=source.index(needle);brace=source.index('{',start);end=brace+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    if source[end:end+1]==';':end+=1
    return source[start:end]

STUBS=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define min(a,b) ((a)<(b)?(a):(b))
#define CHECK(x) do { if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
struct nvmem_keepout {unsigned int start,end;unsigned char value;};
struct qfprom_soc_compatible_data {const struct nvmem_keepout *keepout;unsigned int nkeepout;bool raw_read_only;};
struct nvmem_device {const struct nvmem_keepout *keepout;unsigned int nkeepout;};
static unsigned int hardware_bytes,calls;
static bool allowed(unsigned int offset) {
 return (offset>=0xb0 && offset<0xb8) || (offset>=0x450 && offset<0x460);
}
static int __nvmem_reg_read(struct nvmem_device *n,unsigned int offset,void *val,size_t bytes) {
 (void)n;calls++;CHECK(offset+bytes<=4096);
 for(size_t i=0;i<bytes;i++)CHECK(allowed(offset+i));
 memset(val,0xa5,bytes);hardware_bytes+=bytes;return 0;
}
static int __nvmem_reg_write(struct nvmem_device *n,unsigned int o,void *v,size_t b) {
 (void)n;(void)o;(void)v;(void)b;CHECK(0);return -1;
}
'''
CASES=r'''
int main(void) {
 struct nvmem_device n={.keepout=msm8926_raw_qfprom.keepout,.nkeepout=msm8926_raw_qfprom.nkeepout};
 unsigned char buffer[4096];unsigned int ranges=0;unsigned int lengths[]={1,3,4,7,8,16,64,4096};
 CHECK(msm8926_raw_qfprom.raw_read_only && n.nkeepout==3);
 for(unsigned int offset=0;offset<4096;offset++) {
  for(size_t l=0;l<ARRAY_SIZE(lengths);l++) {
   unsigned int bytes=lengths[l];if(offset+bytes>4096)continue;
   memset(buffer,0xcc,sizeof(buffer));CHECK(!nvmem_access_with_keepouts(&n,offset,buffer,bytes,0));
   for(unsigned int i=0;i<bytes;i++)CHECK(buffer[i]==(allowed(offset+i)?0xa5:0));
   ranges++;
  }
 }
 hardware_bytes=calls=0;CHECK(!nvmem_access_with_keepouts(&n,0,buffer,4096,0));
 CHECK(hardware_bytes==24 && calls==2);
 hardware_bytes=calls=0;CHECK(!nvmem_access_with_keepouts(&n,0x1b0,buffer,8,0));
 CHECK(!hardware_bytes && !calls);for(int i=0;i<8;i++)CHECK(!buffer[i]);
 printf("%u bounded ranges passed; full bank reads 24 permitted bytes; secure row untouched\n",ranges);return 0;
}
'''

@unittest.skipUnless((TREE/'drivers/nvmem/qfprom.c').exists(),'Candidate kernel sources required')
class QfpromRawKeepoutTests(unittest.TestCase):
    def test_actual_core_filter_never_reads_protected_bytes(self):
        driver=(TREE/'drivers/nvmem/qfprom.c').read_text();core=(TREE/'drivers/nvmem/core.c').read_text()
        text=STUBS+'\n'+block(driver,'static const struct nvmem_keepout msm8926_raw_keepout[]')+'\n'+block(driver,'static const struct qfprom_soc_compatible_data msm8926_raw_qfprom')+'\n'+block(core,'static int nvmem_access_with_keepouts(')+'\n'+CASES
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source=base/'test.c';source.write_text(text);exe=base/'test'
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True,capture_output=True,text=True)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
            self.assertIn('secure row untouched',result.stdout)
            print(result.stdout.strip())
if __name__=='__main__':unittest.main()
