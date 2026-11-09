# Matching r59 moduleless RAM startup preparation

This image prepares the first startup of the independently built
`6.18.59-fx0-nfc-open-teardown-alpine` family. It contains no NFC/CPU modules,
firmware or registration worker. Its startup result checks kernel identity,
bootstrap state and the unbound NFC client; it does not establish controller
communication, RF behavior or the corrected open teardown on hardware.

The [manifest](../../manifests/nfc-open-teardown-startup-ram.json) records the
exact image, linked notes, certificate, DTB and source APK. The image remains
unstaged/unbooted. The previous cold-lifecycle return on native boot
`2e6126b9-498e-4d89-b23e-f08fe6ccc361` still needs its own display/touch result;
the earlier moduleless-return answer covers another boot.

## Image and runtime guard

The qualified r58 moduleless image supplies fourteen CPIO entries. Eleven
payloads and modes remain identical, including BusyBox, serial/HTTP support and
init's independent 180-second return timer. Only the family permit, expected
linked-note hash and read-only startup checker change. The command line and
DTB are unchanged. No filesystem outside the allowed RAM/pseudo-filesystem
types may be mounted.

An isolated decompressor scratch reproduces the original r59 zImage twice:
from its original objects, then after replaying the recorded piggy assembler
command. It includes all thirty members of the thin EFI archive. XZ preset 3
changes only encoding; both Python and the actual XZ tool decompress the final
linked payload to the exact runtime Image. The original ELF, notes, certificate,
ABI, APK and build intermediates remain untouched. This encoding follows the
qualified r58 workaround; the underlying intermittent USB fault is unresolved.

The new checker requires the exact r59 release and notes, enforced module
signatures, schedutil, zero taint, four CPUs, an empty module list and no
CPUfreq policy or CPR provider. It checks two bounded temperature readings and
one unbound PN547 client on enabled QUP3. It also validates and records the RAM
boot UUID, requires NFC pins 20/21/22 unclaimed, original moduleless GPIO
direction/pull/drive states with VEN/FIRM low, and reference-clock votes
0/0/0 at 19.2 MHz. Those votes do not prove the physical clock is off; the
clock-summary hardware-enabled flag can still be Y.

## Verification

Two tests cover fifty fixture cases, preserving fixture bytes and checking
that no module, I2C or GPIO operation is called. Both host execution and the
exact image's ARM BusyBox shell/read applets pass all fifty cases. Three
isolated weakened clock, pin-ownership and boot-ID guards are detected.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s tests -p test_nfc_open_teardown_startup.py -v
```

For exact BusyBox execution, additionally set `FX0_NFC_TEST_BUSYBOX` to its
absolute extracted path and `FX0_NFC_TEST_SHELL` to
`/usr/bin/qemu-arm-static ABSOLUTE_BUSYBOX_PATH sh`. The fixture creates
wrappers for its actual `cat`, `sha256sum`, `awk`, `readlink` and `tr` applets.

Independent image parsing verifies addresses, Android digest, kernel/DTB,
all fourteen CPIO hashes and executable checker mode, zero module/firmware
entries and the kernel/BSS limit below the forced ramdisk address. Init, HTTP
and checker syntax also pass under the exact ARM BusyBox.

## Entry and recovery

Private trial helpers reside in `local/ram-nfc-open-teardown-startup-01`.
The entry first requires the exact previous-native boot and passed UI status,
before importing the phone client. The actual pending entry and instrumented
pending/wrong-boot cases stop there. The instrumented passed case stops before
the client import executes; it does not simulate a phone trial.

A valid entry must run a fresh, one-use native preflight before requesting
reboot. That preflight checks r50 identity/hash/services, programmed 1.15 V APC
target, temperatures, released NFC pins and zero clock votes. Its output is
separate from the read-only preparation baseline, which already passes on the
same native boot. No preflight directory has been consumed by staging.

The existing transfer/BOOT protocol remains: identified lk2nd, terminal
successful transfer with absent PID, exact full readback, live serial/network
observers, then one BOOT. A failed or uncertain operation does not authorize a
retry. The timer runs independently of the checker/observer. Native postflight
requires a changed native boot, original r50 hash, zero taint, services, the
1.15 V target, restored NFC pins/clock votes and host route/DNS/profile state.
Display/touch must then be confirmed for that new native return.

No phone entry or installation occurs in this checkpoint. See
[preparation evidence](../../evidence/2026-11-08-nfc-r59-startup-preparation.json).
