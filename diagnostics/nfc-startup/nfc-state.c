// SPDX-License-Identifier: GPL-2.0-only
/* Fixed NFC generic-netlink get/up/down diagnostic. No poll/vendor/FW API. */
#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/genetlink.h>
#include <linux/netlink.h>
#include <linux/nfc.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define PACKET_BYTES 16384U
#define ATTR_SLOTS 64U
#define CTRL_VERSION 2U
#define EXPECTED_PROTOCOLS (NFC_PROTO_JEWEL_MASK | NFC_PROTO_MIFARE_MASK | \
        NFC_PROTO_FELICA_MASK | NFC_PROTO_ISO14443_MASK | \
        NFC_PROTO_ISO14443_B_MASK | NFC_PROTO_NFC_DEP_MASK)

_Static_assert(sizeof(struct nlmsghdr) == 16 && sizeof(struct genlmsghdr) == 4 &&
               sizeof(struct nlattr) == 4 && sizeof(struct nlmsgerr) == 20,
               "pinned netlink wire sizes");
_Static_assert(NFC_CMD_GET_DEVICE == 1 && NFC_CMD_DEV_UP == 2 && NFC_CMD_DEV_DOWN == 3 &&
               NFC_ATTR_DEVICE_INDEX == 1 && NFC_ATTR_DEVICE_NAME == 2 &&
               NFC_ATTR_PROTOCOLS == 3 && NFC_ATTR_RF_MODE == 11 &&
               NFC_ATTR_DEVICE_POWERED == 12 && NFC_RF_NONE == 2 &&
               EXPECTED_PROTOCOLS == 126, "pinned NFC UAPI contract");

struct peer {
    struct sockaddr_nl address;
    socklen_t length;
    int flags;
};
struct transport {
    void *opaque;
    uint32_t port;
    ssize_t (*send)(void *, const void *, size_t);
    ssize_t (*receive)(void *, void *, size_t, struct peer *, int64_t);
    int64_t (*now)(void *);
};
struct attribute {
    const unsigned char *data;
    size_t size;
    uint16_t flags;
    bool present;
};
struct device {
    uint32_t index, protocols;
    uint8_t powered, rf_mode;
    char name[NFC_DEVICE_NAME_MAXSIZE];
};
enum reply_kind { FAMILY_REPLY, DEVICE_REPLY, ACK_ONLY };
struct transaction {
    enum reply_kind kind;
    uint32_t sequence, port;
    uint16_t type;
    size_t request_size;
    bool ack, reply;
    const char *family_name;
    uint32_t family_version;
    uint16_t family;
    uint32_t index;
    struct device device;
};
struct session {
    struct transport io;
    uint32_t sequence, requests;
    int64_t deadline;
    bool mutation_attempted;
    const char *phase;
};

static int protocol_error(void) { errno = EPROTO; return -1; }
static size_t aligned(size_t n) { return (n + 3U) & ~(size_t)3U; }

