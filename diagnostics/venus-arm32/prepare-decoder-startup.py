#!/usr/bin/env python3
"""Extract matched first-access-unit and header-only Annex-B H.264 inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


MAX_CHUNK_BYTES = 64 * 1024
SEQUENCE_FRAMES = 12
START_CODE = re.compile(rb"\x00\x00(?:\x00)?\x01")


def split_first_picture(packet):
    starts = list(START_CODE.finditer(packet))
    if not starts or any(packet[:starts[0].start()]):
        raise ValueError("first packet has no opening Annex-B start code")
    offsets = [m.start() for m in starts] + [len(packet)]
    kinds = []
    for start, end in zip(starts, offsets[1:]):
        if start.end() >= end or packet[start.end()] & 0x80:
            raise ValueError("invalid Annex-B NAL header")
        kinds.append(packet[start.end()] & 0x1f)

    try:
        first_picture = next(index for index, kind in enumerate(kinds) if 1 <= kind <= 5)
    except StopIteration as error:
        raise ValueError("first packet has no picture slice") from error
    prefix = kinds[:first_picture]
    if kinds[first_picture] != 5 or not {7, 8}.issubset(prefix):
        raise ValueError("first picture must be IDR preceded by SPS and PPS")
    return packet[:offsets[first_picture]], kinds


def inspect_packets(path):
    report = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-f", "h264", "-select_streams", "v:0",
        "-show_entries", "packet=pos,size,flags:stream=width,height",
        "-show_packets", "-show_streams", "-of", "json", str(path),
    ], timeout=15))
    stream, = report["streams"]
    if (stream["width"], stream["height"]) != (320, 240):
        raise ValueError("startup probe requires a known 320x240 fixture")
    if not report["packets"]:
        raise ValueError("fixture has no H.264 packet")
    return report["packets"]


def first_packet(packet, body):
    size = int(packet["size"])
    if int(packet["pos"]) != 0 or not 0 < size <= MAX_CHUNK_BYTES or size > len(body):
        raise ValueError("first packet lies outside the startup probe bounds")
    if "K" not in packet["flags"]:
        raise ValueError("fixture does not start on a keyframe")
    return body[:size]


def frame_sequence(packets, body):
    if len(packets) != SEQUENCE_FRAMES:
        raise ValueError("sequence probe requires exactly twelve access units")
    pieces = []
    offset = 0
    for packet in packets:
        size = int(packet["size"])
        if int(packet["pos"]) != offset or not 0 < size <= len(body) - offset:
            raise ValueError("access units do not cover contiguous fixture bytes")
        pieces.append(struct.pack("<I", size) + body[offset:offset + size])
        offset += size
    if offset != len(body) or offset + 4 * len(packets) > MAX_CHUNK_BYTES:
        raise ValueError("framed sequence does not match the fixture or exceeds the probe limit")
    return b"".join(pieces)


def describe(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("directory", type=Path, help="new output directory")
    parser.add_argument("--sequence", action="store_true", help="also prepare all twelve access units")
    args = parser.parse_args()

    body = args.fixture.read_bytes()
    packets = inspect_packets(args.fixture)
    packet = first_packet(packets[0], body)
    headers, kinds = split_first_picture(packet)
    outputs = {"first-access-unit.h264": packet, "before-first-slice.h264": headers}
    if args.sequence:
        outputs["reference-au.bin"] = frame_sequence(packets, body)
    report = {
        "reference": describe(body),
        "first_packet_nal_types": kinds,
        "headers_are_exact_prefix": packet.startswith(headers),
        "fixture_width": 320,
        "fixture_height": 240,
        "probe_inputs": {name: describe(payload) for name, payload in outputs.items()},
    }
    args.directory.mkdir(mode=0o700)
    for name, payload in outputs.items():
        (args.directory / name).write_bytes(payload)
    (args.directory / "fixture.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
