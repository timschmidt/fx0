#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check the paired Fx0 firmware's linked hooks and complete boot-image payload."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Elf:
    def __init__(self, data):
        self.data = data
        require(data[:6] == b'\x7fELF\x01\x01', 'expected little-endian ELF32')
        require(struct.unpack_from('<H', data, 18)[0] == 40, 'expected ARM')
        at = struct.unpack_from('<I', data, 32)[0]
        size, count, _ = struct.unpack_from('<HHH', data, 46)
        require(size == 40, 'unexpected ELF32 section format')
        self.sections = [struct.unpack_from('<10I', data, at + i * size) for i in range(count)]
        self.symbols = {}
        for section in self.sections:
            if section[1] != 2:  # SHT_SYMTAB
                continue
            require(section[9] == 16, 'unexpected ELF32 symbol format')
            strings = self.sections[section[6]]
            names = data[strings[4]:strings[4] + strings[5]]
            for offset in range(section[4], section[4] + section[5], 16):
                name, value, length, info, other, index = struct.unpack_from('<IIIBBH', data, offset)
                name = names[name:].split(b'\0', 1)[0].decode('ascii')
                if name and index != 0:
                    self.symbols[name] = (value, length, info, index)

    def file_offset(self, address, length):
        for section in self.sections:
            if section[1] != 8 and section[2] & 2 and section[3] <= address and address + length <= section[3] + section[5]:
                return section[4] + address - section[3]
        raise ValueError('address does not map to allocated file contents')

    def read(self, address, length):
        offset = self.file_offset(address, length)
        result = self.data[offset:offset + length]
        require(len(result) == length, 'truncated ELF contents')
        return result

    def word(self, address):
        return struct.unpack('<I', self.read(address, 4))[0]

    def string(self, address):
        result = bytearray()
        for i in range(1024):
            value = self.read(address + i, 1)
            if value == b'\0':
                return result.decode('ascii')
            result.extend(value)
        raise ValueError('unterminated firmware string')

    def symbol(self, name):
        require(name in self.symbols, 'missing symbol: ' + name)
        return self.symbols[name][0]


def check_linked(data):
    elf = Elf(data)
    start, end = elf.symbol('__dt_update_start'), elf.symbol('__dt_update_end')
    require(end > start and (end - start) % 8 == 0, 'invalid DT hook table bounds')
    entries = {}
    for at in range(start, end, 8):
        name = elf.string(elf.word(at))
        require(name not in entries, 'duplicate DT hook')
        function = elf.word(at + 4)
        require(function == elf.symbol(name), 'DT hook pointer differs from named function')
        section = elf.sections[elf.symbols[name][3]]
        require(section[2] & 4, 'DT hook does not point into executable contents')
        entries[name] = at
    required = ['madai_battery_update_dt', 'madai_charge_gate_update_dt']
    require(all(name in entries for name in required), 'missing paired battery/gate hook')
    for name in required:
        require(entries[name] == elf.symbol('_dt_update_' + name), 'hook registration outside table')
    detect = elf.symbol('_lk2nd_device_init_madai_battery_detect')
    require(elf.symbol('__lk2nd_device_init_start') <= detect <= elf.symbol('__lk2nd_device_init_end') - 8,
            'battery detection registration outside table')
    require(elf.string(elf.word(detect)) == 'lg,madai-battery', 'wrong battery detection compatible')
    require(elf.word(detect + 4) == elf.symbol('madai_battery_detect'), 'wrong battery detection callback')
    require(elf.string(elf.word(elf.symbol('LK2ND_VERSION'))) == 'next-2ce7574-20261030', 'wrong firmware version')
    return {'DT_hook_count': len(entries), 'battery_profile_and_charge_gate_registered': True,
            'battery_detection_registered': True, 'firmware_version': 'next-2ce7574-20261030'}, elf, entries


