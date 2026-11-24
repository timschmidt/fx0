# Passive RMTFS RAM trial

The image pairs the exact installed r50 zImage with the verified RMTFS DTB.
It preserves all ten files, directories and modes from the qualified
reconstructed r50 RAM archive, including the 180-second return timer and
USB console. The reconstructed and installed zImages have distinct hashes.
The installed zImage supplies the kernel identity used for QRTR validation.
[Qualified RAM archive](../../evidence/2026-11-08-r50-ram-baseline.json)

The DTB splits the original 4 MiB reservation into a 2.5 MiB reservation and
the 1.5 MiB RFSA region at `0x0fd80000`, with client ID 1. The total reserved
interval and all other device-tree properties are preserved. MSS is disabled.
The RFSA region has `no-map` and the driver manages its mapping. This DTB
requests no SCM VMID reassignment. [Description verification](verify-rmtfs-description.py)

The kernel already includes `qcom_rmtfs_mem`. The only packaged module is
the signed `qrtr.ko` core, with signature enforcement enabled in the kernel
command line. All 119 imported CRCs match the exact installed kernel and
its CMS signature matches the kernel trust certificate. The core brings up
the kernel QRTR name service. No SMD, MHI, or tunneled QRTR transport is loaded.

## Rebuild on the host

Use the locally retained r50 backup and the [verified ARM daemon](rmtfs-lifecycle.md).
The observer uses `qrtr-local-rmtfs.c` with the ARMv7 musl toolchain, static
linking and the verified target runtime inputs in `lookup-build.json`.
`local/rmtfs-passive-ram-01/build-lookup.py` records the exact build recipe
used with the retained toolchain. All binaries and the backup stay local.

```sh
base=local/rmtfs-passive-ram-01
retained=local/modem-probe-preparation-01
dt=local/modem-firmware-audit-01/rmtfs-description-check-03
export PYTHONDONTWRITEBYTECODE=1

python3 diagnostics/modem-control/verify-passive-qrtr.py \
  --backup local/upower-r5-deploy-01/host-backup/before-files.tar.gz \
  --retained "$retained" --output "$base/qrtr-recheck"
python3 diagnostics/modem-control/build-passive-rmtfs-image.py \
  --qualified-image local/kernel-reconstruction/fx0-r50-reconstructed-ram.img \
  --native-kernel "$retained/retained-r50/boot/vmlinuz" \
  --baseline-dtb "$dt/baseline.dtb" --rmtfs-dtb "$dt/candidate.dtb" \
  --rmtfs local/rmtfs-lifecycle-01/arm-clean-runtime-final/rmtfs \
  --qrtr "$base/qrtr-recheck/qrtr.ko" --observer "$base/qrtr-local-rmtfs" \
  --observer-build "$base/lookup-build.json" --output "$base/recheck.img"
python3 tests/test_rmtfs_passive.py -v
```

## Physical acceptance

Use a verified RAM transfer with byte-exact readback. Once the image starts,
connect the USB serial console and run `/bin/rmtfs-passive` once. Init leaves
the worker idle and owns the return timer. The worker refuses entry at 120
seconds of uptime and checks the kernel notes, signature setting, DT,
payload digests, RAM mounts, module set, RFSA address, size and client ID.
It removes the legacy `/dev/mem` node from the RAM devtmpfs and requires the
UIO fallback to be absent. Storage is an empty RAM directory and the daemon
uses read-only mode without remoteproc management.

Capture `RMTFS_LOCAL_SERVICE_ABSENT`, `RMTFS_LOCAL_SERVICE_PRESENT`,
`RMTFS_RFSA_OPEN`, `RMTFS_LOCAL_SERVICE_ABSENT` and `RMTFS_PASSIVE_PASS`.
The observer sends a local name-service lookup for service 14, version 1,
instance 0. It sends no RMTFS request. The worker checks the live RFSA
descriptor, waits for clean SIGTERM exit, checks withdrawal, and unloads
QRTR. If a step fails, retain the output and allow the independent timer to
return the phone to installed r50. Verify the native boot image, rail,
services and display and touch after return.

Two host builds matched byte for byte. ARM/QEMU checked the packaged BusyBox
shell syntax and the observer's early CLI rejection. Host fixtures covered
notification validation, publication order, single-use execution and refusal
before mutation. The image is unstaged. Live RFSA mapping, QRTR publication,
native return, modem firmware and GNSS remain unqualified by this trial.
[Evidence](../../evidence/2026-11-10-rmtfs-passive-ram.json)
