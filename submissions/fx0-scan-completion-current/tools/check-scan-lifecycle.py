# SPDX-License-Identifier: GPL-2.0-only
"""Run actual scan completion/request-release functions with synthetic work and messages."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['no-deferred-work', 'retain-delivered-message'])
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir(mode=0o700)
text = a.source.read_text()
if a.mutation == 'no-deferred-work':
    marker = 'rdev->scan_msg = msg;\n\twiphy_work_queue(&rdev->wiphy, &rdev->scan_done_wk);'
    assert text.count(marker) == 1
    text = text.replace(marker, 'rdev->scan_msg = msg;')
if a.mutation == 'retain-delivered-message':
    assert text.count('rdev->scan_msg = NULL;') == 1
    text = text.replace('rdev->scan_msg = NULL;', '')


def definition(name):
    m = re.search(r'(?:static\s+)?void\s+' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', text)
    assert m, name
    end = text.index('{', m.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[m.start():end] + '\n'


prefix = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"service invariant line %d: %s\n",__LINE__,#x);exit(2);}}while(0)
#define EXPECT(x) do {checks++;if(!(x)){failures++;fprintf(stderr,"behavior line %d: %s\n",__LINE__,#x);}}while(0)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define lockdep_assert_held(p) CHECK(*(p)==1)
#define WARN_ON(x) CHECK(!(x))
#define WIPHY_FLAG_SPLIT_SCAN_6GHZ 1
#define NL80211_SCAN_FLAG_FLUSH 1
struct wiphy {int mtx;unsigned int flags;};
struct wiphy_work {bool pending;};
struct wireless_dev {void *netdev;bool running;};
struct cfg80211_scan_info {bool aborted;uint64_t scan_start_tsf;unsigned char tsf_bssid[6];};
struct cfg80211_scan_request {struct wireless_dev *wdev;struct wiphy *wiphy;unsigned int flags;bool scan_6ghz;unsigned long scan_start;};
struct cfg80211_scan_request_int {struct cfg80211_scan_request req;struct cfg80211_scan_info info;bool driver_owns,stale,notified;};
struct sk_buff {int token;};
struct cfg80211_registered_device {struct wiphy wiphy;struct wiphy_work scan_done_wk;struct cfg80211_scan_request_int *scan_req,*int_scan_req;struct sk_buff *scan_msg;int bss_lock;};
static int checks,failures,cases,requests,freed,messages,sent,refs,queued,notifications;
static struct sk_buff *live_message;
static bool fail_message;
static struct cfg80211_registered_device *wiphy_to_rdev(struct wiphy *w) {return container_of(w,struct cfg80211_registered_device,wiphy);}
static bool wdev_running(struct wireless_dev *w) {return w->running;}
static int cfg80211_scan_6ghz(struct cfg80211_registered_device *r,bool ignored) {(void)r;(void)ignored;return -1;}
static void cfg80211_sme_scan_done(void *dev) {CHECK(dev);notifications++;}
static void spin_lock_bh(int *lock) {CHECK(!*lock);*lock=1;}
static void spin_unlock_bh(int *lock) {CHECK(*lock);*lock=0;}
static void __cfg80211_bss_expire(struct cfg80211_registered_device *r,unsigned long start) {CHECK(r->bss_lock);(void)start;}
static void dev_put(void *dev) {CHECK(dev&&refs==1);refs--;}
static void kfree(void *ptr) {CHECK(ptr&&requests>freed);freed++;free(ptr);}
static struct sk_buff *nl80211_build_scan_msg(struct cfg80211_registered_device *r,struct wireless_dev *w,bool aborted) {
 (void)r;(void)w;(void)aborted;if(fail_message)return NULL;CHECK(!live_message);
 live_message=calloc(1,sizeof(*live_message));CHECK(live_message);live_message->token=++messages;return live_message;
}
static void nl80211_send_scan_msg(struct cfg80211_registered_device *r,struct sk_buff *msg) {
 (void)r;if(!msg)return;CHECK(msg==live_message);sent++;free(msg);live_message=NULL;
}
static void wiphy_work_queue(struct wiphy *w,struct wiphy_work *work) {
 CHECK(w->mtx==1&&work==&wiphy_to_rdev(w)->scan_done_wk);work->pending=true;queued++;
}
#define trace_cfg80211_scan_done(req,info) do{(void)(req);(void)(info);}while(0)
'''
harness = r'''
static struct cfg80211_scan_request_int *request(struct cfg80211_registered_device *r,struct wireless_dev *w,bool owned) {
 struct cfg80211_scan_request_int *q=calloc(1,sizeof(*q));CHECK(q);requests++;
 q->req.wiphy=&r->wiphy;q->req.wdev=w;q->driver_owns=owned;return q;
}
static void drain(struct cfg80211_registered_device *r) {
 int n=0;while(r->scan_done_wk.pending){CHECK(n++<4);r->scan_done_wk.pending=false;__cfg80211_scan_done(&r->wiphy,&r->scan_done_wk);}
}
static void retire(struct cfg80211_scan_request_int *q) {
 struct cfg80211_scan_info info={.aborted=true};cfg80211_scan_done(&q->req,&info);
}
static void cleanup_message(struct cfg80211_registered_device *r) {
 /* Cleanup after expected baseline/control failures does not masquerade as delivery. */
 if(live_message){free(live_message);live_message=NULL;}r->scan_msg=NULL;
}
static void cycle(bool direct,bool owned,bool internal,bool worker_first,bool message_failure) {
 struct cfg80211_registered_device r={.wiphy={.mtx=1}};int netdev=1;
 struct wireless_dev w={.netdev=&netdev,.running=false};
 int old_sent=sent,old_freed=freed,old_requests=requests;
 fail_message=message_failure;r.scan_req=request(&r,&w,internal?false:owned);refs=1;
 if(internal)r.int_scan_req=request(&r,&w,owned);
 struct cfg80211_scan_request_int *late=owned?(internal?r.int_scan_req:r.scan_req):NULL;
 ___cfg80211_scan_done(&r,direct);
 EXPECT(!r.scan_req&&!r.int_scan_req&&!refs);
 if(worker_first)drain(&r);
 if(late)retire(late);
 drain(&r);
 EXPECT(!r.scan_msg); /* A retained message keeps nl80211's scan admission busy. */
 EXPECT(sent==old_sent+!message_failure);
 EXPECT(freed-old_freed==requests-old_requests);
 EXPECT(!r.scan_done_wk.pending);
 cleanup_message(&r);cases++;
}
int main(void) {
 /* Driver-owned and already-released requests, including split request ownership. */
 for(int internal=0;internal<2;internal++)for(int first=0;first<2;first++)
  cycle(false,true,internal,first,false);
 cycle(false,false,false,false,false);
 cycle(false,false,true,false,false);
 cycle(true,true,false,false,false);
 cycle(true,true,true,false,false);
 cycle(false,true,false,false,true);
 /* Repeated interface cycles must each deliver once and release scan admission. */
 for(int i=0;i<20;i++)cycle(false,true,i%2,i%3==0,false);
 struct cfg80211_registered_device empty={.wiphy={.mtx=1}};
 int before_sent=sent,before_queue=queued;
 ___cfg80211_scan_done(&empty,false);drain(&empty);
 EXPECT(sent==before_sent&&queued==before_queue);cases++;
 CHECK(requests==freed&&!live_message&&!refs);
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d,\"delivered\":%d,\"requests_freed\":%d}\n",cases,checks,failures,sent,freed);
 return failures?1:0;
}
'''
functions = ''.join(definition(name) for name in ['cfg80211_put_scan_req', '___cfg80211_scan_done',
                                                 '__cfg80211_scan_done', 'cfg80211_scan_done'])
program = a.output / 'model.c'
program.write_text(prefix + '#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wunused-parameter"\n' +
                   functions + '\n#pragma GCC diagnostic pop\n' + harness)
exe = a.output / 'model'
c = subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g',
                    str(program), '-o', str(exe)], capture_output=True, text=True)
(a.output / 'compile.log').write_text(c.stdout + c.stderr)
assert c.returncode == 0, c.stderr
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
env.pop('LSAN_OPTIONS', None)
r = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)
(a.output / 'stdout').write_text(r.stdout)
(a.output / 'stderr').write_text(r.stderr)
j = json.loads(r.stdout)
j.update(returncode=r.returncode, mutation=a.mutation,
         source_SHA256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
         actual_functions=4, work_messages_and_driver_timing_synthetic=True,
         physical_wireless_or_concurrency_acceptance=False,
         sanitizer_diagnostics=any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:']))
(a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
assert not j['sanitizer_diagnostics'] and r.returncode == bool(j['failures'])
print(json.dumps(j))
