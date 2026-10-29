# Temporary Fx0 camera EEPROM reader

This GPL-2.0-only diagnostic reads the camera EEPROM on the production LG Fx0
(`lg,madai`). It is a temporary development tool, not a native CCI/NVMEM driver
or camera implementation. It has been tested on RAM kernel
`6.18.59-00039-g341246daef48`.

The default is a GPIO preflight with **no I2C transfer**. Capture requires
`capture=1`; accepted lengths are 2560 and 65536 bytes. The only slave address
is 7-bit `0x50`. Each transfer writes a two-byte address pointer, then reads
32 bytes with a repeated START. There is no EEPROM data-programming command,
bus scan, OIS initialization or calibration operation.

The module requires a disabled `qcom,msm8226-cci` node, exclusive GPIO ownership,
GPIO29/30 initially inputs, and GPIO64 initially input-low. It releases SDA/SCL
through open-drain GPIOs, enables the camera I/O supply through GPIO64, and
checks both bus lines are high. After reading, it removes its temporary adapter,
returns SDA/SCL to inputs, drives GPIO64 low and returns it to input. Check the
actual GPIO state after both successful and failed attempts. Do not use this
while a camera driver or another bus consumer is active.

Build with the exact running kernel's configured build output and toolchain:

```sh
make -C /private/exact-kernel-output ARCH=arm LLVM=1 \
  M="$PWD/diagnostics/camera-eeprom-read" W=1 modules
```

If module signatures are enforced, sign the result and the matching
`i2c-algo-bit.ko` dependency with a key trusted by that running kernel. Do not
force version or signature checks. Keep private signing keys outside public
repositories. Transfer the modules to the RAM diagnostic's `/tmp`, and verify
the selected device, release and artifact hashes before loading them.

Example commands **on the verified RAM diagnostic**, with debugfs mounted:

```sh
insmod /tmp/i2c-algo-bit.ko
insmod /tmp/fx0_eeprom_read.ko
rmmod fx0_eeprom_read
insmod /tmp/fx0_eeprom_read.ko capture=1 read_bytes=65536
# Transfer the root-only debugfs blob to private host storage before unloading:
base64 /sys/kernel/debug/fx0-camera-calibration/readout
rmmod fx0_eeprom_read
rmmod i2c_algo_bit
```

Do not paste the encoded calibration into public logs. Decode it into a private
file, check its exact length, and verify independent copies on two host
filesystems. Reload the module for an independent hardware read and compare.
The blob is mode 0400 and is removed on unload; the module also clears its buffer
on normal unload. A signed external module still sets the expected out-of-tree
kernel taint (4096 on the tested boot).

Three independent 65536-byte reads matched on this unit, including one using
the exact published source. They cover every 16-bit word address at `0x50` and
repeat every 8192 bytes. Aliasing alone does not establish physical capacity or
coverage of other slave banks/security areas. Maker byte 0x0700 selects the
vendor's old LGIT OIS path; the extended coefficient range contains data.
Neither fact identifies a functioning OIS controller or validates calibration.
The original stock-cache reader remains a separate, untested positive path.
See [the camera record](../../docs/camera-bringup.md) for remaining work.
