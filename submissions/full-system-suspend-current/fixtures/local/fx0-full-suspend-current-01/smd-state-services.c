// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define EPROBE_DEFER 517
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define RPMSG_ADDR_ANY UINT32_MAX
enum {SMD_CHANNEL_CLOSED,SMD_CHANNEL_OPENING,SMD_CHANNEL_OPENED,SMD_CHANNEL_FLUSHING,SMD_CHANNEL_CLOSING,SMD_CHANNEL_RESET,SMD_CHANNEL_RESET_OPENING};
static int cases,checks,failures,creates,removes,fail_create,create_error;
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define EXPECT(x) do {checks++;if(!(x)){if(failures++<12)fprintf(stderr,"%d: %s\n",__LINE__,#x);}}while(0)
struct work_struct {int unused;};
struct device {int unused;};
struct qcom_smd_channel {const char *name;unsigned int state,remote_state;bool registered;};
struct list_head {struct qcom_smd_channel *items[4];int count;};
struct qcom_smd_edge {struct work_struct state_work;struct device dev;struct list_head channels;bool no_suspend;int channels_lock;};
struct rpmsg_channel_info {char name[32];unsigned int src,dst;};
static struct qcom_smd_edge edge;
static struct qcom_smd_channel channels[4];
#define GET_RX_CHANNEL_INFO(c,m) ((c)->remote_state)
#define list_for_each_entry(c,l,m) for(int model_i=0;model_i<(l)->count&&((c)=(l)->items[model_i]);model_i++)
#define spin_lock_irqsave(l,f) do {(f)=0;CHECK(!*(l));*(l)=1;}while(0)
#define spin_unlock_irqrestore(l,f) do {(void)(f);CHECK(*(l)==1);*(l)=0;}while(0)
static int qcom_smd_create_device(struct qcom_smd_channel *c) {CHECK(!edge.channels_lock&&!c->registered);creates++;return creates==fail_create?create_error:0;}
static void strscpy_pad(char *dst,const char *src,size_t size) {CHECK(strlen(src)<size);memset(dst,0,size);memcpy(dst,src,strlen(src));}
static void rpmsg_unregister_device(struct device *d,struct rpmsg_channel_info *info) {
 CHECK(d==&edge.dev&&!edge.channels_lock&&info->src==RPMSG_ADDR_ANY&&info->dst==RPMSG_ADDR_ANY);removes++;
 bool found=false;for(int i=0;i<edge.channels.count;i++)if(!strcmp(edge.channels.items[i]->name,info->name)){edge.channels.items[i]->state=SMD_CHANNEL_CLOSED;found=true;break;}CHECK(found);
}