def check_image(data, kernel, ramdisk, qcdt):
    require(data[:8] == b'ANDROID!', 'wrong Android image magic')
    fields = struct.unpack_from('<10I', data, 8)
    require(fields == (len(kernel), 0x8000, 1, 0x01000000, 0, 0x00f00000, 0x100, 2048, len(qcdt), 0),
            'unexpected firmware image header')
    require(data[64:576].split(b'\0', 1)[0] == b'lk2nd', 'wrong firmware command line')
    require(ramdisk == b'\0', 'unexpected firmware RAM disk')
    page, at = 2048, 2048
    for part in (kernel, ramdisk, qcdt):
        require(data[at:at + len(part)] == part, 'boot-image payload differs from built artifact')
        next_at = at + ((len(part) + page - 1) // page) * page
        require(not any(data[at + len(part):next_at]), 'nonzero payload padding')
        at = next_at
    require(data[at:] == b'SEANDROIDENFORCE', 'unexpected image trailer or length')
    digest = hashlib.sha1()
    for part in (kernel, ramdisk, b'', qcdt):
        digest.update(part)
        digest.update(struct.pack('<I', len(part)))
    require(data[576:608] == digest.digest() + b'\0' * 12, 'wrong Android header payload digest')


def check_binary(elf, binary, kernel, qcdt, board):
    sections = [s for s in elf.sections if s[1] != 8 and s[2] & 2 and s[5]]
    start = min(s[3] for s in sections)
    end = max(s[3] + s[5] for s in sections)
    require(start == 0x07f00000 and 0 < end - start < 512 * 1024, 'unexpected firmware binary extent')
    expected = bytearray(end - start)
    for section in sections:
        expected[section[3] - start:section[3] - start + section[5]] = elf.read(section[3], section[5])
    require(binary == expected, 'raw binary differs from allocated linked ELF contents')
    require(kernel.startswith(binary), 'appended-DTB kernel does not contain the linked binary')
    require(board[:4] == b'\xd0\x0d\xfe\xed' and struct.unpack_from('>I', board, 4)[0] == len(board),
            'invalid built Fx0 firmware DTB')
    require(kernel[len(binary):].count(board) + qcdt.count(board) == 1,
            'built Fx0 firmware DTB missing or duplicated in boot payload')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path, help='build-lk2nd-msm8226 directory')
    args = parser.parse_args()
    root = args.build
    data = (root / 'lk').read_bytes()
    result, elf, entries = check_linked(data)
    image = (root / 'lk2nd.img').read_bytes()
    parts = [(root / name).read_bytes() for name in ('lk.bin-dtb', 'ramdisk.img', 'qcdt.img')]
    binary = (root / 'lk.bin').read_bytes()
    board = (root / 'lk2nd/device/dts/msm8226/msm8926-lg-madai.dtb').read_bytes()
    check_binary(elf, binary, parts[0], parts[2], board)
    check_image(image, *parts)
    damaged = bytearray(data)
    offset = elf.file_offset(entries['madai_charge_gate_update_dt'] + 4, 4)
    damaged[offset:offset + 4] = b'\0' * 4
    try:
        check_linked(damaged)
    except ValueError:
        pass
    else:
        raise ValueError('missing gate registration negative control accepted')
    damaged = bytearray(image)
    damaged[2048 + 64] ^= 1
    try:
        check_image(damaged, *parts)
    except ValueError:
        pass
    else:
        raise ValueError('modified boot payload negative control accepted')
    damaged = bytearray(binary)
    damaged[64] ^= 1
    try:
        check_binary(elf, damaged, parts[0], parts[2], board)
    except ValueError:
        pass
    else:
        raise ValueError('raw binary/ELF mismatch negative control accepted')
    damaged = bytearray(image)
    damaged[576] ^= 1
    try:
        check_image(damaged, *parts)
    except ValueError as error:
        require(str(error) == 'wrong Android header payload digest', 'unexpected digest-control failure')
    else:
        raise ValueError('modified header digest negative control accepted')
    result.update(image_bytes=len(image), image_SHA256=hashlib.sha256(image).hexdigest(),
                  complete_image_payload_and_header_digest_verified=True,
                  raw_binary_matches_allocated_ELF_contents=True,
                  built_Fx0_DTB_in_boot_payload=True,
                  negative_controls_rejected=4, physical_boot_qualified=False)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
