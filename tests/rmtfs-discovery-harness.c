// SPDX-License-Identifier: MIT
/* Exercise corrected Linux constructors with virtual fds, udev, DT and mmap. */
#define _GNU_SOURCE
#include <sys/mman.h>
#include <sys/stat.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>

/* Bind only calls from sharedmem.c, regardless of libc symbol redirects. */
int fixture_open(const char *,int,...);
int fixture_openat(int,const char *,int,...);
int fixture_close(int);
int fixture_fstat(int,struct stat *);
DIR *fixture_fdopendir(int);
struct dirent *fixture_readdir(DIR *);
int fixture_closedir(DIR *);
ssize_t fixture_read(int,void *,size_t);
void *fixture_mmap(void *,size_t,int,int,int,off_t);
int fixture_munmap(void *,size_t);

#define open fixture_open
#define openat fixture_openat
#define close fixture_close
#define fstat fixture_fstat
#define fdopendir fixture_fdopendir
#define readdir fixture_readdir
#define closedir fixture_closedir
#define read fixture_read
#define mmap fixture_mmap
#define munmap fixture_munmap
#include "sharedmem.c"
#undef open
#undef openat
#undef close
#undef fstat
#undef fdopendir
#undef readdir
#undef closedir
#undef read
#undef mmap
#undef munmap

#define BASE UINT64_C(0x0fd80000)
#define LENGTH UINT64_C(0x180000)
enum backend { RFSA, UIO, DT };
enum fault {
    NONE, WHITESPACE, DENIED, STAT, STAT_MISSING, NON_CHAR, UDEV_CONTEXT, UDEV_DEVICE,
    NO_ADDRESS, NO_SIZE, EMPTY_ADDRESS, NEGATIVE, TRAILING, OVERFLOW, EMPTY_REGION,
    WRAP_REGION, FD_WIDTH, MAP_ERROR, MAP_ENOENT, MAP_ZERO, MAP_WIDTH,
    MIXED_CELLS, WIDE_CELLS, ROOT_MISSING, DIR_OPEN, NO_NODE, DIR_READ, NO_CELLS,
    BAD_CELLS, DUPLICATE, NODE_OPEN, NO_REG, SHORT_REG, LONG_REG, REG_ERROR,
    PARTIAL_REG, PHYS_WIDTH, DEVMEM_DENIED,
};
struct scenario { const char *name; enum backend backend; enum fault fault; int error, maps; };
static const struct scenario scenarios[] = {
    {"rfsa-ok",RFSA,NONE,0,0}, {"rfsa-whitespace",RFSA,WHITESPACE,0,0},
    {"rfsa-denied",RFSA,DENIED,EACCES,0}, {"rfsa-stat",RFSA,STAT,EIO,0},
    {"rfsa-stat-missing",RFSA,STAT_MISSING,ENODEV,0}, {"rfsa-regular-file",RFSA,NON_CHAR,ENODEV,0},
    {"rfsa-udev-context",RFSA,UDEV_CONTEXT,ENOMEM,0}, {"rfsa-udev-device",RFSA,UDEV_DEVICE,ENODEV,0},
    {"rfsa-address-missing",RFSA,NO_ADDRESS,ENODATA,0}, {"rfsa-size-missing",RFSA,NO_SIZE,ENODATA,0},
    {"rfsa-address-empty",RFSA,EMPTY_ADDRESS,EINVAL,0}, {"rfsa-negative",RFSA,NEGATIVE,EINVAL,0},
    {"rfsa-trailing",RFSA,TRAILING,EINVAL,0}, {"rfsa-overflow",RFSA,OVERFLOW,ERANGE,0},
    {"rfsa-empty-region",RFSA,EMPTY_REGION,EINVAL,0}, {"rfsa-wrap-region",RFSA,WRAP_REGION,EINVAL,0},
    {"rfsa-offset-width",RFSA,FD_WIDTH,EINVAL,0},
    {"uio-ok",UIO,NONE,0,1}, {"uio-denied",UIO,DENIED,EACCES,0}, {"uio-stat",UIO,STAT,EIO,0},
    {"uio-metadata-missing",UIO,NO_SIZE,ENODATA,0}, {"uio-map-error",UIO,MAP_ERROR,ENOMEM,1},
    {"uio-map-enoent",UIO,MAP_ENOENT,ENODEV,1}, {"uio-map-zero",UIO,MAP_ZERO,EFAULT,1},
    {"uio-mapping-width",UIO,MAP_WIDTH,SIZE_MAX==UINT32_MAX?EINVAL:ENOMEM,SIZE_MAX==UINT32_MAX?0:1},
    {"dt-ok",DT,NONE,0,1}, {"dt-mixed-cells",DT,MIXED_CELLS,0,1}, {"dt-wide-cells",DT,WIDE_CELLS,0,1},
    {"dt-root-missing",DT,ROOT_MISSING,ENOENT,0}, {"dt-fdopendir",DT,DIR_OPEN,ENOMEM,0},
    {"dt-no-node",DT,NO_NODE,ENOENT,0}, {"dt-readdir-error",DT,DIR_READ,EIO,0},
    {"dt-no-cells",DT,NO_CELLS,ENOENT,0}, {"dt-bad-cells",DT,BAD_CELLS,EINVAL,0},
    {"dt-duplicate",DT,DUPLICATE,EEXIST,0}, {"dt-node-open",DT,NODE_OPEN,EACCES,0},
    {"dt-reg-missing",DT,NO_REG,ENOENT,0}, {"dt-reg-short",DT,SHORT_REG,EINVAL,0},
    {"dt-reg-long",DT,LONG_REG,EINVAL,0}, {"dt-reg-read-error",DT,REG_ERROR,EIO,0},
    {"dt-partial-read",DT,PARTIAL_REG,0,1}, {"dt-empty-region",DT,EMPTY_REGION,EINVAL,0},
    {"dt-physical-width",DT,PHYS_WIDTH,EINVAL,0}, {"dt-devmem-denied",DT,DEVMEM_DENIED,EACCES,0},
    {"dt-map-error",DT,MAP_ERROR,ENOMEM,1}, {"dt-map-zero",DT,MAP_ZERO,EFAULT,1},
};
static const struct scenario *c;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %s:%d: %s\n",c?c->name:"setup",__LINE__,#x); exit(1); } } while (0)

