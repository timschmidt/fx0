# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual IOMMU domain/resume callbacks with owned service models."""
from pathlib import Path
import argparse,hashlib,json,os,re,resource,subprocess
P=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--expected-wrong',type=int,required=True);a=ap.parse_args();a.output.mkdir(mode=0o700);resource.setrlimit(resource.RLIMIT_CORE,(0,0));source=a.source.read_text()
def function(name):
 m=re.search(r'^static (?:enum io_pgtable_fmt|int|struct qcom_iommu_domain \*) (?:__maybe_unused )?'+name+r'\([^;{}]*\)\n\{',source,re.M);assert m,name;b=source.index('{',m.start());end=b+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[m.start():end]
body='\n'.join(function(n) for n in ['qcom_iommu_pgtbl_fmt','qcom_iommu_init_domain','qcom_iommu_resume','qcom_iommu_suspend'])
shim=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define __maybe_unused
#define CLK_NUM 3
#define ARM_SMMU_TTBRn_ASID (0xffULL<<48)
#define FIELD_PREP(mask,value) (((uint64_t)(value)<<__builtin_ctzll(mask))&(mask))
#define ARM_SMMU_TCR_EAE (1U<<31)
#define ARM_SMMU_SCTLR_CFIE (1U<<6)
#define ARM_SMMU_SCTLR_CFRE (1U<<5)
#define ARM_SMMU_SCTLR_AFE (1U<<2)
#define ARM_SMMU_SCTLR_TRE (1U<<1)
#define ARM_SMMU_SCTLR_M 1U
#define ARM_SMMU_SCTLR_S1_ASIDPNE (1U<<12)
#define ARM_SMMU_SCTLR_CFCFG (1U<<7)
#define ARM_SMMU_SCTLR_E (1U<<4)
#define IS_ENABLED(x) 0
#define dev_err(...) ((void)0)
enum io_pgtable_fmt {ARM_V7S=1,ARM_32_LPAE_S1=2};
struct mutex {bool held;};
struct iommu_domain {unsigned long pgsize_bitmap;struct {uint64_t aperture_end;bool force_aperture;} geometry;};
struct iommu_fwspec {unsigned num_ids;unsigned ids[3];};
struct io_pgtable_ops {unsigned tag;};
struct device {void *data,*pm_domain;struct iommu_fwspec *fwspec;};
struct qcom_iommu_cfg {enum io_pgtable_fmt fmt;bool no_afe,no_stall,ctx_restore;};
struct qcom_iommu_ctx {bool secure_init,secured_ctx;unsigned asid;struct iommu_domain *domain;uint64_t ttbr0;u32 tcr[2],mair[2],contextidr,sctlr;};
struct qcom_iommu_dev {struct device *dev;const struct qcom_iommu_cfg *cfg;bool non_secure;unsigned sec_id,max_asid;int clks[CLK_NUM];struct qcom_iommu_ctx *ctxs[4];};
struct qcom_iommu_domain {struct io_pgtable_ops *pgtbl_ops;struct mutex init_mutex;struct iommu_domain domain;struct qcom_iommu_dev *iommu;struct iommu_fwspec *fwspec;};
struct io_pgtable_cfg {unsigned long pgsize_bitmap;unsigned ias,oas;const void *tlb;struct device *iommu_dev;struct {uint64_t ttbr;u32 tcr,prrr,nmrr;} arm_v7s_cfg;struct {uint64_t ttbr,mair;} arm_lpae_s1_cfg;};
static int qcom_flush_ops,alloc_error,restore_error_at,restore_calls,programs,clock_error,clock_votes,clock_disables,reset_error,bfb_calls;
static unsigned allocations,frees,unlock_without_ops;
static struct io_pgtable_ops *owned;
static struct qcom_iommu_domain *observed;
static void mutex_lock(struct mutex *m) {assert(!m->held);m->held=true;}
static void mutex_unlock(struct mutex *m) {assert(m->held);m->held=false;if(observed->iommu&&!observed->pgtbl_ops)unlock_without_ops++;}
static struct qcom_iommu_domain *to_qcom_iommu_domain(struct iommu_domain *d) {return (void*)((char*)d - offsetof(struct qcom_iommu_domain,domain));}
static struct iommu_fwspec *dev_iommu_fwspec_get(struct device *d) {return d->fwspec;}
static struct qcom_iommu_ctx *to_ctx(struct qcom_iommu_domain *d,unsigned id) {assert(d->iommu&&id<4);return d->iommu->ctxs[id];}
static struct io_pgtable_ops *alloc_io_pgtable_ops(enum io_pgtable_fmt fmt,struct io_pgtable_cfg *c,struct qcom_iommu_domain *d) {
 assert(d->init_mutex.held&&c->ias==32&&c->oas==(fmt==ARM_V7S?32U:40U));
 if(alloc_error)return NULL;assert(!owned);owned=calloc(1,sizeof(*owned));assert(owned);allocations++;
 c->arm_v7s_cfg.ttbr=0x1234000;c->arm_v7s_cfg.tcr=0x123;c->arm_v7s_cfg.prrr=0x55;c->arm_v7s_cfg.nmrr=0x66;
 c->arm_lpae_s1_cfg.ttbr=0x2345000;c->arm_lpae_s1_cfg.mair=0x8765432112345678ULL;return owned;
}
static void free_io_pgtable_ops(struct io_pgtable_ops *p) {if(!p)return;assert(p==owned);free(p);owned=NULL;frees++;}
static int qcom_scm_restore_sec_cfg(unsigned sec,unsigned asid) {(void)sec;(void)asid;restore_calls++;return restore_calls==restore_error_at?-EIO:0;}
static u32 arm_smmu_lpae_tcr(struct io_pgtable_cfg *c) {(void)c;return 0x99;}
static u32 arm_smmu_lpae_tcr2(struct io_pgtable_cfg *c) {(void)c;return 0x88;}
static void qcom_iommu_program_ctx(struct qcom_iommu_dev *d,struct qcom_iommu_ctx *c) {assert(d&&c&&!c->secured_ctx);programs++;}
static void *dev_get_drvdata(struct device *d) {return d->data;}
static int clk_bulk_prepare_enable(unsigned n,int *clks) {assert(n==CLK_NUM&&clks);if(clock_error)return clock_error;clock_votes++;return 0;}
static void clk_bulk_disable_unprepare(unsigned n,int *clks) {assert(n==CLK_NUM&&clks&&clock_votes==1);clock_votes--;clock_disables++;}
static int qcom_iommu_reset_ns(struct qcom_iommu_dev *d) {assert(d->non_secure&&clock_votes);return reset_error;}
static void qcom_iommu_bfb_setup(struct qcom_iommu_dev *d) {assert(d&&clock_votes);bfb_calls++;}
'''
main=r'''
static void reset(void) {assert(!owned);alloc_error=restore_error_at=restore_calls=programs=clock_error=clock_votes=clock_disables=reset_error=bfb_calls=0;allocations=frees=unlock_without_ops=0;}
int main(void) {
 unsigned cases=0,wrong=0;
 for(unsigned fmt=0;fmt<2;fmt++)for(unsigned ns=0;ns<2;ns++)for(unsigned secure=0;secure<2;secure++)for(unsigned failure=0;failure<5;failure++) {
  reset();struct qcom_iommu_domain dom={0};observed=&dom;struct iommu_fwspec fw={.num_ids=3,.ids={0,1,2}};struct device dev={.fwspec=&fw};struct qcom_iommu_cfg cfg={.fmt=fmt?ARM_V7S:ARM_32_LPAE_S1,.no_afe=fmt,.no_stall=fmt};struct qcom_iommu_ctx ctx[3]={{.asid=0},{.asid=1},{.asid=2}};ctx[1].secured_ctx=secure;struct qcom_iommu_dev io={.dev=&dev,.cfg=&cfg,.non_secure=ns,.max_asid=2,.ctxs={&ctx[0],&ctx[1],&ctx[2],NULL}};
  if(failure==4)alloc_error=-ENOMEM;else restore_error_at=failure;
  int ret=qcom_iommu_init_domain(&dom.domain,&io,&dev);bool fail=failure==4||(!ns&&failure>0);
  assert(ret==(failure==4?-ENOMEM:fail?-EIO:0));assert(!dom.init_mutex.held&&!unlock_without_ops);
  if(fail) {
   bool bad=owned||dom.pgtbl_ops||dom.iommu||dom.fwspec||programs;
   for(unsigned i=0;i<3;i++)bad|=ctx[i].domain!=NULL;
   wrong+=bad;
   // Clean the deliberately broken baseline's owned allocation after measuring
   // its contract violation, so the baseline also runs with normal LSan.
   if(owned)free_io_pgtable_ops(owned);
  } else {
   assert(dom.iommu==&io&&dom.pgtbl_ops==owned&&dom.fwspec==&fw&&programs==(secure?2:3));
   for(unsigned i=0;i<3;i++)assert(ctx[i].domain==&dom.domain);
   unsigned old=allocations;assert(!qcom_iommu_init_domain(&dom.domain,&io,&dev)&&allocations==old);
   free_io_pgtable_ops(owned);
  }
  cases++;
 }
 for(unsigned ns=0;ns<2;ns++)for(unsigned pd=0;pd<2;pd++)for(unsigned failure=0;failure<3;failure++) {
  reset();struct qcom_iommu_domain dom={0};observed=&dom;struct device dev={.pm_domain=pd?&dom:NULL};struct qcom_iommu_cfg cfg={.fmt=ARM_V7S,.ctx_restore=true};struct qcom_iommu_ctx ctx[3]={{.domain=&dom.domain},{.domain=&dom.domain,.secured_ctx=true},{0}};struct qcom_iommu_dev io={.dev=&dev,.cfg=&cfg,.non_secure=ns,.max_asid=2,.ctxs={&ctx[0],&ctx[1],&ctx[2],NULL}};dev.data=&io;
  if(failure==1)clock_error=-EREMOTEIO;if(failure==2){reset_error=-ETIMEDOUT;restore_error_at=1;}
  int ret=qcom_iommu_resume(&dev);bool fail=failure==1||(failure==2&&(ns||pd));assert(ret==(failure==1?-EREMOTEIO:failure==2&&ns?-ETIMEDOUT:failure==2&&pd?-EIO:0));
  if(fail)wrong+=clock_votes||bfb_calls||programs;
  else {assert(clock_votes==1&&bfb_calls==1&&programs==1);assert(!qcom_iommu_suspend(&dev)&&clock_votes==0);}
  if(clock_votes)clk_bulk_disable_unprepare(CLK_NUM,io.clks);
  cases++;
 }
 printf("{\"cases\":%u,\"wrong\":%u}\n",cases,wrong);return 0;
}
'''
c=a.output/'model.c';c.write_text(shim+'\n'+body+'\n'+main);binary=a.output/'model';env=os.environ|{'TMPDIR':str(a.output),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-sign-compare','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(c),'-o',str(binary)],capture_output=True,text=True,env=env);(a.output/'compile.stdout').write_text(r.stdout);(a.output/'compile.stderr').write_text(r.stderr);assert r.returncode==0 and not r.stderr,r.stderr
r=subprocess.run([str(binary)],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0 and not r.stderr,(r.returncode,r.stderr);result=json.loads(r.stdout);assert result['wrong']==a.expected_wrong,result
j=dict(passed=True,**result,source_SHA256=hashlib.sha256(source.encode()).hexdigest(),extracted_callbacks_SHA256=hashlib.sha256(body.encode()).hexdigest(),model_SHA256=hashlib.sha256(c.read_bytes()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,baseline_owned_allocation_cleaned_only_after_violation_observed=True,context_programming_and_secure_firmware_and_clocks_mocked=True,phone_access=False);(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
