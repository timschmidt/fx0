#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Protocol tests for private retained-RAM decoding; no device access."""
import struct
import unittest

from decode import decode_names, retained_events


def frame(cpu, sequence=100):
    result = []
    values = {'address': 'fabcdef0', 'fsr': '12345678',
              'pc': 'c0010100', 'cpsr': '600001d3'}
    for key, value in values.items():
        result.append((sequence, cpu, 'fx0_abort_' + key))
        sequence += 1
        for digit in value:
            result.append((sequence, cpu, 'fx0_abort_digit_' + digit))
            sequence += 1
    result.append((sequence, cpu, 'fx0_abort_end'))
    return result


class DecodeTests(unittest.TestCase):
    def test_interleaved_cpu_frames_and_selftest(self):
        events = frame(0) + frame(3, 105)
        events.append((200, 0, 'fx0_abort_selftest_end'))
        captures = decode_names(reversed(events))
        self.assertEqual(len(captures), 2)
        self.assertTrue(all(item['complete'] for item in captures))
        self.assertTrue(captures[0]['synthetic_selftest'])
        self.assertFalse(captures[1]['synthetic_selftest'])
        self.assertEqual(captures[1]['address'], 'fabcdef0')
        self.assertEqual(captures[1]['fsr'], '12345678')
        self.assertEqual(captures[1]['pc'], 'c0010100')
        self.assertEqual(captures[1]['cpsr'], '600001d3')

    def test_truncated_field_is_not_a_complete_capture(self):
        capture = decode_names(frame(2)[:5])[0]
        self.assertFalse(capture['complete'])
        self.assertIsNone(capture['synthetic_selftest'])
        self.assertEqual(capture['address'], 'fabc')

    def test_wrapped_ring_and_symbol_bounds(self):
        raw = bytearray(524288)
        sig = 0x43474244 ^ ((6 << 16) | (18 << 8) | 59)
        table = [(0x1000, 32, 'fx0_abort_address')]
        for cpu in range(4):
            offset = 262144 + cpu * 65536
            struct.pack_into('<III', raw, offset, sig, 0, 0)
        # Chronological ring starts after one stray byte; discard the partial record.
        data = b'x' + struct.pack('<IIQ', 0x1008 | 2, 0, 100)
        data += struct.pack('<IIQ', 0x2000 | 2, 0, 101)
        start = 7
        stored = data[-start:] + data[:-start]
        offset = 262144 + 2 * 65536
        struct.pack_into('<III', raw, offset, sig, start, len(data))
        raw[offset + 12:offset + 12 + len(data)] = stored
        self.assertEqual(retained_events(raw, table), [(100, 2, 'fx0_abort_address')])
        raw[offset] ^= 1
        with self.assertRaises(ValueError):
            retained_events(raw, table)


if __name__ == '__main__':
    unittest.main()
