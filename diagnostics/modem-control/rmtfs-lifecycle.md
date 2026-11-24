# RMTFS daemon lifecycle and remoteproc ownership

The patch keeps remoteproc ownership independent of QRTR registration. The
pinned 6.18.59 source takes one power reference on each successful `start`,
including when the remote processor is already running. A second start during
QRTR recovery would therefore need a second stop. The daemon now queues one
start after publishing and preserves that reference while republishing QRTR.
A successful start is paired with one stop when the daemon shuts down.

The optional `-s` path allocates a worker and completion pipe before acquiring
a power reference. The worker serializes state writes and reports their
complete results. The daemon continues to process QMI requests during start
and stop. A failed or short state write returns an error. A failed stop can
leave a reference held by the kernel. SIGINT and SIGTERM use a flag and
`ppoll` to handle shutdown even when a signal arrives just before the wait.
A pending shutdown is observed before firmware start. Socket publication
failure closes the socket, and the remoteproc directory scans close each
descriptor through its owner.

Apply [the lifecycle patch](rmtfs-lifecycle.patch) after the
[Linux discovery patch](rmtfs-device-discovery.patch). Parsing `-s` now records
intent before opening resources, and the normal `-r -P` entry point keeps
remoteproc control external. The existing upstream unit runs `-s` with
`Restart=always`. The planned first fx0 RMTFS trial uses `-r -P` with separately
controlled firmware ownership.

Nineteen lifecycle cases pass on host ASan/UBSan and static ARM/QEMU. They run
the daemon's entry point and actual remoteproc worker against synthetic sysfs,
local sockets and simulated state writes. Real signals, threads and the poll
loop exercise startup, resource acquisition failures, publication failure,
short state writes, shutdown during start, and reconnect during start. Both
successful and failed reconnects retain one start and one stop. The successful
shutdown cases decode replies to ordinary QMI requests while each state write
is pending. They also check fd cleanup and unchanged fixture contents. Thirty-five
memory checks and fifteen selected protocol/storage regressions pass on each
platform.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/modem-control/check-rmtfs-lifecycle.py \
  --source /private/rmtfs-candidate --qrtr /private/qrtr-candidate \
  --harness tests/rmtfs-lifecycle-harness.c --output local/rmtfs-lifecycle-replay \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]'
```

Use a fresh output directory. The checker accepts JSON compiler and runner
prefixes for static ARM builds and isolated QEMU. The complete ARM build is an
858,724-byte hard-float static PIE with SHA-256
`281b6d358ff6ddc44523821d79876e362024eaf5168dce796760ce976336cfae`.
All eleven persistent linker inputs match previously authenticated package
members. The full binary's unsupported-option invocation exits before device
or socket access. Live driver behavior, failure timing, firmware ownership,
physical modem operation and packaging still require qualification.

A fresh read-only phone sample confirms installed r50 and UPower r5, the
original boot hash and rail settings, active Sway and a disabled modem. The
prepared offline probe image matches its recorded hash. Its physical entry
and return still require the current boot's display and touch baseline.
[Manifest](../../manifests/rmtfs-lifecycle-candidate.json) ·
[Evidence](../../evidence/2026-11-10-rmtfs-lifecycle-candidate.json)
