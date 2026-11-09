/* Execute the production protocol/state machine with controlled kernel datagrams. */
#define main diagnostic_main
#include "../diagnostics/nfc-startup/nfc-state.c"
#undef main
#include <assert.h>

struct datagram { unsigned char data[4096]; size_t size; struct peer peer; };
struct fake {
    const char *mode;
    const char *verb;
    struct datagram queue[4];
    unsigned queued, read, sends, mutation_sends, receives;
    uint8_t commands[8];
    bool powered;
    int64_t clock;
};
static bool mode(const struct fake *f, const char *name) { return !strcmp(f->mode, name); }
static struct peer kernel_peer(void)
{
    return (struct peer){ .length = sizeof(struct sockaddr_nl),
        .address = { .nl_family = AF_NETLINK } };
}
static void finish_message(struct datagram *d, struct nlmsghdr *h, size_t size)
{
    h->nlmsg_len = (uint32_t)size; memcpy(d->data, h, sizeof(*h));
    d->size = size; d->peer = kernel_peer();
}
static void ack(struct datagram *d, const struct nlmsghdr *request, int error)
{
    struct nlmsghdr h = { .nlmsg_type = NLMSG_ERROR, .nlmsg_flags = NLM_F_CAPPED,
        .nlmsg_seq = request->nlmsg_seq, .nlmsg_pid = request->nlmsg_pid };
    struct nlmsgerr e = { .error = error, .msg = *request };
    memcpy(d->data + sizeof(h), &e, sizeof(e));
    finish_message(d, &h, sizeof(h) + sizeof(e));
}
static void attr(struct datagram *d, size_t *size, uint16_t type, const void *data, size_t n)
{
    assert(!add_attribute(d->data, sizeof(d->data), size, type, data, n));
}
static void family_message(struct fake *f, struct datagram *d, const struct nlmsghdr *request)
{
    struct nlmsghdr h = { .nlmsg_type = GENL_ID_CTRL, .nlmsg_seq = request->nlmsg_seq,
        .nlmsg_pid = request->nlmsg_pid };
    struct genlmsghdr g = { .cmd = CTRL_CMD_NEWFAMILY, .version = 2 };
    memcpy(d->data + sizeof(h), &g, sizeof(g));
    size_t n = sizeof(h) + sizeof(g);
    uint16_t id = mode(f,"reserved_id") ? GENL_ID_CTRL : 42;
    uint32_t version = mode(f,"family_version") ? 2 : 1;
    const char *name = mode(f,"family_name") ? "other" : "nfc";
    attr(d,&n,CTRL_ATTR_FAMILY_NAME,name,strlen(name)+1);
    attr(d,&n,CTRL_ATTR_FAMILY_ID,&id,sizeof(id));
    attr(d,&n,CTRL_ATTR_VERSION,&version,sizeof(version));
    if (mode(f,"duplicate_attr")) attr(d,&n,CTRL_ATTR_FAMILY_ID,&id,sizeof(id));
    finish_message(d,&h,n);
}
static void device_message(struct fake *f, struct datagram *d, const struct nlmsghdr *request)
{
    struct nlmsghdr h = { .nlmsg_type = request->nlmsg_type,
        .nlmsg_seq = request->nlmsg_seq, .nlmsg_pid = request->nlmsg_pid };
    struct genlmsghdr g = { .cmd = NFC_CMD_GET_DEVICE, .version = 1 };
    memcpy(d->data + sizeof(h),&g,sizeof(g));
    size_t n=sizeof(h)+sizeof(g);
    uint32_t index=mode(f,"device_index") ? 1 : 0;
    uint32_t protocols=mode(f,"protocols") ? EXPECTED_PROTOCOLS^128 : EXPECTED_PROTOCOLS;
    uint8_t powered=mode(f,"powered_range") ? 2 : f->powered;
    uint8_t rf=mode(f,"RF_active") ? NFC_RF_INITIATOR : NFC_RF_NONE;
    const char *name=mode(f,"device_name") ? "nfc1" : "nfc0";
    attr(d,&n,NFC_ATTR_DEVICE_NAME,name,strlen(name)+1);
    attr(d,&n,NFC_ATTR_DEVICE_INDEX,&index,sizeof(index));
    attr(d,&n,NFC_ATTR_PROTOCOLS,&protocols,sizeof(protocols));
    if (!mode(f,"powered_missing")) attr(d,&n,NFC_ATTR_DEVICE_POWERED,&powered,sizeof(powered));
    attr(d,&n,NFC_ATTR_RF_MODE,&rf,sizeof(rf));
    if (mode(f,"duplicate_device")) attr(d,&n,NFC_ATTR_DEVICE_INDEX,&index,sizeof(index));
    finish_message(d,&h,n);
}
static void damage(struct fake *f, struct datagram *d)
{
    struct nlmsghdr h; memcpy(&h,d->data,sizeof(h));
    if(mode(f,"wrong_sequence")) h.nlmsg_seq++;
    if(mode(f,"wrong_header_pid")) h.nlmsg_pid++;
    if(mode(f,"wrong_type")) h.nlmsg_type++;
    if(mode(f,"multipart")) h.nlmsg_flags=NLM_F_MULTI;
    if(mode(f,"dump_interrupted")) h.nlmsg_flags=NLM_F_DUMP_INTR;
    if(mode(f,"NOOP")) h.nlmsg_type=NLMSG_NOOP;
    if(mode(f,"DONE")) h.nlmsg_type=NLMSG_DONE;
    if(mode(f,"OVERRUN")) h.nlmsg_type=NLMSG_OVERRUN;
    if(mode(f,"short_nlmsg")) h.nlmsg_len=15;
    if(mode(f,"long_nlmsg")) h.nlmsg_len=(uint32_t)d->size+4;
    memcpy(d->data,&h,sizeof(h));
    if(mode(f,"short_header")) d->size=12;
    if(mode(f,"empty_datagram")) d->size=0;
    if(mode(f,"trailing_byte")) d->data[d->size++]=0;
    if(mode(f,"peer_pid")) d->peer.address.nl_pid=99;
    if(mode(f,"peer_groups")) d->peer.address.nl_groups=1;
    if(mode(f,"peer_family")) d->peer.address.nl_family=AF_INET;
    if(mode(f,"peer_size")) d->peer.length=4;
    if(mode(f,"truncated")) d->peer.flags|=MSG_TRUNC;
    if(mode(f,"control_truncated")) d->peer.flags|=MSG_CTRUNC;
    size_t base=sizeof(struct nlmsghdr),at=base+sizeof(struct genlmsghdr);
    if(mode(f,"genl_command")) d->data[base]++;
    if(mode(f,"genl_version")) d->data[base+1]++;
    if(mode(f,"genl_reserved")) d->data[base+2]=1;
    if(mode(f,"short_attr")) {uint16_t n=3;memcpy(d->data+at,&n,2);}
    if(mode(f,"long_attr")) {uint16_t n=UINT16_MAX;memcpy(d->data+at,&n,2);}
    if(mode(f,"nested_scalar") || mode(f,"network_scalar")) {
        uint16_t type;memcpy(&type,d->data+at+2,2);
        type|=mode(f,"nested_scalar") ? NLA_F_NESTED : NLA_F_NET_BYTEORDER;
        memcpy(d->data+at+2,&type,2);
    }
    if(mode(f,"zero_attr")) {uint16_t type=0;memcpy(d->data+at+2,&type,2);}
    if(mode(f,"high_attr")) {uint16_t type=ATTR_SLOTS;memcpy(d->data+at+2,&type,2);}
    if(mode(f,"string_not_terminated")) d->data[at+sizeof(struct nlattr)+3]='x';
}
static ssize_t fake_send(void *opaque,const void *data,size_t size)
{
    struct fake *f=opaque;
    assert(size>=20 && size<=256 && f->sends<8 && f->read==f->queued);
    f->queued=f->read=0;
    struct nlmsghdr h;struct genlmsghdr g;
    memcpy(&h,data,sizeof(h));memcpy(&g,(const unsigned char *)data+sizeof(h),sizeof(g));
    assert(h.nlmsg_len==size && h.nlmsg_flags==(NLM_F_REQUEST|NLM_F_ACK) && h.nlmsg_pid==4242);
    assert(h.nlmsg_seq==f->sends+1);
    struct attribute a[ATTR_SLOTS];assert(!attributes((const unsigned char *)data+20,size-20,a));
    f->commands[f->sends++]=g.cmd;
    bool control=h.nlmsg_type==GENL_ID_CTRL;
    bool mutate=!control && g.cmd!=NFC_CMD_GET_DEVICE;
    if(control) {assert(g.cmd==CTRL_CMD_GETFAMILY);assert(!string_is(&a[CTRL_ATTR_FAMILY_NAME],"nfc"));}
    else {uint32_t index;assert(h.nlmsg_type==42);assert(!scalar(&a[NFC_ATTR_DEVICE_INDEX],&index,4)&&index==0);}
    if(mutate) {
        assert(g.cmd==NFC_CMD_DEV_UP || g.cmd==NFC_CMD_DEV_DOWN);
        f->mutation_sends++;
        if(mode(f,"short_send")) return (ssize_t)size-1;
        if(mode(f,"send_EINTR")) {errno=EINTR;return -1;}
        if(mode(f,"send_error")) {errno=EIO;return -1;}
        if(!mode(f,"not_applied") && !mode(f,"mutation_rejected")) f->powered=g.cmd==NFC_CMD_DEV_UP;
        if(mode(f,"send_deadline")) f->clock+=30000;
    }
    struct datagram response={0},acknowledgement={0};
    int error=mode(f,"negative_ack") ? -EPERM : mutate&&mode(f,"mutation_rejected") ? -ERFKILL : 0;
    ack(&acknowledgement,&h,error);
    if(mode(f,"ack_not_capped") || mode(f,"ack_extack") || mode(f,"ack_tail")) {
        struct nlmsghdr ah;memcpy(&ah,acknowledgement.data,16);
        if(mode(f,"ack_not_capped"))ah.nlmsg_flags=0;
        if(mode(f,"ack_extack"))ah.nlmsg_flags|=NLM_F_ACK_TLVS;
        size_t n=acknowledgement.size;
        if(mode(f,"ack_tail")){memset(acknowledgement.data+n,0,4);n+=4;}
        finish_message(&acknowledgement,&ah,n);
    }
    if(mode(f,"positive_ack") || mode(f,"INT_MIN_ack") || mode(f,"wrong_echo") || mode(f,"short_ack")) {
        struct nlmsgerr e;memcpy(&e,acknowledgement.data+16,sizeof(e));
        if(mode(f,"positive_ack")) e.error=1;
        if(mode(f,"INT_MIN_ack")) e.error=INT_MIN;
        if(mode(f,"wrong_echo")) e.msg.nlmsg_seq++;
        memcpy(acknowledgement.data+16,&e,sizeof(e));
        if(mode(f,"short_ack")) {struct nlmsghdr ah;memcpy(&ah,acknowledgement.data,16);ah.nlmsg_len=20;finish_message(&acknowledgement,&ah,20);}
    }
    if(mutate) {f->queue[f->queued++]=acknowledgement;return (ssize_t)size;}
    if(control)family_message(f,&response,&h);else device_message(f,&response,&h);
    if(control)damage(f,&response);
    if(mode(f,"missing_ack")) f->queue[f->queued++]=response;
    else if(mode(f,"missing_reply"))f->queue[f->queued++]=acknowledgement;
    else if(mode(f,"coalesced") || mode(f,"duplicate_ack") || mode(f,"duplicate_reply")) {
        struct datagram both=response;
        memcpy(both.data+both.size,acknowledgement.data,acknowledgement.size);both.size+=acknowledgement.size;
        if(mode(f,"duplicate_ack")){memcpy(both.data+both.size,acknowledgement.data,acknowledgement.size);both.size+=acknowledgement.size;}
        if(mode(f,"duplicate_reply")){memcpy(both.data+both.size,response.data,response.size);both.size+=response.size;}
        f->queue[f->queued++]=both;
    } else if(mode(f,"ack_first")) {f->queue[f->queued++]=acknowledgement;f->queue[f->queued++]=response;}
    else {f->queue[f->queued++]=response;f->queue[f->queued++]=acknowledgement;}
    return (ssize_t)size;
}
static ssize_t fake_receive(void *opaque,void *data,size_t size,struct peer *peer,int64_t deadline)
{
    struct fake *f=opaque;f->receives++;assert(deadline>f->clock);
    if(mode(f,"mutation_timeout")&&f->mutation_sends){errno=ETIMEDOUT;return -1;}
    if(f->read==f->queued){errno=ETIMEDOUT;return -1;}
    struct datagram *d=&f->queue[f->read++];assert(d->size<=size);
    memcpy(data,d->data,d->size);*peer=d->peer;return (ssize_t)d->size;
}
static int64_t fake_now(void *opaque){return ((struct fake *)opaque)->clock;}
static int fuzz_packets(void)
{
    struct fake f={.mode="normal"};struct datagram base={0};
    struct nlmsghdr request={.nlmsg_len=28,.nlmsg_type=GENL_ID_CTRL,
        .nlmsg_flags=NLM_F_REQUEST|NLM_F_ACK,.nlmsg_seq=1,.nlmsg_pid=4242};
    family_message(&f,&base,&request);
    uint32_t random=0x4e434931U;unsigned accepted=0;
    for(unsigned n=0;n<16384;n++) {
        struct datagram d=base;random=random*1664525U+1013904223U;
        switch(n%5) {
        case 0:d.size=random%(base.size+4);break;
        case 1:d.data[random%base.size]^=(unsigned char)(1U<<(random%8));break;
        case 2:{uint32_t length=random;memcpy(d.data,&length,4);break;}
        case 3:{uint16_t length=(uint16_t)random;memcpy(d.data+20,&length,2);break;}
        default:d.data[random%base.size]=(unsigned char)(random>>24);break;
        }
        struct transaction t={.kind=FAMILY_REPLY,.type=GENL_ID_CTRL,.sequence=1,
            .port=4242,.request_size=28,.family_name="nfc",.family_version=1};
        if(!packet(&t,d.data,d.size,&d.peer))accepted++;
    }
    printf("{\"result\":0,\"iterations\":16384,\"accepted_well_formed_variants\":%u,\"mutation_sends\":0}\n",accepted);
    return 0;
}
int main(int argc,char **argv)
{
    if(argc!=3)return 2;
    if(!strcmp(argv[1],"fuzz"))return fuzz_packets();
    struct fake f={.mode=argv[1],.verb=argv[2],.clock=1000,.powered=!strcmp(argv[2],"down")};
    struct session s={.io={.opaque=&f,.port=4242,.send=fake_send,.receive=fake_receive,.now=fake_now},.deadline=31000,.phase="start"};
    struct device before={0},after={0};uint16_t id=0;
    if(mode(&f,"already_up")) f.powered=true;
    if(mode(&f,"already_down"))f.powered=false;
    int rc=run(&s,argv[2],0,&before,&after,&id);int error=rc?errno:0;
    printf("{\"result\":%d,\"error\":%d,\"requests\":%u,\"mutation_attempted\":%s,\"mutation_sends\":%u,\"powered_before\":%u,\"powered_after\":%u,\"commands\":[",rc,error,s.requests,s.mutation_attempted?"true":"false",f.mutation_sends,before.powered,after.powered);
    for(unsigned i=0;i<f.sends;i++)printf("%s%u",i?",":"",f.commands[i]);
    puts("]}");return 0;
}
