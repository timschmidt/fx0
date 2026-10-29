"""Exercise binary backup failure modes without touching a physical device."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("fx0_device", Path(__file__).parents[1] / "scripts/fx0_device.py")
device = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device)


class FakeDevice:
    def __init__(self, mode="stable"):
        self.mode = mode
        self.reads = {}

    def identify(self, need_root=False):
        assert need_root
        return {"serial": "test-unit", "properties": ["LGL25"]}

    def partition_map(self):
        return {
            name: {"block": f"/dev/block/mmcblk0p{number}", "bytes": 512}
            for number, name in enumerate(("boot", "recovery", "laf"), start=1)
        }

    def stream(self, block, output):
        n = self.reads.get(block, 0)
        self.reads[block] = n + 1
        if self.mode == "failure":
            output.write(b"partial")
            raise RuntimeError("transport disconnected")
        if self.mode == "short":
            output.write(b"short")
        else:
            data = bytes(reversed(range(256))) if self.mode == "changing" and n else bytes(range(256))
            output.write(data * 2)


class PartitionDiscovery(unittest.TestCase):
    def test_sizes_and_duplicate_aliases(self):
        row = "boot\t/dev/block/mmcblk0p7\t16384\n"
        self.assertEqual(device.parse_partitions(row + row)["boot"]["bytes"], 8388608)

    def test_rejects_conflicts_and_non_partition_paths(self):
        rows = [
            "boot\t/dev/block/mmcblk0p7\t1\nboot\t/dev/block/mmcblk0p8\t1\n",
            "../boot\t/dev/block/mmcblk0p7\t1\n",
            "boot\t/dev/block/mmcblk0\t1\n",
            "boot\t/dev/block/mmcblk0p7;reboot\t1\n",
            "boot\t/dev/block/mmcblk0p7\t0\n",
            "su: not found\n",
            "",
        ]
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                device.parse_partitions(row)


class BackupVerification(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "backup"

    def test_binary_reread_and_offline_verification(self):
        adb = FakeDevice()
        manifest = device.backup(adb, self.directory, [])
        self.assertTrue(manifest["verified"])
        self.assertEqual(device.verify_backup(self.directory), 3)
        self.assertEqual(list(adb.reads.values()), [2, 2, 2])
        self.assertFalse(list(self.directory.glob("*.reread.img")))
        self.assertEqual((self.directory.stat().st_mode & 0o777), 0o700)
        for path in self.directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_disconnect_short_read_and_changing_partition_never_verify(self):
        for mode in ("failure", "short", "changing"):
            directory = Path(self.temporary.name) / mode
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                device.backup(FakeDevice(mode), directory, ["boot"])
            self.assertFalse((directory / "manifest.json").exists())
            self.assertTrue(list(directory.glob("*.img*")))

    def test_existing_backup_is_never_replaced(self):
        device.backup(FakeDevice(), self.directory, ["boot"])
        before = (self.directory / "boot.img").read_bytes()
        with self.assertRaises(FileExistsError):
            device.backup(FakeDevice("changing"), self.directory, ["boot"])
        self.assertEqual((self.directory / "boot.img").read_bytes(), before)

    def test_tampered_image_is_rejected(self):
        device.backup(FakeDevice(), self.directory, ["boot"])
        (self.directory / "boot.img").write_bytes(b"c" * 512)
        with self.assertRaises(ValueError):
            device.verify_backup(self.directory)

    def test_manifest_cannot_redirect_image_paths(self):
        device.backup(FakeDevice(), self.directory, ["boot"])
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["images"][0]["file"] = "../other.img"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            device.verify_backup(self.directory)

    def test_unknown_partition_is_rejected_before_creating_backup(self):
        with self.assertRaises(ValueError):
            device.backup(FakeDevice(), self.directory, ["userdata"])
        self.assertFalse(self.directory.exists())


class RemoteCommands(unittest.TestCase):
    def test_kitkat_exec_out_falls_back_to_shell_and_normalizes_terminal_lines(self):
        adb = device.Adb("test-unit")
        calls = []
        def old_daemon(*args):
            calls.append(args)
            if args[0] == "exec-out":
                return subprocess.CompletedProcess(args, 255, b"", b"error: closed\n")
            self.assertNotIn("printf", args[-1])
            return subprocess.CompletedProcess(args, 0, b"LGL25\r\n\r\n__FX0_EXIT__0\r\n", b"")
        adb.run = old_daemon
        result = adb.shell("getprop ro.product.model")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"LGL25\n")
        self.assertEqual(adb.text_transport, "shell")
        adb.shell("id")
        self.assertEqual([x[0] for x in calls], ["exec-out", "shell", "shell"])

    def test_remote_failure_is_detected_when_old_adbd_returns_zero(self):
        adb = device.Adb("test-unit")
        def emulate_old_adbd(*args):
            result = subprocess.run(["sh", "-c", args[-1]], capture_output=True, check=False)
            return subprocess.CompletedProcess(args, 0, result.stdout, result.stderr)
        adb.run = emulate_old_adbd
        failed = adb.shell("printf 'partial text'; exit 37")
        self.assertEqual(failed.returncode, 37)
        self.assertEqual(failed.stdout, b"partial text")
        passed = adb.shell("printf 'working'")
        self.assertEqual(passed.returncode, 0)
        self.assertEqual(passed.stdout, b"working")

    def test_multiline_commands_and_metacharacters_reach_remote_shell_intact(self):
        adb = device.Adb("test-unit")
        command = "printf '%s\\n' 'semi; dollar$ quote\"'\nprintf '%s' 'second'"
        result = subprocess.run(["sh", "-c", adb.remote_command(command)], capture_output=True, check=True)
        self.assertEqual(result.stdout, b'semi; dollar$ quote"\nsecond')

    def test_stream_rejects_device_path_injection(self):
        with self.assertRaises(ValueError):
            device.Adb("test-unit").stream("/dev/block/mmcblk0p1; reboot", io.BytesIO())


if __name__ == "__main__":
    unittest.main()
