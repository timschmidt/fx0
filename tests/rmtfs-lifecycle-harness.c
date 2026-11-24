// SPDX-License-Identifier: MIT
/* Exercise the real daemon entry point, poll loop and remoteproc worker. */
#define _GNU_SOURCE
#include <dirent.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

int fixture_open(const char *, int, ...);
int fixture_close(int);
int fixture_pipe2(int [2], int);
DIR *fixture_fdopendir(int);
ssize_t fixture_pwrite(int, const void *, size_t, off_t);
int fixture_create(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
#define open fixture_open
#define close fixture_close
#define pipe2 fixture_pipe2
#define fdopendir fixture_fdopendir
#define pwrite fixture_pwrite
#define pthread_create fixture_create
#include "rproc.c"
#undef pthread_create
#undef pwrite
#undef fdopendir
#undef pipe2
#undef close
#undef open

ssize_t fixture_recvfrom(int, void *, size_t, int, struct sockaddr *, socklen_t *);
#define recvfrom fixture_recvfrom
#define main rmtfs_daemon_main
#include "rmtfs.c"
#undef main
#undef recvfrom

static const char *scenario, *root;
#define CHECK(cond) do { if (!(cond)) { fprintf(stderr, "%s:%d: %s\n", scenario, __LINE__, #cond); exit(1); } } while (0)
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t event = PTHREAD_COND_INITIALIZER;
static unsigned opens, publishes, socket_closes, replies, starts, stops;
static unsigned state_searches, streams, pipe_calls, worker_creations;
static unsigned mem_opens, mem_closes, storage_inits, storage_exits;
static int server = -1, peer = -1;
static bool start_finished;

static bool is_case(const char *name) { return !strcmp(scenario, name); }

int fixture_open(const char *name, int flags, ...)
{
    char path[4096];
    const char *subdir;
    if (!strcmp(name, RPROC_CLASS_PATH))
        subdir = "class";
    else {
        CHECK(!strcmp(name, RPROC_BASE_PATH));
        subdir = "driver";
    }
    CHECK(flags == (O_RDONLY | O_DIRECTORY | O_CLOEXEC));
    state_searches++;
    int n = snprintf(path, sizeof(path), "%s/%s", root, subdir);
    CHECK(n > 0 && (size_t)n < sizeof(path));
    return open(path, flags);
}

int fixture_close(int fd)
{
    CHECK(close(fd) == 0);
    return 0;
}

DIR *fixture_fdopendir(int fd)
{
    streams++;
    if (is_case("nested-directory-failure") && streams == 3) {
        errno = ENOMEM;
        return NULL;
    }
    return fdopendir(fd);
}

int fixture_pipe2(int fds[2], int flags)
{
    CHECK(++pipe_calls == 1 && flags == O_CLOEXEC);
    if (is_case("pipe-failure")) {
        errno = EMFILE;
        return -1;
    }
    return pipe2(fds, flags);
}

int fixture_create(pthread_t *thread, const pthread_attr_t *attr,
                   void *(*fn)(void *), void *arg)
{
    CHECK(++worker_creations == 1);
    if (is_case("worker-failure"))
        return EAGAIN;
    return pthread_create(thread, attr, fn, arg);
}

static void request_and_wait(void)
{
    unsigned next = replies + 1;
    CHECK(peer >= 0 && write(peer, "A", 1) == 1);
    while (replies < next)
        CHECK(pthread_cond_wait(&event, &lock) == 0);
}

ssize_t fixture_pwrite(int fd, const void *data, size_t len, off_t offset)
{
    char path[64], target[4096];
    sigset_t mask;
    bool start = len == 5 && !memcmp(data, "start", 5);
    CHECK(start || (len == 4 && !memcmp(data, "stop", 4)));
    CHECK(offset == 0 && fd == state_fd);
    snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
    ssize_t n = readlink(path, target, sizeof(target) - 1);
    CHECK(n > 0);
    target[n] = 0;
    CHECK(!strncmp(target, root, strlen(root)) && !strcmp(target + n - 6, "/state"));
    CHECK(pthread_sigmask(SIG_SETMASK, NULL, &mask) == 0);
    CHECK(sigismember(&mask, SIGTERM) == 1 && sigismember(&mask, SIGINT) == 1);

    CHECK(pthread_mutex_lock(&lock) == 0);
    CHECK(publishes >= 1);
    if (start) {
        CHECK(++starts == 1 && stops == 0);
        if (is_case("reconnect") || is_case("reconnect-failure")) {
            CHECK(write(peer, "R", 1) == 1);
            while (publishes < 2)
                CHECK(pthread_cond_wait(&event, &lock) == 0);
        }
        if (is_case("start-error")) {
            CHECK(pthread_mutex_unlock(&lock) == 0);
            errno = EIO;
            return -1;
        }
        if (is_case("start-short")) {
            CHECK(pthread_mutex_unlock(&lock) == 0);
            return 4;
        }
        CHECK(kill(getpid(), SIGTERM) == 0);
        if (!is_case("reconnect-failure"))
            request_and_wait();
        start_finished = true;
    } else {
        CHECK(++stops == 1 && start_finished);
        CHECK(kill(getpid(), SIGINT) == 0);
        if (!is_case("reconnect-failure"))
            request_and_wait();
    }
    CHECK(pthread_mutex_unlock(&lock) == 0);
    if (!start && is_case("stop-error")) {
        errno = EIO;
        return -1;
    }
    if (!start && is_case("stop-short"))
        return 3;
    return len;
}

int __wrap_qrtr_open(int port)
{
    int sockets[2];
    CHECK(port == RMTFS_QMI_SERVICE && server < 0 && peer < 0);
    opens++;
    if (is_case("qrtr-open-failure"))
        return -1;
    CHECK(socketpair(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0, sockets) == 0);
    server = sockets[0];
    peer = sockets[1];
    return server;
}

int __wrap_qrtr_publish(int fd, uint32_t service, uint16_t version, uint16_t instance)
{
    CHECK(fd == server && service == 14 && version == 1 && instance == 0);
    CHECK(pthread_mutex_lock(&lock) == 0);
    publishes++;
    CHECK(pthread_cond_signal(&event) == 0);
    if (is_case("passive"))
        CHECK(write(peer, "A", 1) == 1);
    if (is_case("pending-shutdown"))
        CHECK(kill(getpid(), SIGTERM) == 0);
    int ret = is_case("publish-failure") || (is_case("reconnect-failure") && publishes == 2) ? -1 : 0;
    CHECK(pthread_mutex_unlock(&lock) == 0);
    return ret;
}

void __wrap_qrtr_close(int fd)
{
    CHECK(pthread_mutex_lock(&lock) == 0);
    CHECK(fd == server && server >= 0 && peer >= 0);
    CHECK(close(server) == 0 && close(peer) == 0);
    server = peer = -1;
    socket_closes++;
    CHECK(pthread_mutex_unlock(&lock) == 0);
}

ssize_t fixture_recvfrom(int fd, void *buf, size_t size, int flags,
                         struct sockaddr *addr, socklen_t *addrlen)
{
    char command;
    struct sockaddr_qrtr sq = { .sq_family = AF_QIPCRTR, .sq_node = 7, .sq_port = 4000 };
    CHECK(fd == server && flags == 0 && *addrlen >= sizeof(sq));
    CHECK(recv(fd, &command, 1, MSG_DONTWAIT) == 1);
    if (command == 'R') {
        errno = ENETRESET;
        return -1;
    }
    CHECK(command == 'A');
    struct rmtfs_alloc_buf_req req = { .caller_id = 3, .buff_size = 512 };
    struct qrtr_packet pkt = { .data = buf, .data_len = size };
    CHECK(qmi_encode_message(&pkt, QMI_REQUEST, QMI_RMTFS_ALLOC_BUFF, 9,
                             &req, rmtfs_alloc_buf_req_ei) > 0);
    memcpy(addr, &sq, sizeof(sq));
    *addrlen = sizeof(sq);
    return pkt.data_len;
}

int __wrap_qrtr_sendto(int fd, uint32_t node, uint32_t port, const void *data, unsigned len)
{
    struct rmtfs_alloc_buf_resp response = { 0 };
    struct qrtr_packet pkt = { .data = (void *)data, .data_len = len };
    unsigned txn = 0;
    CHECK(fd == server && node == 7 && port == 4000);
    CHECK(qmi_decode_message(&response, &txn, &pkt, QMI_RESPONSE,
          QMI_RMTFS_ALLOC_BUFF, rmtfs_alloc_buf_resp_ei) >= 0);
    CHECK(txn == 9 && !response.result.result && response.buff_address_valid);
    CHECK(response.buff_address == 0xfd80000);
    CHECK(pthread_mutex_lock(&lock) == 0);
    replies++;
    CHECK(pthread_cond_signal(&event) == 0);
    CHECK(pthread_mutex_unlock(&lock) == 0);
    if (is_case("passive"))
        CHECK(kill(getpid(), SIGTERM) == 0);
    return 0;
}

struct rmtfs_mem { int fixture; };
static struct rmtfs_mem memory;
struct rmtfs_mem *rmtfs_mem_open(void)
{
    mem_opens++;
    if (is_case("memory-failure")) {
        errno = ENODEV;
        return NULL;
    }
    return &memory;
}
void rmtfs_mem_close(struct rmtfs_mem *m) { CHECK(m == &memory); mem_closes++; }
int64_t rmtfs_mem_alloc(struct rmtfs_mem *m, size_t len)
{ CHECK(m == &memory && len == 512); return 0xfd80000; }
void rmtfs_mem_free(struct rmtfs_mem *m) { (void)m; CHECK(0); }
int rmtfs_mem_validate_span(const struct rmtfs_mem *m, uint64_t addr, uint64_t len)
{ (void)m; (void)addr; (void)len; CHECK(0); return -EINVAL; }
ssize_t rmtfs_mem_read(struct rmtfs_mem *m, uint64_t addr, void *buf, ssize_t len)
{ (void)m; (void)addr; (void)buf; (void)len; CHECK(0); return -EINVAL; }
ssize_t rmtfs_mem_write(struct rmtfs_mem *m, uint64_t addr, const void *buf, ssize_t len)
{ (void)m; (void)addr; (void)buf; (void)len; CHECK(0); return -EINVAL; }

int storage_init(const char *path, bool ro, bool partitions)
{
    CHECK(!path && ro && partitions);
    storage_inits++;
    return is_case("storage-failure") ? -EIO : 0;
}
void storage_exit(void) { storage_exits++; }
struct rmtfd *storage_get(unsigned node, int caller)
{ (void)node; (void)caller; return NULL; }
struct rmtfd *storage_open(unsigned node, const char *path, const char *suffix)
{ (void)node; (void)path; (void)suffix; CHECK(0); return NULL; }
void storage_close(struct rmtfd *fd) { (void)fd; CHECK(0); }
int storage_get_caller_id(const struct rmtfd *fd) { (void)fd; CHECK(0); return -1; }
int storage_get_error(const struct rmtfd *fd) { (void)fd; CHECK(0); return -1; }
ssize_t storage_pread(const struct rmtfd *fd, void *buf, size_t n, off_t off)
{ (void)fd; (void)buf; (void)n; (void)off; CHECK(0); return -1; }
ssize_t storage_pwrite(struct rmtfd *fd, const void *buf, size_t n, off_t off)
{ (void)fd; (void)buf; (void)n; (void)off; CHECK(0); return -1; }
int storage_sync(struct rmtfd *fd) { (void)fd; CHECK(0); return -1; }

static unsigned fd_count(void)
{
    unsigned count = 0;
    DIR *dir = opendir("/proc/self/fd");
    CHECK(dir);
    while (readdir(dir))
        count++;
    CHECK(closedir(dir) == 0);
    return count;
}

struct expectation {
    const char *name;
    unsigned exit_code, search, open, publish, close, start, stop, reply;
};
static const struct expectation cases[] = {
    {"passive",                   0,0,1,1,1,0,0,1},
    {"invalid-cli",               1,0,0,0,0,0,0,0},
    {"memory-failure",            1,0,0,0,0,0,0,0},
    {"storage-failure",           1,0,0,0,0,0,0,0},
    {"state-missing",             1,2,0,0,0,0,0,0},
    {"nested-directory-failure",  1,2,0,0,0,0,0,0},
    {"pipe-failure",              1,1,0,0,0,0,0,0},
    {"worker-failure",            1,1,0,0,0,0,0,0},
    {"qrtr-open-failure",         1,1,1,0,0,0,0,0},
    {"publish-failure",           1,1,1,1,1,0,0,0},
    {"pending-shutdown",          0,1,1,1,1,0,0,0},
    {"start-error",               1,1,1,1,1,1,0,0},
    {"start-short",               1,1,1,1,1,1,0,0},
    {"managed-shutdown",          0,1,1,1,1,1,1,2},
    {"driver-fallback",            0,2,1,1,1,1,1,2},
    {"reconnect",                 0,1,2,2,2,1,1,2},
    {"reconnect-failure",         1,1,2,2,2,1,1,0},
    {"stop-error",                1,1,1,1,1,1,1,2},
    {"stop-short",                1,1,1,1,1,1,1,2},
};

int main(int argc, char **argv)
{
    if (argc != 3)
        return 2;
    scenario = argv[1];
    root = argv[2];
    const struct expectation *expected = NULL;
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        if (!strcmp(cases[i].name, scenario))
            expected = &cases[i];
    }
    CHECK(expected);
    char *args[] = { "rmtfs", "-r", "-P", "-s", "-h", NULL };
    int nargs = is_case("passive") ? 3 : is_case("invalid-cli") ? 5 : 4;
    args[nargs] = NULL;
    unsigned before = fd_count();
    int rc = rmtfs_daemon_main(nargs, args);
    CHECK(rc == (int)expected->exit_code && fd_count() == before);
    CHECK(state_fd == -1 && server == -1 && peer == -1);
    CHECK(state_searches == expected->search && opens == expected->open);
    CHECK(publishes == expected->publish && socket_closes == expected->close);
    CHECK(starts == expected->start && stops == expected->stop && replies == expected->reply);
    CHECK(mem_opens == !is_case("invalid-cli"));
    CHECK(mem_closes == (mem_opens && !is_case("memory-failure")));
    CHECK(storage_inits == mem_closes);
    CHECK(storage_exits == (storage_inits && !is_case("storage-failure")));
    printf("LIFECYCLE_CASE_PASS %s starts=%u stops=%u replies=%u\n", scenario, starts, stops, replies);
    return 0;
}
