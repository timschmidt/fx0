// SPDX-License-Identifier: MIT
/* Exact-length synthetic wire buffers; real QRTR codec and RMTFS descriptors. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "qmi_rmtfs.h"

static const char *scenario;
static unsigned char wire[4096];
static size_t used;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %s:%d: %s\n",scenario,__LINE__,#x); exit(1); } } while (0)
static void le16(unsigned char *p,unsigned x) { p[0]=x; p[1]=x>>8; }
static void le32(unsigned char *p,uint32_t x) { for(unsigned i=0;i<4;i++) p[i]=x>>(8*i); }
static void begin(unsigned id) { memset(wire,0,sizeof(wire)); used=7; wire[1]=0x34; wire[2]=0x12; le16(wire+3,id); }
static void tlv(unsigned type,const void *data,size_t n)
{ CHECK(used+n+3<=sizeof(wire)); wire[used++]=type; le16(wire+used,n); used+=2; if(n) memcpy(wire+used,data,n); used+=n; }
static void scalar(unsigned type,uint32_t value,size_t n) { unsigned char data[4]; le32(data,value); tlv(type,data,n); }
static void finish(void) { le16(wire+5,used-7); }
static size_t find_tlv(unsigned type)
{
    for(size_t pos=7;pos+3<=used;) {
        if(wire[pos]==type) return pos;
        pos+=3+wire[pos+1]+((size_t)wire[pos+2]<<8);
    }
    CHECK(0); return 0;
}
static struct qrtr_packet packet(void)
{
    struct qrtr_packet p={.data=malloc(used ? used : 1),.data_len=used};
    CHECK(p.data); memcpy(p.data,wire,used); return p;
}
static void decode(void *dest,struct qmi_elem_info *ei,unsigned id,int valid)
{
    struct qrtr_packet p=packet(); unsigned txn=0;
    int rc=qmi_decode_message(dest,&txn,&p,QMI_REQUEST,id,ei);
    CHECK(valid ? rc>=0 : rc<0); if(valid) CHECK(txn==0x1234);
    free(p.data);
}
static void iovec_wire(unsigned count,unsigned entries,int omit)
{
    unsigned char data[1+255*12]={0}; data[0]=count;
    for(unsigned i=0;i<entries;i++) {
        le32(data+1+i*12,i+1); le32(data+5+i*12,0x10000000+i*512); le32(data+9+i*12,1);
    }
    begin(3); if(omit!=1) scalar(1,0x11223344,4); if(omit!=2) scalar(2,1,1);
    if(omit!=3) tlv(3,data,1+entries*12); if(omit!=4) scalar(4,1,1); finish();
}
struct nested { char text[9]; uint32_t after; };
struct outer { struct nested entries[2]; };
static struct qmi_elem_info nested_ei[]={
    {.data_type=QMI_STRING,.elem_len=8,.elem_size=1,.offset=offsetof(struct nested,text)},
    {.data_type=QMI_UNSIGNED_4_BYTE,.elem_len=1,.elem_size=4,.offset=offsetof(struct nested,after)}, {0}};
static struct qmi_elem_info outer_ei[]={
    {.data_type=QMI_STRUCT,.elem_len=2,.elem_size=sizeof(struct nested),.array_type=STATIC_ARRAY,.tlv_type=1,.ei_array=nested_ei}, {0}};
struct scalar_array { uint32_t count; uint32_t values[3]; };
static struct qmi_elem_info array_ei[]={
    {.data_type=QMI_DATA_LEN,.elem_len=1,.elem_size=2,.tlv_type=1,.offset=offsetof(struct scalar_array,count)},
    {.data_type=QMI_UNSIGNED_4_BYTE,.elem_len=3,.elem_size=4,.array_type=VAR_LEN_ARRAY,.tlv_type=1,.offset=offsetof(struct scalar_array,values)}, {0}};

int main(int argc,char **argv)
{
    CHECK(argc==2); scenario=argv[1];
    if(!strncmp(scenario,"short-header-",13)) {
        unsigned n=atoi(scenario+13),id=99,txn=99; begin(2); used=n;
        struct qrtr_packet p=packet(); struct rmtfs_close_req req={0};
        CHECK(qmi_decode_header(&p,&id)<0);
        CHECK(qmi_decode_message(&req,&txn,&p,QMI_REQUEST,2,rmtfs_close_req_ei)<0); free(p.data);
    } else if(!strcmp(scenario,"null-packet")) {
        unsigned id=0; struct rmtfs_close_req req={0};
        CHECK(qmi_decode_header(NULL,&id)<0);
        CHECK(qmi_decode_message(&req,&id,NULL,QMI_REQUEST,2,rmtfs_close_req_ei)<0);
    } else if(!strcmp(scenario,"null-data")) {
        unsigned id=0; struct qrtr_packet p={.data=NULL,.data_len=7}; struct rmtfs_close_req req={0};
        CHECK(qmi_decode_header(&p,&id)<0);
        CHECK(qmi_decode_message(&req,&id,&p,QMI_REQUEST,2,rmtfs_close_req_ei)<0);
    } else if(!strcmp(scenario,"header-length-short") || !strcmp(scenario,"header-length-long")) {
        struct rmtfs_close_req req={0}; begin(2); scalar(1,7,4); finish();
        le16(wire+5,used-7+(!strcmp(scenario,"header-length-short") ? -1 : 1));
        struct qrtr_packet p=packet(); unsigned id=0; CHECK(qmi_decode_header(&p,&id)<0); free(p.data);
        decode(&req,rmtfs_close_req_ei,2,0);
    } else if(!strncmp(scenario,"tlv-header-",11)) {
        struct rmtfs_close_req req={0}; begin(2); scalar(1,7,4);
        wire[used++]=0x10; if(atoi(scenario+11)==2) wire[used++]=0; finish();
        decode(&req,rmtfs_close_req_ei,2,0);
    } else if(!strcmp(scenario,"tlv-overrun") || !strcmp(scenario,"unknown-optional-overrun")) {
        struct rmtfs_close_req req={0}; begin(2); scalar(1,7,4); tlv(!strcmp(scenario,"tlv-overrun") ? 1 : 0x10,NULL,0);
        le16(wire+used-2,65535); finish(); decode(&req,rmtfs_close_req_ei,2,0);
    } else if(!strcmp(scenario,"scalar-short") || !strcmp(scenario,"scalar-zero") || !strcmp(scenario,"scalar-extra")) {
        struct rmtfs_close_req req={0}; unsigned char data[5]={1,0,0,0,0}; begin(2);
        tlv(1,data,!strcmp(scenario,"scalar-short") ? 3 : (!strcmp(scenario,"scalar-zero") ? 0 : 5)); finish(); decode(&req,rmtfs_close_req_ei,2,0);
    } else if(!strcmp(scenario,"missing-close") || !strcmp(scenario,"missing-alloc")) {
        begin(!strcmp(scenario,"missing-close") ? 2 : 4); finish();
        if(wire[3]==2) { struct rmtfs_close_req req={0}; decode(&req,rmtfs_close_req_ei,2,0); }
        else { struct rmtfs_alloc_buf_req req={0}; decode(&req,rmtfs_alloc_buf_req_ei,4,0); }
    } else if(!strncmp(scenario,"missing-iovec-",14)) {
        struct rmtfs_iovec_req req={0}; iovec_wire(1,1,atoi(scenario+14)); decode(&req,rmtfs_iovec_req_ei,3,0);
    } else if(!strcmp(scenario,"array-missing-count") || !strcmp(scenario,"array-incomplete") ||
              !strcmp(scenario,"array-short-member") || !strcmp(scenario,"array-trailing") ||
              !strcmp(scenario,"array-valid") || !strcmp(scenario,"array-zero") || !strcmp(scenario,"array-max") ||
              !strcmp(scenario,"iovec-reversed")) {
        struct rmtfs_iovec_req req={0}; unsigned entries=!strcmp(scenario,"array-max") ? 255 : (!strcmp(scenario,"array-zero") ? 0 : 1);
        unsigned count=!strcmp(scenario,"array-incomplete") ? 2 : entries;
        iovec_wire(count,entries,0);
        if(!strcmp(scenario,"iovec-reversed")) {
            unsigned char copy[4096]; size_t positions[4],sizes[4],pos=7;
            memcpy(copy,wire,used);
            for(unsigned i=0;i<4;i++) { positions[i]=pos; sizes[i]=3+copy[pos+1]+((size_t)copy[pos+2]<<8); pos+=sizes[i]; }
            pos=7; for(int i=3;i>=0;i--) { memcpy(wire+pos,copy+positions[i],sizes[i]); pos+=sizes[i]; }
        }
        size_t t=find_tlv(3),v=t+3;
        if(!strcmp(scenario,"array-missing-count")) { memmove(wire+v,wire+v+13,used-v-13); used-=13; le16(wire+t+1,0); finish(); }
        if(!strcmp(scenario,"array-short-member")) { memmove(wire+v+12,wire+v+13,used-v-13); used--; le16(wire+t+1,12); finish(); }
        if(!strcmp(scenario,"array-trailing")) { memmove(wire+v+14,wire+v+13,used-v-13); wire[v+13]=0; used++; le16(wire+t+1,14); finish(); }
        int valid=!strcmp(scenario,"array-valid") || !strcmp(scenario,"array-zero") || !strcmp(scenario,"array-max") || !strcmp(scenario,"iovec-reversed");
        decode(&req,rmtfs_iovec_req_ei,3,valid);
        if(valid) { CHECK(req.caller_id==0x11223344 && req.direction==1 && req.iovec_len==count && req.is_force_sync==1); if(count) CHECK(req.iovec[count-1].sector_addr==count); }
    } else if(!strncmp(scenario,"string-",7)) {
        unsigned n=atoi(scenario+7); char data[257]; memset(data,'x',sizeof(data)); begin(1); tlv(1,data,n); finish();
        struct rmtfs_open_req *req=calloc(1,sizeof(*req)); CHECK(req);
        decode(req,rmtfs_open_req_ei,1,n<=256);
        if(n<=256) CHECK(strlen(req->path)==n && !memcmp(req->path,data,n)); free(req);
    } else if(!strcmp(scenario,"unknown-optional") || !strcmp(scenario,"unknown-required") || !strcmp(scenario,"reordered")) {
        struct rmtfs_close_req req={0}; begin(2);
        if(!strcmp(scenario,"reordered")) scalar(0x10,99,4);
        scalar(1,0x12345678,4);
        if(strcmp(scenario,"reordered")) scalar(!strcmp(scenario,"unknown-required") ? 9 : 0x10,99,4);
        finish(); decode(&req,rmtfs_close_req_ei,2,strcmp(scenario,"unknown-required")!=0); CHECK(req.caller_id==0x12345678);
    } else if(!strncmp(scenario,"nested-wide-string-",19)) {
        struct big { char text[301]; uint32_t after; } dest={0};
        struct qmi_elem_info inner[]={
            {.data_type=QMI_STRING,.elem_len=300,.elem_size=1,.offset=offsetof(struct big,text)},
            {.data_type=QMI_UNSIGNED_4_BYTE,.elem_len=1,.elem_size=4,.offset=offsetof(struct big,after)}, {0}};
        struct qmi_elem_info outer[]={
            {.data_type=QMI_STRUCT,.elem_len=1,.elem_size=sizeof(dest),.tlv_type=1,.ei_array=inner}, {0}};
        unsigned char data[306]; le16(data,300); memset(data+2,'x',300); le32(data+302,99);
        int valid=!strcmp(scenario,"nested-wide-string-valid");
        begin(90); tlv(1,data,valid ? sizeof(data) : 1); finish(); decode(&dest,outer,90,valid);
        if(valid) CHECK(strlen(dest.text)==300 && dest.after==99);
    } else if(!strncmp(scenario,"nested-",7)) {
        struct outer dest={0}; unsigned char data[32]={0}; size_t n=0;
        for(unsigned i=0;i<2;i++) { data[n++]=3; memcpy(data+n,"abc",3); n+=3; le32(data+n,0x12345678+i); n+=4; }
        if(!strcmp(scenario,"nested-string-short")) { data[0]=8; n=4; }
        if(!strcmp(scenario,"nested-missing-scalar")) n=4;
        if(!strcmp(scenario,"nested-missing-entry")) n=8;
        begin(88); tlv(1,data,n); finish(); int valid=!strcmp(scenario,"nested-valid"); decode(&dest,outer_ei,88,valid);
        if(valid) CHECK(!strcmp(dest.entries[0].text,"abc") && dest.entries[1].after==0x12345679);
    } else if(!strncmp(scenario,"scalar-array-",13)) {
        struct scalar_array dest={0}; unsigned char data[14]={0}; data[0]=3; le32(data+2,7); le32(data+6,8); le32(data+10,9);
        size_t n=!strcmp(scenario,"scalar-array-prefix-short") ? 1 : (!strcmp(scenario,"scalar-array-short") ? 10 : 14);
        if(!strcmp(scenario,"scalar-array-too-many")) data[0]=4;
        begin(89); tlv(1,data,n); finish(); int valid=!strcmp(scenario,"scalar-array-valid"); decode(&dest,array_ei,89,valid);
        if(valid) CHECK(dest.count==3 && dest.values[2]==9);
    } else if(!strcmp(scenario,"encode-open") || !strcmp(scenario,"encode-empty-open") || !strcmp(scenario,"encode-max-open")) {
        struct rmtfs_open_req req={0}; struct qrtr_packet p={.data=wire,.data_len=sizeof(wire)};
        size_t n=!strcmp(scenario,"encode-empty-open") ? 0 : (!strcmp(scenario,"encode-max-open") ? 256 : 15);
        CHECK(sizeof(req.path)>=n+1); memset(req.path,'x',n);
        CHECK(qmi_encode_message(&p,QMI_REQUEST,1,0x1234,&req,rmtfs_open_req_ei)==(ssize_t)(10+n));
        used=p.data_len; CHECK(wire[7]==1 && wire[8]==(n&255) && wire[9]==(n>>8));
        struct rmtfs_open_req dest={0}; decode(&dest,rmtfs_open_req_ei,1,1); CHECK(strlen(dest.path)==n);
    } else CHECK(0);
    printf("QMI_CASE_PASS %s\n",scenario); return 0;
}
