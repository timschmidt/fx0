# Native CCI calibration qualification

This temporary GPL-2.0-only reader tests the maintained MSM8226 CCI driver
against the private calibration captured with the independent GPIO reader.
It does not require an EEPROM manufacturer or capacity compatible. It is a
bus/power qualification tool, not a permanent NVMEM or camera driver.

**Validation:** exact kernel 39 W=1 build/checkpatch and disabled-CCI guard pass.
The camera-DT RAM image has now booted. Active preflight, a 2560-byte read and
two independent 65536-byte reads pass; every byte matches the independent GPIO
capture. Copies on two host filesystems are verified. The supply returns low
after each read. CCI suspends before/between/after full reads, resumes for the
second, and its clock counts return to zero. Error cleanup, controller unbind
and system suspend remain unqualified. See [runtime evidence](../../evidence/2026-10-29-camera-native-cci-qualification.json).

The prepared [camera branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-camera)
enables CCI, sets its source to 19.2 MHz and describes the source-confirmed shared
camera I/O enable GPIO64 as fixed 1.8 V regulator `cam_io_1v8`. It adds no sensor,
EEPROM-part or capture-engine node. The source is based on kernel 39; RAM image 25
combines its camera DT with the **unchanged compiled kernel 39 and image 23
initramfs/command line**. Its kernel and DT source commits are recorded separately.
The image was booted from RAM after saving the earlier pre-DRM touch test as
incomplete: it had no confirmed owner gestures, so zero events are not a
completed negative touch result.

The reader requires `lg,madai`, an enabled MSM8226 CCI node, its registered
master0 I2C adapter, a real regulator with the exact name above, reported 1.8 V,
and that supply initially disabled. A temporary dummy client reserves fixed
7-bit 0x50 against another kernel client. Default `capture=0` performs software
preflight without enabling the supply or issuing I2C transfers. Explicit capture
supports 2560 or 65536 bytes. Each operation pairs a two-byte address pointer with
an eight-byte read through `i2c_transfer`; the native driver controls the actual
bus sequencing. Eight bytes fit the CCI v1 twelve-byte read limit. There is no
scan, EEPROM data programming, OIS initialization or calibration command.

After capture or an error, the client is removed, the diagnostic's regulator
reference is disabled/released and the adapter is released. A supply-disable
error rejects success. Successful data is exposed as a root-only debugfs blob
at `/sys/kernel/debug/fx0-native-camera-calibration/readout`; unload removes and
clears it. Keep the blob, encoded transfers and its hashes private.

Build against the exact running kernel output and sign with its trusted key:

```sh
make -C /private/exact-kernel-output ARCH=arm LLVM=1 \
  M="$PWD/diagnostics/camera-cci-read" W=1 modules
```

Transfer and verify the signed reader and matching `i2c-qcom-cci.ko` in RAM.
Verify device identity, source/artifact hashes and kernel release. On the
prepared camera-DT boot, load CCI first, save its probe logs and adapter/IRQ/clock
state, then run reader preflight and unload it. Confirm GPIO64 stays low.

```sh
insmod /tmp/i2c-qcom-cci.ko
insmod /tmp/fx0_cci_eeprom.ko
rmmod fx0_cci_eeprom
insmod /tmp/fx0_cci_eeprom.ko capture=1 read_bytes=2560
# Transfer and privately compare the root-only readout before unloading.
rmmod fx0_cci_eeprom
```

Require exact agreement with the independent GPIO capture before full reads.
Then reload for two independent 65536-byte native reads, save verified copies on
two host filesystems and compare every byte. Check supply state after each
attempt; after the CCI autosuspend delay, verify runtime suspend and clock
counts. Exercise reopen and record any NACK/reset/timeout, cleanup failure or
unexpected touch/display behavior. Avoid changing camera power ownership or
unbinding the controller during a transfer.

Only after successful qualification should a permanent read-only NVMEM binding
be selected from adequate part/protocol evidence. Aliasing across 8 KiB at 0x50
remains observed address behavior; it does not establish physical capacity or
other-bank/security-area coverage. All sensor-ID power/clock qualification,
CAMSS/IOMMU DMA, image capture and Nura camera integration remain separate work.
