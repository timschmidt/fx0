
#define main observer_main
#include "qrtr-local-rmtfs.c"
#undef main
#include <assert.h>

int main(void)
{
    struct sockaddr_qrtr from = {AF_QIPCRTR, 1, QRTR_PORT_CTRL};
    struct qrtr_ctrl_pkt packet = {.cmd = htole32(QRTR_TYPE_NEW_SERVER)};

    assert(classify(&packet, 20, &from, sizeof(from), 1) == END_OF_LIST);
    packet.server.service = htole32(14);
    packet.server.instance = htole32(1);
    packet.server.node = htole32(1);
    packet.server.port = htole32(14);
    assert(classify(&packet, 20, &from, sizeof(from), 1) == SERVER);
    assert(classify(&packet, 19, &from, sizeof(from), 1) == INVALID);
    assert(classify(&packet, 21, &from, sizeof(from), 1) == INVALID);
    assert(classify(&packet, 20, &from, sizeof(from) - 1, 1) == INVALID);
    assert(classify(&packet, 20, &from, sizeof(from), 2) == INVALID);
    from.sq_port = 14;
    assert(classify(&packet, 20, &from, sizeof(from), 1) == INVALID);
    from.sq_port = QRTR_PORT_CTRL;
    packet.server.instance = htole32(2);
    assert(classify(&packet, 20, &from, sizeof(from), 1) == INVALID);
    packet.server.instance = htole32(1);
    packet.cmd = htole32(QRTR_TYPE_DEL_SERVER);
    assert(classify(&packet, 20, &from, sizeof(from), 1) == INVALID);
    return 0;
}
