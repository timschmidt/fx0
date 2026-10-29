#!/usr/bin/env python3
"""Read-only host/device inventory and byte-verified Fx0 partition backups."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"/dev/block/mmcblk0p[0-9]+\Z")
NAME = re.compile(r"[A-Za-z0-9_-]+\Z")
CRITICAL = {
    "boot", "recovery", "laf", "aboot", "abootb", "sbl1", "sbl1b",
    "sbl2", "sbl3", "rpm", "rpmb", "tz", "tzb", "modem", "modemst1",
    "modemst2", "fsg", "fsc", "persist", "factory", "misc", "ssd",
    "DDR", "sdi", "sdib", "drm", "encrypt", "fota", "mpt", "rct", "sns",
}
PARTITIONS = r'''
for p in /dev/block/platform/*/by-name/* /dev/block/by-name/*; do
    test -e "$p" || continue
    t=$(readlink -f "$p") || exit 1
    b=${t##*/}
    n=$(cat "/sys/class/block/$b/size") || exit 1
    echo "${p##*/} $t $n"
done
'''
INVENTORY = {
    "properties": "getprop",
    "kernel": "uname -a; cat /proc/cmdline; cat /proc/version",
    "cpu_memory": "cat /proc/cpuinfo; cat /proc/meminfo",
    "partitions": "cat /proc/partitions; cat /sys/class/block/mmcblk0/size",
    "mounts": "cat /proc/mounts",
    "input": "cat /proc/bus/input/devices",
    "kernel_log": "dmesg",
    "power": (
        "for p in /sys/class/power_supply/*/uevent; do "
        'echo "$p"; cat "$p"; done'
    ),
    "framebuffer": (
        "for p in /sys/class/graphics/fb*/name /sys/class/graphics/fb*/modes "
        '/sys/class/graphics/fb*/virtual_size; do test -f "$p" || continue; '
        'echo "$p"; cat "$p"; done'
    ),
    "firmware_files": (
        "ls -l /system/etc/firmware /system/vendor/firmware "
        "/vendor/firmware /firmware/image /persist"
    ),
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def private_directory(path):
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path


def write_json(path, value):
    with path.open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")
    path.chmod(0o600)


def read_text(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def host_probe():
    devices = []
    for p in sorted(Path("/sys/bus/usb/devices").glob("*")):
        if read_text(p / "idVendor") != "1004":
            continue
        interfaces = []
        for interface in sorted(p.glob(p.name + ":*")):
            values = {
                k: read_text(interface / k)
                for k in ("bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol")
            }
            values["adb"] = list(values.values()) == ["ff", "42", "01"]
            interfaces.append(values)
        devices.append({
            "port": p.name,
            "vendor": "1004",
            "product": read_text(p / "idProduct"),
            "model": read_text(p / "product"),
            "interfaces": interfaces,
        })
    disk = shutil.disk_usage(ROOT)
    return {
        "time": utcnow(),
        "tools": {name: shutil.which(name) for name in ("adb", "fastboot", "pmbootstrap", "git")},
        "usb_device_nodes": Path("/dev/bus/usb").is_dir(),
        "lg_devices": devices,
        "free_bytes": disk.free,
        "git_worktree": subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        ).returncode == 0,
    }


class Adb:
    def __init__(self, serial, executable="adb", timeout=30):
        self.argv = [executable, "-s", serial]
        self.serial = serial
        self.timeout = timeout
        self.use_su = False
        self.text_transport = "exec-out"

    def run(self, *args):
        return subprocess.run(
            self.argv + list(args), capture_output=True, timeout=self.timeout,
            check=False,
        )

    def remote_command(self, command, root=False):
        prefix = "su 0 sh -c " if root and self.use_su else "sh -c "
        return prefix + shlex.quote(command)

    def shell(self, command, root=False):
        # Old adbd exec services do not reliably return the remote exit status.
        # Keep a status marker for text commands; binary reads use stream().
        wrapped = "(\n" + command + '\n)\nfx0_status=$?\necho\necho __FX0_EXIT__$fx0_status'
        result = self.run(self.text_transport, self.remote_command(wrapped, root))
        if self.text_transport == "exec-out" and result.returncode and b"closed" in result.stderr:
            self.text_transport = "shell"
            result = self.run("shell", self.remote_command(wrapped, root))
        if result.returncode:
            return result
        if self.text_transport == "shell":
            result = subprocess.CompletedProcess(result.args, result.returncode, result.stdout.replace(b"\r\n", b"\n"), result.stderr)
        marker = re.search(rb"\n__FX0_EXIT__([0-9]+)\r?\n?\Z", result.stdout)
        if not marker:
            return subprocess.CompletedProcess(result.args, 1, result.stdout, result.stderr)
        return subprocess.CompletedProcess(result.args, int(marker[1]), result.stdout[:marker.start()], result.stderr)

    def identify(self, need_root=False):
        state = self.run("get-state")
        if state.returncode or state.stdout.strip() != b"device":
            raise RuntimeError("Selected ADB device is not connected and authorized")
        result = self.shell("getprop ro.product.model; getprop ro.product.device; getprop ro.product.name")
        if result.returncode:
            raise RuntimeError("Cannot read selected device identity")
        identity = result.stdout.decode(errors="replace").splitlines()
        if not any(re.search(r"\b(lgl25|madai|fx0)\b", x, re.I) for x in identity):
            raise RuntimeError("Selected device does not identify as an LG Fx0 LGL25/madai")
        user = self.shell("id")
        if not user.returncode and re.search(rb"\buid=0\b", user.stdout):
            self.use_su = False
        elif need_root:
            # The stock shell must support this form. Never change adbd or flash
            # a recovery automatically just to obtain access.
            self.use_su = True
            candidate = self.shell("id", root=True)
            if candidate.returncode or not re.search(rb"\buid=0\b", candidate.stdout):
                raise RuntimeError("Root shell unavailable; inspect stock su/recovery before backing up")
            # Stock su takes UID, executable, then shell arguments.
            self.use_su = True
        return {"serial": self.serial, "properties": identity, "time": utcnow()}

    def partition_map(self):
        result = self.shell(PARTITIONS, root=True)
        if result.returncode:
            raise RuntimeError("Could not discover named partitions")
        return parse_partitions(result.stdout.decode())

    def stream(self, block, destination):
        if not BLOCK.fullmatch(block):
            raise ValueError("Refusing unexpected block-device path")
        if self.text_transport == "shell":
            if self.use_su:
                raise RuntimeError("Legacy binary pull requires root adbd; restart adbd as root after checking ro.debuggable")
            # Stock KitKat adbd lacks exec-out. Its sync service handles block
            # devices and preserves every byte, unlike its terminal shell.
            with tempfile.TemporaryDirectory(prefix="fx0-pull-") as directory:
                image = Path(directory) / "partition.img"
                result = subprocess.run(self.argv + ["pull", block, str(image)], capture_output=True, timeout=1800, check=False)
                if result.returncode or not image.is_file():
                    raise RuntimeError("Legacy ADB sync partition read failed")
                with image.open("rb") as source:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
            return
        command = "cat " + block
        # stderr is separate from the binary stream. A timeout or nonzero exit
        # cannot yield a completed image or verification manifest.
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(self.argv + ["exec-out", self.remote_command(command, root=True)], stdout=destination, stderr=errors)
            try:
                status = process.wait(timeout=1800)
            except BaseException:
                process.kill()
                process.wait()
                raise
            if status:
                raise RuntimeError("ADB partition read failed; partial output retained without a verified image")


def parse_partitions(text):
    parts = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 3:
            raise ValueError("Unexpected partition discovery output")
        name, block, sectors = fields
        if not NAME.fullmatch(name) or not BLOCK.fullmatch(block):
            raise ValueError("Unexpected partition name or block-device path")
        if not sectors.isdecimal() or int(sectors) <= 0:
            raise ValueError("Invalid partition size")
        entry = {"block": block, "bytes": int(sectors) * 512}
        if name in parts and parts[name] != entry:
            raise ValueError("Conflicting partition aliases")
        parts[name] = entry
    if not parts:
        raise ValueError("No named partitions found")
    return parts


def digest_file(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def capture_image(adb, entry, path):
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists():
        raise FileExistsError("Existing backup image will not be overwritten")
    with partial.open("xb") as output:
        partial.chmod(0o600)
        adb.stream(entry["block"], output)
        output.flush()
        os.fsync(output.fileno())
    if partial.stat().st_size != entry["bytes"]:
        raise RuntimeError("Partition stream size mismatch; partial image is not verified")
    digest = digest_file(partial)
    # The destination directory is private and newly created by this run.
    partial.rename(path)
    return digest


def inventory(adb, parent):
    identity = adb.identify()
    directory = private_directory(parent)
    results = {"identity": identity, "commands": {}, "complete": False}
    for name, command in INVENTORY.items():
        result = adb.shell(command)
        (directory / (name + ".txt")).write_bytes(result.stdout)
        (directory / (name + ".stderr.txt")).write_bytes(result.stderr)
        for path in (directory / (name + ".txt"), directory / (name + ".stderr.txt")):
            path.chmod(0o600)
        results["commands"][name] = {"exit_code": result.returncode}
    results["complete"] = all(x["exit_code"] == 0 for x in results["commands"].values())
    write_json(directory / "inventory.json", results)
    return results


def backup(adb, directory, requested):
    identity = adb.identify(need_root=True)
    parts = adb.partition_map()
    names = sorted(set(requested) if requested else (set(parts) & CRITICAL))
    unknown = set(names) - set(parts)
    if unknown:
        raise ValueError("Requested partition not in live device partition map")
    if not requested and not {"boot", "recovery", "laf"} <= set(names):
        raise ValueError("Expected recovery partitions missing; inspect the live map before proceeding")
    required = sum(parts[name]["bytes"] for name in names) * 2 + 64 * 1024 * 1024
    directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(directory.parent).free < required:
        raise RuntimeError("Not enough free space for backup and independent reread")
    private_directory(directory)
    write_json(directory / "device.json", identity)
    write_json(directory / "partitions.json", parts)
    manifest = {"schema": 1, "time": utcnow(), "scope": "selected partitions", "images": [], "verified": False}
    for name in names:
        entry = parts[name]
        first = capture_image(adb, entry, directory / (name + ".img"))
        reread = directory / (name + ".reread.img")
        second = capture_image(adb, entry, reread)
        if first != second:
            raise RuntimeError("Partition changed between reads; both copies retained, no verified manifest")
        reread.unlink()
        manifest["images"].append({"name": name, "file": name + ".img", "sha256": first, **entry})
    if adb.partition_map() != parts:
        raise RuntimeError("Partition layout changed during backup")
    manifest["verified"] = True
    manifest["limits"] = "Matching rereads do not prove a globally consistent full-disk snapshot or restoration capability."
    write_json(directory / "manifest.json", manifest)
    return manifest


def verify_backup(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("verified") is not True or not manifest.get("images"):
        raise ValueError("Backup manifest is not complete and verified")
    for image in manifest["images"]:
        if not NAME.fullmatch(image["name"]) or image["file"] != image["name"] + ".img":
            raise ValueError("Invalid backup image name")
        path = directory / image["file"]
        if path.is_symlink() or path.stat().st_size != image["bytes"] or digest_file(path) != image["sha256"]:
            raise ValueError("Backup image verification failed")
    return len(manifest["images"])


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("probe")
    for name in ("inventory", "backup"):
        p = sub.add_parser(name)
        p.add_argument("--serial", required=True, help="Explicit ADB serial; not printed in summaries")
        p.add_argument("--adb", default="adb")
        p.add_argument("--output", type=Path, required=True, help="New private directory, usually under local/ or backups/")
        if name == "backup":
            p.add_argument("--partition", action="append", default=[], help="Exact live partition name; default selects critical partitions")
    p = sub.add_parser("verify-backup")
    p.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "probe":
        print(json.dumps(host_probe(), indent=2))
    elif args.action == "verify-backup":
        print(f"Verified {verify_backup(args.directory)} backup images")
    elif args.action == "inventory":
        result = inventory(Adb(args.serial, args.adb), args.output)
        failed = sum(x["exit_code"] != 0 for x in result["commands"].values())
        print(f"Inventory saved privately; {failed} commands require follow-up")
    else:
        result = backup(Adb(args.serial, args.adb), args.output, args.partition)
        print(f"Backed up and independently reread {len(result['images'])} partitions")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"fx0-device: {error}", file=sys.stderr)
        sys.exit(1)
