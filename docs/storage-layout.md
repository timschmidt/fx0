# Fx0 storage consolidation work

The required endpoint is one maximum-capacity native Linux root/data filesystem, with only the additional partitions the boot chain and working hardware require. External SD remains removable Linux media. The current userdata subpartition installation is transitional.

**Applied 2026-10-31.** The phone now uses the final layout: partitions 1–34 unchanged, partition 35 `nura-root` (14.3 GiB native ext4) replacing system/cache/userdata/sdcard/grow, no boot filesystem. It has 12.67 GB available on first boot, against 1.4 GB before. See the [final-layout evidence](../evidence/2026-10-31-final-storage-layout.json). The sections below record the preview and qualification that led there. Factory-stock restoration and the remaining requirements in [plan section 2.1](bringup-plan.md#21-verify-full-stock-restoration-then-consolidate-internal-storage) must pass before migration.

## Measured contiguous space

The eMMC user area contains 30,777,344 sectors of 512 bytes. The following original partitions are adjacent:

| Original number | Name | First sector | Last sector |
| --- | --- | ---: | ---: |
| 35 | system | 786432 | 2883583 |
| 36 | cache | 2883584 | 4317183 |
| 37 | userdata | 4317184 | 12705791 |
| 38 | sdcard | 12705792 | 30507007 |
| 39 | grow | 30507008 | 30777310 |

The preview replaces those five entries with partition 35, `nura-root`, covering sectors 786432–30777310: **15,355,330,048 bytes, approximately 14.30 GiB**. The partition ends immediately before the reserved backup-GPT area. A 4 KiB-block filesystem uses 15,355,326,464 bytes, leaving 3,584 bytes in its final partial block.

A fresh ext4 filesystem retains extents, 64-bit metadata and metadata checksums. Its initial root-only block reserve is 1%, about 146 MiB, to allow system recovery when ordinary users exhaust their allocation. This replaces the default 5% reservation on a small device. Filesystem metadata, journal space and the reserve must be reported separately from raw partition capacity; 14.30 GiB is not a claim about `df` available space.

Both GPT headers and partition arrays pass CRC checks. The first 34 partition entries and all data bytes from LBA 34 to the root start remain identical to the verified development snapshot. The standalone empty ext4 passes `e2fsck -fn`; after copying it into the host disk image, a complete embedded-filesystem readback hash matches.

The preview deliberately retains the original 40-entry GPT capacity. `sgdisk --verify` reports no structural problems but warns about that nonstandard capacity, gaps around GPT metadata, and the root end boundary. The owner decided on 2026-10-31 to keep the original 40-entry capacity and not
to test a 128-entry table. SBL1 parses the GPT before any code we control, and
no emergency-download recovery is available, so a failed test could leave the
phone unrecoverable. The boot chain already parses the 40-entry table, and the
migration changes only the reclaimed entries. `sgdisk`'s capacity warning is
accepted. Preserve the exact original table for stock restoration.

The private host disk image contains firmware and provisioning from the device; it must not be published. Reviewed measurements are in [the preview evidence](../evidence/2026-10-29-storage-layout-preview.json).

## Boot without another filesystem partition

The existing 32 MiB `boot` partition can hold lk2nd in its first 512 KiB and an Android-format Linux boot image in the remaining **33,030,144 bytes (31.5 MiB)**. This is a documented lk2nd boot path. Linux can then mount a modern ext4 root without requiring lk2nd to parse that root filesystem. [lk2nd boot documentation](https://github.com/msm8916-mainline/lk2nd/blob/main/Documentation/boot.md).

This is the preferred candidate before allocating a separate boot filesystem. It still requires all of the following:

1. Assemble a Nura image containing the maintained kernel, correct Fx0 DTB and matching initramfs. Prove it fits with update headroom and boots from the actual reserved offset.
2. Set its root selection to the new native root UUID and remove the current userdata/MBR-subpartition dependency. Qualify firmware and calibration lookup after the old payload entries are removed.
3. Preserve the lk2nd prefix during on-device updates. The installed boot-deploy 0.23.0 and inspected upstream 0.25.0 write at the physical boot partition's start. Enabling that write unchanged would replace lk2nd.
4. Qualify the proposed offset-aware updater, full readback, power-loss/interrupted-update recovery and a known-good recovery image. lk2nd fastboot already applies its own offset; an on-device updater accesses the physical partition and needs its own correct offset.
5. Prove cold/key recovery into lk2nd independently of a valid root or OS image. A preserved bootloader prefix and available backups alone do not establish this recovery test.

The separate [lk2nd preparation branch](https://github.com/timschmidt/fx0-lk2nd/tree/integration/fx0-rawboot) adds `LK2ND_EXTLINUX=0` to exclude filesystem discovery while preserving the Android-image and fastboot boot paths. The default remains `1`. Default, disabled-search and forced-fastboot/disabled-search Fx0 builds pass; their symbols and bundled board entry match the selected configuration. Invalid values fail before compilation. This permits a future raw-image test without removing the existing userdata installation, and prevents removable filesystems from taking precedence in the intended configuration. None of these new bootloader images has been flashed. The [build and host-image evidence](../evidence/2026-10-29-lk2nd-rawboot-preparation.json) records that limit.

A host regular-file test also uses the actual 6,197,248-byte diagnostic image with a private copy of the 32 MiB boot partition. The offset-aware updater preserves the entire 512 KiB prefix, writes a byte-identical Linux image and preserves all trailing bytes and partition length. This leaves 26,832,896 bytes after that diagnostic image. It is a host write/readback check, not a phone boot or a final Nura image-size guarantee.

The public [boot-deploy preparation branch](https://github.com/timschmidt/fx0-boot-deploy/tree/integration/fx0-boot-offset) adds `deviceinfo_flash_bootimg_offset` in canonical decimal bytes. It checks image fit after subtracting the prefix, requires 512-byte alignment, and preserves both the prefix and trailing bytes. Project CI passes in Alpine 3.24. Tests perform real writes against regular files, including rejected inputs and exact remaining-capacity writes. This has **not** been installed or qualified on the phone.

The matching [pmaports schema branch](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-storage) defines the setting without enabling it in any device profile. A positive fixture passes and a negative value is rejected. All 296 existing deviceinfo files produce the same diagnostics with the original and modified schema under dint 0.2.1: 305 pre-existing warnings. This is not a clean full pmaports CI result or an upstream submission.

**First hardware boot, 2026-10-31.** The installed r7 kernel, DTB and initramfs
were packed into one 17.5 MB Android image (15.5 MB headroom). The installed
lk2nd's fastboot wrote it at the 512 KiB offset. An lk2nd built with
`LK2ND_EXTLINUX=0`, booted from RAM, then booted Nura r7 from that image: a
command-line marker proved the path, with taint 0 and Wi-Fi up. The lk2nd prefix
hash was unchanged and the payload read back byte-identical. Normal reboots
still use extlinux. This qualifies item 1's fit and boot from the real offset.
The on-device updater, interrupted-update recovery, an installed raw-preferring
lk2nd and cold/key recovery remain. See [evidence](../evidence/2026-10-31-rawboot-first-boot.json).

**On-device updates, 2026-10-31.** The offset change was backported to boot-deploy
0.23.0 and built as a signed `boot-deploy-0.23.0-r1`, installed with
`mkbootimg-osm0sis`. `/etc/deviceinfo` now generates an Android image and
flashes it at offset 524288. A `mkinitfs` run wrote it with the lk2nd prefix,
padding and trailing bytes unchanged. The payload equals `/boot/boot.img`
(`vmlinuz`+DTB, current initramfs, extlinux-identical command line). The
extlinux-disabled lk2nd booted it. Extlinux remains the installed lk2nd's path
and the fallback. See [evidence](../evidence/2026-10-31-boot-deploy-offset-updates.json).
Remaining: interrupted-update and key-entry recovery, then a raw-preferring
installed lk2nd.

**Key escape, 2026-10-31.** The production candidate lk2nd (no extlinux, no
forced fastboot), chain-loaded from RAM, detects the Fx0 and its GPIO volume
keys. With Volume Down held it stays in fastboot instead of booting the raw
image, and `fastboot continue` boots it. Still to test with the prefix
installed: cold power-on entry (stock aboot runs first, and LG's
Power+Volume Down combination may open the stock factory-reset prompt), a
host-triggered reboot into the bootloader, and the 20 cold/20 warm boot run.
See [evidence](../evidence/2026-10-31-lk2nd-key-entry.json).

**Installed, 2026-10-31.** That lk2nd is now the installed prefix. The phone boots
Nura unattended from the boot-deploy raw image on warm and cold (power key)
starts. A Volume Down cold start reaches lk2nd fastboot, with no LG reset
prompt. A host-requested `reboot --reboot-argument=bootloader` does not: LG
aboot consumes the IMEM restart reason before lk2nd reads it. The extlinux menu is no longer used; the rescue image stays available
through `fastboot boot`. Items 1, 3, 4 and 5 above pass for the current userdata
installation; item 2 (native root) waits for the repartition. See
[evidence](../evidence/2026-10-31-lk2nd-production-install.json).

If the raw-image route cannot meet boot/update/recovery requirements, evaluate a small separate boot filesystem. Size it from actual kernel, DTB, initramfs, fallback and update requirements. Do not reduce the entire root filesystem's integrity features just to satisfy the current ext2 reader.

## Retained space audit

The [partition reference audit](partition-audit.md) records loader, stock-init and kernel references for every entry. It supports keeping all 34 leading entries at their original offsets: nine are located by unique type GUID in SBL1, and the rest are named by aboot, TZ or stock init. The six without a unique reference gain nothing if removed. The table below keeps its investigation-stage wording.

Keeping the first 34 partitions preserves existing offsets while the large contiguous region is tested. It does not prove that 34 extra entries are necessary in the final layout.

| Retained material | Reason to preserve during investigation | Remaining work |
| --- | --- | --- |
| SBL, SDI, DDR, aboot, RPM, TZ and redundant boot-chain entries | Required boot/recovery dependencies are not all mapped | Establish exact boot-ROM/loader dependencies before moving or deleting any entry |
| modem | Contains the original remote-processor firmware filesystem | Qualify firmware lookup and any replacement storage scheme |
| persist, modemst1/2, fsg, fsc, ssd, drm, sns | Device-specific calibration/provisioning or state may be required | Reconcile original/current differences and test every dependent hardware function |
| boot and recovery | Existing boot and recovery paths | Qualify the new OS/update/fallback paths and final recovery contents |
| misc, laf, factory, fota, encrypt, rct, mpt | Factory, boot-mode or other roles remain partly unverified | Audit actual reads/writes and stock restoration before reclaiming |
| pad entries and unallocated gaps | Names and empty-looking areas are insufficient proof of disposability | Inspect coverage and boot-chain constraints; justify every retained range |

The first-region gaps total 31.5 MiB in six segments. Reclaiming them into the single root would require changing other retained offsets or proving another layout; deleting their labels alone would not enlarge the contiguous root. Further partition removal or relocation remains part of the requested minimum-layout work.

## Migration tool

[`scripts/fx0_storage_migrate.py`](../scripts/fx0_storage_migrate.py) turns the
[audited](partition-audit.md) target into a tool. `plan` keeps entries 1–34
byte for byte, including their unique GUIDs and attributes, and replaces entries
35–39 with one `nura-root` Linux-filesystem entry over sectors 786432–30777310.
It keeps the original 40-entry table, recomputes every CRC, and refuses
non-standard array locations or data that would be lost. `verify` re-checks a
target pair against the original.

`apply` refuses unless all of the following hold:

- the restoration rehearsal is confirmed
- the target is the whole non-removable `/dev/mmcblk0` with the exact sector count
- no reclaimed partition is mounted
- both on-device GPT regions are byte-identical to the original

It writes only the two GPT regions (backup first) and compares a readback. Eight
synthetic-GPT tests pass, covering every refusal. For the real original GPT,
`plan` produces a target that `sgdisk -v` reports as "No problems found". It has
the same 40-entry and end-alignment cautions as the earlier preview and 31.5 MiB
of free space in six segments. The target regions stay private. Nothing has
been written to the phone. The restoration rehearsal has since passed and the
40-entry capacity is kept by owner decision; the root filesystem/installation
steps remain. See
[migration-tool evidence](../evidence/2026-10-30-storage-migration-tool.json).

## Original restoration sources

All 29 original critical images, the original 1 GiB system image, and both original GPT regions now have direct copies on two host filesystems. Expected sizes and original SHA-256 values match after independent rehashing; the new system copy was fsynced and its file cache discarded before verification. This is stronger recovery-source coverage, not a claim that original userdata exists or that restoration has passed.

The original boot and recovery images were verified before extracting their initramfs configuration privately. Both enable the debuggable build property and configure ADB. Recovery init starts adbd and enables USB for that property; actual recovery ADB/root access remains to be tested. Its fstab identifies stock system/cache/userdata by partition label, while the normal boot configuration identifies internal FAT storage as partition 38. Recovery's SD path points at external mmcblk1p1, so internal and external SD must not be confused during restoration.

Before booting original recovery, inspect retained boot-control and recovery commands for an automatic wipe request. Finish the unmounted development snapshot first. A stock-kernel diagnostic with a replacement initramfs is useful hardware evidence but does not prove the original recovery/factory initialization path. See [the restoration-source evidence](../evidence/2026-10-29-original-stock-restore-sources.json).

## Next physical sequence

The factory-stock restoration rehearsal passed on 2026-10-31.

1. From the RAM rescue, a fresh whole-eMMC snapshot of the r7 state was
   verified on two host filesystems.
2. The partitions that differed from stock (boot and seven runtime-modified
   partitions) were rewritten from the original images and hash-checked on the
   device.
3. A `--wipe_data` request in the misc boot-control block made stock recovery
   recreate userdata and cache. Firefox OS then booted to its first-run wizard,
   with display, touch and keys working and stock storage and firmware visible.
4. The original LAF was restored from stock root ADB, and LG download mode
   worked.
5. LAF was cleared again. The return went through stock fastboot, a RAM-booted
   lk2nd and the RAM rescue.
6. The snapshot was written back and verified by a full readback hash. Nura r7
   booted normally.

See [rehearsal evidence](../evidence/2026-10-31-factory-stock-rehearsal.json).
Repeat it from the consolidated layout after migration.

Next qualify the raw-image boot and update path while the original GPT is still intact. Only after those checks, the retained-partition audit, stable power and final host-image validation pass should the phone receive the new layout. Verify both GPT copies, retained data, filesystems, boot, updates and recovery again after migration. Test external SD detection, mount/unmount and removal independently, including normal boot with no card inserted.
