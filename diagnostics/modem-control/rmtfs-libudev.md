# Verified libudev provider and ARM link inputs

A new complete ARM RMTFS diagnostic build uses a verified eudev static library
and clean target GCC/musl runtime files. Every persistent linker input matches
bytes inside an independently verified signed package with a clean recipe
commit. Five real libudev API cases pass under isolated ARM/QEMU with synthetic
sysfs. The full daemon runs only its early unsupported-option exit. Nothing is
uploaded, installed or started as a service on the phone.

The original systemd 261 archive and all earlier builds remain intact. Their
`-dirty` metadata is not retroactively resolved by this new build. A newer
systemd package download was also rejected: its package signing key was not
established in the selected trust store, and its inspected recipe field still
said `-dirty`. No package payload from that attempt is used or executed.
An initial fetch used the wrong key-directory layout; all rejected attempts and
the corrected trust-store setup are retained. Signature verification is never
bypassed and no new signing key is trusted.

The replacement is [Alpine eudev 3.2.14-r6 for armv7](https://pkgs.alpinelinux.org/package/v3.24/main/armv7/eudev-libs),
whose library is also used by Alpine's RMTFS package. The signed development
and library APKs identify clean recipe
[4133df77](https://github.com/alpinelinux/aports/tree/4133df77f8cc98f92679b79de07736589fa48bff/main/eudev).
All seven recipe files match their Git blobs. The public 3.2.14 source archive
matches the recipe's SHA512, as do its four source sidecars. Only the public
static archive, header and pkg-config file are selected as build inputs.
No systemd/udevd service or target package is replaced.

RMTFS uses exactly five libudev functions: `udev_new`,
`udev_device_new_from_devnum`, `udev_device_get_sysattr_value`,
`udev_device_unref` and `udev_unref`. The source audit follows device-number
lookup to sysfs and attribute reads. The
[probe](../../tests/libudev-rmtfs-probe.c) executes those functions with a fake
character device's read-only sysfs tree and an empty isolated /run. It checks
normal/cached attributes, missing attributes/devices and 32 context/device
creation-release cycles. There is no real device node, memory mapping, udev
database, firmware or provisioning data in the fixture. Syscall traces and
unchanged fixture hashes accompany the five passing cases.

The first new link exposed an additional provenance gap: runtime objects bundled
with the cross compiler belonged to a `gcc-armv7` package whose recipe field is
also `-dirty`. The final build selects target GCC runtime files explicitly with
`-B/target/usr/lib/gcc/armv7-alpine-linux-musleabihf/15.2.0/` before the other
search paths. All persistent LOAD entries match signed `gcc`, `libgcc-static`,
`musl-dev` or eudev development package members. GCC 15.2.0-r5 records recipe
`423a8ad043d07f2c7546c8ec3e2b0384cda360ae`; musl 1.2.6-r3 records
`8f79d39391b46d6dbf1800fb68b8212a21d5ee2e`. The compiler executable's own recipe
identity remains unqualified; its retained hash is unchanged. This checkpoint
does not prove a clean compiler build or bit-for-bit reproducibility.

The 785,476-byte final daemon is ELF32 ARM hard-float static PIE, with no
interpreter or NEEDED library. Header tracing selects the new provider header.
Link maps exclude the old libudev archive, systemd and ucontext. The source
includes the prior storage/handler/codec fixes and the generator-produced RMTFS
header. It uses the same public API and protocol; eudev is a static client
library here, with native systemd/udevd unchanged.

For an equivalent build, prepare the corrected RMTFS/QRTR sources and verified
provider archive/header, then use a cross compiler and read-only target sysroot:

```sh
armv7-alpine-linux-musleabihf-gcc --sysroot=/target \
  -B/target/usr/lib/gcc/armv7-alpine-linux-musleabihf/15.2.0/ \
  -B/target/usr/lib/ -static -O2 -g -fstack-protector-strong \
  -I/provider -I/qrtr/include \
  /rmtfs/qmi_rmtfs.c /rmtfs/rmtfs.c /rmtfs/rproc.c \
  /rmtfs/sharedmem.c /rmtfs/storage.c /rmtfs/util.c \
  /qrtr/lib/qmi.c /qrtr/lib/qrtr.c /qrtr/lib/logging.c \
  /provider/libudev.a -lpthread -Wl,-Map=rmtfs.map -o rmtfs
```

Build the probe with the same compiler/sysroot/provider, then run from the
repository root:

```sh
python3 diagnostics/modem-control/check-libudev-rmtfs.py \
  --probe /private/provider-probe --daemon /private/rmtfs \
  --output local/libudev-rmtfs-replay
```

Use a fresh output directory. The checker isolates networking,
mounts only its synthetic sysfs and executable inputs, and preserves syscall
traces. Recorded compiler/source roots are read-only; no signing-key home or
physical device is mounted.

This closes the selected library and linked runtime provenance gaps for this
diagnostic candidate. Compiler-executable recipe closure, distribution packaging
and static-library redistribution/relink materials still require work before
promotion. Shared-memory bounds, service/remoteproc ownership and physical
startup remain unqualified. The current display/touch gate is still pending.
All five private host provisioning payloads are separately reverified; no phone
command, reboot, module/package operation, firmware/radio action, provisioning
write or recovery-disk write occurs. See
[evidence](../../evidence/2026-11-09-rmtfs-libudev-candidate.json).
