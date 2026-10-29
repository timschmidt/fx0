# Fx0 inventory and backup operations

The initial device helper only reads the phone. It has no flash, erase, bootloader-unlock, or device-reboot command. Inventory and backups require an explicit ADB serial and a new output directory so another connected device or an existing backup is not selected accidentally.

## Host and USB check

```sh
python3 scripts/fx0_device.py probe
```

The probe uses host USB metadata, reports whether USB nodes are exposed, checks tool availability and Git state, and omits device serials. It can identify an ADB interface even when the sandbox cannot open the USB device. A positive metadata result does not prove ADB connectivity.

## Stock inventory

Once ADB is installed and host USB access is available, list devices and select the Fx0's serial. The helper checks that it identifies as LGL25, madai, or Fx0. Accept the phone's debugging prompt if presented.

```sh
adb devices -l
python3 scripts/fx0_device.py inventory --serial SERIAL --output local/stock-inventory-01
```

Replace `SERIAL` with the actual device serial. Inventory outputs may contain device identifiers and firmware details. They are written under the ignored local directory, with private directory/file permissions. Inspect failed commands individually; stock privileges and tool availability vary. The helper carries text-command exit codes in an explicit marker because old ADB transports may otherwise report success for a failed remote command.

## Partition backup

```sh
python3 scripts/fx0_device.py backup --serial SERIAL --output backups/stock-critical-01
python3 scripts/fx0_device.py verify-backup backups/stock-critical-01
```

The default selection includes recognized critical partitions found in the live named-partition map, and requires boot, recovery, and LAF to exist. It does not assume partition numbers. Root must already be available through adbd or the stock `su 0 sh -c` form; the helper does not install root or replace recovery. If the stock su interface differs, inspect and adapt that interface before proceeding.

Modern adbd uses a binary exec service. On this KitKat build, text commands fall back to the legacy shell, while binary images use the native ADB sync pull service with root adbd. Shell output must never carry raw partition bytes. Stock `adb root` works because `ro.debuggable=1`; it must be repeated after reboot.

Each image is transferred without terminal byte conversion, checked against its exact size in sysfs sectors, independently reread, and compared by SHA-256. Failed, short, or changing reads leave diagnostic copies but no successful manifest. Successful manifests identify the selected-partition scope; they do not claim a globally consistent whole-disk snapshot or prove restoration capability. Live modem calibration may change between reads and require a quiescent environment.

For an explicitly reviewed subset, repeat `--partition NAME` using exact names discovered on this device. The default critical selection is not a substitute for auditing the complete partition layout and deciding whether a full eMMC backup is needed. Preserve a verified second copy off the development storage before destructive writes.

## Tool verification

```sh
python3 -m unittest discover -s tests -v
```

The tests exercise backup interruption, truncated binary streams, partition changes between reads, image tampering, existing-backup protection, partition/path validation, remote shell quoting, and old ADB exit-status behavior. Passing these tests does not establish physical-device communication or a recovery route.

## Verified stock restore route and fastboot preparation

On this unit the live named map resolves LAF to `/dev/block/mmcblk0p27`, exactly 33,554,432 bytes (65,536 sectors). Never reuse that number on an uninspected unit. Original boot and recovery are p15/p16 and remain intact. Selected backups live privately in `backups/stock-critical-01`, on Disk B, and at `/sdcard/fx0-recovery/stock-critical-01` on the phone.

The original LAF image was read back from the phone's recovery-copy directory and checked against the verified host backup. With root adbd, restoration was exercised using the byte-identical original image:

```sh
adb -s SERIAL shell 'dd if=/sdcard/fx0-recovery/stock-critical-01/laf.img of=/dev/block/mmcblk0p27 bs=4096 count=8192 && sync'
adb -s SERIAL pull /dev/block/mmcblk0p27 local/laf-restored-check.img
```

The host compared exact size and SHA-256 against the verified original backup; both matched. This qualifies that stock-root write/read path while stock boot/system and internal SD remain intact. It does not prove emergency recovery after damage to the primary boot chain.

After this restore test, only LAF was cleared with `dd if=/dev/zero of=/dev/block/mmcblk0p27 bs=4096 count=8192 && sync`. A separate native-sync pull verified exactly 32 MiB of zeros and the partition map remained unchanged. Boot, recovery, aboot, and all other primary boot-chain partitions were retained. The finite length is deliberate. Private operation records are in `local/laf-access-01`.

The [historical Fx0 procedure](https://github.com/stephanfriedrich/ffos_on_lgfx0/blob/master/README.md) then requires a fully powered-off phone, Volume Up held, and USB insertion. Physical entry is pending; successful LAF clearing alone does not establish fastboot or image acceptance. To restore the original download agent later, boot the retained stock OS, enable root adbd, perform the verified restore above, and independently compare the readback again.

## Installed diagnostic lk2nd

After the first successful RAM handoff, the original boot image was restored from the phone's verified recovery copy and independently reread against the original SHA-256. The diagnostic lk2nd image was uploaded, pulled back and compared byte for byte. Then its 286,736-byte file was written to the verified p15 boot partition with `bs=4096 count=71`. A full 32 MiB reread confirmed the new image prefix and unchanged remainder. The original recovery partition and primary bootloader were retained. A normal reboot successfully entered lk2nd fastboot.

Stock boot is now available as a saved image rather than the active boot partition. Preserve the phone's internal SD recovery copy. To restore stock boot from stock root ADB, write `/sdcard/fx0-recovery/stock-critical-01/boot.img` to the reverified boot block with `bs=4096 count=8192`, sync, and independently verify a complete readback against the original manifest. That exact write/read path was tested before installation. Reaching stock root ADB from the installed secondary bootloader still requires booting the original image or restoring through the stock fastboot/recovery route; do not infer it solely from the prior write test.

Stock fastboot remains accessible through the LAF workaround and physical key sequence. In **lk2nd** fastboot, `flash boot` writes the OS at a 512 KiB offset; it is not a direct whole-partition stock restore. Choose the correct environment and verify offset behavior before any restoration command.
