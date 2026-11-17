
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

#define DECLARE_FLEX_ARRAY(type,name) struct { struct { } __empty_ ## name; type name[]; }
#define le32_to_cpu(x) (x)
#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))
#define PTR_ALIGN(p,a) ((void *)(((uintptr_t)(p)+(a)-1)&~((uintptr_t)(a)-1)))
#define memcpy_fromio memcpy
#define dev_err(dev,fmt,...) ((void)(dev))
struct qcom_smd_rpm {
	struct rpmsg_endpoint *rpm_channel;
	struct device *dev;

	struct completion ack;
	struct mutex lock;
	int ack_status;
};
struct qcom_rpm_header {
	__le32 service_type;
	__le32 length;
};
struct qcom_rpm_request {
	__le32 msg_id;
	__le32 flags;
	__le32 type;
	__le32 id;
	__le32 data_len;
};
struct qcom_rpm_message {
	__le32 msg_type;
	__le32 length;
	union {
		__le32 msg_id;
		DECLARE_FLEX_ARRAY(u8, message);
	};
};
#define RPM_REQUEST_TIMEOUT     (5 * HZ)
#define RPM_SERVICE_TYPE_REQUEST	0x00716572 /* "req\0" */
#define RPM_MSG_TYPE_ERR		0x00727265 /* "err\0" */
#define RPM_MSG_TYPE_MSG_ID		0x2367736d /* "msg#" */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
int qcom_rpm_smd_write(struct qcom_smd_rpm *rpm,
		       int state,
		       u32 type, u32 id,
		       void *buf,
		       size_t count)
{
	static unsigned msg_id = 1;
	int left;
	int ret;
	struct {
		struct qcom_rpm_header hdr;
		struct qcom_rpm_request req;
		u8 payload[];
	} *pkt;
	size_t size = sizeof(*pkt) + count;

	/* SMD packets to the RPM may not exceed 256 bytes */
	if (WARN_ON(size >= 256))
		return -EINVAL;

	pkt = kmalloc(size, GFP_ATOMIC);
	if (!pkt)
		return -ENOMEM;

	mutex_lock(&rpm->lock);

	pkt->hdr.service_type = cpu_to_le32(RPM_SERVICE_TYPE_REQUEST);
	pkt->hdr.length = cpu_to_le32(sizeof(struct qcom_rpm_request) + count);

	pkt->req.msg_id = cpu_to_le32(msg_id++);
	pkt->req.flags = cpu_to_le32(state);
	pkt->req.type = cpu_to_le32(type);
	pkt->req.id = cpu_to_le32(id);
	pkt->req.data_len = cpu_to_le32(count);
	memcpy(pkt->payload, buf, count);

	ret = rpmsg_send(rpm->rpm_channel, pkt, size);
	if (ret)
		goto out;

	left = wait_for_completion_timeout(&rpm->ack, RPM_REQUEST_TIMEOUT);
	if (!left)
		ret = -ETIMEDOUT;
	else
		ret = rpm->ack_status;

out:
	kfree(pkt);
	mutex_unlock(&rpm->lock);
	return ret;
}
static int qcom_smd_rpm_callback(struct rpmsg_device *rpdev,
				 void *data,
				 int count,
				 void *priv,
				 u32 addr)
{
	const struct qcom_rpm_header *hdr = data;
	size_t hdr_length = le32_to_cpu(hdr->length);
	const struct qcom_rpm_message *msg;
	struct qcom_smd_rpm *rpm = dev_get_drvdata(&rpdev->dev);
	const u8 *buf = data + sizeof(struct qcom_rpm_header);
	const u8 *end = buf + hdr_length;
	char msgbuf[32];
	int status = 0;
	u32 len, msg_length;

	if (le32_to_cpu(hdr->service_type) != RPM_SERVICE_TYPE_REQUEST ||
	    hdr_length < sizeof(struct qcom_rpm_message)) {
		dev_err(rpm->dev, "invalid request\n");
		return 0;
	}

	while (buf < end) {
		msg = (struct qcom_rpm_message *)buf;
		msg_length = le32_to_cpu(msg->length);
		switch (le32_to_cpu(msg->msg_type)) {
		case RPM_MSG_TYPE_MSG_ID:
			break;
		case RPM_MSG_TYPE_ERR:
			len = min_t(u32, ALIGN(msg_length, 4), sizeof(msgbuf));
			memcpy_fromio(msgbuf, msg->message, len);
			msgbuf[len - 1] = 0;

			if (!strcmp(msgbuf, "resource does not exist"))
				status = -ENXIO;
			else
				status = -EINVAL;
			break;
		}

		buf = PTR_ALIGN(buf + 2 * sizeof(u32) + msg_length, 4);
	}

	rpm->ack_status = status;
	complete(&rpm->ack);
	return 0;
}

#pragma GCC diagnostic pop

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
