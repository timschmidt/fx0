# RAM transfer failure journal

`scripts/transfer_fx0_ram.py` stages and verifies RAM bytes; it sends no BOOT,
flash, erase, reset or retry. Use a fresh private output directory and the
existing identified-device entry procedure. The latest r59 download failed
before verified readback or BOOT; its source/image and hardware status remain
unchanged by this host diagnostic.

The helper now writes `io.jsonl` for the download/upload framing. Every attempted
command, size/status read and data chunk has a flushed `started` event before
I/O, then `returned` or `failed`. Events contain a sequence, UTC, phase,
direction, requested byte count and data offset where applicable. Completion
adds elapsed seconds and a returned count; failure adds exception type, errno
and `actual_bytes: null`. Neither payload nor serial is written to this journal.
The existing identity probe runs separately and is outside this frame trace.

`result.json` retains the last event and the existing confirmed-byte progress.
On timeout, the failed request may have transferred a prefix. Do not interpret
its unknown count as zero, advance progress, resume the remainder, or send
upload/BOOT. A positive short OUT count is recorded separately and still aborts
immediately. Partial IN readback remains allowed within the requested bounds;
the final length, status and exact payload comparison are still required.

The append stream is flushed for live observation; it is not fsynced per event
and does not promise survival of host power loss. The XZ4 hardware attempt
records the complete prefix and the terminal timeout. Logging adds host work.
A logging error also stops transfer.
Do not attach a live syscall tracer to a blocked transfer: an earlier attachment
interrupted its syscall. Observation expiry never authorizes a reset or retry.
Recovery still requires authoritative terminal controllers and absent PIDs,
then separately identified device recovery. Full readback and live observers
remain prerequisites for a single BOOT.

Verification uses the real CLI and framed transfer with injected I/O. All 29
targeted tests pass, including ten failure boundaries from command write to
final upload status, partial delivery before error, partial readback, positive
short OUT, and trace failure before another I/O. They check visible starts,
unknown failed counts, exact successful readback, claim cleanup and no retries.
The previous helper fails the new metadata contract for both data and status
timeouts. Mutants that substitute zero for unknown or omit journal flushing
are rejected. The existing extracted lk2nd C framing tests cover five callback
modes; they stub UDC/DMA/cache/IRQ behavior.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s tests -p 'test_ram_transfer*.py' -v
```

The installed bootloader's reviewed USB sources exactly match commit
`079eebe745de650df02e92fd9ca8d9fec5110c56`. The selected host journal shows no
disconnect or reported controller error during the latest stalled download.
That limited record does not identify the root cause. No bootloader change,
kernel failure or reliable transport claim follows. The next physical entry needs the display and touch check for its current boot.

See [evidence](../../evidence/2026-11-09-ram-transfer-journal.json) and the
[first failed attempt](../../evidence/2026-11-09-nfc-r59-transfer-timeout.json).


## Alternate r59 encoding

The first unconfirmed r59 request falls in the compressed kernel. The new XZ4 image changes 16,325 bytes in that 16 KiB frame while preserving the decoded kernel, appended DTB and compressed initramfs. The exact r59 ARM decompressor verifies all three encodings under QEMU. On hardware XZ4 passes the original 512 KiB offset, then times out at 656 KiB before readback or BOOT. Both first-unconfirmed requests fall in their respective compressed kernels. [Encoding and verification](r59-xz4.md) · [Physical attempt](../../evidence/2026-11-10-nfc-r59-xz4-transfer-timeout.json)


## lk2nd request-size comparison

Two temporary lk2nd images isolate the 32 KiB versus 16 KiB Fastboot request limit. Their raw ARM binaries differ only in four limit-immediate bytes, and their board table and configuration match. Sixteen mocked framing cases pass. Physical comparison will use the same previously stalled r59 payload. [Build and comparison](lk2nd-single-td.md)


## Native Linux comparison and working physical port

A same-boot, same-cable A/B/A comparison reproduces payload-sensitive native
USB upload failure on `1-14`, passes on `1-7`, and fails again after returning
to `1-14`. The periodic-pattern controls pass on both ports. On `1-7`, ordinary
4 MiB SSH upload, 16 MiB pseudorandom raw upload and the exact 6,330,368-byte
r59 XZ4 image as unexecuted data all pass their full hashes with no sampled
transmit errors. The owner restores `1-7`; installed r50/r6 remains unchanged.

Use the freshly identified working path for later trials, including the same
`--usb-port 1-7` for both temporary lk2nd arms. No bootloader transfer or Linux
BOOT occurs in this comparison. A common cause for the native and Fastboot
failures, or reliable Fastboot operation on the new path, is not yet proved.
[Procedure, controls and limitations](../usb-native-bulk/README.md)
