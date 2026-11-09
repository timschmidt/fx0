#!/usr/bin/env python3
"""Stage and verify Fx0 RAM bytes with bounded synchronous USB transfers.

This tool stops after readback. It sends no boot, flash, erase or reset command.
Use a new private output directory. Errors leave device-state diagnosis to the
caller; an uncertain transfer is never retried automatically.
Short USB data writes also stop: resuming the remaining bytes can violate
lk2nd's download framing. Partial readback remains allowed.
The payload-free io.jsonl journal records each framed I/O before execution.
An error leaves its transferred byte count unknown; it never implies zero.
"""
import argparse
import ctypes as c
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time

import boot_fx0_ram as boot

CHUNK = 16384
MAX_BYTES = 64 * 1024 * 1024


def bulk(fd, endpoint, *, data=None, size=64):
    buffer = c.create_string_buffer(data if data is not None else size)
    length = len(data) if data is not None else size
    request = boot.Bulk(endpoint, length, 30000, c.addressof(buffer))
    actual = boot.ioctl(fd, boot.BULK, request)
    return actual if data is not None else buffer.raw[:actual]


def stage_readback(fd, output, input_, data, io=bulk, progress=lambda **kw: None,
                   pause=lambda: None, trace=lambda **kw: None):
    boot.require(0 < len(data) <= MAX_BYTES, 'Invalid RAM transfer size')

    def exchange(phase, *, payload=None, size=64, offset=None):
        operation = {'phase': phase, 'direction': 'OUT' if payload is not None else 'IN',
                     'requested_bytes': len(payload) if payload is not None else size}
        if offset is not None:
            operation['offset'] = offset
        trace(event='started', **operation)
        started = time.monotonic()
        try:
            result = (io(fd, output, data=payload) if payload is not None
                      else io(fd, input_, size=size))
        except Exception as error:
            trace(event='failed', elapsed_seconds=time.monotonic() - started,
                  error_type=type(error).__name__, errno=getattr(error, 'errno', None),
                  actual_bytes=None, **operation)
            raise
        trace(event='returned', elapsed_seconds=time.monotonic() - started,
              actual_bytes=result if payload is not None else len(result), **operation)
        return result

    def send(payload, phase):
        boot.require(exchange(phase, payload=payload) == len(payload), 'Short command write')

    def status(phase):
        for _ in range(32):
            packet = exchange(phase)
            if packet.startswith(b'INFO'):
                continue
            if packet.startswith(b'FAIL'):
                raise ValueError('Bootloader rejected RAM transfer: ' + repr(packet[4:]))
            return packet
        raise ValueError('Too many INFO packets')

    def size_response(phase):
        packet = status(phase)
        boot.require(re.fullmatch(b'DATA[0-9a-fA-F]{8}', packet) is not None,
                     'Expected DATA size response')
        boot.require(int(packet[4:], 16) == len(data), 'RAM transfer size differs')

    send(f'download:{len(data):08x}'.encode(), 'download-command')
    size_response('download-size')
    offset = 0
    while offset < len(data):
        part = data[offset:offset + CHUNK]
        actual = exchange('download-data', payload=part, offset=offset)
        # A short OUT transfer can terminate lk2nd's pending USB read. Its
        # cmd_download rejects a short result, so the remaining bytes cannot
        # safely be sent as a continuation or a new command.
        boot.require(actual == len(part),
                     f'Short or invalid data write at offset {offset}: '
                     f'{actual} of {len(part)} bytes; do not resume or boot')
        offset += actual
        pause()
        progress(phase='download', bytes=offset)
    boot.require(status('download-status') == b'OKAY', 'Missing download acknowledgement')
    send(b'upload', 'upload-command')
    size_response('upload-size')
    received = bytearray()
    while len(received) < len(data):
        size = min(CHUNK, len(data) - len(received))
        part = exchange('readback-data', size=size, offset=len(received))
        boot.require(0 < len(part) <= size, 'Invalid data read progress')
        received.extend(part)
        pause()
        progress(phase='readback', bytes=len(received))
    boot.require(status('upload-status') == b'OKAY', 'Missing readback acknowledgement')
    boot.require(received == data, 'RAM readback differs; do not boot')
    return bytes(received)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pace-ms', type=int, default=5,
                        help='Pause between data chunks (0 through 100 milliseconds)')
    args = parser.parse_args()
    boot.require(0 <= args.pace_ms <= 100, 'Invalid pacing interval')
    data = args.payload.read_bytes()
    boot.require(re.fullmatch('[0-9a-f]{64}', args.sha256) is not None, 'Expected SHA-256')
    boot.require(hashlib.sha256(data).hexdigest() == args.sha256, 'Payload checksum mismatch')
    boot.require(0 < len(data) <= MAX_BYTES, 'Invalid RAM transfer size')
    args.output.mkdir(parents=True, mode=0o700)
    report = {'started_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'state': 'identity probe', 'bytes': 0, 'payload_bytes': len(data),
              'sha256': args.sha256, 'chunk_bytes': CHUNK, 'pace_ms': args.pace_ms}

    def save():
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    def progress(**values):
        report.update(values)
        if values['bytes'] % (CHUNK * 16) == 0 or values['bytes'] == len(data):
            save()

    sequence = 0
    def trace(**values):
        nonlocal sequence
        if values['event'] == 'started':
            sequence += 1
        event = {'sequence': sequence,
                 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), **values}
        journal.write(json.dumps(event) + '\n')
        journal.flush()
        report['last_IO'] = event

    fd = None
    claimed = False
    save()
    journal = (args.output / 'io.jsonl').open('x')
    try:
        report['identity'] = boot.query(args.serial)
        node, interface, output, input_ = boot.device(args.serial)
        fd = os.open(node, os.O_RDWR)
        index = c.c_uint(interface)
        boot.ioctl(fd, boot.CLAIM, index)
        claimed = True
        report['state'] = 'transferring'
        save()
        received = stage_readback(fd, output, input_, data, progress=progress,
                                  pause=lambda: time.sleep(args.pace_ms / 1000), trace=trace)
        (args.output / 'readback.bin').write_bytes(received)
        report.update(state='verified', readback_sha256=hashlib.sha256(received).hexdigest())
    except Exception as error:
        report.update(state='failed', error=str(error).replace(args.serial, '<serial>'))
        raise
    finally:
        try:
            if claimed:
                try:
                    boot.ioctl(fd, boot.RELEASE, index)
                except OSError:
                    pass
            if fd is not None:
                os.close(fd)
            report['finished_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save()
        finally:
            journal.close()
    print('RAM bytes staged and read back exactly; no boot command sent.')


if __name__ == '__main__':
    main()
