// SPDX-License-Identifier: MIT
/* Execute actual RMTFS handlers/codec/storage; transport and memory are synthetic. */
#define _GNU_SOURCE
#define main fx0_unused_daemon_main
#include "rmtfs.c"
#undef main

static const char *scenario, *fixture;
static unsigned char request[4096], response[4096], memory[8192];
static size_t request_len, response_len;
static unsigned node = 7, sends, frees, mem_reads, mem_writes, syncs;
static unsigned allocations;
static off_t storage_offset = -1;
static int sync_error, mem_fault;
struct rmtfs_mem { int unused; };
static struct rmtfs_mem mock_memory;
#define BASE 0x10000000UL
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %s:%d: %s\n",scenario,__LINE__,#x); exit(1); } } while (0)

int __real_open(const char *, int, ...);
int __wrap_open(const char *path, int flags, ...)
{
    size_t n = strlen(fixture);
    CHECK(!strncmp(path,fixture,n) && path[n]=='/');
    CHECK(!strcmp(path+n+1,"modem_fs1") || !strcmp(path+n+1,"modem_fs2"));
    CHECK(flags == O_RDONLY);
    return __real_open(path, flags);
}
ssize_t __wrap_pwrite(int fd, const void *buf, size_t n, off_t off)
{ (void)fd; (void)buf; (void)n; (void)off; CHECK(0); return -1; }
int __wrap_fdatasync(int fd) { (void)fd; CHECK(0); return -1; }
int __wrap_socket(int domain, int type, int protocol)
{ (void)domain; (void)type; (void)protocol; CHECK(0); return -1; }
ssize_t __wrap_recvfrom(int fd, void *buf, size_t n, int flags, struct sockaddr *sa, socklen_t *len)
{
    struct sockaddr_qrtr *sq=(void *)sa;
    CHECK(fd==123 && flags==0 && n>=request_len && *len>=sizeof(*sq));
    memset(sq,0,sizeof(*sq)); sq->sq_family=AF_QIPCRTR; sq->sq_node=node; sq->sq_port=4000;
    *len=sizeof(*sq); memcpy(buf,request,request_len); return request_len;
}
int __wrap_qrtr_sendto(int fd, uint32_t dest, uint32_t port, const void *data, unsigned n)
{
    CHECK(fd==123 && dest==node && port==4000 && n<=sizeof(response));
    memcpy(response,data,n); response_len=n; sends++; return n;
}
ssize_t __real_storage_pread(const struct rmtfd *,void *,size_t,off_t);
ssize_t __real_storage_pwrite(struct rmtfd *,const void *,size_t,off_t);
int __real_storage_sync(struct rmtfd *);
ssize_t __wrap_storage_pread(const struct rmtfd *fd,void *buf,size_t n,off_t off)
{ storage_offset=off; return __real_storage_pread(fd,buf,n,off); }
ssize_t __wrap_storage_pwrite(struct rmtfd *fd,const void *buf,size_t n,off_t off)
{ storage_offset=off; return __real_storage_pwrite(fd,buf,n,off); }
int __wrap_storage_sync(struct rmtfd *fd)
{ CHECK(fd); syncs++; if(sync_error) { errno=EIO; return -1; } return __real_storage_sync(fd); }
struct rmtfs_mem *rmtfs_mem_open(void) { CHECK(0); return NULL; }
void rmtfs_mem_close(struct rmtfs_mem *m) { (void)m; CHECK(0); }
int rproc_init(void) { CHECK(0); return -1; }
int rproc_start(void) { CHECK(0); return -1; }
int rproc_stop(void) { CHECK(0); return -1; }
int64_t rmtfs_mem_alloc(struct rmtfs_mem *m,size_t size)
{ CHECK(m==&mock_memory); allocations++; if(size>sizeof(memory)) return -ENOMEM; return BASE; }
void rmtfs_mem_free(struct rmtfs_mem *m) { CHECK(m==&mock_memory); frees++; }
static ssize_t memory_transfer(struct rmtfs_mem *m,unsigned long address,void *buf,ssize_t n,int write)
{
    CHECK(m==&mock_memory && n==512);
    if(write) mem_writes++; else mem_reads++;
    if(mem_fault) return mem_fault==1 ? -EIO : 511;
    if(address<BASE || (uint64_t)address-BASE+(uint64_t)n>sizeof(memory)) return -EINVAL;
    if(write) memcpy(memory+(address-BASE),buf,n); else memcpy(buf,memory+(address-BASE),n);
    return n;
}
ssize_t rmtfs_mem_read(struct rmtfs_mem *m,unsigned long address,void *buf,ssize_t n)
{ return memory_transfer(m,address,buf,n,0); }
ssize_t rmtfs_mem_write(struct rmtfs_mem *m,unsigned long address,const void *buf,ssize_t n)
{ return memory_transfer(m,address,(void *)buf,n,1); }

