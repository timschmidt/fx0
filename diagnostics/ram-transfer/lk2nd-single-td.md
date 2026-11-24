# lk2nd Fastboot request-size comparison

The installed-source Fastboot code requests up to 32 KiB per HSUSB operation.
The USB device controller code uses 16 KiB transfer descriptors, so a full
request uses two. Its completion handler loops while a descriptor reports
`ACTIVE`. A host timeout does not show whether that loop ran on the phone.
[Transfer failure and journal](README.md)

The candidate caps Fastboot reads and writes at 16 KiB per device request.
This removes descriptor chaining from the Fastboot data path while keeping
the same fastboot command framing and the same total image lengths. The
one-line patch uses the same source line for the limit, so the compiled
assertion locations match. [Patch](lk2nd-fastboot-single-td.patch)

Both builds use installed-source commit
`079eebe745de650df02e92fd9ca8d9fec5110c56`, force the secondary bootloader into
Fastboot and disable extlinux. They use the same MSM8226 configuration, one
LG Madai QCDT entry and the same Android header fields. Independent parsing
checks the boot checksum and the file-backed ARM ELF load. The raw images
differ by four instruction bytes. Each change replaces a 32 KiB immediate
with a 16 KiB immediate in `hsusb_usb_read` or `hsusb_usb_write`. The board
table, ramdisk, build configuration and every other raw LK byte match.

| Temporary bootloader | Image SHA-256 | Bytes |
| --- | --- | ---: |
| 32 KiB control | `d85a1dbb3720e468504c1a14a417d79191e3e6852013d41ed230139005da09ef` | 258,064 |
| 16 KiB candidate | `60a88b8bedfe6c3f18815493701e0f981e0af45eb2ddfb2ca2e05073bf2d938b` | 258,064 |

The host check compiles the actual Fastboot download and upload functions with
mocked USB completion. Eight valid payload sizes run per build, including both
r59 encodings and sizes on either side of 16 and 32 KiB. The checks cover the
DATA frames, complete acknowledgements, contiguous requests and their total
sizes. Descriptor counts follow from the driver’s 16 KiB limit. DMA, IRQ
completion and physical USB behavior remain open.

```sh
base=local/lk2nd-fastboot-td-01
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/ram-transfer/check-lk2nd-td-budget.py \
  --control "$base/control-source" --candidate "$base/single-td-source" \
  --output local/lk2nd-td-budget-recheck
```

The prepared comparison uses temporary lk2nd sessions entered through the
verified stock Fastboot RAM-boot path. Use the same XZ3 r59 payload, host port,
cable and 16 KiB host requests for both sessions. Compare the data-only
transfer journals and exact readback when a transfer completes. Record USB
speed and identify each temporary bootloader session from its launch receipt.
The first timeout leaves delivery of its final request unknown. Terminal
status and the existing recovery procedure govern return to native before a
separate trial. A Linux BOOT is unnecessary for the transfer comparison.

## Run the comparison

The host runner verifies all three pinned images before USB work. Use the
current r50 display and touch check as the native baseline. For each arm,
power the phone fully off, unplug USB, then hold Volume Up while reconnecting
the same cable to the same host port. The runner queries the selected device
for stock product `MADAI` and protocol `0.5` before issuing a temporary boot.
It verifies a fresh USB device generation and the temporary
`fx0-usb-td-pair` version. Both temporary builds report that version, so
the launch receipt identifies which image ran.

```sh
runner=diagnostics/ram-transfer/run-lk2nd-td-trial.py
base=local/lk2nd-td-physical
python3 "$runner" --check-inputs
python3 "$runner" --arm control --usb-port 1-14 --output "$base/control"
# Verify the native return, then enter stock Fastboot again.
python3 "$runner" --arm single_td --usb-port 1-14 --output "$base/single-td"
python3 "$runner" --compare "$base/control" "$base/single-td"
```

Each arm runs one transfer of the original 6,809,600-byte XZ3 r59 image
with 16 KiB host requests and 5 ms pacing. A completed transfer requires
exact readback. The runner preserves the process receipts, separate download
and readback counts, and any unconfirmed request. It waits for the transfer
process to exit before touching USB again. A terminal timeout gets one
identified USB reset, followed by verification of the temporary loader and a
normal reboot. A successful readback goes directly to the normal reboot.
The receipt verifies native USB re-enumeration. Check r50 boot files and
services separately after each arm.

The offline comparison checks both launch receipts, the common payload,
port, negotiated speed, host settings, nonoverlapping session times and
readback hashes. It reports each outcome independently. It cannot establish
what happened on the wire during an unconfirmed request.

The controller and comparison pass 20 host tests, alongside 18 existing
transfer tests. Both physical sessions remain pending. [Image manifest](../../manifests/lk2nd-fastboot-single-td.json) ·
[Build evidence](../../evidence/2026-11-10-lk2nd-fastboot-single-td.json) ·
[Trial preparation](../../evidence/2026-11-10-lk2nd-fastboot-td-trial-preparation.json)
