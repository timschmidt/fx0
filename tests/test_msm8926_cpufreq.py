"""Execute the supplier query and CPUfreq probe, including unwind and retries."""
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
TREE = KERNEL
spec = importlib.util.spec_from_file_location('domain', ROOT/'tests/test_msm8926_domain.py')
FIXTURE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FIXTURE)

COMMON = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define EPROBE_DEFER 517
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
typedef uint32_t u32;
struct device_node { int refs; const char *compatible; };
struct device { struct device_node *of_node; void *driver,*platform_data; int refs,id; };
struct platform_device { struct device dev; void *data; };
struct device_driver { int unused; };
struct platform_driver { struct device_driver driver; };
static __attribute__((unused)) void of_node_put(struct device_node *np) { if(np)CHECK(np->refs-->0); }
static __attribute__((unused)) int of_device_is_compatible(struct device_node *np,const char *name) {
 return np && !strcmp(np->compatible,name);
}
static __attribute__((unused)) void *platform_get_drvdata(struct platform_device *p) {return p->data;}
'''

QUERY = r'''
struct of_phandle_args { struct device_node *np; int args_count; };
struct cpr_msm8926_data { u32 supported_hw; };
struct cpr_drv { struct cpr_msm8926_data *msm8926; };
static struct platform_driver cpr_driver;
static struct device_node supplier_node={.compatible="qcom,msm8926-cpr"};
static struct platform_device supplier;
static int name_error,parse_error,args_count,missing,locked;
static int of_property_match_string(struct device_node *np,const char *prop,const char *name) {
 CHECK(np && !strcmp(prop,"power-domain-names") && !strcmp(name,"cpr"));
 return name_error?name_error:1;
}
static int of_parse_phandle_with_args(struct device_node *np,const char *prop,
 const char *cells,int index,struct of_phandle_args *args) {
 CHECK(np && !strcmp(prop,"power-domains") && !strcmp(cells,"#power-domain-cells") && index==1);
 if(parse_error)return parse_error;
 supplier_node.refs++;*args=(struct of_phandle_args){&supplier_node,args_count};return 0;
}
static struct platform_device *of_find_device_by_node(struct device_node *np) {
 CHECK(np==&supplier_node);if(missing)return NULL;supplier.dev.refs++;return &supplier;
}
static void device_lock(struct device *dev) {CHECK(dev==&supplier.dev && !locked);locked=1;}
static void device_unlock(struct device *dev) {CHECK(dev==&supplier.dev && locked);locked=0;}
static void put_device(struct device *dev) {CHECK(dev==&supplier.dev && dev->refs-->0);}
'''

QUERY_MAIN = r'''
int main(void) {
 struct device_node cpu_node={.compatible="cpu"};struct device cpu={.of_node=&cpu_node};
 struct cpr_msm8926_data data={127};struct cpr_drv drv={&data};
 supplier.dev.driver=&cpr_driver.driver;supplier.data=&drv;
 for(int fault=0;fault<12;fault++) {
  u32 out=0x5a5a5a5a;int expected=-EINVAL;
  if(fault==3){name_error=-ENOENT;expected=-ENOENT;}
  if(fault==4){parse_error=-EPROBE_DEFER;expected=-EPROBE_DEFER;}
  if(fault==5)args_count=1;
  if(fault==6)supplier_node.compatible="qcom,qcs404-cpr";
  if(fault==7){missing=1;expected=-EPROBE_DEFER;}
  if(fault==8){supplier.dev.driver=NULL;expected=-EPROBE_DEFER;}
  if(fault==9){supplier.data=NULL;expected=-EPROBE_DEFER;}
  if(fault==10){drv.msm8926=NULL;expected=-EPROBE_DEFER;}
  if(fault==11)data.supported_hw=0;
  if(fault==1)cpu.of_node=NULL;
  CHECK(qcom_cpr_msm8926_get_supported_hw(fault==0?NULL:&cpu,fault==2?NULL:&out)==expected);
  CHECK(out==0x5a5a5a5a && !locked && !supplier.dev.refs && !supplier_node.refs);
  cpu.of_node=&cpu_node;name_error=parse_error=args_count=missing=0;
  supplier_node.compatible="qcom,msm8926-cpr";supplier.dev.driver=&cpr_driver.driver;
  supplier.data=&drv;drv.msm8926=&data;data.supported_hw=127;
  CHECK(!qcom_cpr_msm8926_get_supported_hw(&cpu,&out) && out==127);
  CHECK(!locked && !supplier.dev.refs && !supplier_node.refs);
 }
 puts("12 supplier failures preserve output and release references; every retry passes");
}
'''

PROBE = r'''
#define GFP_KERNEL 0
#define __free(x) __attribute__((cleanup(cleanup_##x)))
#define struct_size(p,member,count) (sizeof(*(p))+sizeof((p)->member[0])*(count))
#define num_possible_cpus() 4
#define for_each_present_cpu(cpu) for((cpu)=0;(cpu)<4;(cpu)++)
#define dev_err(...) ((void)0)
#define PD_FLAG_DEV_LINK_ON 1
#define PD_FLAG_REQUIRED_OPP 2
static void cleanup_device_node(struct device_node **np) {of_node_put(*np);}
struct of_device_id { const void *data; };
struct nvmem_cell { int unused; };
struct dev_pm_domain_list {int id;};
struct dev_pm_opp_config { const u32 *supported_hw;unsigned supported_hw_count;const char *prop_name; };
struct dev_pm_domain_attach_data {const char **pd_names;unsigned num_pd_names,pd_flags;};
struct qcom_cpufreq_drv;
struct qcom_cpufreq_match_data {
 int (*get_version)(struct device *,struct nvmem_cell *,char **,struct qcom_cpufreq_drv *);
 const char **pd_names; unsigned num_pd_names;bool cpr_supported_hw;
};
struct qcom_cpufreq_drv_cpu {int opp_token;struct dev_pm_domain_list *pd_list;};
struct qcom_cpufreq_drv {u32 versions;const struct qcom_cpufreq_match_data *data;struct qcom_cpufreq_drv_cpu cpus[];};
static struct device_node table={.compatible="operating-points-v2-msm8926-cpu"};
static struct device cpus[4];
static struct dev_pm_domain_list domains[4];
static struct platform_device child,*cpufreq_dt_pdev;
static int cpu_missing,alloc_fail,query_fail,config_fail,attach_fail,register_fail;
static int query_calls,configs[4],attachments[4],registrations,unregisters,clears,detaches;
static void *allocation;
static struct device *get_cpu_device(unsigned cpu) {return (int)cpu==cpu_missing?NULL:&cpus[cpu];}
static struct device_node *dev_pm_opp_of_get_opp_desc_node(struct device *cpu) {
 CHECK(cpu==&cpus[0]);table.refs++;return &table;
}
static void *devm_kzalloc(struct device *dev,size_t size,int flags) {
 (void)dev;(void)flags;if(alloc_fail)return NULL;return allocation=calloc(1,size);
}
static int qcom_cpr_msm8926_get_supported_hw(struct device *cpu,u32 *mask) {
 CHECK(cpu==&cpus[0]);query_calls++;
 for(int i=0;i<4;i++)CHECK(!configs[i] && !attachments[i]);
 if(query_fail)return -EPROBE_DEFER;*mask=127;return 0;
}
static int dev_err_probe(struct device *dev,int error,const char *text) {
 CHECK(dev && text);return error;
}
static struct nvmem_cell *of_nvmem_cell_get(struct device_node *node,void *name) {
 (void)node;(void)name;CHECK(0);return NULL;
}
static void nvmem_cell_put(struct nvmem_cell *cell) {(void)cell;CHECK(0);}
static int dev_pm_opp_set_config(struct device *cpu,struct dev_pm_opp_config *config) {
 int i=cpu->id;CHECK(query_calls==1 && config->supported_hw && *config->supported_hw==127);
 CHECK(config->supported_hw_count==1 && !config->prop_name && !configs[i]);
 if(i==config_fail)return -EIO;configs[i]=1;return i+1;
}
static int dev_pm_domain_attach_list(struct device *cpu,struct dev_pm_domain_attach_data *data,
 struct dev_pm_domain_list **out) {
 int i=cpu->id;CHECK(configs[i] && data->num_pd_names==1 && !strcmp(data->pd_names[0],"cpr"));
 CHECK(data->pd_flags==(PD_FLAG_DEV_LINK_ON|PD_FLAG_REQUIRED_OPP));
 if(i==attach_fail)return -EPROBE_DEFER;
 CHECK(!attachments[i]);attachments[i]=1;*out=&domains[i];return 1;
}
static void dev_pm_domain_detach_list(struct dev_pm_domain_list *list) {
 if(!list)return;CHECK(attachments[list->id] && configs[list->id]);
 attachments[list->id]=0;detaches++;
}
static void dev_pm_opp_clear_config(int token) {
 if(token<=0)return;CHECK(token<=4 && configs[token-1] && !attachments[token-1]);
 configs[token-1]=0;clears++;
}
static struct platform_device *platform_device_register_simple(const char *name,int id,void *data,int size) {
 CHECK(!strcmp(name,"cpufreq-dt") && id==-1 && !data && !size && !registrations);
 for(int i=0;i<4;i++)CHECK(configs[i] && attachments[i]);
 if(register_fail)return (void *)(intptr_t)-EIO;registrations++;return &child;
}
static void platform_set_drvdata(struct platform_device *pdev,void *data) {pdev->data=data;}
static void platform_device_unregister(struct platform_device *pdev) {
 CHECK(pdev==&child && registrations==1);registrations=0;unregisters++;
}
'''

PROBE_MAIN = r'''
static void reset(void) {
 cpu_missing=config_fail=attach_fail=-1;alloc_fail=query_fail=register_fail=0;
 query_calls=registrations=unregisters=clears=detaches=0;allocation=NULL;
 for(int i=0;i<4;i++){configs[i]=attachments[i]=0;cpus[i].id=domains[i].id=i;}
}
int main(void) {
 const char *names[]={"cpr"};
 struct qcom_cpufreq_match_data data={.pd_names=names,.num_pd_names=1,.cpr_supported_hw=true};
 struct of_device_id match={&data};struct platform_device pdev={.dev={.platform_data=&match}};
 for(int fault=0;fault<14;fault++) {
  reset();int expected=-EIO;
  if(fault==0){cpu_missing=0;expected=-ENODEV;}
  if(fault==1){alloc_fail=1;expected=-ENOMEM;}
  if(fault==2){query_fail=1;expected=-EPROBE_DEFER;}
  if(fault>=3 && fault<=6)config_fail=fault-3;
  if(fault>=7 && fault<=10){attach_fail=fault-7;expected=-EPROBE_DEFER;}
  if(fault==11)register_fail=1;
  if(fault>=12){cpu_missing=fault-11;expected=-ENODEV;}
  CHECK(qcom_cpufreq_probe(&pdev)==expected);
  CHECK(!table.refs && !registrations);
  for(int i=0;i<4;i++)CHECK(!configs[i] && !attachments[i]);
  CHECK(clears==detaches+(fault>=7 && fault<=10?1:0));
  free(allocation);reset();
  CHECK(!qcom_cpufreq_probe(&pdev) && registrations==1 && !table.refs);
  qcom_cpufreq_remove(&pdev);
  CHECK(!registrations && unregisters==1 && clears==4 && detaches==4);
  for(int i=0;i<4;i++)CHECK(!configs[i] && !attachments[i]);
  free(allocation);
 }
 reset();table.compatible="operating-points-v2";
 CHECK(qcom_cpufreq_probe(&pdev)==-ENOENT && !query_calls && !table.refs);
 table.compatible="operating-points-v2-msm8926-cpu";
 pdev.dev.platform_data=NULL;CHECK(qcom_cpufreq_probe(&pdev)==-EINVAL);
 pdev.dev.platform_data=&match;match.data=NULL;CHECK(qcom_cpufreq_probe(&pdev)==-EINVAL);
 puts("14 CPUfreq failures unwind; every retry configures/attaches all 4 CPUs before child registration");
}
'''

REGISTER = r'''
struct generic_pm_domain {struct device dev;};
struct cpr_msm8926_data {u32 supported_hw;int opp_token;};
struct cpr_drv {struct device *dev;struct generic_pm_domain pd;struct cpr_msm8926_data *msm8926;};
static int stage,fault,clear_count,remove_count,filtered;
static int pm_genpd_init(struct generic_pm_domain *pd,void *gov,bool off) {
 CHECK(pd && !gov);CHECK(off==!filtered);stage++;return fault==1?-EIO:0;
}
static int dev_pm_opp_set_supported_hw(struct device *dev,u32 *mask,unsigned count) {
 CHECK(stage==1 && dev->of_node && *mask==127 && count==1);stage++;
 return fault==2?-EPROBE_DEFER:42;
}
static int of_genpd_add_provider_simple(struct device_node *node,struct generic_pm_domain *pd) {
 CHECK(node && pd);CHECK(stage==(filtered?2:1));stage++;
 return fault==3?-EINVAL:0;
}
static void dev_pm_opp_clear_config(int token) {CHECK(token==42 && stage==3);clear_count++;}
static void pm_genpd_remove(struct generic_pm_domain *pd) {
 CHECK(pd);CHECK(clear_count==(filtered && fault==3));remove_count++;
}
'''

REGISTER_MAIN = r'''
int main(void) {
 struct device_node node={0};struct device dev={.of_node=&node};
 struct cpr_msm8926_data data={.supported_hw=127};struct cpr_drv drv={.dev=&dev};
 for(filtered=0;filtered<2;filtered++)for(fault=0;fault<4;fault++) {
  if(!filtered && fault==2)continue;
  stage=clear_count=remove_count=0;drv.msm8926=filtered?&data:NULL;
  CHECK(cpr_register_domain(&drv)==(fault==1?-EIO:fault==2?-EPROBE_DEFER:fault==3?-EINVAL:0));
  CHECK(remove_count==(fault>=2));CHECK(clear_count==(filtered && fault==3));
  if(!fault && filtered)CHECK(data.opp_token==42 && drv.pd.dev.of_node==&node);
 }
 puts("provider filtering precedes table parsing; each registration failure releases its resources");
}
'''

ROUTE = r'''
#define __init
#define __free(x) __attribute__((cleanup(cleanup_##x)))
#define unlikely(x) (x)
static int ptr_err_or_zero(void *p) {return IS_ERR(p)?PTR_ERR(p):0;}
#define PTR_ERR_OR_ZERO(p) ptr_err_or_zero(p)
struct cpufreq_dt_platform_data {int unused;};
static void cleanup_device_node(struct device_node **np) {of_node_put(*np);}
struct qcom_cpufreq_match_data {bool cpr_supported_hw;};
struct of_device_id {const void *data;};
static struct qcom_cpufreq_match_data match_data={true};
static const struct of_device_id qcom_cpufreq_match_list[]={{&match_data}},allowlist[]={{0}},blocklist[]={{0}};
static struct platform_driver qcom_cpufreq_driver;
static struct platform_device child,*cpufreq_pdev;
static struct device_node root,cpu,opps={.compatible="operating-points-v2"};
static int no_root,no_cpu,no_opps,allow,block,driver_fail,device_fail,driver_regs,driver_unregs,qcom_regs,generic_regs;
static struct device_node *of_find_node_by_path(const char *path) {
 CHECK(!strcmp(path,"/"));if(no_root)return NULL;root.refs++;return &root;
}
static struct device_node *of_cpu_device_node_get(unsigned int id) {
 CHECK(!id);if(no_cpu)return NULL;cpu.refs++;return &cpu;
}
static struct device_node *of_parse_phandle(struct device_node *node,const char *name,int index) {
 CHECK(!strcmp(name,"operating-points-v2") && !index);
 if(!node || no_opps)return NULL;opps.refs++;return &opps;
}
static bool of_property_present(struct device_node *node,const char *name) {
 CHECK(!strcmp(name,"operating-points-v2"));return node && !no_opps;
}
static const struct of_device_id *of_match_node(const struct of_device_id *table,struct device_node *node) {
 CHECK(node==&root);return table==qcom_cpufreq_match_list?table:table==allowlist?(allow?table:NULL):(block?table:NULL);
}
static int platform_driver_register(struct platform_driver *drv) {
 CHECK(drv==&qcom_cpufreq_driver);if(driver_fail)return -EIO;driver_regs++;return 0;
}
static void platform_driver_unregister(struct platform_driver *drv) {CHECK(drv==&qcom_cpufreq_driver);driver_unregs++;}
static struct platform_device *platform_device_register_data(struct device *parent,const char *name,int id,const void *data,size_t size) {
 CHECK(!parent && id==-1);
 if(!strcmp(name,"cpufreq-dt")){CHECK(!data && size==sizeof(struct cpufreq_dt_platform_data));generic_regs++;return &child;}
 CHECK(data==qcom_cpufreq_match_list && size==sizeof(struct of_device_id));
 CHECK(!strcmp(name,"qcom-cpufreq-nvmem"));if(device_fail)return (void *)(intptr_t)-EIO;qcom_regs++;return &child;
}
'''

ROUTE_MAIN = r'''
int main(void) {
 /* Ordinary MSM8926 keeps its existing generic path. */
 CHECK(!cpufreq_dt_platdev_init() && generic_regs==1);
 CHECK(qcom_cpufreq_init()==-ENODEV && !qcom_regs && !driver_regs);
 /* Even an allowlist entry must not bypass the calibrated path. */
 opps.compatible="operating-points-v2-msm8926-cpu";allow=1;
 CHECK(cpufreq_dt_platdev_init()==-ENODEV && generic_regs==1);
 CHECK(!qcom_cpufreq_init() && qcom_regs==1 && driver_regs==1);
 for(int fault=0;fault<5;fault++) {
  no_root=fault==0;no_cpu=fault==1;no_opps=fault==2;
  driver_fail=fault==3;device_fail=fault==4;
  CHECK(qcom_cpufreq_init()==(fault<3?-ENODEV:-EIO));
  CHECK(!root.refs && !cpu.refs && !opps.refs && qcom_regs==1);
 }
 CHECK(driver_unregs==1);
 puts("legacy generic routing retained; explicit MSM8926 table prevents duplicate registration and releases OF references");
}
'''


class CpufreqTests(unittest.TestCase):
    def compile_run(self, prelude, callbacks, main, expected):
        with tempfile.TemporaryDirectory() as directory:
            source, executable = Path(directory)/'test.c', Path(directory)/'test'
            source.write_text(COMMON+prelude+callbacks+main)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     '-Wno-misleading-indentation', str(source), '-o', str(executable)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)

    def test_supplier_query_lifetime_and_retry(self):
        text = (TREE/'drivers/pmdomain/qcom/cpr.c').read_text()
        # The exported query has no static qualifier.
        start = text.index('int qcom_cpr_msm8926_get_supported_hw(')
        end = text.index('\nEXPORT_SYMBOL_GPL', start)
        self.compile_run(QUERY, text[start:end], QUERY_MAIN, 'every retry passes')

    def test_actual_cpufreq_probe_and_remove(self):
        text = (TREE/'drivers/cpufreq/qcom-cpufreq-nvmem.c').read_text()
        callbacks = ''.join(FIXTURE.function(text, name) for name in
                            ['qcom_cpufreq_probe(', 'qcom_cpufreq_remove('])
        self.compile_run(PROBE, callbacks, PROBE_MAIN, 'attaches all 4 CPUs')

    def test_provider_filters_before_parsing(self):
        text = (TREE/'drivers/pmdomain/qcom/cpr.c').read_text()
        self.compile_run(REGISTER, FIXTURE.function(text, 'cpr_register_domain('),
                         REGISTER_MAIN, 'filtering precedes table parsing')

    def test_legacy_and_opt_in_platform_routing(self):
        generic = (TREE/'drivers/cpufreq/cpufreq-dt-platdev.c').read_text()
        nvmem = (TREE/'drivers/cpufreq/qcom-cpufreq-nvmem.c').read_text()
        callbacks = ''.join(FIXTURE.function(generic, name) for name in
                            ['cpu0_node_has_opp_v2_prop(', 'cpu0_uses_msm8926_cpr(',
                             'cpufreq_dt_platdev_init('])
        callbacks += FIXTURE.function(nvmem, 'qcom_cpufreq_init(')
        self.compile_run(ROUTE, callbacks, ROUTE_MAIN, 'duplicate registration')


if __name__ == '__main__':
    unittest.main()
