# Native eMMC regular-file integrity trial

`worker.py` tests a bounded synthetic file on the installed r50 ext4 root.
It opens no block device for writing and changes no mount, CPU, charging or
network policy. The full storage, power-loss, update and reliability acceptance
requirements remain separate.

The fixed workload overwrites one 512 MiB file in four rounds. Each 512-byte
sector carries the run UUID, round/complement and absolute sector index, with
deterministic payload bytes. This detects stale rounds, sector misdirection and
ordinary byte corruption. The host computes all four expected SHA256 values
before launch. Every round writes through an aligned anonymous mapping with
`O_DIRECT`, calls `fsync`, closes, reopens with `O_DIRECT`, checks every byte and
compares the whole-file checksum. The final directory is also synchronized.
Whole-device block counters must account for at least the tested read/write
volume; other services may contribute additional sectors.

The worker requires the exact installed kernel, native boot ID, untainted
schedutil 300–787.2 MHz policy, root mount `/dev/mmcblk0p35` as read/write ext4, original root
partition geometry, non-removable MMC, USB input and two temperatures below
60°C. Existing filesystem errors reject. It starts only with the file capacity
plus a 2 GiB available-space reserve and checks the reserve, temperature, power,
taint, policy, boot and filesystem errors every 8 MiB. Its own elapsed-time
budget is 15 minutes. The trial directory must be root-owned mode 0700 on the
native root, with no symlink components; the payload is created exclusively.

Stage the reviewed worker in
`/var/tmp/fx0-emmc-integrity-<canonical UUID>/worker.py`, verify its SHA256,
and invoke it with `--run-id <UUID> --boot-id <exact current native boot ID>`.
The recorded launch uses one transient systemd service with a 900-second
runtime limit, 96 MiB memory limit, nice 10, idle I/O scheduling and a temporary
sleep inhibitor. Observe that exact unit and worker PID until terminal; an
observation timeout does not authorize another launch. No reboot is part of
this test.

Four host tests use real direct I/O against disposable regular files and check
close/reopen/readback, sector tags, deliberate bit flips, sector aliasing, stale
rounds and truncated reads:

```sh
python3 -m unittest discover -s tests -p 'test_emmc_integrity.py' -v
```

The host controls require Linux and a temporary-file filesystem that supports
`O_DIRECT`; they do not substitute buffered I/O or silently skip those checks.

Successful completion leaves `payload.bin` and the exact final hash for a
later cross-boot read. `complete-awaiting-persistence` does not qualify
cross-boot or power-loss retention. Preserve the host run manifest and report;
after an independently authorized boot, bind the changed boot ID, validate the
stored worker and file length, and directly read/verify the retained fourth
pattern against the host hash. Remove only this trial's files after that check.
Stopping the finished transient unit does not remove the file. File flushing
and direct I/O alone do not prove survival of sudden power loss or eMMC-internal
cache behavior. Durations include pattern generation, integrity checks and
other system activity; they are not isolated storage benchmarks.

The first native r50 run passes all four rounds, totaling 2 GiB written and
directly verified in 417.83 seconds, with 512 reported temperature samples of
39–45°C, zero filesystem errors and no new storage kernel errors. The original
boot/hash/policy/services remain intact; the final file awaits cross-boot
verification. See [native evidence](../../evidence/2026-11-08-emmc-native-integrity.json).
