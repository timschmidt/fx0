"""Execute actual RPM send/callback code across stale, malformed and late replies."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/soc/qcom/smd-rpm.c'

PREFIX = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <sys/mman.h>
#include <unistd.h>
typedef uint32_t u32;
typedef unsigned char u8;
typedef uint32_t __le32;
#define EINVAL 22
#define ENOMEM 12
#define ENXIO 6
#define ETIMEDOUT 110
#define EIO 5
#define HZ 100
#define GFP_ATOMIC 0
#define WARN_ON(x) (x)
#define ALIGN(x,a) (((x)+(a)-1)&~((a)-1))
#define cpu_to_le32(x) (x)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct qcom_smd_rpm;
struct completion {int done;};
struct mutex {int held;};
typedef struct {int held;} spinlock_t;
struct device {void *data;};
struct rpmsg_device {struct device dev;};
struct rpmsg_endpoint {struct qcom_smd_rpm *rpm;};
static void *dev_get_drvdata(struct device *dev) {return dev->data;}
static void mutex_lock(struct mutex *lock) {CHECK(!lock->held);lock->held=1;}
static void mutex_unlock(struct mutex *lock) {CHECK(lock->held);lock->held=0;}
#define spin_lock_irqsave(lock,flags) do{flags=0;CHECK(!(lock)->held);(lock)->held=1;}while(0)
#define spin_unlock_irqrestore(lock,flags) do{(void)flags;CHECK((lock)->held);(lock)->held=0;}while(0)
static u32 get_unaligned_le32(const void *p) {
 const u8 *v=p;return v[0]|(u32)v[1]<<8|(u32)v[2]<<16|(u32)v[3]<<24;
}
static int allocated,allocation_fail;
static void *kmalloc(size_t size,int flags) {(void)flags;if(allocation_fail)return NULL;allocated++;return malloc(size);}
static void kfree(void *p) {CHECK(allocated>0);allocated--;free(p);}
static void reinit_completion(struct completion *c) {c->done=0;}
static void complete(struct completion *c);
static int wait_for_completion_timeout(struct completion *c,int timeout);
static int rpmsg_send(struct rpmsg_endpoint *,void *,size_t);
static int qcom_smd_rpm_callback(struct rpmsg_device *,void *,int,void *,u32);
'''

HARNESS = r'''
static int mode;
static u32 last_id,old_id;
static int sends,completions,waits;
enum {FAST,TIMEOUT,LATE_THEN_CORRECT,STALE_ONLY,NACK,BOUNDARY,SEND_ERROR,DUPLICATE};
static void put32(u8 *p,u32 value) {for(int i=0;i<4;i++)p[i]=(value>>(8*i))&255;}
static void response(struct qcom_smd_rpm *rpm,u32 id,const char *error) {
 u8 buffer[129]={0};u8 *p=buffer+1; /* Deliberately unaligned transport data. */
 size_t size=20;
 put32(p,RPM_SERVICE_TYPE_REQUEST);put32(p+4,12);
 put32(p+8,RPM_MSG_TYPE_MSG_ID);put32(p+12,4);put32(p+16,id);
 if(error) {
  size_t len=strlen(error)+1;
  CHECK(len<80);
  put32(p+20,RPM_MSG_TYPE_ERR);put32(p+24,len);memcpy(p+28,error,len);
  size=28+ALIGN(len,4);put32(p+4,size-8);
 }
 struct rpmsg_device rpdev={.dev={.data=rpm}};
 CHECK(!qcom_smd_rpm_callback(&rpdev,p,size,NULL,0));
}
static void complete(struct completion *c) {
 struct qcom_smd_rpm *rpm=container_of(c,struct qcom_smd_rpm,ack);
 CHECK(rpm->ack_lock.held && !rpm->waiting);
 c->done++;completions++;
}
static int rpmsg_send(struct rpmsg_endpoint *endpoint,void *data,size_t size) {
 struct qcom_smd_rpm *rpm=endpoint->rpm;
 CHECK(rpm->lock.held && !rpm->ack_lock.held && rpm->waiting);
 CHECK(size>=28 && size<256);
 last_id=get_unaligned_le32((u8 *)data+8);sends++;
 CHECK(last_id==rpm->pending_id && last_id);
 if(mode==SEND_ERROR)return -EIO;
 if(mode==FAST||mode==DUPLICATE){response(rpm,last_id,NULL);if(mode==DUPLICATE)response(rpm,last_id,NULL);}
 if(mode==NACK)response(rpm,last_id,"resource does not exist");
 if(mode==LATE_THEN_CORRECT||mode==STALE_ONLY)response(rpm,old_id,NULL);
 return 0;
}
static int wait_for_completion_timeout(struct completion *c,int timeout) {
 struct qcom_smd_rpm *rpm=container_of(c,struct qcom_smd_rpm,ack);
 CHECK(timeout==5*HZ && rpm->lock.held && !rpm->ack_lock.held);waits++;
 if(mode==LATE_THEN_CORRECT){CHECK(!c->done && rpm->waiting);response(rpm,last_id,NULL);}
 if(mode==BOUNDARY){response(rpm,last_id,NULL);return 0;}
 if(c->done){c->done--;return 1;}
 return 0;
}
static int request(struct qcom_smd_rpm *rpm,int selected) {
 mode=selected;
 int ret=qcom_rpm_smd_write(rpm,0,0x61646c72,3,NULL,0);
 CHECK(!rpm->waiting && !rpm->lock.held && !rpm->ack_lock.held && !allocated);
 return ret;
}
int main(void) {
 struct qcom_smd_rpm rpm={0},other={0};
 struct rpmsg_endpoint endpoint={.rpm=&rpm},endpoint2={.rpm=&other};
 rpm.rpm_channel=&endpoint;other.rpm_channel=&endpoint2;
 CHECK(!request(&rpm,FAST) && last_id==1 && completions==1);
 CHECK(request(&rpm,TIMEOUT)==-ETIMEDOUT);old_id=last_id;
 response(&rpm,old_id,NULL);CHECK(!rpm.ack.done); /* Retired late ACK. */
 CHECK(!request(&rpm,LATE_THEN_CORRECT));CHECK(!rpm.ack.done);
 CHECK(request(&rpm,STALE_ONLY)==-ETIMEDOUT);
 CHECK(request(&rpm,NACK)==-ENXIO);
 CHECK(request(&rpm,BOUNDARY)==-ETIMEDOUT && rpm.ack.done==1);
 CHECK(request(&rpm,STALE_ONLY)==-ETIMEDOUT && !rpm.ack.done);
 CHECK(request(&rpm,SEND_ERROR)==-EIO && !rpm.ack.done);
 int completed=completions;
 CHECK(!request(&rpm,DUPLICATE) && completions==completed+1);
 CHECK(!request(&other,FAST) && last_id==1 && other.msg_id==1);
 rpm.msg_id=UINT_MAX;CHECK(!request(&rpm,FAST) && last_id==1);
 int before=sends;
 CHECK(qcom_rpm_smd_write(&rpm,0,0,0,NULL,SIZE_MAX)==-EINVAL && sends==before && !allocated);
 allocation_fail=1;CHECK(qcom_rpm_smd_write(&rpm,0,0,0,NULL,0)==-ENOMEM);allocation_fail=0;
 /* Structural fuzzing must never complete or read past the packet boundary. */
 struct rpmsg_device rpdev={.dev={.data=&rpm}};
 CHECK(!qcom_smd_rpm_callback(&rpdev,NULL,-1,NULL,0));
 struct rpmsg_device unbound={0};
 CHECK(!qcom_smd_rpm_callback(&unbound,NULL,20,NULL,0));
 u8 packet[97]={0};u8 *p=packet+1;
 long page=sysconf(_SC_PAGESIZE);CHECK(page>80);
 u8 *mapping=mmap(NULL,2*page,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 CHECK(mapping!=MAP_FAILED && !mprotect(mapping+page,page,PROT_NONE));
 rpm.waiting=true;rpm.pending_id=0x1234;rpm.ack_status=-ETIMEDOUT;
 int malformed=0;
 for(int count=0;count<=80;count++)for(u32 length=0;length<=80;length++)for(u32 tlv=0;tlv<=16;tlv++) {
  memset(packet,0,sizeof(packet));put32(p,RPM_SERVICE_TYPE_REQUEST);put32(p+4,length);
  put32(p+8,RPM_MSG_TYPE_MSG_ID);put32(p+12,tlv);put32(p+16,0x9999); /* Wrong ID if structurally valid. */
  u8 *bounded=mapping+page-count;
  if(count)memcpy(bounded,p,count);
  CHECK(!qcom_smd_rpm_callback(&rpdev,bounded,count,NULL,0));
  CHECK(!rpm.ack.done && rpm.waiting && rpm.ack_status==-ETIMEDOUT);malformed++;
 }
 CHECK(!munmap(mapping,2*page));
 /* Duplicate and truncated matching IDs must not be accepted. */
 memset(packet,0,sizeof(packet));put32(p,RPM_SERVICE_TYPE_REQUEST);put32(p+4,24);
 put32(p+8,RPM_MSG_TYPE_MSG_ID);put32(p+12,4);put32(p+16,0x1234);
 put32(p+20,RPM_MSG_TYPE_MSG_ID);put32(p+24,4);put32(p+28,0x1234);
 CHECK(!qcom_smd_rpm_callback(&rpdev,p,32,NULL,0) && !rpm.ack.done && rpm.waiting);
 put32(p+4,13);CHECK(!qcom_smd_rpm_callback(&rpdev,p,21,NULL,0) && !rpm.ack.done && rpm.waiting);
 put32(p+4,0xffffffff);CHECK(!qcom_smd_rpm_callback(&rpdev,p,20,NULL,0) && !rpm.ack.done && rpm.waiting);
 response(&rpm,0x1234,"unsupported request");CHECK(rpm.ack_status==-EINVAL && rpm.ack.done==1 && !rpm.waiting);
 printf("request correlation, timeout/late/duplicate/fast ACKs and %d bounded packet cases passed\n",malformed);
 return 0;
}
'''


def definition(source, name):
    pattern = r'(?:static\s+)?int\s+' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{'
    match = re.search(pattern, source)
    if not match:
        raise AssertionError(name)
    end = source.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end] + '\n'


def struct(source, name):
    start = source.index('struct ' + name + ' {')
    end = source.index('\n};', start) + 3
    return source[start:end] + '\n'


class RpmAckTests(unittest.TestCase):
    def test_actual_send_callback_and_packet_boundaries(self):
        text = SOURCE.read_text()
        declarations = ''.join(struct(text, name) for name in
                               ['qcom_smd_rpm', 'qcom_rpm_header', 'qcom_rpm_request'])
        constants = '\n'.join(line for line in text.splitlines()
                              if line.startswith('#define RPM_')) + '\n'
        functions = definition(text, 'qcom_rpm_smd_write') + definition(text, 'qcom_smd_rpm_callback')
        functions = ('#pragma GCC diagnostic push\n'
                     '#pragma GCC diagnostic ignored "-Wunused-parameter"\n'
                     + functions + '#pragma GCC diagnostic pop\n')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, executable = base/'test.c', base/'test'
            source.write_text(PREFIX + declarations + constants + functions + HARNESS)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     str(source), '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('111537 bounded packet cases passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
