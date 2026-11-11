# Native USB bulk-transfer comparison

The native r50 upload failure reproduces independently of SSH. The same phone,
cable, host controller and native boot pass the demanding cases on physical
port `1-7` and fail the pseudorandom upload on `1-14`, including after a return
to that port. This identifies a usable connection for further bringup; it does
not identify the electrical or software cause, establish long-term reliability,
or qualify the separate Fastboot transport.

## Controlled observations

The phone stays on installed kernel r50 and Sxmo r6 throughout. Host Linux
7.2.11 uses `cdc_ncm` on the AMD X370 controller at `0000:02:00.0`. Every tested
connection negotiates 480 Mbit/s. Both ports have the same recorded NCM
parameters, including 16,384-byte input/output limits and a 14,848-byte padding
threshold. The original connection has host autosuspend disabled already.
No package, service, driver, sysfs/register, network-profile, route or DNS
configuration is changed by these probes. The owner moves the same cable.

All 4 MiB periodic streams repeat bytes 0 through 255. Pseudorandom streams
concatenate `SHA256(b'fx0-usb-bulk-entropy-v1' + index.to_bytes(4, 'little'))`.
The native receiver hashes bytes incrementally and stores no payload. Exact
whole-stream hashes are required for a pass; a host send count is not delivery
proof.

| Connection and case | Native result | Host TX-error increment during sampled interval |
| --- | --- | --- |
| Initial `1-14`, periodic 4 MiB, TCP port 49161 | Complete; exact hash | 0 |
| Initial `1-14`, pseudorandom 4 MiB, TCP port 49162 | Incomplete; 1,107,568 bytes before EOF | 8 |
| Initial `1-14`, periodic 4 MiB, TCP port 49162 | Complete; exact hash | 0 |
| Initial `1-14`, pseudorandom 4 MiB, TCP port 49161 | Incomplete; 343,176 bytes at native deadline | 3 |
| Moved to `1-7`, periodic 4 MiB | Complete; exact hash | 0 |
| `1-7`, pseudorandom 4 MiB | Complete; exact hash | 0 |
| `1-7`, normal unpaced SSH upload, 4 MiB | Complete; exact hash | 0 |
| `1-7`, pseudorandom 16 MiB | Complete; exact hash | 0 |
| `1-7`, exact 6,330,368-byte r59 XZ4 image as data | Complete; exact hash | 0 |
| Returned to `1-14`, identical pseudorandom 4 MiB | Incomplete; 1,511,712 bytes at native deadline | 9 |

The native raw receiver takes about 0.24 seconds for each successful 4 MiB
periodic case and 1.16 seconds for the 16 MiB case. The r59 image hash is
`6ccb35ccfc6637902951314f47b61a9925c33eb5b8d163ec1c3b0db8fe1c7020`.
Those image bytes are hashed only: no bootloader download, readback, BOOT,
flash, reboot or kernel execution occurs.

Full NCM blocks also pass: the two original periodic transfers increment
`tx_reason_ntb_full` by 250 and 264. A generic maximum-NTB failure is therefore
not established. TCP_INFO during pseudorandom failure shows loss/retransmission
and congestion-window collapse. Host logs contain transmit-queue watchdogs.
These observations do not establish on-wire CRC errors or their cause. Sampled
counter deltas end with the host socket phase and can omit later cleanup events.

Supporting controls on the original connection pass a 4 MiB SSH download with
an exact host hash. The identical 4 MiB pseudorandom payload passes Wi-Fi SSH
and native hashing. Earlier USB SSH uploads fail unpaced and paced; a 4 KiB
end-to-end acknowledged window also fails. Pacing and a smaller outstanding
window are not demonstrated workarounds. All delivered prefixes checked by the
probe match the expected bytes.

## Bounded receiver and lifecycle

[`receive.py`](receive.py) accepts one TCP connection on an explicit private
USB IPv4 address. It has a maximum 16 MiB size and 30-second deadline; the
physical raw tests use 20 seconds. It emits `READY` only after listening,
records a terminal failure on exceptions, and reports the length/hash to the
sender only after complete reception. Run it as the ordinary phone user from
RAM, with an owned private directory for `--record`:

```sh
python3 receive.py --address 172.16.42.1 --port 49160 \
  --bytes 4194304 --deadline 20 --record /run/user/10000/PROBE/result.json
```

Keep the management SSH session in the foreground for the receiver's entire
lifetime. The first detached launcher exits before a valid application receipt;
its stale listening record and absent PID are retained and that attempt is
excluded. Foreground Wi-Fi management fixes the harness lifecycle. No native
package or service is installed to run this receiver.

The first acknowledged-SSH helper also leaves a stale `reading` state after
its host connection closes. Its native PID is independently absent; the last
recorded byte count is a consumed-prefix observation, not a completion claim.
The corrected public receiver records exceptions explicitly. A local directory
guard typo on the first new-port SSH invocation fails before any network
process starts, then is corrected. A final nested-output wrapper initially drops some fields in its saved report;
an isolated namespace fixes the wrapper and the read-only check is repeated.
These harness failures are retained.

After a timeout, inspect the same host process/session and native PID. Do not
start a replacement from an observation timeout. Collect the native receipt
over the independent management connection; verify terminal processes and no
owned listeners, fsync the metadata archive on the host, then remove only the
owned RAM files. The three phase archives cover 16 JSON receipts and an empty setup log,
including the excluded setup receipt. No proprietary data or private key is exported.

## Next transfer procedure

The owner restores the working port `1-7` after the A/B/A comparison. Identify
that physical path and the pinned phone identity again before a new operation;
USB device numbers change on reconnect. Both temporary lk2nd comparison arms
must use the same `--usb-port 1-7`. Their existing fresh-generation, exact
readback and single-BOOT guards remain in force. The native image-data result
is not Fastboot readback or a Linux boot result. That physical qualification,
reboot/update/recovery reliability and wider hardware acceptance remain open.

The final native USB readback checks the original boot/database/world/module,
unchanged Sway and notification processes, idle vibrator/cameras/NFC, original
1.15 V APC target and complete probe cleanup. The Sxmo r7 controller remains
staged and unstarted pending its separate installation approval. The current
boot's physical UI gate is not filled using an earlier NFC answer.
[Evidence](../../evidence/2026-11-11-usb-native-bulk.json)
