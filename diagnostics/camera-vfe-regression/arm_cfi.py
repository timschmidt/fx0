# SPDX-License-Identifier: GPL-2.0-only
"""Decode complete A32 KCFI XOR-immediate guards in real ELF function bodies."""
import struct


def functions(data, name):
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    assert header[0][:6] == b'\x7fELF\x01\x01' and header[1:3] == (1, 40)
    assert header[11] == 40
    sections = [struct.unpack_from('<10I', data, header[6] + i * 40) for i in range(header[12])]
    result = []
    for table in sections:
        if table[1] != 2:
            continue
        strings = sections[table[6]]
        names = data[strings[4]:strings[4] + strings[5]]
        assert table[9] == 16
        for offset in range(table[4], table[4] + table[5], 16):
            string, address, size, info, other, index = struct.unpack_from('<IIIBBH', data, offset)
            if info & 15 != 2 or names[string:].split(b'\0', 1)[0].decode() != name:
                continue
            assert address & 1 == 0, 'This verifier requires A32, not Thumb'
            section = sections[index]
            assert section[1] == 1 and size > 0 and address + size <= section[5]
            result.append((section[4] + address, size))
    assert result, 'Required function symbol absent'
    return result


def immediate(word):
    byte = word & 255
    rotate = ((word >> 8) & 15) * 2
    return ((byte >> rotate) | (byte << ((32 - rotate) % 32))) & 0xffffffff


def xor_guards(data, name='vfe_isr'):
    """Require type-word load, flag-setting XOR, EQ skip, UDF, same-target BLX."""
    result = []
    for start, length in functions(data, name):
        assert length % 4 == 0
        words = list(struct.unpack_from('<' + 'I' * (length // 4), data, start))
        for index in range(1, len(words) - 4):
            if words[index] != 0xe51cc004:  # ldr ip, [ip, #-4]
                continue
            previous = words[index - 1]
            if previous & 0xfff0ffff != 0xe3c0c001:  # bic ip, target, #1
                continue
            target = (previous >> 16) & 15
            if target in [12, 15]:
                continue
            at = index + 1
            value = 0
            offsets = []
            for _ in range(4):
                if at >= len(words):
                    break
                word = words[at]
                if word & 0xffeff000 != 0xe22cc000:  # AL EOR(S) ip, ip, #imm
                    break
                value ^= immediate(word)
                offsets.append(start + at * 4)
                at += 1
                if word & 0x00100000:
                    # BEQ skips exactly the UDF and reaches BLX on equality.
                    if at + 2 < len(words) and words[at] == 0x0a000000 and words[at + 1] & 0xfff000f0 == 0xe7f000f0 and words[at + 2] == (0xe12fff30 | target):
                        result.append(dict(type_word=value, function_file_offset=start,
                                           type_load_file_offset=start + index * 4,
                                           xor_instruction_file_offsets=offsets,
                                           branch_file_offset=start + at * 4,
                                           trap_file_offset=start + (at + 1) * 4,
                                           call_file_offset=start + (at + 2) * 4,
                                           call_target_register=target))
                    break
    return result


def require_type(data, expected, count=1):
    matches = [r for r in xor_guards(data) if r['type_word'] == expected]
    if len(matches) != count:
        raise ValueError('Expected %d complete guards for type0x%08x, found%d' % (count, expected, len(matches)))
    return matches
