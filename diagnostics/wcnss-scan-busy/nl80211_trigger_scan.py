#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Send one NL80211_CMD_TRIGGER_SCAN, print the errno, then wait for its outcome.

Standard library only, for systems without iw.
Usage: nl80211_trigger_scan.py IFNAME [TIMEOUT_SECONDS]
"""
import errno
import os
import select
import socket
import struct
import sys
import time

NETLINK_GENERIC = 16
GENL_ID_CTRL = 0x10
CTRL_CMD_GETFAMILY = 3
CTRL_ATTR_FAMILY_ID = 1
CTRL_ATTR_FAMILY_NAME = 2
CTRL_ATTR_MCAST_GROUPS = 7
CTRL_ATTR_MCAST_GRP_NAME = 1
CTRL_ATTR_MCAST_GRP_ID = 2
SOL_NETLINK = 270
NETLINK_ADD_MEMBERSHIP = 1
NL80211_CMD_TRIGGER_SCAN = 33
NL80211_CMD_NEW_SCAN_RESULTS = 34
NL80211_CMD_SCAN_ABORTED = 35
OUTCOMES = {NL80211_CMD_NEW_SCAN_RESULTS: 'completed', NL80211_CMD_SCAN_ABORTED: 'aborted'}
NL80211_ATTR_IFINDEX = 3
NLM_F_REQUEST = 1
NLM_F_ACK = 4
NLMSG_ERROR = 2


def attr(kind, payload):
    data = struct.pack('=HH', 4 + len(payload), kind) + payload
    return data + bytes(-len(data) % 4)


def request(sock, family, cmd, attrs, seq):
    body = struct.pack('=BBH', cmd, 1, 0) + attrs
    sock.send(struct.pack('=IHHII', 16 + len(body), family, NLM_F_REQUEST | NLM_F_ACK, seq, 0) + body)
    replies = []
    while True:
        data = sock.recv(65536)
        offset = 0
        while offset < len(data):
            length, kind, _, rseq, _ = struct.unpack_from('=IHHII', data, offset)
            if rseq == seq:
                if kind == NLMSG_ERROR:
                    return struct.unpack_from('=i', data, offset + 16)[0], replies
                replies.append(data[offset + 16:offset + length])
            offset += (length + 3) & ~3


def attrs(payload):
    offset = 0
    while offset + 4 <= len(payload):
        length, kind = struct.unpack_from('=HH', payload, offset)
        yield kind & 0x3fff, payload[offset + 4:offset + length]
        offset += (length + 3) & ~3


def family(sock, name):
    err, replies = request(sock, GENL_ID_CTRL, CTRL_CMD_GETFAMILY, attr(CTRL_ATTR_FAMILY_NAME, name.encode() + b'\0'), 1)
    for reply in replies:
        found = dict(attrs(reply[4:]))
        if CTRL_ATTR_FAMILY_ID in found:
            groups = {}
            for _, group in attrs(found.get(CTRL_ATTR_MCAST_GROUPS, b'')):
                fields = dict(attrs(group))
                groups[fields[CTRL_ATTR_MCAST_GRP_NAME].rstrip(b'\0').decode()] = struct.unpack('=I', fields[CTRL_ATTR_MCAST_GRP_ID])[0]
            return struct.unpack_from('=H', found[CTRL_ATTR_FAMILY_ID])[0], groups
    raise OSError(-err, 'nl80211 family lookup failed')


ifindex = socket.if_nametoindex(sys.argv[1])
timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 30
sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_GENERIC)
sock.bind((0, 0))
nl80211, groups = family(sock, 'nl80211')
events = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_GENERIC)
events.bind((0, 0))
events.setsockopt(SOL_NETLINK, NETLINK_ADD_MEMBERSHIP, groups['scan'])
start = time.monotonic()
err, _ = request(sock, nl80211, NL80211_CMD_TRIGGER_SCAN, attr(NL80211_ATTR_IFINDEX, struct.pack('=I', ifindex)), 2)
print('trigger_scan', 0 if err == 0 else -err, 'ok' if err == 0 else errno.errorcode.get(-err, '?'), flush=True)
if err:
    sys.exit(1)
while (left := timeout - (time.monotonic() - start)) > 0:
    if not select.select([events], [], [], left)[0]:
        break
    data = events.recv(65536)
    offset = 0
    while offset + 20 <= len(data):
        length = struct.unpack_from('=I', data, offset)[0]
        cmd = data[offset + 16]
        payload = dict(attrs(data[offset + 20:offset + length]))
        if NL80211_ATTR_IFINDEX in payload and struct.unpack('=I', payload[NL80211_ATTR_IFINDEX])[0] == ifindex and cmd in OUTCOMES:
            print('scan_outcome', OUTCOMES[cmd], 'seconds', round(time.monotonic() - start, 2))
            sys.exit(0 if cmd == NL80211_CMD_NEW_SCAN_RESULTS else 2)
        offset += (length + 3) & ~3
print('scan_outcome none', 'seconds', round(time.monotonic() - start, 2))
sys.exit(3)
