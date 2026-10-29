#!/usr/bin/env python3
"""Expand only the verified stock RAM diagnostic's EEPROM read map.

Host files only. This preserves the kernel, initramfs, load addresses, QCDT
matches and every DT property except qcom,mem0's read length. It prepares a
2560-byte calibration read, not proof of the physical EEPROM's entire capacity.
"""

import argparse
import hashlib
import json
import os
import struct
from pathlib import Path


EEPROM_PATH = "/soc/qcom,cci@fda0c000/qcom,eeprom@a0"


def property_offset(blob):
    if len(blob) < 40:
        raise ValueError("truncated DTB")
    header = struct.unpack_from(">10I", blob)
    magic, total, start, strings, _, version, _, _, string_size, size = header
    if magic != 0xD00DFEED or version != 17 or total > len(blob):
        raise ValueError("unexpected DTB header")
    if start + size > total or strings + string_size > total:
        raise ValueError("invalid DTB bounds")
    cursor, end = start, start + size
    stack, found = [], []
    model_matches = False
    while cursor < end:
        token = struct.unpack_from(">I", blob, cursor)[0]
        cursor += 4
        if token == 1:  # FDT_BEGIN_NODE
            terminator = blob.index(0, cursor, end)
            stack.append(bytes(blob[cursor:terminator]).decode("ascii"))
            cursor = (terminator + 4) & ~3
        elif token == 2:  # FDT_END_NODE
            stack.pop()
        elif token == 3:  # FDT_PROP
            length, name_offset = struct.unpack_from(">II", blob, cursor)
            cursor += 8
            if name_offset >= string_size or cursor + length > end:
                raise ValueError("invalid DT property")
            terminator = blob.index(0, strings + name_offset, strings + string_size)
            name = bytes(blob[strings + name_offset:terminator]).decode("ascii")
            path = "/" + "/".join(stack[1:])
            value = bytes(blob[cursor:cursor + length])
            if path == "/" and name == "compatible":
                model_matches = b"qcom,msm8926-madai" in value.split(b"\0")
            if path == EEPROM_PATH and name == "qcom,mem0":
                if value != struct.pack(">6I", 0x900, 0, 2, 0, 1, 0):
                    raise ValueError("EEPROM read map differs from the original verified map")
                found.append(cursor)
            cursor = (cursor + length + 3) & ~3
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            break
        else:
            raise ValueError("unknown DT structure token")
    if not model_matches or len(found) != 1:
        raise ValueError("expected one Fx0 EEPROM read-map property")
    return found[0]


def prepare(data):
    if len(data) < 2048 or data[:8] != b"ANDROID!":
        raise ValueError("expected the verified Android v0 RAM diagnostic")
    fields = struct.unpack_from("<10I", data, 8)
    kernel_size, _, ramdisk_size, _, second_size, _, _, page, dt_size, _ = fields
    if page != 2048:
        raise ValueError("unexpected Fx0 boot-image page size")
    cursor, payloads = page, []
    for size in (kernel_size, ramdisk_size, second_size, dt_size):
        if cursor + size > len(data):
            raise ValueError("truncated boot-image payload")
        payloads.append(data[cursor:cursor + size])
        cursor += (size + page - 1) // page * page
    old_id = hashlib.sha1()
    for payload in payloads:
        old_id.update(payload)
        old_id.update(struct.pack("<I", len(payload)))
    if data[576:596] != old_id.digest():
        raise ValueError("input Android image ID does not match its payloads")
    table = bytearray(payloads[3])
    if len(table) < 108 or struct.unpack_from("<3I", table) != (0x54444351, 2, 4):
        raise ValueError("expected the four-entry stock Fx0 QCDT v2")
    offsets = set()
    for index in range(4):
        platform, board, subtype, revision, offset, size = struct.unpack_from(
            "<6I", table, 12 + index * 24
        )
        if platform not in (200, 224) or board != 150 or subtype or revision not in (0, 65537):
            raise ValueError("unexpected QCDT hardware match")
        if offset < 108 or offset + size > len(table):
            raise ValueError("invalid QCDT payload bounds")
        offsets.add((offset, size))
    if len(offsets) != 1:
        raise ValueError("expected all four QCDT matches to share one DTB")
    offset, size = offsets.pop()
    at = offset + property_offset(table[offset:offset + size])
    struct.pack_into(">I", table, at, 0xA00)
    result = bytearray(data)
    dt_start = page + sum((len(p) + page - 1) // page * page for p in payloads[:3])
    result[dt_start:dt_start + len(table)] = table
    payloads[3] = bytes(table)
    image_id = hashlib.sha1()
    for payload in payloads:
        image_id.update(payload)
        image_id.update(struct.pack("<I", len(payload)))
    result[576:596] = image_id.digest()
    differences = [i for i, (old, new) in enumerate(zip(data, result)) if old != new]
    if len(result) != len(data) or any(
        not (576 <= i < 596 or dt_start + at <= i < dt_start + at + 4)
        for i in differences
    ):
        raise ValueError("unexpected change outside read length and Android checksum")
    return bytes(result), len(differences)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--sha256", required=True, help="expected hash from the input's private manifest")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        data = args.input.read_bytes()
        if hashlib.sha256(data).hexdigest() != args.sha256:
            raise ValueError("input SHA-256 mismatch")
        result, changed_bytes = prepare(data)
        os.umask(0o077)
        with args.output.open("xb") as output:
            output.write(result)
            output.flush()
            os.fsync(output.fileno())
    except (OSError, ValueError, IndexError, struct.error) as error:
        parser.error(str(error))
    print(json.dumps({
        "file": args.output.name,
        "bytes": len(result),
        "sha256": hashlib.sha256(result).hexdigest(),
        "input_sha256": args.sha256,
        "changed_bytes": changed_bytes,
        "change": "EEPROM read-map length 0x900 -> 0xa00 and Android payload checksum only",
        "kernel_initramfs_other_dt_bytes_preserved": True,
        "scope": "Unbooted RAM diagnostic preparation; no flash, EEPROM programming or capacity proof",
    }, indent=2))


if __name__ == "__main__":
    main()