static void exchange(unsigned id,void *req,struct qmi_elem_info *req_ei,void *resp,struct qmi_elem_info *resp_ei,unsigned error)
{
    struct qrtr_packet pkt={.data=request,.data_len=sizeof(request)};
    unsigned txn=0, before=sends;
    /* Pinned generated OPEN descriptor says VAR_LEN_ARRAY without DATA_LEN;
     * its encoder rejects it. Build the specified string TLV on the wire. */
    if(id==QMI_RMTFS_OPEN) {
        size_t n=strlen(((struct rmtfs_open_req *)req)->path);
        struct qmi_packet *header=(void *)request;
        header->flags=QMI_REQUEST; header->txn_id=0x1234; header->msg_id=id; header->msg_len=n+3;
        request[7]=1; request[8]=n & 255; request[9]=n >> 8;
        memcpy(request+10,((struct rmtfs_open_req *)req)->path,n); pkt.data_len=n+10;
    } else CHECK(qmi_encode_message(&pkt,QMI_REQUEST,id,0x1234,req,req_ei)>0);
    request_len=pkt.data_len;
    CHECK(handle_rmtfs(123)==0 && sends==before+1);
    pkt.data=response; pkt.data_len=response_len;
    CHECK(qmi_decode_message(resp,&txn,&pkt,QMI_RESPONSE,id,resp_ei)>=0 && txn==0x1234);
    struct rmtfs_qmi_result *result=resp;
    CHECK(result->result==(error ? QMI_RMTFS_RESULT_FAILURE : QMI_RMTFS_RESULT_SUCCESS));
    CHECK(result->error==error);
}
static unsigned open_file(const char *path)
{
    struct rmtfs_open_req req={0}; struct rmtfs_open_resp resp={0};
    CHECK(strlen(path)<sizeof(req.path)); strcpy(req.path,path);
    exchange(1,&req,rmtfs_open_req_ei,&resp,rmtfs_open_resp_ei,0);
    CHECK(resp.caller_id_valid); return resp.caller_id;
}
static void close_file(unsigned id,unsigned error)
{
    struct rmtfs_close_req req={.caller_id=id}; struct rmtfs_close_resp resp={0};
    exchange(2,&req,rmtfs_close_req_ei,&resp,rmtfs_close_resp_ei,error);
}
static void dev_error(unsigned id,unsigned error)
{
    struct rmtfs_dev_error_req req={.caller_id=id}; struct rmtfs_dev_error_resp resp={0};
    exchange(5,&req,rmtfs_dev_error_req_ei,&resp,rmtfs_dev_error_resp_ei,error);
    CHECK(resp.status_valid==!error); if(!error) CHECK(resp.status==0);
}
static void io(unsigned id,unsigned direction,uint32_t sector,uint32_t address,unsigned count,unsigned error)
{
    struct rmtfs_iovec_req req={.caller_id=id,.direction=direction,.iovec_len=1,.is_force_sync=1};
    struct rmtfs_iovec_resp resp={0};
    req.iovec[0]=(struct rmtfs_iovec_entry){sector,address,count};
    exchange(3,&req,rmtfs_iovec_req_ei,&resp,rmtfs_iovec_resp_ei,error);
}
static void malformed_dispatch(void)
{
    unsigned id=open_file("/boot/modem_fs1"),msg=2,txn=0,before=sends;
    struct qrtr_packet pkt={.data=request,.data_len=sizeof(request)};
    struct rmtfs_close_req close_req={.caller_id=id};
    struct qmi_elem_info *resp_ei=rmtfs_close_resp_ei;
    if(strstr(scenario,"iovec")) {
        struct rmtfs_iovec_req req={.caller_id=id,.direction=1,.iovec_len=1,.is_force_sync=1};
        req.iovec[0]=(struct rmtfs_iovec_entry){0,BASE,1}; msg=3; resp_ei=rmtfs_iovec_resp_ei;
        CHECK(qmi_encode_message(&pkt,QMI_REQUEST,msg,0x1234,&req,rmtfs_iovec_req_ei)>0);
        if(strstr(scenario,"missing-direction")) {
            memmove(request+14,request+18,pkt.data_len-18); pkt.data_len-=4;
        } else { CHECK(request[18]==3 && request[21]==1); request[21]=2; }
    } else if(strstr(scenario,"alloc")) {
        struct rmtfs_alloc_buf_req req={.caller_id=id,.buff_size=512}; msg=4; resp_ei=rmtfs_alloc_buf_resp_ei;
        CHECK(qmi_encode_message(&pkt,QMI_REQUEST,msg,0x1234,&req,rmtfs_alloc_buf_req_ei)>0); pkt.data_len=14;
    } else {
        CHECK(qmi_encode_message(&pkt,QMI_REQUEST,msg,0x1234,&close_req,rmtfs_close_req_ei)>0);
        if(strstr(scenario,"missing")) pkt.data_len=7;
        else if(strstr(scenario,"short-scalar")) { pkt.data_len--; request[8]=3; }
        else if(strstr(scenario,"optional-overrun")) {
            request[pkt.data_len++]=0x10; request[pkt.data_len++]=255; request[pkt.data_len++]=255;
        } else if(strstr(scenario,"short-header")) pkt.data_len=6;
        else CHECK(0);
    }
    request[5]=(pkt.data_len-7)&255; request[6]=(pkt.data_len-7)>>8;
    request_len=pkt.data_len;
    int rc=handle_rmtfs(123);
    fprintf(stderr,"DISPATCH_EFFECTS %s live=%u frees=%u allocations=%u memory_reads=%u memory_writes=%u syncs=%u\n",
            scenario,!!storage_get(node,id),frees,allocations,mem_reads,mem_writes,syncs);
    if(strstr(scenario,"short-header")) CHECK(rc<0 && sends==before);
    else {
        union { struct rmtfs_close_resp close; struct rmtfs_alloc_buf_resp alloc; } resp={0};
        pkt.data=response; pkt.data_len=response_len;
        CHECK(rc==0 && sends==before+1);
        CHECK(qmi_decode_message(&resp,&txn,&pkt,QMI_RESPONSE,msg,resp_ei)>=0);
        CHECK(txn==0x1234 && resp.close.result.result==1 && resp.close.result.error==2);
    }
    CHECK(storage_get(node,id) && !frees && !mem_reads && !mem_writes && !syncs && !allocations);
}
int main(int argc,char **argv)
{
    CHECK(argc==3); scenario=argv[1]; fixture=argv[2]; rmem=&mock_memory;
    CHECK(storage_init(fixture,true,false)==0);
    memset(memory,0x5a,sizeof(memory));
    if(!strncmp(scenario,"malformed-",10)) malformed_dispatch();
    else if(!strcmp(scenario,"allocation-global") || !strcmp(scenario,"allocation-oversize")) {
        struct rmtfs_alloc_buf_req req={.caller_id=77,.buff_size=!strcmp(scenario,"allocation-global") ? 8192 : 8193};
        struct rmtfs_alloc_buf_resp resp={0};
        dbgprintf_enabled=true;
        exchange(4,&req,rmtfs_alloc_buf_req_ei,&resp,rmtfs_alloc_buf_resp_ei,req.buff_size==8192 ? 0 : 1);
        CHECK(resp.buff_address_valid==(req.buff_size==8192));
        if(resp.buff_address_valid) CHECK(resp.buff_address==BASE);
    } else {
        unsigned id=open_file("/boot/modem_fs1"); CHECK(id==0);
        if(!strcmp(scenario,"open-reuse")) CHECK(open_file("/boot/modem_fs1")==id);
        else if(!strcmp(scenario,"wrong-message-type") || !strcmp(scenario,"unknown-request")) {
            struct rmtfs_close_req req={.caller_id=id};
            struct qrtr_packet pkt={.data=request,.data_len=sizeof(request)};
            unsigned before=sends,txn=99;
            int unknown=!strcmp(scenario,"unknown-request");
            CHECK(qmi_encode_message(&pkt,unknown ? QMI_REQUEST : QMI_RESPONSE,unknown ? 77 : 2,0x1234,&req,rmtfs_close_req_ei)>0);
            request_len=pkt.data_len; CHECK(handle_rmtfs(123)==0);
            CHECK(storage_get(node,id) && !frees && !mem_reads && !mem_writes);
            CHECK(sends==before+(unknown ? 0 : 1));
            if(!unknown) {
                struct rmtfs_close_resp resp={0}; pkt.data=response; pkt.data_len=response_len;
                CHECK(qmi_decode_message(&resp,&txn,&pkt,QMI_RESPONSE,2,rmtfs_close_resp_ei)>=0);
                CHECK(txn==0 && resp.result.result==1 && resp.result.error==2);
            }
        }
        else if(!strcmp(scenario,"close-verbose")) {
            unsigned second=open_file("/boot/modem_fs2"); CHECK(second==1);
            dbgprintf_enabled=true; close_file(second,0); CHECK(frees==1 && !storage_get(node,second));
        } else if(!strcmp(scenario,"close-invalid")) { close_file(99,1); CHECK(frees==0); }
        else if(!strcmp(scenario,"close-foreign")) { node=8; close_file(id,1); CHECK(frees==0); }
        else if(!strcmp(scenario,"error-valid")) dev_error(id,0);
        else if(!strcmp(scenario,"error-invalid")) dev_error(99,1);
        else if(!strcmp(scenario,"error-foreign")) { node=8; dev_error(id,1); }
        else if(!strcmp(scenario,"error-closed")) { close_file(id,0); dev_error(id,1); }
        else if(!strcmp(scenario,"io-invalid")) { io(99,1,0,BASE,1,1); CHECK(!mem_reads && !syncs); }
        else if(!strcmp(scenario,"io-foreign")) { node=8; io(id,0,0,BASE,1,1); CHECK(!mem_writes); }
        else if(!strcmp(scenario,"io-closed")) { close_file(id,0); io(id,1,0,BASE,1,1); CHECK(!mem_reads && !syncs); }
        else if(!strcmp(scenario,"read-multiple")) { io(id,0,0,BASE,2,0); CHECK(mem_writes==2 && memory[0]==0x21 && memory[1023]==0x21 && memory[1024]==0x5a); }
        else if(!strcmp(scenario,"write-shadow")) {
            io(id,1,2,BASE,2,0); CHECK(mem_reads==2 && syncs==1);
            memset(memory,0,sizeof(memory)); io(id,0,2,BASE,2,0); CHECK(memory[0]==0x5a && memory[1023]==0x5a);
        } else if(!strcmp(scenario,"read-far") || !strcmp(scenario,"write-far") || !strcmp(scenario,"read-max-sector")) {
            int write=!strcmp(scenario,"write-far");
            uint32_t sector=!strcmp(scenario,"read-max-sector") ? UINT32_MAX : 0x800000;
            io(id,write,sector,BASE,1,write ? 1 : 0);
            CHECK(storage_offset==(off_t)((uint64_t)sector*512));
            if(!write) CHECK(memory[0]==0 && memory[511]==0);
        } else if(!strcmp(scenario,"sync-error")) { sync_error=1; io(id,1,0,BASE,1,1); CHECK(syncs==1); }
        else if(!strcmp(scenario,"memory-invalid")) { io(id,0,0,BASE-1,1,1); CHECK(mem_writes==1); }
        else if(!strcmp(scenario,"memory-read-error")) { mem_fault=1; io(id,1,0,BASE,1,1); CHECK(storage_offset==-1); }
        else if(!strcmp(scenario,"memory-short")) { mem_fault=2; io(id,1,0,BASE,1,1); CHECK(storage_offset==-1); }
        else if(!strcmp(scenario,"zero-sectors")) { io(id,0,0,BASE,0,0); CHECK(!mem_reads && !mem_writes); }
        else CHECK(0);
    }
    storage_exit(); printf("PROTOCOL_CASE_PASS %s\n",scenario); return 0;
}
