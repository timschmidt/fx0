#!/usr/bin/env python3
"""Build a RAM-only Fx0 Linux/BusyBox diagnostic Android v0 image.

No device access or flashing. The initramfs offers a root USB serial shell and
read-only HTTP diagnostic logs on the isolated USB link (172.16.42.1).
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import struct

INIT = r'''#!/bin/sh
/bin/busybox --install -s /bin
export PATH=/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /sys/kernel/config /sys/kernel/debug /www
mount -t devpts devpts /dev/pts
mount -t debugfs debugfs /sys/kernel/debug
mount -t configfs configfs /sys/kernel/config
exec >/dev/kmsg 2>&1
echo 'Fx0 RAM diagnostic init started'
mkdir -p /sys/kernel/config/usb_gadget/fx0
cd /sys/kernel/config/usb_gadget/fx0 || exec sh
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
mkdir -p strings/0x409
echo fx0-diagnostic > strings/0x409/serialnumber
echo 'Nura Fx0 development' > strings/0x409/manufacturer
echo 'Fx0 Linux diagnostic' > strings/0x409/product
mkdir -p configs/c.1/strings/0x409
echo 'NCM networking and serial diagnostics' > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower
mkdir -p functions/ncm.usb0 functions/acm.usb0
echo 02:46:58:30:00:01 > functions/ncm.usb0/dev_addr
echo 02:46:58:30:00:02 > functions/ncm.usb0/host_addr
ln -s functions/ncm.usb0 configs/c.1/
ln -s functions/acm.usb0 configs/c.1/
for i in $(seq 1 60); do
    udc=$(ls /sys/class/udc | head -n 1)
    test -n "$udc" && break
    sleep 1
done
echo "$udc" > UDC
ip link set usb0 up
ip address add 172.16.42.1/24 dev usb0
cd /
httpd -f -p 172.16.42.1:80 -h /www &
(
    while :; do
        setsid sh -c 'exec </dev/ttyGS0 >/dev/ttyGS0 2>&1; stty sane; exec cttyhack sh'
        sleep 1
    done
) &
while :; do
    dmesg > /www/dmesg.txt.tmp && mv /www/dmesg.txt.tmp /www/dmesg.txt
    { uname -a; cat /proc/cmdline; cat /proc/meminfo; cat /proc/cpuinfo; cat /proc/partitions; ip address; cat /sys/kernel/debug/devices_deferred 2>/dev/null; } > /www/status.txt.tmp
    mv /www/status.txt.tmp /www/status.txt
    {
        printf '\033[2J\033[H'
        echo 'Fx0 Linux RAM diagnostic: USB status'
        uname -r
        echo 'UDC devices:'
        ls /sys/class/udc
        echo 'Gadget state:'
        cat /sys/class/udc/*/state 2>/dev/null
        echo 'Network:'
        ip -brief address show usb0 2>/dev/null || ip address show usb0
        echo 'Deferred probes:'
        head -n 8 /sys/kernel/debug/devices_deferred 2>/dev/null
        echo 'Recent USB/probe messages:'
        dmesg | grep -Ei 'usb|ulpi|ci_hdrc|defer|error|failed' | tail -n 18
    } >/dev/tty0 2>&1
    sleep 10
done
'''


def archive(entries):
    """Canonical newc records, including zero padding and trailer."""
    out = bytearray()
    for ino, (name, mode, data) in enumerate(entries + [('TRAILER!!!', 0, b'')], 1):
        encoded = name.encode() + b'\0'
        values = [ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(encoded), 0]
        out += b'070701' + ''.join(f'{x:08x}' for x in values).encode() + encoded
        out += bytes((-len(out)) % 4)
        out += data
        out += bytes((-len(out)) % 4)
    return bytes(out)


def make_image(kernel, dtb, ramdisk, cmdline):
    if dtb[:4] != b'\xd0\x0d\xfe\xed':
        raise ValueError('Not a flattened device tree')
    if len(kernel) < 48 or struct.unpack_from('<I', kernel, 36)[0] != 0x016f2818:
        raise ValueError('Not an ARM zImage')
    command = cmdline.encode()
    if len(command) >= 512:
        raise ValueError('Diagnostic command line must fit legacy header')
    payload = kernel + dtb
    page = 2048
    digest = hashlib.sha1()
    for data in (payload, ramdisk, b''):
        digest.update(data)
        digest.update(struct.pack('<I', len(data)))
    header = b'ANDROID!' + struct.pack('<10I', len(payload), 0x8000, len(ramdisk), 0x02000000, 0, 0x00f00000, 0x01e00000, page, 0, 0)
    header += b'fx0-diagnostic'.ljust(16, b'\0') + command.ljust(512, b'\0') + digest.digest().ljust(32, b'\0') + bytes(1024)
    pad = lambda data: data + bytes((-len(data)) % page)
    return pad(header) + pad(payload) + pad(ramdisk)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'dtb', 'busybox', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--simplefb', action='store_true', help='Use lk2nd inherited framebuffer for diagnostic console; requires built-in simpledrm')
    a = p.parse_args()
    busybox = a.busybox.read_bytes()
    if busybox[:6] != b'\x7fELF\x01\x01' or struct.unpack_from('<H', busybox, 18)[0] != 40:
        p.error('BusyBox must be a little-endian ARM ELF32 executable')
    phoff = struct.unpack_from('<I', busybox, 28)[0]
    phsize, phnum = struct.unpack_from('<HH', busybox, 42)
    if any(struct.unpack_from('<I', busybox, phoff + i * phsize)[0] == 3 for i in range(phnum)):
        p.error('BusyBox must be static (no PT_INTERP)')
    entries = [(d, stat.S_IFDIR | 0o755, b'') for d in ('bin', 'dev', 'proc', 'sys', 'tmp', 'www')]
    entries += [('bin/busybox', stat.S_IFREG | 0o755, busybox), ('bin/sh', stat.S_IFLNK | 0o777, b'busybox'), ('init', stat.S_IFREG | 0o755, INIT.encode())]
    ramdisk = gzip.compress(archive(entries), mtime=0)
    cmdline = 'console=ttyMSM0,115200 earlycon rdinit=/init loglevel=8 ignore_loglevel panic=60 lk2nd.pass-ramoops=zap'
    if a.simplefb:
        cmdline += ' console=tty0 lk2nd.pass-simplefb=autorefresh'
    data = make_image(a.kernel.read_bytes(), a.dtb.read_bytes(), ramdisk, cmdline)
    with a.output.open('xb') as f:
        f.write(data)
    print(json.dumps({'file':a.output.name, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest(), 'ramdisk_bytes':len(ramdisk), 'cmdline':cmdline}, indent=2))


if __name__ == '__main__':
    main()
