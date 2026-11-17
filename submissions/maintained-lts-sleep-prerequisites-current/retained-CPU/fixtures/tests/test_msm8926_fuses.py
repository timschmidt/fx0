"""Execute the candidate calibration loader against NVMEM/SCM failures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/pmdomain/qcom'

STUBS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define EINVAL 22
#define EIO 5
#define EPROBE_DEFER 517
#define ENOMEM 12
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define clamp(x,l,h) min(max(x,l),h)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x)>=(uintptr_t)-4095)
#define PTR_ERR(x) ((int)(intptr_t)(x))
#define dev_err_probe(dev, err, ...) ((void)(dev), (err))
struct device { int unused; };
struct nvmem_cell { int index; };
struct nvmem_cell *nvmem_cell_get(struct device *, const char *);
void *nvmem_cell_read(struct nvmem_cell *, size_t *);
void nvmem_cell_put(struct nvmem_cell *);
void kfree_sensitive(const void *);
int qcom_scm_legacy_fuse_read(u32, u64 *);
static inline u64 get_unaligned_le64(const void *data) {
 const unsigned char *p=data;
 u64 value=0;
 for(unsigned int i=0;i<8;i++)value|=(u64)p[i]<<(8*i);
 return value;
}
'''

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "stubs.h"
#include "cpr-msm8926-fuses.h"
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static struct device device;
static struct nvmem_cell cells[]={{0},{1},{2}};
static const char *names[]={"cpu_calibration","cpr_primary","cpr_redundant"};
static u64 rows[3],conditional;
static int gets,reads,releases,frees,secure_calls,live_cell,live_buffer;
static int get_fault,read_fault,length_fault,secure_error,error_code;
static size_t bad_length;

struct nvmem_cell *nvmem_cell_get(struct device *dev,const char *name) {
 CHECK(dev==&device && gets<3 && !live_cell && !live_buffer);
 CHECK(!strcmp(name,names[gets]));
 int index=gets++;
 if(gets==get_fault)return ERR_PTR(error_code);
 live_cell=1;
 return &cells[index];
}
void *nvmem_cell_read(struct nvmem_cell *cell,size_t *length) {
 CHECK(live_cell && cell==&cells[gets-1]);
 reads++;
 if(reads==read_fault)return ERR_PTR(error_code);
 unsigned char *data=malloc(16);
 CHECK(data);
 for(int i=0;i<8;i++)data[i]=(rows[cell->index]>>(8*i))&255;
 *length=reads==length_fault?bad_length:8;
 live_buffer=1;
 return data;
}
void nvmem_cell_put(struct nvmem_cell *cell) {
 CHECK(live_cell && cell==&cells[gets-1]);
 live_cell=0;releases++;
}
void kfree_sensitive(const void *buffer) {
 CHECK(live_buffer && !live_cell);live_buffer=0;frees++;
 free((void *)buffer);
}
int qcom_scm_legacy_fuse_read(u32 address,u64 *value) {
 CHECK(address==0xfc4b81b0 && !gets && !reads);
 secure_calls++;*value=conditional;
 return secure_error;
}
static void reset(void) {
 gets=reads=releases=frees=secure_calls=live_cell=live_buffer=0;
 get_fault=read_fault=length_fault=secure_error=0;error_code=-EPROBE_DEFER;
 rows[0]=1|8|16|(21ULL<<6)|(1ULL<<53);
 rows[1]=(700ULL<<24)|(900ULL<<12)|1200|(1ULL<<37);
 rows[2]=(650ULL<<24)|(850ULL<<12)|1300;
 conditional=7ULL<<42;
}
static int run(void) {
 struct cpr_msm8926_calibration output,before,expected;
 memset(&output,0x5a,sizeof(output));before=output;
 int ret=cpr_msm8926_read_calibration(&device,&output);
 CHECK(!live_cell && !live_buffer);
 if(ret) {
  CHECK(!memcmp(&output,&before,sizeof(output)));
 } else {
  struct cpr_msm8926_fuses f={.row22=rows[0],.row138=rows[1],.row139=rows[2],
   .conditional_matches=((conditional>>42)&63)==7};
  CHECK(!cpr_msm8926_decode(&f,&expected));
  CHECK(!memcmp(&output,&expected,sizeof(output)));
  CHECK(secure_calls==1 && gets==3 && reads==3 && releases==3 && frees==3);
 }
 return ret;
}
int main(void) {
 struct cpr_msm8926_calibration output;
 reset();CHECK(!run());
 /* Preserve the full upper CPU row, including uplift and redundant PVS. */
 for(int redundant=0;redundant<2;redundant++)
  for(int uplift=0;uplift<2;uplift++)
   for(int match=0;match<2;match++) {
    reset();rows[0]=1|8|16|(21ULL<<6)|(5ULL<<27)|
     ((u64)redundant*2<<24)|((u64)!uplift<<53);
    if(redundant)rows[1]|=1ULL<<57;
    conditional=match?7ULL<<42:6ULL<<42;
    CHECK(!run());
   }
 reset();CHECK(cpr_msm8926_read_calibration(NULL,&output)==-EINVAL);
 CHECK(cpr_msm8926_read_calibration(&device,NULL)==-EINVAL);
 CHECK(!secure_calls && !gets);
 int errors[]={-EPROBE_DEFER,-EIO,-ENOMEM,-95};
 for(unsigned int e=0;e<sizeof(errors)/sizeof(errors[0]);e++) {
  reset();secure_error=errors[e];CHECK(run()==errors[e]);
  CHECK(secure_calls==1 && !gets && !reads);
  for(int position=1;position<=3;position++) {
   reset();get_fault=position;error_code=errors[e];CHECK(run()==errors[e]);
   CHECK(gets==position && reads==position-1 && releases==reads && frees==reads);
   reset();read_fault=position;error_code=errors[e];CHECK(run()==errors[e]);
   CHECK(gets==position && reads==position && releases==reads && frees==reads-1);
  }
 }
 reset();secure_error=1;CHECK(run()==-EIO);CHECK(!gets);
 size_t lengths[]={0,1,4,7,9,16};
 for(int position=1;position<=3;position++)
  for(unsigned int i=0;i<sizeof(lengths)/sizeof(lengths[0]);i++) {
   reset();length_fault=position;bad_length=lengths[i];
   CHECK(run()==-EINVAL);
   CHECK(reads==position && gets==reads && releases==reads && frees==reads);
  }
 /* Other secure bits cannot influence the selector comparison. */
 reset();conditional=~(63ULL<<42)|(7ULL<<42);CHECK(!run());
 puts("SCM/NVMEM faults, 18 malformed lengths, full-row decoding and cleanup passed");
 return 0;
}
'''


class CalibrationLoadTests(unittest.TestCase):
    def test_transport_errors_lengths_and_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'linux/firmware/qcom').mkdir(parents=True)
            for header in ['device.h', 'err.h', 'errno.h', 'types.h', 'minmax.h',
                           'nvmem-consumer.h', 'slab.h', 'unaligned.h',
                           'firmware/qcom/qcom_scm.h']:
                (base/'linux'/header).write_text('')
            (base/'stubs.h').write_text(STUBS)
            for name in ['cpr-msm8926.h', 'cpr-msm8926-fuses.h']:
                (base/name).write_bytes((SOURCE/name).read_bytes())
            source, executable = base/'test.c', base/'test'
            source.write_text(HARNESS)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(base), str(source), '-o', str(executable)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], check=True,
                                    capture_output=True, text=True)
            self.assertIn('full-row decoding and cleanup passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
