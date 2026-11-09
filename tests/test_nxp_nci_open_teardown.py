"""Run extracted Linux close/reset/IRQ/remove code against modeled kernel services.

Unlike the frozen r58 test, include the NCI closing reset and its response. The
bus, scheduling, queues and completion wait are models, not a kernel emulator.
FX0_NFC_OPEN_TEARDOWN_SOURCE selects another checkout for regression controls.
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FX0_NFC_OPEN_TEARDOWN_SOURCE',
                             ROOT / 'worktrees/linux-fx0-nfc-open-teardown'))


def block(text, pattern):
    match = re.search(pattern, text, re.M)
    if not match:
        raise ValueError('Missing source block: ' + pattern)
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if text[end:end + 1] == ';':
        end += 1
    return text[match.start():end] + '\n'


def function(text, name):
    return block(text, r'^(?:static )?(?:int|void|irqreturn_t) ' +
                 re.escape(name) + r'\([^;]*?\)\n\{')


def harness(source):
    driver = source / 'drivers/nfc/nxp-nci'
    i2c = (driver / 'i2c.c').read_text()
    core = (driver / 'core.c').read_text()
    header = (driver / 'nxp-nci.h').read_text()
    nci = (source / 'net/nfc/nci/core.c').read_text()
    rsp = (source / 'net/nfc/nci/rsp.c').read_text()
    types = block(header, r'^enum nxp_nci_mode \{')
    for name in ['nxp_nci_phy_ops', 'nxp_nci_fw_info', 'nxp_nci_info']:
        types += block(header, '^struct ' + name + r' \{')
    types += block(i2c, r'^struct nxp_nci_i2c_phy \{')
    # Keep actual function bodies and actual transport callback wiring.
    transport = ''.join(function(i2c, name) for name in
                        ['nxp_nci_i2c_set_mode', 'nxp_nci_i2c_write',
                         'nxp_nci_i2c_nci_read', 'nxp_nci_i2c_irq_thread_fn'])
    if 'static void nxp_nci_i2c_stop_rx(' in i2c:
        transport += function(i2c, 'nxp_nci_i2c_stop_rx')
    transport += block(i2c, r'^static const struct nxp_nci_phy_ops i2c_phy_ops = \{')
    transport += function(core, 'nxp_nci_open') + function(core, 'nxp_nci_close')
    transport += function(core, 'nxp_nci_send')
    network = function(nci, 'nci_reset_req')
    network += function(nci, 'nci_close_device')
    network += function(nci, 'nci_unregister_device')
    network += function(nci, 'nci_recv_frame')
    network += function(rsp, 'nci_core_reset_rsp_packet')
    removal = function(core, 'nxp_nci_remove')
    removal += function(i2c, 'nxp_nci_i2c_probe')
    removal += function(i2c, 'nxp_nci_i2c_remove')
    fixture = (ROOT / 'tests/nxp_nci_open_teardown_harness.c').read_text()
    for marker, value in [('TYPES', types), ('TRANSPORT', transport),
                          ('NETWORK', network), ('REMOVAL', removal)]:
        assert fixture.count('/* ACTUAL_' + marker + ' */') == 1
        fixture = fixture.replace('/* ACTUAL_' + marker + ' */', value)
    return fixture


class NxpNciOpenTeardownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        path = base / 'open-teardown.c'
        path.write_text(harness(SOURCE))
        cls.binary = base / 'open-teardown'
        command = shlex.split(os.environ.get('CC', 'cc'))
        command += ['-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-sign-compare']
        command += shlex.split(os.environ.get('FX0_NFC_TEST_CFLAGS', ''))
        command += [str(path), '-o', str(cls.binary)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check_mode(self, mode):
        result = subprocess.run([str(self.binary), mode], capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_open_unregister_receives_reset_before_IRQ_drain(self):
        for mode in ['open', 'open_pending_irq', 'open_no_clock',
                     'open_data_exchange']:
            with self.subTest(mode=mode):
                self.check_mode(mode)

    def test_cold_and_serialized_firmware_remove_keep_state_alive_until_IRQ_drain(self):
        for mode in ['cold', 'cold_pending_irq', 'firmware_pending_irq']:
            with self.subTest(mode=mode):
                self.check_mode(mode)

    def test_IRQ_registration_failure_does_not_release_an_unowned_IRQ(self):
        self.check_mode('probe_irq_failure')

    def test_optional_transport_stop_callback(self):
        self.check_mode('core_legacy')

    def test_missing_reset_response_still_closes_and_drains(self):
        self.check_mode('open_timeout_pending_irq')


if __name__ == '__main__':
    unittest.main()
