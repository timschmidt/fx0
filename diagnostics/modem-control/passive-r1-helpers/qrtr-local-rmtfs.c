// SPDX-License-Identifier: MIT
/* A local name-service lookup only. No RMTFS request or remote node traffic. */
#define _DEFAULT_SOURCE
#include <endian.h>
#include <linux/qrtr.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define RMTFS_SERVICE 14u
#define RMTFS_INSTANCE 1u /* Version 1, instance 0, as packed by libqrtr. */

enum notification {
	INVALID,
	SERVER,
	END_OF_LIST,
};

static enum notification classify(const struct qrtr_ctrl_pkt *packet, ssize_t bytes,
				  const struct sockaddr_qrtr *from, socklen_t from_size,
				  unsigned int local_node)
{
	unsigned int service, instance, node, port;

	if (bytes != sizeof(*packet) || from_size != sizeof(*from) ||
	    from->sq_family != AF_QIPCRTR || from->sq_port != QRTR_PORT_CTRL ||
	    from->sq_node != local_node || le32toh(packet->cmd) != QRTR_TYPE_NEW_SERVER)
		return INVALID;
	service = le32toh(packet->server.service);
	instance = le32toh(packet->server.instance);
	node = le32toh(packet->server.node);
	port = le32toh(packet->server.port);
	if (!service && !instance && !node && !port)
		return END_OF_LIST;
	if (service == RMTFS_SERVICE && instance == RMTFS_INSTANCE &&
	    node == local_node && port == RMTFS_SERVICE)
		return SERVER;
	return INVALID;
}

static int lookup(int fd, bool expected)
{
	struct sockaddr_qrtr local = {}, target, from;
	struct timeval timeout = { .tv_sec = 1 };
	struct qrtr_ctrl_pkt query = {}, response;
	socklen_t size = sizeof(local);
	ssize_t bytes;
	bool found = false;
	int i;

	if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
	    getsockname(fd, (struct sockaddr *)&local, &size) < 0)
		return -1;
	if (size != sizeof(local) || local.sq_family != AF_QIPCRTR)
		return -1;

	target = local;
	target.sq_port = QRTR_PORT_CTRL;
	query.cmd = htole32(QRTR_TYPE_NEW_LOOKUP);
	query.server.service = htole32(RMTFS_SERVICE);
	query.server.instance = htole32(RMTFS_INSTANCE);
	if (sendto(fd, &query, sizeof(query), 0, (struct sockaddr *)&target, sizeof(target)) != sizeof(query))
		return -1;

	/* One local publication and one end marker are the largest valid listing. */
	for (i = 0; i < 2; ++i) {
		size = sizeof(from);
		bytes = recvfrom(fd, &response, sizeof(response), MSG_TRUNC, (struct sockaddr *)&from, &size);
		switch (classify(&response, bytes, &from, size, local.sq_node)) {
		case END_OF_LIST:
			return found == expected ? 0 : 1;
		case SERVER:
			if (found)
				return -1;
			found = true;
			break;
		default:
			return -1;
		}
	}
	return -1;
}

int main(int argc, char **argv)
{
	bool present;
	int fd, result;

	if (argc != 2 || (strcmp(argv[1], "present") && strcmp(argv[1], "absent")))
		return 2;
	present = !strcmp(argv[1], "present");
	fd = socket(AF_QIPCRTR, SOCK_DGRAM | SOCK_CLOEXEC, 0);
	if (fd < 0)
		return 1;
	result = lookup(fd, present);
	close(fd);
	if (result)
		return 1;
	printf("RMTFS_LOCAL_SERVICE_%s\n", present ? "PRESENT" : "ABSENT");
	return 0;
}
