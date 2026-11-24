# SPDX-License-Identifier: MIT
"""Root integrity controls for the isolated normal-package build workflow."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / 'diagnostics/modem-control' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


bootstrap = module('modem_bootstrap', 'bootstrap-userspace-roots.py')
builder = module('modem_builder', 'build-userspace-package.py')


class RootIntegrity(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'usr/lib/apk/db').mkdir(parents=True)
        (self.root / 'lib').symlink_to('usr/lib')

    def records(self, rows):
        text = 'P:fixture\n'
        for name, value in rows:
            folder, filename = name.rsplit('/', 1)
            checksum = base64.b64encode(hashlib.sha1(value).digest()).decode()
            text += f'F:{folder}\nR:{filename}\nZ:Q1{checksum}\n'
        (self.root / 'lib/apk/db/installed').write_text(text)

    def test_absolute_directory_link_resolves_inside_root(self):
        (self.root / 'usr/lib/value').write_bytes(b'fixture')
        (self.root / 'alias').symlink_to('/usr/lib')
        self.records([('alias/value', b'fixture')])
        result = bootstrap.package_payload_audit(self.root, False)
        self.assertEqual(result['checked_paths'], 1)
        self.assertTrue(result['all_other_package_payloads_exact'])

    def test_link_checksum_uses_link_bytes_and_detects_change(self):
        link = self.root / 'usr/lib/link'
        link.symlink_to('value')
        self.records([('usr/lib/link', b'value')])
        self.assertEqual(bootstrap.package_payload_audit(
            self.root, False)['symlinks_checked'], 1)
        link.unlink()
        link.symlink_to('/outside')
        with self.assertRaisesRegex(ValueError, 'payload mismatch'):
            bootstrap.package_payload_audit(self.root, False)

    def test_payload_mutation_rejected(self):
        (self.root / 'usr/lib/value').write_bytes(b'changed')
        self.records([('usr/lib/value', b'fixture')])
        with self.assertRaisesRegex(ValueError, 'payload mismatch'):
            bootstrap.package_payload_audit(self.root, False)

    def test_parent_link_cannot_escape_root(self):
        (self.root / 'alias').symlink_to('../outside')
        self.records([('alias/value', b'fixture')])
        with self.assertRaisesRegex(ValueError, 'escapes build root'):
            bootstrap.package_payload_audit(self.root, False)

    def test_shadow_body_is_never_opened(self):
        # A directory would fail if opened as a regular file. Exclusion must
        # happen before resolving or opening the recorded credential path.
        (self.root / 'etc/shadow').mkdir(parents=True)
        self.records([('etc/shadow', b'not read')])
        result = bootstrap.package_payload_audit(self.root, True)
        self.assertEqual(result['checked_paths'], 0)
        self.assertEqual(result['credential_paths_excluded'], ['/etc/shadow'])

    def test_builder_rejects_changed_database_or_account_setup(self):
        database = self.root / 'lib/apk/db/installed'
        database.write_text('original database\n')
        config = self.root / 'etc/passwd'
        config.parent.mkdir()
        config.write_text('fixture account\n')
        plan = {'roots': {'native': str(self.root)},
                'root_DB_SHA256': {'native': builder.sha(database)},
                'native_config_SHA256': {'etc/passwd': builder.sha(config)}}
        builder.check_roots(plan)
        database.write_text('changed database\n')
        with self.assertRaisesRegex(ValueError, 'database changed'):
            builder.check_roots(plan)
        database.write_text('original database\n')
        config.write_text('changed account\n')
        with self.assertRaisesRegex(ValueError, 'Native setup changed'):
            builder.check_roots(plan)


if __name__ == '__main__':
    unittest.main()
