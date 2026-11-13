"""Guard distro-owned files against a lower-priority package's payload."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'diagnostics/stable-update/apk_payload_ownership.py'
SPEC = importlib.util.spec_from_file_location('apk_payload_ownership', SOURCE)
ownership = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ownership)


class PayloadOwnership(unittest.TestCase):
    def setUp(self):
        self.database = ('P:distro-release\nV:62-r0\nC:old-control\no:distro-base\n'
                         'r:alpine-release distro-base\nF:etc\nR:issue\n'
                         'F:lib\nR:os-release\n\n')
        self.candidates = {p: dict(packages=['alpine-release'], expected=dict(kind='file'))
                           for p in ['/etc/issue', '/usr/lib/os-release']}
        self.incoming = {'alpine-release': dict(version='3.24.4-r0', checksum='new-control',
                                               origin='alpine-base', replaces=[], priority=0)}

    def retained(self):
        return ownership.retained_payloads(self.database, self.candidates, self.incoming)

    def test_distro_replacement_rule_retains_files_before_protected_config_processing(self):
        result = self.retained()
        self.assertEqual(set(result), set(self.candidates))
        self.assertEqual(result['/etc/issue']['owner_identity'], dict(version='62-r0', checksum='old-control'))
        self.assertEqual(result['/etc/issue']['owner_priority'], 0)
        self.assertEqual(result['/etc/issue']['incoming_priority'], -1)

    def test_incoming_valid_replace_wins_equal_priority(self):
        self.incoming['alpine-release']['replaces'] = ['distro-release']
        self.assertEqual(self.retained(), {})

    def test_higher_original_priority_retains_despite_reciprocal_replace(self):
        self.database = self.database.replace('r:alpine-release distro-base', 'q:2\nr:alpine-release distro-base')
        self.incoming['alpine-release'].update(replaces=['distro-release'], priority=1)
        self.assertEqual(set(self.retained()), set(self.candidates))

    def test_inconclusive_collision_refuses_even_when_bytes_might_match(self):
        self.database = self.database.replace('r:alpine-release distro-base\n', '')
        with self.assertRaisesRegex(AssertionError, 'Unresolved package file conflict'):
            self.retained()

    def test_versioned_replacement_refuses_instead_of_guessing(self):
        self.database = self.database.replace('r:alpine-release ', 'r:alpine-release>=3 ')
        with self.assertRaisesRegex(AssertionError, 'separate qualification'):
            self.retained()

    def test_selected_owner_requires_additional_qualification(self):
        self.incoming['distro-release'] = dict(version='63-r0', checksum='other-control')
        with self.assertRaisesRegex(AssertionError, 'Selected owner collision'):
            self.retained()

    def test_same_owner_upgrade_and_shared_directory_are_not_collisions(self):
        self.database = self.database.replace('P:distro-release', 'P:alpine-release')
        self.candidates['/etc'] = dict(packages=['alpine-release', 'another'], expected=dict(kind='directory'))
        self.assertEqual(self.retained(), {})

    def test_duplicate_owner_and_alias_escape_are_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'Multiple installed file owners'):
            ownership.retained_payloads(self.database + self.database.replace('P:distro-release', 'P:other'),
                                        self.candidates, self.incoming)
        with self.assertRaises(AssertionError):
            ownership.canonical('/usr/../etc/issue')


if __name__ == '__main__':
    unittest.main()
