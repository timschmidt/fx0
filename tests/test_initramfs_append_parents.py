# SPDX-License-Identifier: MIT
"""Regression for the real early-governor image's missing /usr/libexec."""
import importlib.util
from pathlib import Path
import stat
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "diagnostics"
          / "kernel-maintenance" / "initramfs_append.py")
spec = importlib.util.spec_from_file_location("append_layout", SOURCE)
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
DIR = stat.S_IFDIR | 0o755
FILE = stat.S_IFREG | 0o444


class AppendParents(unittest.TestCase):
    def setUp(self):
        self.existing = {"usr": DIR, "usr/bin": DIR,
                         "init": stat.S_IFREG | 0o755}

    def test_actual_missing_governor_parent(self):
        with self.assertRaisesRegex(ValueError, "usr/libexec"):
            layout.require_append_parents(self.existing, [
                ("usr/libexec/fx0-cpufreq-userspace.ko", FILE, b"signed module")])

    def test_corrected_existing_directory_and_init_replacement(self):
        layout.require_append_parents(self.existing, [
            ("init", stat.S_IFREG | 0o755, b"prefix"),
            ("usr/bin/fx0-cpufreq-userspace.ko", FILE, b"signed module")])

    def test_parent_must_precede_child(self):
        directory = ("usr/libexec", DIR, b"")
        child = ("usr/libexec/helper", FILE, b"helper")
        layout.require_append_parents(self.existing, [directory, child])
        with self.assertRaises(ValueError):
            layout.require_append_parents(self.existing, [child, directory])

    def test_file_and_symlink_are_not_canonical_directory_parents(self):
        for mode in [FILE, stat.S_IFLNK | 0o777]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                layout.require_append_parents(self.existing | {"usr/libexec": mode},
                                              [("usr/libexec/helper", FILE, b"")])

    def test_path_boundaries_and_duplicate_entries(self):
        for name in ["", ".", "/usr/bin/helper", "usr/../helper",
                     "usr//bin/helper", "usr/./bin/helper"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                layout.require_append_parents(self.existing, [(name, FILE, b"")])
        with self.assertRaises(ValueError):
            layout.require_append_parents(self.existing,
                                          [("init", FILE, b"")] * 2)

    def test_replaced_directory_cannot_parent_later_entry(self):
        with self.assertRaises(ValueError):
            layout.require_append_parents(self.existing, [
                ("usr/bin", FILE, b"replacement"),
                ("usr/bin/helper", FILE, b"helper")])


if __name__ == "__main__":
    unittest.main()