static int attributes(const unsigned char *data, size_t size,
                      struct attribute result[ATTR_SLOTS])
{
    memset(result, 0, sizeof(*result) * ATTR_SLOTS);
    while (size) {
        struct nlattr header;
        if (size < sizeof(header)) return protocol_error();
        memcpy(&header, data, sizeof(header));
        size_t length = header.nla_len;
        unsigned type = header.nla_type & NLA_TYPE_MASK;
        if (length < sizeof(header) || length > size || !type ||
            type >= ATTR_SLOTS || result[type].present)
            return protocol_error();
        result[type] = (struct attribute) {
            .data = data + sizeof(header), .size = length - sizeof(header),
            .flags = header.nla_type & ~NLA_TYPE_MASK, .present = true
        };
        size_t step = aligned(length);
        if (step > size) {
            if (length != size) return protocol_error();
            step = size;
        }
        data += step;
        size -= step;
    }
    return 0;
}
static int scalar(const struct attribute *a, void *value, size_t size)
{
    if (!a->present || a->flags || a->size != size) return protocol_error();
    memcpy(value, a->data, size);
    return 0;
}
static int string_is(const struct attribute *a, const char *expected)
{
    size_t n = strlen(expected) + 1U;
    if (!a->present || a->flags || a->size != n || memcmp(a->data, expected, n))
        return protocol_error();
    return 0;
}
static int payload(struct transaction *t, const unsigned char *data, size_t size)
{
    struct genlmsghdr header;
    struct attribute a[ATTR_SLOTS];
    if (t->kind == ACK_ONLY || t->reply || size < sizeof(header))
        return protocol_error();
    memcpy(&header, data, sizeof(header));
    unsigned command = t->kind == FAMILY_REPLY ? CTRL_CMD_NEWFAMILY : NFC_CMD_GET_DEVICE;
    unsigned version = t->kind == FAMILY_REPLY ? CTRL_VERSION : NFC_GENL_VERSION;
    if (header.cmd != command || header.version != version || header.reserved ||
        attributes(data + sizeof(header), size - sizeof(header), a))
        return protocol_error();
    if (t->kind == FAMILY_REPLY) {
        uint32_t family_version;
        if (string_is(&a[CTRL_ATTR_FAMILY_NAME], t->family_name) ||
            scalar(&a[CTRL_ATTR_FAMILY_ID], &t->family, sizeof(t->family)) ||
            scalar(&a[CTRL_ATTR_VERSION], &family_version, sizeof(family_version)) ||
            family_version != t->family_version || t->family < GENL_MIN_ID)
            return protocol_error();
    } else {
        char expected[NFC_DEVICE_NAME_MAXSIZE];
        int n = snprintf(expected, sizeof(expected), "nfc%" PRIu32, t->index);
        if (n < 0 || (size_t)n >= sizeof(expected) ||
            string_is(&a[NFC_ATTR_DEVICE_NAME], expected) ||
            scalar(&a[NFC_ATTR_DEVICE_INDEX], &t->device.index, sizeof(uint32_t)) ||
            scalar(&a[NFC_ATTR_PROTOCOLS], &t->device.protocols, sizeof(uint32_t)) ||
            scalar(&a[NFC_ATTR_DEVICE_POWERED], &t->device.powered, sizeof(uint8_t)) ||
            scalar(&a[NFC_ATTR_RF_MODE], &t->device.rf_mode, sizeof(uint8_t)) ||
            t->device.index != t->index || t->device.protocols != EXPECTED_PROTOCOLS ||
            t->device.powered > 1 || t->device.rf_mode != NFC_RF_NONE)
            return protocol_error();
        memcpy(t->device.name, expected, (size_t)n + 1U);
    }
    t->reply = true;
    return 0;
}
static int packet(struct transaction *t, const unsigned char *data, size_t size,
                  const struct peer *peer)
{
    if (!size || size > PACKET_BYTES || peer->length != sizeof(struct sockaddr_nl) ||
        peer->address.nl_family != AF_NETLINK || peer->address.nl_pid ||
        peer->address.nl_groups || (peer->flags & (MSG_TRUNC | MSG_CTRUNC)))
        return protocol_error();
    while (size) {
        struct nlmsghdr header;
        if (size < sizeof(header)) return protocol_error();
        memcpy(&header, data, sizeof(header));
        size_t length = header.nlmsg_len;
        if (length < sizeof(header) || length > size ||
            header.nlmsg_seq != t->sequence ||
            (header.nlmsg_pid && header.nlmsg_pid != t->port))
            return protocol_error();
        const unsigned char *body = data + sizeof(header);
        size_t body_size = length - sizeof(header);
        if (header.nlmsg_type == NLMSG_ERROR) {
            struct nlmsgerr error;
            if (t->ack || body_size != sizeof(error) ||
                header.nlmsg_flags != NLM_F_CAPPED)
                return protocol_error();
            memcpy(&error, body, sizeof(error));
            if (error.msg.nlmsg_seq != t->sequence || error.msg.nlmsg_type != t->type ||
                error.msg.nlmsg_pid != t->port || error.msg.nlmsg_len != t->request_size ||
                error.msg.nlmsg_flags != (NLM_F_REQUEST | NLM_F_ACK) ||
                error.error > 0 || error.error < -4095)
                return protocol_error();
            if (error.error) { errno = -error.error; return -1; }
            t->ack = true;
        } else {
            if (header.nlmsg_type != t->type || header.nlmsg_flags ||
                payload(t, body, body_size)) return protocol_error();
        }
        size_t step = aligned(length);
        if (step > size) {
            if (length != size) return protocol_error();
            step = size;
        }
        data += step;
        size -= step;
    }
    return 0;
}
static int add_attribute(unsigned char *message, size_t capacity, size_t *length,
                         uint16_t type, const void *value, size_t size)
{
    size_t n = sizeof(struct nlattr) + size, step = aligned(n);
    if (n > UINT16_MAX || *length > capacity || step > capacity - *length) {
        errno = EMSGSIZE; return -1;
    }
    struct nlattr header = { .nla_len = (uint16_t)n, .nla_type = type };
    memcpy(message + *length, &header, sizeof(header));
    memcpy(message + *length + sizeof(header), value, size);
    memset(message + *length + n, 0, step - n);
    *length += step;
    return 0;
}
static int rpc(struct session *s, struct transaction *t, uint8_t command,
               uint16_t attribute_type, const void *value, size_t value_size,
               int64_t timeout_ms, bool mutation)
{
    unsigned char request[256] = {0}, response[PACKET_BYTES];
    struct nlmsghdr header = { .nlmsg_type = t->type,
        .nlmsg_flags = NLM_F_REQUEST | NLM_F_ACK,
        .nlmsg_seq = ++s->sequence, .nlmsg_pid = s->io.port };
    struct genlmsghdr generic = { .cmd = command,
        .version = t->kind == FAMILY_REPLY ? 1 : NFC_GENL_VERSION };
    size_t length = sizeof(header) + sizeof(generic);
    if (!s->sequence || add_attribute(request, sizeof(request), &length,
                                      attribute_type, value, value_size))
        return protocol_error();
    header.nlmsg_len = (uint32_t)length;
    memcpy(request, &header, sizeof(header));
    memcpy(request + sizeof(header), &generic, sizeof(generic));
    int64_t now = s->io.now(s->io.opaque);
    if (now < 0) return -1;
    int64_t end = now + timeout_ms;
    if (end > s->deadline) end = s->deadline;
    if (now >= end) { errno = ETIMEDOUT; return -1; }
    t->sequence = s->sequence; t->port = s->io.port; t->request_size = length;
    s->requests++;
    if (mutation) s->mutation_attempted = true;
    ssize_t sent = s->io.send(s->io.opaque, request, length);
    /* An interrupted, failed or short send is never resumed or repeated. */
    if (sent < 0) return -1;
    if ((size_t)sent != length) { errno = EIO; return -1; }
    for (unsigned n = 0; n < 16; n++) {
        now = s->io.now(s->io.opaque);
        if (now < 0) return -1;
        if (now >= end) { errno = ETIMEDOUT; return -1; }
        struct peer peer = {0};
        ssize_t got = s->io.receive(s->io.opaque, response, sizeof(response), &peer, end);
        if (got < 0) return -1;
        if (packet(t, response, (size_t)got, &peer)) return -1;
        if (t->ack && (t->reply || t->kind == ACK_ONLY)) return 0;
    }
    errno = EOVERFLOW; return -1;
}
static int family(struct session *s, const char *name, uint32_t version, uint16_t *id)
{
    struct transaction t = { .kind = FAMILY_REPLY, .type = GENL_ID_CTRL,
        .family_name = name, .family_version = version };
    s->phase = "family";
    if (rpc(s, &t, CTRL_CMD_GETFAMILY, CTRL_ATTR_FAMILY_NAME,
            name, strlen(name) + 1U, 2000, false)) return -1;
    *id = t.family;
    return 0;
}
static int get_device(struct session *s, uint16_t id, uint32_t index, struct device *device)
{
    struct transaction t = { .kind = DEVICE_REPLY, .type = id, .index = index };
    if (rpc(s, &t, NFC_CMD_GET_DEVICE, NFC_ATTR_DEVICE_INDEX,
            &index, sizeof(index), 2000, false)) return -1;
    *device = t.device;
    return 0;
}
static int run(struct session *s, const char *verb, uint32_t index,
               struct device *before, struct device *after, uint16_t *id)
{
    if (strcmp(verb, "get") && strcmp(verb, "up") && strcmp(verb, "down")) {
        errno = EINVAL; return -1;
    }
    if (family(s, NFC_GENL_NAME, NFC_GENL_VERSION, id)) return -1;
    if (*id < GENL_START_ALLOC) return protocol_error();
    s->phase = "get-before";
    if (get_device(s, *id, index, before)) return -1;
    *after = *before;
    if (!strcmp(verb, "get")) return 0;
    bool up = !strcmp(verb, "up");
    if (before->powered == (unsigned)up) { errno = EALREADY; return -1; }
    s->phase = up ? "up" : "down";
    struct transaction t = { .kind = ACK_ONLY, .type = *id };
    if (rpc(s, &t, up ? NFC_CMD_DEV_UP : NFC_CMD_DEV_DOWN,
            NFC_ATTR_DEVICE_INDEX, &index, sizeof(index), 20000, true)) return -1;
    s->phase = "get-after";
    if (get_device(s, *id, index, after)) return -1;
    if (after->powered != (unsigned)up) return protocol_error();
    return 0;
}
static int64_t real_now(void *unused)
{
    (void)unused;
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static ssize_t real_send(void *opaque, const void *data, size_t size)
{
    int fd = *(int *)opaque;
    struct sockaddr_nl kernel = { .nl_family = AF_NETLINK };
    struct iovec iov = { .iov_base = (void *)data, .iov_len = size };
    struct msghdr message = { .msg_name = &kernel, .msg_namelen = sizeof(kernel),
        .msg_iov = &iov, .msg_iovlen = 1 };
    return sendmsg(fd, &message, MSG_NOSIGNAL | MSG_DONTWAIT);
}
static ssize_t real_receive(void *opaque, void *data, size_t size,
                            struct peer *peer, int64_t deadline)
{
    int fd = *(int *)opaque;
    for (;;) {
        int64_t now = real_now(NULL);
        if (now < 0) return -1;
        int64_t left = deadline - now;
        if (left <= 0) { errno = ETIMEDOUT; return -1; }
        struct pollfd p = { .fd = fd, .events = POLLIN };
        int ready = poll(&p, 1, left > INT_MAX ? INT_MAX : (int)left);
        if (ready < 0 && errno == EINTR) continue;
        if (ready < 0) return -1;
        if (!ready) { errno = ETIMEDOUT; return -1; }
        if (p.revents & (POLLERR | POLLHUP | POLLNVAL)) { errno = EIO; return -1; }
        if (!(p.revents & POLLIN)) { errno = EIO; return -1; }
        struct iovec iov = { .iov_base = data, .iov_len = size };
        struct msghdr message = { .msg_name = &peer->address,
            .msg_namelen = sizeof(peer->address), .msg_iov = &iov, .msg_iovlen = 1 };
        ssize_t got = recvmsg(fd, &message, MSG_DONTWAIT);
        if (got < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        peer->length = message.msg_namelen; peer->flags = message.msg_flags;
        return got;
    }
}
static int open_transport(struct transport *io, int *fd)
{
    *fd = socket(AF_NETLINK, SOCK_RAW | SOCK_CLOEXEC | SOCK_NONBLOCK, NETLINK_GENERIC);
    if (*fd < 0) return -1;
    struct sockaddr_nl address = { .nl_family = AF_NETLINK };
    if (bind(*fd, (struct sockaddr *)&address, sizeof(address))) return -1;
    socklen_t length = sizeof(address);
    if (getsockname(*fd, (struct sockaddr *)&address, &length)) return -1;
    if (length != sizeof(address) || address.nl_family != AF_NETLINK ||
        !address.nl_pid || address.nl_groups) return protocol_error();
    int yes = 1;
    if (setsockopt(*fd, SOL_NETLINK, NETLINK_CAP_ACK, &yes, sizeof(yes))) return -1;
    *io = (struct transport) { .opaque = fd, .port = address.nl_pid,
        .send = real_send, .receive = real_receive, .now = real_now };
    return 0;
}
static int parse_index(const char *text, uint32_t *index)
{
    if (!*text) return -1;
    uint64_t n = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; p++) {
        if (*p < '0' || *p > '9') return -1;
        n = n * 10U + (*p - '0');
        if (n > UINT32_MAX) return -1;
    }
    char name[NFC_DEVICE_NAME_MAXSIZE];
    int length = snprintf(name, sizeof(name), "nfc%" PRIu32, (uint32_t)n);
    if (length < 0 || (size_t)length >= sizeof(name)) return -1;
    *index = (uint32_t)n;
    return 0;
}
int main(int argc, char **argv)
{
    uint32_t index;
    if (argc != 3 || (strcmp(argv[1], "get") && strcmp(argv[1], "up") &&
                     strcmp(argv[1], "down")) || parse_index(argv[2], &index)) {
        fputs("Usage: nfc-state get|up|down INDEX\n", stderr); return 2;
    }
    int fd = -1;
    struct session session = { .phase = "socket" };
    struct device before = {0}, after = {0};
    uint16_t id = 0;
    int64_t start = real_now(NULL);
    if (start < 0) goto failed;
    session.deadline = start + 30000;
    if (open_transport(&session.io, &fd) || run(&session, argv[1], index, &before, &after, &id))
        goto failed;
    int64_t finished = real_now(NULL);
    if (finished < 0) goto failed;
    close(fd);
    printf("{\"ok\":true,\"action\":\"%s\",\"index\":%" PRIu32
           ",\"name\":\"%s\",\"protocols\":%" PRIu32 ",\"powered_before\":%u,"
           "\"powered_after\":%u,\"rf_mode\":%u,\"family\":%u,\"requests\":%" PRIu32
           ",\"elapsed_ms\":%" PRId64 "}\n", argv[1], index, after.name,
           after.protocols, before.powered, after.powered, after.rf_mode, id,
           session.requests, finished - start);
    return 0;
failed:;
    int error = errno ? errno : EIO;
    if (fd >= 0) close(fd);
    printf("{\"ok\":false,\"phase\":\"%s\",\"error\":%d,\"mutation_attempted\":%s,"
           "\"requests\":%" PRIu32 "}\n", session.phase, error,
           session.mutation_attempted ? "true" : "false", session.requests);
    fprintf(stderr, "nfc-state %s: %s\n", session.phase, strerror(error));
    return 1;
}