enum handle_type { DEVICE, ROOT, NODE, ADDR_CELLS, SIZE_CELLS, REG, DEVMEM };
struct handle { enum handle_type type; size_t pos; bool live; };
static struct handle handles[16];
static unsigned issued, closed, rfsa, uio, dt, devmem, maps, unmaps, dir_index;
static bool dir_live, ctx_live, dev_live, map_live, interrupted;
static int dir_fd;
static char dir_cookie, map_cookie, ctx_cookie, dev_cookie;
static void *map_base;
static size_t map_len;
static struct dirent entry;

static int alloc_handle(enum handle_type type)
{
    CHECK(issued<sizeof(handles)/sizeof(handles[0]));
    handles[issued]=(struct handle){.type=type,.live=true};return 100+(int)issued++;
}
static struct handle *get_handle(int fd)
{
    CHECK(fd>=100 && (unsigned)(fd-100)<issued && handles[fd-100].live);
    return &handles[fd-100];
}
static int failure(int error) { errno=error;return -1; }
int fixture_open(const char *path,int flags,...)
{
    if(!strcmp(path,"/dev/qcom_rmtfs_mem1")) {
        CHECK(++rfsa==1 && flags==(O_RDWR|O_CLOEXEC));
        if(c->backend!=RFSA) return failure(ENOENT);
        if(c->fault==DENIED) return failure(EACCES);
        return alloc_handle(DEVICE);
    }
    if(!strcmp(path,"/dev/qcom_rmtfs_uio1")) {
        CHECK(++uio==1 && c->backend!=RFSA && flags==(O_RDWR|O_CLOEXEC));
        if(c->backend!=UIO) return failure(ENOENT);
        if(c->fault==DENIED) return failure(EACCES);
        return alloc_handle(DEVICE);
    }
    if(!strcmp(path,"/proc/device-tree/reserved-memory/")) {
        CHECK(++dt==1 && c->backend==DT && flags==(O_RDONLY|O_DIRECTORY|O_CLOEXEC));
        if(c->fault==ROOT_MISSING) return failure(ENOENT);
        return alloc_handle(ROOT);
    }
    if(!strcmp(path,"/dev/mem")) {
        CHECK(++devmem==1 && c->backend==DT && !dir_live && issued==closed);
        CHECK(flags==(O_RDWR|O_SYNC|O_CLOEXEC));
        CHECK(c->maps || c->fault==DEVMEM_DENIED);
        if(c->fault==DEVMEM_DENIED) return failure(EACCES);
        return alloc_handle(DEVMEM);
    }
    CHECK(0);return -1;
}
int fixture_close(int fd)
{
    struct handle *h=get_handle(fd);
    CHECK(!(dir_live && fd==dir_fd));
    CHECK(!map_live || (h->type!=DEVICE && h->type!=DEVMEM));
    h->live=false;closed++;errno=EBUSY;return 0;
}
int fixture_fstat(int fd,struct stat *st)
{
    CHECK(get_handle(fd)->type==DEVICE);
    if(c->fault==STAT) return failure(EIO);
    if(c->fault==STAT_MISSING) return failure(ENOENT);
    *st=(struct stat){.st_mode=c->fault==NON_CHAR?S_IFREG:S_IFCHR,.st_rdev=0xf001};return 0;
}
DIR *fixture_fdopendir(int fd)
{
    CHECK(get_handle(fd)->type==ROOT && !dir_live);
    if(c->fault==DIR_OPEN) { errno=ENOMEM;return NULL; }
    dir_fd=fd;dir_live=true;return (void *)&dir_cookie;
}
struct dirent *fixture_readdir(DIR *dir)
{
    const char *name=NULL;
    CHECK(dir_live && dir==(void *)&dir_cookie);
    switch(dir_index++) {
    case 0:name=".";break;
    case 1:name="unrelated@0";break;
    case 2:
        if(c->fault==DIR_READ) errno=EIO;
        else if(c->fault!=NO_NODE) name="rmtfs@fd80000";
        break;
    case 3:if(c->fault==DUPLICATE) name="rmtfs@20000000";break;
    default:CHECK(0);
    }
    if(!name) return NULL;
    strcpy(entry.d_name,name);return &entry;
}
int fixture_closedir(DIR *dir)
{
    CHECK(dir_live && dir==(void *)&dir_cookie);
    dir_live=false;return fixture_close(dir_fd);
}
int fixture_openat(int fd,const char *name,int flags,...)
{
    struct handle *h=get_handle(fd);
    CHECK(dir_live);
    if(h->type==ROOT) {
        if(!strcmp(name,"rmtfs@fd80000")) {
            CHECK(flags==(O_RDONLY|O_DIRECTORY|O_CLOEXEC));
            if(c->fault==NODE_OPEN) return failure(EACCES);
            return alloc_handle(NODE);
        }
        CHECK(flags==(O_RDONLY|O_CLOEXEC));
        if(!strcmp(name,"#address-cells")) {
            if(c->fault==NO_CELLS) return failure(ENOENT);
            return alloc_handle(ADDR_CELLS);
        }
        CHECK(!strcmp(name,"#size-cells"));return alloc_handle(SIZE_CELLS);
    }
    CHECK(h->type==NODE && flags==(O_RDONLY|O_CLOEXEC) && !strcmp(name,"reg"));
    if(c->fault==NO_REG) return failure(ENOENT);
    return alloc_handle(REG);
}
static unsigned address_cells(void)
{ return c->fault==MIXED_CELLS || c->fault==WIDE_CELLS || c->fault==PHYS_WIDTH ? 2 : 1; }
static unsigned size_cells(void) { return c->fault==WIDE_CELLS?2:1; }
static uint64_t region_address(void)
{
    if(c->fault==PHYS_WIDTH) return (uint64_t)INT64_MAX-LENGTH+1;
    return address_cells()==2 ? BASE+(UINT64_C(1)<<32) : BASE;
}
ssize_t fixture_read(int fd,void *buf,size_t n)
{
    struct handle *h=get_handle(fd);
    uint32_t words[6]={0};size_t total=4,pos=0;
    uint64_t addr=region_address(),size=c->fault==EMPTY_REGION?0:LENGTH;
    if(h->type==ADDR_CELLS) words[0]=htobe32(c->fault==BAD_CELLS?3:address_cells());
    else if(h->type==SIZE_CELLS) words[0]=htobe32(size_cells());
    else {
        CHECK(h->type==REG);
        if(c->fault==REG_ERROR) return failure(EIO);
        if(address_cells()==2) words[pos++]=htobe32(addr>>32);
        words[pos++]=htobe32(addr);
        if(size_cells()==2) words[pos++]=htobe32(size>>32);
        words[pos++]=htobe32(size);total=pos*4;
        if(c->fault==SHORT_REG) total--;
        if(c->fault==LONG_REG) total+=4;
        if(c->fault==PARTIAL_REG) {
            if(!interrupted) { interrupted=true;return failure(EINTR); }
            if(n>3) n=3;
        }
    }
    CHECK(h->pos<=total);
    if(n>total-h->pos) n=total-h->pos;
    memcpy(buf,(char *)words+h->pos,n);h->pos+=n;return n;
}
void *fixture_mmap(void *addr,size_t len,int prot,int flags,int fd,off_t offset)
{
    CHECK(++maps==1 && c->maps==1 && !addr && !map_live);
    CHECK(prot==(PROT_READ|PROT_WRITE) && flags==MAP_SHARED);
    CHECK(get_handle(fd)->type==(c->backend==DT?DEVMEM:DEVICE));
    CHECK(offset==(off_t)(c->backend==DT?region_address():0));
    CHECK((uint64_t)len==(c->fault==MAP_WIDTH?(UINT64_C(1)<<32):LENGTH));
    if(c->fault==MAP_ERROR || c->fault==MAP_WIDTH || c->fault==MAP_ENOENT) {
        errno=c->fault==MAP_ENOENT?ENOENT:ENOMEM;return MAP_FAILED;
    }
    map_live=true;map_len=len;map_base=c->fault==MAP_ZERO?NULL:&map_cookie;
    return map_base;
}
int fixture_munmap(void *addr,size_t len)
{
    CHECK(map_live && addr==map_base && len==map_len);
    map_live=false;unmaps++;errno=EBUSY;return 0;
}
struct udev *udev_new(void)
{
    CHECK(!ctx_live && c->backend!=DT);
    if(c->fault==UDEV_CONTEXT) { errno=0;return NULL; }
    ctx_live=true;return (void *)&ctx_cookie;
}
struct udev_device *udev_device_new_from_devnum(struct udev *u,char type,dev_t number)
{
    CHECK(ctx_live && !dev_live && u==(void *)&ctx_cookie && type=='c' && number==0xf001);
    if(c->fault==UDEV_DEVICE) { errno=ENOENT;return NULL; }
    dev_live=true;return (void *)&dev_cookie;
}
const char *udev_device_get_sysattr_value(struct udev_device *dev,const char *name)
{
    CHECK(dev_live && dev==(void *)&dev_cookie);
    if(!strcmp(name,c->backend==UIO?"maps/map0/addr":"phys_addr")) {
        switch(c->fault) {
        case WHITESPACE:return "  0x0fd80000\n";
        case NO_ADDRESS:errno=ENOENT;return NULL;
        case EMPTY_ADDRESS:return " \n";
        case NEGATIVE:return "-1";
        case TRAILING:return "0xfd80000 junk";
        case OVERFLOW:return "0x10000000000000000";
        case WRAP_REGION:return "0xffffffffffffffff";
        case FD_WIDTH:return "0";
        default:return "0xfd80000";
        }
    }
    CHECK(!strcmp(name,c->backend==UIO?"maps/map0/size":"size"));
    if(c->fault==NO_SIZE) { errno=ENOENT;return NULL; }
    if(c->fault==EMPTY_REGION) return "0";
    if(c->fault==FD_WIDTH) return "0x8000000000000000";
    if(c->fault==MAP_WIDTH) return "0x100000000";
    return "0x180000";
}
struct udev_device *udev_device_unref(struct udev_device *dev)
{
    CHECK(dev_live && dev==(void *)&dev_cookie);
    dev_live=false;errno=EBUSY;return NULL;
}
struct udev *udev_unref(struct udev *ctx)
{
    CHECK(ctx_live && !dev_live && ctx==(void *)&ctx_cookie);
    ctx_live=false;errno=EBUSY;return NULL;
}
int main(int argc,char **argv)
{
    CHECK(argc==2);
    for(size_t i=0;i<sizeof(scenarios)/sizeof(scenarios[0]);i++) {
        if(!strcmp(argv[1],"--list")) puts(scenarios[i].name);
        else if(!strcmp(argv[1],scenarios[i].name)) c=&scenarios[i];
    }
    if(!strcmp(argv[1],"--list")) return 0;
    CHECK(c);struct rmtfs_mem *m=rmtfs_mem_open();int error=errno;
    if(c->error) CHECK(!m && error==c->error);
    else {
        CHECK(m && m->size==LENGTH && m->address==region_address());
        CHECK(get_handle(m->fd)->type==(c->backend==DT?DEVMEM:DEVICE));
        CHECK(m->base==(c->backend==RFSA?NULL:&map_cookie));
        CHECK(rmtfs_mem_alloc(m,LENGTH)==(int64_t)region_address());
        CHECK(!dir_live && !ctx_live && !dev_live && issued==closed+1);
        rmtfs_mem_close(m);
    }
    rmtfs_mem_close(NULL);
    CHECK(rfsa==1 && uio==(c->backend!=RFSA) && dt==(c->backend==DT));
    CHECK(devmem==(c->backend==DT && (c->maps || c->fault==DEVMEM_DENIED)));
    CHECK(maps==(unsigned)c->maps && unmaps==(maps && (!c->error || c->fault==MAP_ZERO)));
    CHECK(!dir_live && !ctx_live && !dev_live && !map_live && issued==closed);
    CHECK(interrupted==(c->fault==PARTIAL_REG));
    printf("DISCOVERY_CASE_PASS %s fds=%u maps=%u unmaps=%u errno=%d\n",c->name,issued,maps,unmaps,c->error);
    return 0;
}
