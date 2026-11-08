"""Run the actual candidate probe with fake resources, never real MMIO."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE=Path(os.environ.get('FX0_QFPROM_SOURCE',KERNEL/'drivers/nvmem/qfprom.c'))
STUBS=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define __iomem
#define GFP_KERNEL 0
#define IORESOURCE_MEM 1
#define NVMEM_DEVID_AUTO -1
#define QFPROM_VERSION_OFFSET 0
#define QFPROM_MAJOR_VERSION_SHIFT 28
#define QFPROM_MINOR_VERSION_SHIFT 16
#define QFPROM_MAJOR_VERSION_MASK (15u << 28)
#define QFPROM_MINOR_VERSION_MASK (4095u << 16)
#define ERR_PTR(v) ((void *)(intptr_t)(v))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define PTR_ERR_OR_ZERO(p) (IS_ERR(p) ? PTR_ERR(p) : 0)
#define dev_err_probe(dev,err,...) (err)
struct device { int unused; };
struct platform_device { struct device dev; };
struct resource { size_t start,end; };
#define resource_size(r) ((r)->end-(r)->start+1)
struct qfprom_soc_data { int unused; };
struct qfprom_soc_compatible_data { const void *keepout; unsigned nkeepout; bool raw_read_only; };
struct qfprom_priv { void *qfpcorrected,*qfpraw,*qfpconf,*qfpsecurity,*vcc,*secclk; struct device *dev; const struct qfprom_soc_data *soc_data; };
struct nvmem_device { int unused; };
struct nvmem_config {
 const char *name; bool add_legacy_fixed_of_cells,read_only,root_only;
 int stride,word_size,id;
 int (*reg_read)(void *,unsigned,void *,size_t);
 int (*reg_write)(void *,unsigned,void *,size_t);
 void (*fixup_dt_cell_info)(void);
 size_t size; struct device *dev; void *priv;
 const void *keepout; unsigned nkeepout;
};
static const struct qfprom_soc_data qfprom_7_8_data={0},qfprom_7_15_data={0};
static struct qfprom_soc_compatible_data data;
static struct resource regions[4];
static int count,maps,clocks,regulators,registered,pm_enabled,pm_disabled;
static int fail_alloc,fail_map,fail_action,fail_register,clock_present;
static void *allocation;
static struct nvmem_config captured;
static unsigned char memory[64];
static const void *device_get_match_data(struct device *d) { (void)d;return &data; }
static struct resource *platform_get_resource(struct platform_device *p,int type,int n) { (void)p;(void)type;return n<count?&regions[n]:NULL; }
static void *devm_kzalloc(struct device *d,size_t size,int flags) { (void)d;(void)flags;if(fail_alloc)return NULL;allocation=calloc(1,size);return allocation; }
static void *devm_platform_get_and_ioremap_resource(struct platform_device *p,int n,struct resource **r) { (void)p;maps++;*r=&regions[n];return fail_map?ERR_PTR(-ENXIO):memory; }
static void *devm_ioremap_resource(struct device *d,struct resource *r) { (void)d;(void)r;maps++;return memory; }
static void *devm_platform_ioremap_resource(struct platform_device *p,int n) { (void)p;(void)n;maps++;return memory; }
static u32 readl(void *p) { (void)p;return (7u<<28)|(15u<<16); }
static void *devm_regulator_get(struct device *d,const char *n) { (void)d;(void)n;regulators++;return memory; }
static void *devm_clk_get_optional(struct device *d,const char *n) { (void)d;(void)n;clocks++;return clock_present?memory:NULL; }
static void pm_runtime_enable(struct device *d) { (void)d;pm_enabled++; }
static void qfprom_runtime_disable(void *d) { (void)d;pm_disabled++; }
static int devm_add_action_or_reset(struct device *d,void (*fn)(void *),void *arg) { (void)d;if(fail_action){fn(arg);return -ENOMEM;}return 0; }
static int qfprom_reg_read(void *p,unsigned o,void *v,size_t n) { (void)p;(void)o;(void)v;(void)n;return 0; }
static int qfprom_reg_write(void *p,unsigned o,void *v,size_t n) { (void)p;(void)o;(void)v;(void)n;return 0; }
static void qfprom_fixup_dt_cell_info(void) {}
static struct nvmem_device *devm_nvmem_register(struct device *d,struct nvmem_config *config) { (void)d;registered++;captured=*config;return fail_register?ERR_PTR(-EIO):(struct nvmem_device *)memory; }
'''
CASES=r'''
#define CHECK(x) do { if(!(x)){fprintf(stderr,"failed line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
static void reset(bool raw,int resources) {
 free(allocation);allocation=NULL;memset(&data,0,sizeof(data));data.raw_read_only=raw;
 count=resources;for(int i=0;i<4;i++){regions[i].start=i*4096;regions[i].end=i*4096+4095;}
 maps=clocks=regulators=registered=pm_enabled=pm_disabled=0;
 fail_alloc=fail_map=fail_action=fail_register=0;clock_present=1;memset(&captured,0,sizeof(captured));
}
int main(void) {
 struct platform_device p={0};
 reset(true,1);CHECK(qfprom_probe(&p)==0);CHECK(registered==1);CHECK(captured.read_only && captured.root_only);CHECK(!strcmp(captured.name,"qfprom-raw"));CHECK(captured.reg_write==NULL);CHECK(captured.reg_read==qfprom_reg_read);CHECK(maps==1 && clocks==0 && regulators==0);
 reset(true,4);CHECK(qfprom_probe(&p)==-EINVAL);CHECK(maps==0 && registered==0 && clocks==0 && regulators==0);
 reset(false,1);CHECK(qfprom_probe(&p)==0);CHECK(!strcmp(captured.name,"qfprom"));CHECK(!captured.read_only && !captured.root_only && captured.reg_write==NULL);
 reset(false,4);CHECK(qfprom_probe(&p)==0);CHECK(captured.reg_write==qfprom_reg_write);CHECK(maps==4 && clocks==1 && regulators==1);
 reset(false,4);clock_present=0;CHECK(qfprom_probe(&p)==0);CHECK(captured.reg_write==NULL);
 reset(true,1);fail_alloc=1;CHECK(qfprom_probe(&p)==-ENOMEM);CHECK(maps==0 && registered==0);
 reset(true,1);fail_map=1;CHECK(qfprom_probe(&p)==-ENXIO);CHECK(registered==0 && clocks==0 && regulators==0);
 reset(true,1);fail_action=1;CHECK(qfprom_probe(&p)==-ENOMEM);CHECK(pm_enabled==1 && pm_disabled==1 && registered==0);
 reset(true,1);fail_register=1;CHECK(qfprom_probe(&p)==-EIO);CHECK(captured.reg_write==NULL && captured.read_only && captured.root_only);
 free(allocation);puts("9 actual-probe contracts passed");return 0;
}
'''

@unittest.skipUnless(SOURCE.exists(),'Candidate QFPROM source required')
class QfpromRawProbeTests(unittest.TestCase):
    def test_probe_contracts(self):
        source=SOURCE.read_text();start=source.index('static int qfprom_probe(');body=source.index('{',start);depth=1;end=body+1
        while depth:
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);c=base/'probe.c';exe=base/'probe';c.write_text(STUBS+'\n'+source[start:end]+'\n'+CASES)
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True,capture_output=True,text=True)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
            self.assertIn('9 actual-probe contracts passed',result.stdout)

if __name__=='__main__':unittest.main()
