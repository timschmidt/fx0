#!/usr/bin/env python3
"""Receive one bounded synthetic stream on the phone's USB IPv4 address."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True)
    parser.add_argument('--port', type=int, default=49160)
    parser.add_argument('--bytes', type=int, default=4 * 1024 * 1024)
    parser.add_argument('--deadline', type=int, default=20)
    parser.add_argument('--record', required=True, type=Path)
    args = parser.parse_args()
    address = ipaddress.IPv4Address(args.address)
    if not address.is_private or address.is_unspecified or address.is_multicast:
        parser.error('Use an explicit private USB IPv4 address')
    if not 1024 <= args.port <= 65535 or not 1 <= args.bytes <= 16 * 1024 * 1024 or not 1 <= args.deadline <= 30:
        parser.error('Port, size or deadline outside diagnostic bounds')
    if args.record.exists() or args.record.is_symlink():
        parser.error('Record already exists')
    if args.record.parent.stat().st_uid != os.getuid():
        parser.error('Record directory must belong to the current user')
    started = time.monotonic()
    state = dict(PID=os.getpid(),state='starting',bytes=0,requested_bytes=args.bytes,
                 boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    digest = hashlib.sha256()

    def save():
        state.update(elapsed_seconds=round(time.monotonic()-started,3),sha256=digest.hexdigest())
        temporary=args.record.with_suffix('.tmp')
        with temporary.open('w') as file:
            os.fchmod(file.fileno(),0o600)
            json.dump(state,file)
            file.write('\n')
        temporary.replace(args.record)

    def alarm(signum,frame):
        raise TimeoutError('Native overall deadline')

    signal.signal(signal.SIGALRM,alarm)
    signal.alarm(args.deadline)
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as server:
            server.bind((str(address),args.port))
            server.listen(1)
            state['state']='listening'
            save()
            print('READY',flush=True)
            connection,peer=server.accept()
            with connection:
                state['state']='receiving'
                while state['bytes']<args.bytes:
                    data=connection.recv(min(65536,args.bytes-state['bytes']))
                    if not data:
                        raise EOFError('Input ended before expected length')
                    digest.update(data)
                    state['bytes']+=len(data)
                state['state']='complete'
                save()
                connection.sendall((json.dumps(state)+'\n').encode())
    except BaseException as error:
        state.update(state='failed',error=type(error).__name__+': '+str(error))
    finally:
        signal.alarm(0)
        save()
    return 0 if state['state']=='complete' else 1


if __name__=='__main__':
    raise SystemExit(main())
