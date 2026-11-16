# SPDX-License-Identifier: GPL-2.0-only
"""Compare actual RPM code using well-formed, deterministically scheduled replies."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--mutation', choices=['accept-wrong-id', 'retain-completion'])
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir(mode=0o700)
spec = importlib.util.spec_from_file_location('rpm_fixture', a.fixture)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
text = a.source.read_text()
if a.mutation == 'accept-wrong-id':
    assert text.count('rpm->pending_id == response_id') == 1
    text = text.replace('rpm->pending_id == response_id', '(rpm->pending_id == response_id || response_id)')
if a.mutation == 'retain-completion':
    assert text.count('reinit_completion(&rpm->ack);') == 1
    text = text.replace('reinit_completion(&rpm->ack);', '')
declarations = ''.join(fixture.struct(text, name) for name in
                       ['qcom_smd_rpm', 'qcom_rpm_header', 'qcom_rpm_request', 'qcom_rpm_message'])
constants = '\n'.join(line for line in text.splitlines() if line.startswith('#define RPM_')) + '\n'
functions = fixture.definition(text, 'qcom_rpm_smd_write') + fixture.definition(text, 'qcom_smd_rpm_callback')
prefix = fixture.PREFIX + r'''
#define DECLARE_FLEX_ARRAY(type,name) struct { struct { } __empty_ ## name; type name[]; }
#define le32_to_cpu(x) (x)
#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))
#define PTR_ALIGN(p,a) ((void *)(((uintptr_t)(p)+(a)-1)&~((uintptr_t)(a)-1)))
#define memcpy_fromio memcpy
#define dev_err(dev,fmt,...) ((void)(dev))
'''
harness = r'''
static int selected,checks,failures;
static u32 last_id,previous_id;
enum {FAST, SILENT, STALE, NACK, DUPLICATE, BOUNDARY, SEND_ERROR};
#define EXPECT(x) do { checks++; if (!(x)) { failures++; fprintf(stderr,"check line %d failed: %s\n",__LINE__,#x); } } while(0)
static void put32(u8 *p,u32 value) { for(int i=0;i<4;i++)p[i]=(value>>(8*i))&255; }
static void reply(struct qcom_smd_rpm *rpm,u32 id,int nack) {
 /* All packets are aligned, complete, well formed and contain synthetic IDs. */
 u32 words[16]={0};u8 *p=(u8 *)words;size_t size=20;
 put32(p,RPM_SERVICE_TYPE_REQUEST);put32(p+8,RPM_MSG_TYPE_MSG_ID);
 put32(p+12,4);put32(p+16,id);
 if(nack) {const char error[]="resource does not exist";
  put32(p+20,RPM_MSG_TYPE_ERR);put32(p+24,sizeof(error));
  memcpy(p+28,error,sizeof(error));size=28+ALIGN(sizeof(error),4);
 }
 put32(p+4,size-8);struct rpmsg_device device={.dev={.data=rpm}};
 CHECK(!qcom_smd_rpm_callback(&device,p,size,NULL,0));
}
static void complete(struct completion *c) { c->done++; }
static int rpmsg_send(struct rpmsg_endpoint *endpoint,void *data,size_t size) {
 CHECK(size==28);struct qcom_smd_rpm *rpm=endpoint->rpm;
 last_id=get_unaligned_le32((u8 *)data+8);
 if(selected==SEND_ERROR)return -EIO;
 if(selected==FAST||selected==DUPLICATE)reply(rpm,last_id,0);
 if(selected==DUPLICATE)reply(rpm,last_id,0);
 if(selected==STALE)reply(rpm,previous_id,0);
 if(selected==NACK)reply(rpm,last_id,1);
 return 0;
}
static int wait_for_completion_timeout(struct completion *c,int timeout) {
 CHECK(timeout==5*HZ);struct qcom_smd_rpm *rpm=container_of(c,struct qcom_smd_rpm,ack);
 if(selected==BOUNDARY) {reply(rpm,last_id,0);return 0;}
 if(selected==SILENT||selected==STALE)EXPECT(!c->done);
 if(c->done) {c->done--;return 1;}return 0;
}
static int request(struct qcom_smd_rpm *rpm,int mode) {
 selected=mode;char ignored=0;
 int ret=qcom_rpm_smd_write(rpm,0,0x61646c72,3,&ignored,0);
 CHECK(!allocated&&!rpm->lock.held);return ret;
}
int main(void) {
 struct qcom_smd_rpm rpm={0};struct rpmsg_endpoint ep={.rpm=&rpm};rpm.rpm_channel=&ep;
 EXPECT(request(&rpm,FAST)==0);
 EXPECT(request(&rpm,SILENT)==-ETIMEDOUT);previous_id=last_id;
 reply(&rpm,previous_id,0); /* A complete, valid ACK arrives after retirement. */
 EXPECT(request(&rpm,SILENT)==-ETIMEDOUT);
 previous_id=last_id;EXPECT(request(&rpm,STALE)==-ETIMEDOUT);
 EXPECT(request(&rpm,NACK)==-ENXIO);
 EXPECT(request(&rpm,DUPLICATE)==0);
 EXPECT(request(&rpm,SILENT)==-ETIMEDOUT);
 EXPECT(request(&rpm,BOUNDARY)==-ETIMEDOUT);
 EXPECT(request(&rpm,SILENT)==-ETIMEDOUT);
 EXPECT(request(&rpm,SEND_ERROR)==-EIO);previous_id=last_id;
 reply(&rpm,previous_id,0);
 EXPECT(request(&rpm,SILENT)==-ETIMEDOUT);
 EXPECT(request(&rpm,FAST)==0);
 printf("{\"checks\":%d,\"failures\":%d}\n",checks,failures);
 return failures?1:0;
}
'''
translation = a.output / 'model.c'
translation.write_text(prefix + declarations + constants +
                       '#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wunused-parameter"\n' +
                       functions + '\n#pragma GCC diagnostic pop\n' + harness)
exe = a.output / 'model'
compile_result = subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
    '-Wno-unused-function', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g',
    str(translation), '-o', str(exe)], capture_output=True, text=True)
(a.output / 'compile.log').write_text(compile_result.stdout + compile_result.stderr)
assert compile_result.returncode == 0, compile_result.stderr
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
env.pop('LSAN_OPTIONS', None)
r = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)
(a.output / 'stdout').write_text(r.stdout)
(a.output / 'stderr').write_text(r.stderr)
j = json.loads(r.stdout)
diagnostics = any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:'])
j.update(returncode=r.returncode, sanitizer_diagnostics=diagnostics,
         source_SHA256=hashlib.sha256(a.source.read_bytes()).hexdigest(), mutation=a.mutation,
         well_formed_synthetic_replies_only=True, actual_send_and_callback_executed=True,
         deterministic_scheduling_not_concurrency_or_firmware_acceptance=True)
(a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
assert not diagnostics and r.returncode == bool(j['failures'])
print(json.dumps(j))
