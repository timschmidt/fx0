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
and does not promise survival of host power loss. Added logging changes host
timing and is unqualified on hardware. A logging error also stops transfer.
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
kernel failure or reliable transport claim follows. The current physical UI
question remains pending before another entry.

See [evidence](../../evidence/2026-11-09-ram-transfer-journal.json) and the
[latest failed attempt](../../evidence/2026-11-09-nfc-r59-transfer-timeout.json).


## Alternate r59 encoding

The first unconfirmed r59 request falls in the compressed kernel. The new XZ4 image changes 16,325 bytes in that 16 KiB frame while preserving the decoded kernel, appended DTB and compressed initramfs. The exact r59 ARM decompressor verifies all three encodings under QEMU. Physical transfer qualification remains open. [Encoding and verification](r59-xz4.md)


## lk2nd request-size comparison

Two temporary lk2nd images isolate the 32 KiB versus 16 KiB Fastboot request limit. Their raw ARM binaries differ only in four limit-immediate bytes, and their board table and configuration match. Sixteen mocked framing cases pass. Physical comparison will use the same previously stalled r59 payload. [Build and comparison](lk2nd-single-td.md)
