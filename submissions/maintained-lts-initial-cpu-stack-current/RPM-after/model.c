
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
	spinlock_t ack_lock; /* Protects response matching and completion retirement. */
	u32 msg_id;
	u32 pending_id;
	bool waiting;
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
	unsigned long flags;
	u32 request_id;
	int left;
	int ret;
	struct {
		struct qcom_rpm_header hdr;
		struct qcom_rpm_request req;
		u8 payload[];
	} *pkt;
	size_t size = sizeof(*pkt) + count;

	/* SMD packets to the RPM may not exceed 256 bytes */
	if (WARN_ON(count >= 256 - sizeof(*pkt)))
		return -EINVAL;

	pkt = kmalloc(size, GFP_ATOMIC);
	if (!pkt)
		return -ENOMEM;

	mutex_lock(&rpm->lock);

	pkt->hdr.service_type = cpu_to_le32(RPM_SERVICE_TYPE_REQUEST);
	pkt->hdr.length = cpu_to_le32(sizeof(struct qcom_rpm_request) + count);

	request_id = ++rpm->msg_id;
	if (!request_id)
		request_id = ++rpm->msg_id;
	pkt->req.msg_id = cpu_to_le32(request_id);
	pkt->req.flags = cpu_to_le32(state);
	pkt->req.type = cpu_to_le32(type);
	pkt->req.id = cpu_to_le32(id);
	pkt->req.data_len = cpu_to_le32(count);
	memcpy(pkt->payload, buf, count);

	spin_lock_irqsave(&rpm->ack_lock, flags);
	reinit_completion(&rpm->ack);
	rpm->pending_id = request_id;
	rpm->ack_status = -ETIMEDOUT;
	rpm->waiting = true;
	spin_unlock_irqrestore(&rpm->ack_lock, flags);

	ret = rpmsg_send(rpm->rpm_channel, pkt, size);
	if (ret)
		goto out;

	left = wait_for_completion_timeout(&rpm->ack, RPM_REQUEST_TIMEOUT);
	if (!left) {
		ret = -ETIMEDOUT;
	} else {
		spin_lock_irqsave(&rpm->ack_lock, flags);
		ret = rpm->ack_status;
		spin_unlock_irqrestore(&rpm->ack_lock, flags);
	}

out:
	spin_lock_irqsave(&rpm->ack_lock, flags);
	rpm->waiting = false;
	spin_unlock_irqrestore(&rpm->ack_lock, flags);
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
	struct qcom_smd_rpm *rpm = dev_get_drvdata(&rpdev->dev);
	const u8 *buf = data, *end;
	unsigned long flags;
	u32 length, type, msg_length, response_id = 0;
	size_t remaining;
	bool have_id = false, have_error = false;
	int status = 0;

	if (!rpm || count < (int)sizeof(struct qcom_rpm_header))
		return 0;
	length = get_unaligned_le32(buf + sizeof(u32));
	if (get_unaligned_le32(buf) != RPM_SERVICE_TYPE_REQUEST ||
	    length > count - sizeof(struct qcom_rpm_header))
		return 0;
	buf += sizeof(struct qcom_rpm_header);
	end = buf + length;
	while (buf < end) {
		remaining = end - buf;
		if (remaining < 2 * sizeof(u32))
			return 0;
		type = get_unaligned_le32(buf);
		msg_length = get_unaligned_le32(buf + sizeof(u32));
		buf += 2 * sizeof(u32);
		remaining = end - buf;
		if (msg_length > remaining || ALIGN(msg_length, 4) > remaining)
			return 0;
		switch (type) {
		case RPM_MSG_TYPE_MSG_ID:
			if (have_id || msg_length != sizeof(u32))
				return 0;
			response_id = get_unaligned_le32(buf);
			have_id = true;
			break;
		case RPM_MSG_TYPE_ERR:
			if (have_error || !msg_length)
				return 0;
			have_error = true;
			if (msg_length == sizeof("resource does not exist") &&
			    !memcmp(buf, "resource does not exist", msg_length))
				status = -ENXIO;
			else
				status = -EINVAL;
			break;
		}
		buf += ALIGN(msg_length, 4);
	}
	if (!have_id)
		return 0;

	spin_lock_irqsave(&rpm->ack_lock, flags);
	if (rpm->waiting && rpm->pending_id == response_id) {
		rpm->ack_status = status;
		rpm->waiting = false;
		/* Complete before the waiter can retire/reinitialize this request. */
		complete(&rpm->ack);
	}
	spin_unlock_irqrestore(&rpm->ack_lock, flags);
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
