// SPDX-License-Identifier: MIT
/* Patched implementation only; all backing and transport are synthetic. */
#define _GNU_SOURCE
#define main unused_rmtfs_daemon_main
#include "rmtfs.c"
#undef main
#include "sharedmem.c"

static const char *scenario;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %s:%d: %s\n",scenario,__LINE__,#x); exit(1); } } while (0)
#define BASE UINT64_C(0x10000000)
#define LENGTH 2048
static unsigned char backing[LENGTH+2], disk[LENGTH], response[256];
static unsigned fd_reads, fd_writes, disk_reads, disk_writes, syncs, sends;
static size_t response_len;
static struct rmtfd *const synthetic_fd = (void *)&disk;
_Static_assert(sizeof(off_t) >= 8, "test requires 64-bit file offsets");

ssize_t __wrap_pread(int fd, void *buf, size_t len, off_t off)
{
    CHECK(fd==42 && off>=0 && (uint64_t)off<=LENGTH && len<=LENGTH-(uint64_t)off);
    fd_reads++; memcpy(buf,backing+1+(size_t)off,len); return len;
}
ssize_t __wrap_pwrite(int fd, const void *buf, size_t len, off_t off)
{
    CHECK(fd==42 && off>=0 && (uint64_t)off<=LENGTH && len<=LENGTH-(uint64_t)off);
    fd_writes++; memcpy(backing+1+(size_t)off,buf,len); return len;
}
int __wrap_open(const char *p,int flags,...)
{ (void)p; (void)flags; CHECK(0); return -1; }
void *__wrap_mmap(void *p,size_t n,int prot,int flags,int fd,off_t off)
{ (void)p;(void)n;(void)prot;(void)flags;(void)fd;(void)off;CHECK(0);return MAP_FAILED; }
int __wrap_socket(int d,int t,int p)
{ (void)d;(void)t;(void)p;CHECK(0);return -1; }
struct rmtfd *storage_get(unsigned node,int caller)
{ CHECK(node==7 && caller==3); return synthetic_fd; }
ssize_t storage_pread(const struct rmtfd *fd,void *buf,size_t n,off_t off)
{
    CHECK(fd==synthetic_fd && off>=0 && (uint64_t)off<=LENGTH && n<=LENGTH-(uint64_t)off);
    disk_reads++;memcpy(buf,disk+(size_t)off,n);return n;
}
ssize_t storage_pwrite(struct rmtfd *fd,const void *buf,size_t n,off_t off)
{
    CHECK(fd==synthetic_fd && off>=0 && (uint64_t)off<=LENGTH && n<=LENGTH-(uint64_t)off);
    disk_writes++;memcpy(disk+(size_t)off,buf,n);return n;
}
int storage_sync(struct rmtfd *fd) { CHECK(fd==synthetic_fd);syncs++;return 0; }
int __wrap_qrtr_sendto(int sock,uint32_t node,uint32_t port,const void *data,unsigned len)
{
    CHECK(sock==123 && node==7 && port==4000 && len<=sizeof(response));
    memcpy(response,data,len);response_len=len;sends++;return len;
}
static void io_case(struct rmtfs_mem *m)
{
    struct rmtfs_iovec_req req={.caller_id=3,.iovec_len=2,.is_force_sync=1};
    struct rmtfs_iovec_resp resp={0};
    unsigned char wire[512];
    struct qrtr_packet pkt={.node=7,.port=4000,.data=wire,.data_len=sizeof(wire)};
    unsigned txn=0;
    int write=strstr(scenario,"write")!=NULL, reject=strstr(scenario,"reject")!=NULL;
    req.direction=write;
    req.iovec[0]=(struct rmtfs_iovec_entry){0,BASE,1};
    req.iovec[1]=(struct rmtfs_iovec_entry){1,BASE+LENGTH-512,1};
    if(reject) req.iovec[1].phys_offset++;
    if(strstr(scenario,"zero")) req.iovec[0].num_sector=req.iovec[1].num_sector=0;
    if(strstr(scenario,"empty")) req.iovec_len=0;
    CHECK(qmi_encode_message(&pkt,QMI_REQUEST,QMI_RMTFS_RW_IOVEC,0x1234,&req,rmtfs_iovec_req_ei)>0);
    rmem=m;rmtfs_iovec(123,&pkt);
    pkt.data=response;pkt.data_len=response_len;
    CHECK(sends==1 && qmi_decode_message(&resp,&txn,&pkt,QMI_RESPONSE,QMI_RMTFS_RW_IOVEC,rmtfs_iovec_resp_ei)>=0);
    CHECK(txn==0x1234 && resp.result.result==(reject?1:0) && resp.result.error==(reject?1:0));
    if(reject || strstr(scenario,"zero") || strstr(scenario,"empty")) {
        CHECK(!fd_reads && !fd_writes && !disk_reads && !disk_writes);
        CHECK(syncs==(!reject && write));
        for(size_t i=0;i<LENGTH;i++) CHECK(backing[1+i]==0x5a && disk[i]==0x21);
    } else if(write) {
        CHECK(disk_writes==2 && !disk_reads && syncs==1);
        for(size_t i=0;i<LENGTH;i++) CHECK(disk[i]==(i<1024?0x5a:0x21));
        CHECK(backing[1]==0x5a && backing[LENGTH]==0x5a);
    } else {
        CHECK(disk_reads==2 && !disk_writes && !syncs);
        for(size_t i=0;i<LENGTH;i++) CHECK(backing[i+1]==(i<512 || i>=LENGTH-512?0x21:0x5a));
    }
}
int main(int argc,char **argv)
{
    CHECK(argc==2);scenario=argv[1];
    struct rmtfs_mem m={.address=BASE,.size=LENGTH,.base=backing+1,.fd=-1};
    unsigned char data[512],readback[512];memset(data,0x36,sizeof(data));
    memset(backing,0x5a,sizeof(backing));memset(disk,0x21,sizeof(disk));
    if(strstr(scenario,"fd")) {m.base=NULL;m.fd=42;}
    if(!strncmp(scenario,"io-",3)) io_case(&m);
    else if(strstr(scenario,"roundtrip")) {
        if(strstr(scenario,"wide")) m.address=UINT64_C(0x100001000);
        for(unsigned i=0;i<2;i++) {
            uint64_t addr=m.address+(i?LENGTH-512:0);
            CHECK(rmtfs_mem_write(&m,addr,data,512)==512);
            CHECK(rmtfs_mem_read(&m,addr,readback,512)==512 && !memcmp(data,readback,512));
        }
        CHECK(fd_reads==(m.base?0:2) && fd_writes==(m.base?0:2));
    } else if(strstr(scenario,"zero")) {
        CHECK(!rmtfs_mem_read(&m,BASE+LENGTH,NULL,0));
        CHECK(!rmtfs_mem_write(&m,BASE+LENGTH,NULL,0));
        CHECK(!fd_reads && !fd_writes);
    } else if(!strcmp(scenario,"allocation")) {
        CHECK(rmtfs_mem_alloc(&m,0)==BASE && rmtfs_mem_alloc(&m,LENGTH)==BASE);
        CHECK(rmtfs_mem_alloc(&m,LENGTH+1)==-EINVAL);
        m.address=UINT64_C(0x8000000000000000);CHECK(rmtfs_mem_alloc(&m,1)==-EINVAL);
    } else {
        uint64_t addr=BASE;ssize_t len=512;void *buf=data;
        if(strstr(scenario,"below")) addr--;
        else if(strstr(scenario,"cross-end")) addr+=LENGTH-511;
        else if(strstr(scenario,"past-end")) {addr+=LENGTH+1;len=0;}
        else if(strstr(scenario,"negative")) len=-1;
        else if(strstr(scenario,"null-buffer")) buf=NULL;
        else if(!strcmp(scenario,"empty-region")) m.size=0;
        else if(!strcmp(scenario,"wrapped-region")) m.address=UINT64_MAX-16;
        else if(!strcmp(scenario,"invalid-fd")) {m.base=NULL;m.fd=-1;}
        else if(!strcmp(scenario,"fd-offset-limit")) {
            m.base=NULL;m.fd=42;m.address=0;m.size=UINT64_MAX;addr=INT64_MAX;
        } else if(!strcmp(scenario,"mapped-size-limit")) {
            m.size=(uint64_t)SIZE_MAX;
            if(SIZE_MAX==UINT32_MAX) {m.size++;CHECK(rmtfs_mem_validate_span(&m,BASE,1)==-EINVAL);}
            else {m.address=0;CHECK(rmtfs_mem_validate_span(&m,0,1)==0);}
            puts("MEMORY_CASE_PASS mapped-size-limit");return 0;
        } else if(!strcmp(scenario,"null-region")) {
            CHECK(rmtfs_mem_validate_span(NULL,BASE,512)==-EINVAL);
            CHECK(rmtfs_mem_read(NULL,BASE,data,512)==-EINVAL);
            CHECK(rmtfs_mem_write(NULL,BASE,data,512)==-EINVAL);
            puts("MEMORY_CASE_PASS null-region");return 0;
        } else CHECK(0);
        CHECK(rmtfs_mem_read(&m,addr,buf,len)==-EINVAL);
        CHECK(rmtfs_mem_write(&m,addr,buf,len)==-EINVAL);
        CHECK(!fd_reads && !fd_writes && !memcmp(data,(unsigned char[512]){[0 ... 511]=0x36},512));
        for(size_t i=0;i<sizeof(backing);i++) CHECK(backing[i]==0x5a);
    }
    CHECK(backing[0]==0x5a && backing[LENGTH+1]==0x5a);
    printf("MEMORY_CASE_PASS %s\n",scenario);return 0;
}
