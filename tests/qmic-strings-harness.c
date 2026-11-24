// SPDX-License-Identifier: MIT
/* Normal generated-schema round trips compared with independent wire bytes. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "qmi_qmicstrings.h"
#include "qmi_rmtfs.h"

static const char *scenario;
static unsigned char actual[4096],expected[4096];
static size_t used;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %s:%d: %s\n",scenario,__LINE__,#x); exit(1); } } while (0)
#define CAP(type,field) _Static_assert(sizeof(((type *)0)->field)==257,"string requires 256 wire bytes plus NUL")
CAP(struct qmicstrings_leaf,label);
CAP(struct qmicstrings_transfer_req,title);
CAP(struct qmicstrings_transfer_req,alias);
CAP(struct qmicstrings_transfer_resp,reply_text);
CAP(struct rmtfs_open_req,path);
_Static_assert(sizeof(((struct rmtfs_iovec_req *)0)->iovec_len)==4,"QMI count is 32-bit");
_Static_assert(sizeof(((struct rmtfs_force_sync *)0)->caller_id_len)==4,"QMI count is 32-bit");
static void le16(unsigned char *p,unsigned v) { p[0]=v; p[1]=v>>8; }
static void le32(unsigned char *p,uint32_t v) { for(unsigned i=0;i<4;i++) p[i]=v>>(8*i); }
static void begin(unsigned type,unsigned id) { memset(expected,0,sizeof(expected));used=7;expected[0]=type;le16(expected+1,0x4142);le16(expected+3,id); }
static void tlv(unsigned type,const void *data,size_t n)
{ CHECK(used+3+n<=sizeof(expected));expected[used++]=type;le16(expected+used,n);used+=2;if(n) memcpy(expected+used,data,n);used+=n; }
static size_t leaf_bytes(unsigned char *p,const struct qmicstrings_leaf *leaf)
{ size_t n=strlen(leaf->label);CHECK(n<=255);p[0]=n;memcpy(p+1,leaf->label,n);le32(p+1+n,leaf->marker);return n+5; }
static void round_trip(unsigned type,unsigned id,const void *source,void *dest,struct qmi_elem_info *ei)
{
    struct qrtr_packet pkt={.data=actual,.data_len=sizeof(actual)};unsigned txn=0;
    le16(expected+5,used-7);
    CHECK(qmi_encode_message(&pkt,type,id,0x4142,source,ei)==(ssize_t)used);
    CHECK(pkt.data_len==used && !memcmp(actual,expected,used));
    CHECK(qmi_decode_message(dest,&txn,&pkt,type,id,ei)>=0 && txn==0x4142);
}
int main(int argc,char **argv)
{
    CHECK(argc==2);scenario=argv[1];
    if(!strncmp(scenario,"open-",5)) {
        unsigned n=atoi(scenario+5);CHECK(n<=256);
        struct rmtfs_open_req req={0},dest={0};memset(req.path,'p',n);
        begin(QMI_REQUEST,1);tlv(1,req.path,n);round_trip(QMI_REQUEST,1,&req,&dest,rmtfs_open_req_ei);
        CHECK(strlen(dest.path)==n && !memcmp(dest.path,req.path,n+1));
    } else if(!strcmp(scenario,"iovec-count")) {
        struct rmtfs_iovec_req req={.caller_id=7,.direction=1,.iovec_len=2,.is_force_sync=1},dest={0};
        unsigned char data[25];data[0]=2;
        for(unsigned i=0;i<2;i++) { req.iovec[i]=(struct rmtfs_iovec_entry){i+2,0x10000000+i*512,1};le32(data+1+i*12,i+2);le32(data+5+i*12,0x10000000+i*512);le32(data+9+i*12,1); }
        begin(QMI_REQUEST,3);unsigned char scalar[4];le32(scalar,7);tlv(1,scalar,4);scalar[0]=1;tlv(2,scalar,1);tlv(3,data,sizeof(data));tlv(4,scalar,1);
        round_trip(QMI_REQUEST,3,&req,&dest,rmtfs_iovec_req_ei);CHECK(dest.iovec_len==2 && dest.iovec[1].sector_addr==3 && dest.is_force_sync==1);
    } else if(!strcmp(scenario,"force-sync-count")) {
        struct rmtfs_force_sync req={.caller_id_len=2,.caller_id={7,9}},dest={0};unsigned char data[9]={2};le32(data+1,7);le32(data+5,9);
        begin(QMI_INDICATION,6);tlv(1,data,sizeof(data));round_trip(QMI_INDICATION,6,&req,&dest,rmtfs_force_sync_ei);
        CHECK(dest.caller_id_len==2 && dest.caller_id[0]==7 && dest.caller_id[1]==9);
    } else if(!strcmp(scenario,"response-256")) {
        struct qmicstrings_transfer_resp req={0},dest={0};memset(req.reply_text,'r',256);
        begin(QMI_RESPONSE,1);tlv(1,req.reply_text,256);round_trip(QMI_RESPONSE,1,&req,&dest,qmicstrings_transfer_resp_ei);CHECK(strlen(dest.reply_text)==256);
    } else {
        struct qmicstrings_transfer_req req={0},dest={0};unsigned title_n=1,nested_n=1;
        if(!strncmp(scenario,"title-",6)) title_n=atoi(scenario+6);
        else if(!strncmp(scenario,"nested-",7)) nested_n=atoi(scenario+7);
        else CHECK(!strcmp(scenario,"alias-present") || !strcmp(scenario,"alias-absent"));
        CHECK(title_n<=256 && nested_n<=255);memset(req.title,'t',title_n);memset(req.item.label,'n',nested_n);req.item.marker=0x12345678;
        req.alias_valid=!strcmp(scenario,"alias-present");strcpy(req.alias,"alias");req.items_len=2;
        strcpy(req.items[0].label,"first");req.items[0].marker=1;req.items[1].marker=2;
        begin(QMI_REQUEST,1);tlv(1,req.title,title_n);if(req.alias_valid) tlv(16,req.alias,strlen(req.alias));
        unsigned char data[1024];size_t n=leaf_bytes(data,&req.item);tlv(2,data,n);data[0]=2;n=1;
        for(unsigned i=0;i<2;i++) n+=leaf_bytes(data+n,&req.items[i]);tlv(3,data,n);
        round_trip(QMI_REQUEST,1,&req,&dest,qmicstrings_transfer_req_ei);
        CHECK(!strcmp(dest.title,req.title) && !strcmp(dest.item.label,req.item.label) && dest.item.marker==req.item.marker);
        CHECK(dest.alias_valid==req.alias_valid);if(dest.alias_valid) CHECK(!strcmp(dest.alias,req.alias));
        CHECK(dest.items_len==2 && !strcmp(dest.items[0].label,"first") && dest.items[1].label[0]==0 && dest.items[1].marker==2);
    }
    printf("QMIC_STRING_CASE_PASS %s\n",scenario);return 0;
}
