# Fx0 storage consolidation work

The required endpoint is one maximum-capacity native Linux root/data filesystem, with only the additional partitions the boot chain and working hardware require. External SD remains removable Linux media. The current userdata subpartition installation is transitional.

This document records a **host-only preview**, not an approved final partition map. No phone partition table or filesystem has been changed by this work. Factory-stock restoration and the remaining requirements in [plan section 2.1](bringup-plan.md#21-verify-full-stock-restoration-then-consolidate-internal-storage) must pass before migration.

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

The preview deliberately retains the original 40-entry GPT capacity. `sgdisk --verify` reports no structural problems but warns about that nonstandard capacity, gaps around GPT metadata, and the root end boundary. Before finalizing, test primary/secondary bootloader compatibility with a standard 128-entry table and regenerate the preview accordingly. Preserve the exact original table for stock restoration. The current preview does not waive these checks.

The private host disk image contains firmware and provisioning from the device; it must not be published. Reviewed measurements are in [the preview evidence](../evidence/2026-10-29-storage-layout-preview.json).

## Boot without another filesystem partition

The existing 32 MiB `boot` partition can hold lk2nd in its first 512 KiB and an Android-format Linux boot image in the remaining **33,030,144 bytes (31.5 MiB)**. This is a documented lk2nd boot path. Linux can then mount a modern ext4 root without requiring lk2nd to parse that root filesystem. [lk2nd boot documentation](https://github.com/msm8916-mainline/lk2nd/blob/main/Documentation/boot.md).

This is the preferred candidate before allocating a separate boot filesystem. It still requires all of the following:

1. Assemble a Nura image containing the maintained kernel, correct Fx0 DTB and matching initramfs. Prove it fits with update headroom and boots from the actual reserved offset.
2. Set its root selection to the new native root UUID and remove the current userdata/MBR-subpartition dependency. Qualify firmware and calibration lookup after the old payload entries are removed.
3. Preserve the lk2nd prefix during on-device updates. The installed boot-deploy 0.23.0 and inspected upstream 0.25.0 write at the physical boot partition's start. Enabling that write unchanged would replace lk2nd.
4. Qualify the proposed offset-aware updater, full readback, power-loss/interrupted-update recovery and a known-good recovery image. lk2nd fastboot already applies its own offset; an on-device updater accesses the physical partition and needs its own correct offset.
5. Prove cold/key recovery into lk2nd independently of a valid root or OS image. A preserved bootloader prefix and available backups alone do not establish this recovery test.

The public [boot-deploy preparation branch](https://github.com/timschmidt/fx0-boot-deploy/tree/integration/fx0-boot-offset) adds `deviceinfo_flash_bootimg_offset` in canonical decimal bytes. It checks image fit after subtracting the prefix, requires 512-byte alignment, and preserves both the prefix and trailing bytes. Project CI passes in Alpine 3.24. Tests perform real writes against regular files, including rejected inputs and exact remaining-capacity writes. This has **not** been installed or qualified on the phone.

The matching [pmaports schema branch](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-storage) defines the setting without enabling it in any device profile. A positive fixture passes and a negative value is rejected. All 296 existing deviceinfo files produce the same diagnostics with the original and modified schema under dint 0.2.1: 305 pre-existing warnings. This is not a clean full pmaports CI result or an upstream submission.

If the raw-image route cannot meet boot/update/recovery requirements, evaluate a small separate boot filesystem. Size it from actual kernel, DTB, initramfs, fallback and update requirements. Do not reduce the entire root filesystem's integrity features just to satisfy the current ext2 reader.

## Retained space still needs an audit

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

## Original restoration sources

All 29 original critical images, the original 1 GiB system image, and both original GPT regions now have direct copies on two host filesystems. Expected sizes and original SHA-256 values match after independent rehashing; the new system copy was fsynced and its file cache discarded before verification. This is stronger recovery-source coverage, not a claim that original userdata exists or that restoration has passed.

The original boot and recovery images were verified before extracting their initramfs configuration privately. Both enable the debuggable build property and configure ADB. Recovery init starts adbd and enables USB for that property; actual recovery ADB/root access remains to be tested. Its fstab identifies stock system/cache/userdata by partition label, while the normal boot configuration identifies internal FAT storage as partition 38. Recovery's SD path points at external mmcblk1p1, so internal and external SD must not be confused during restoration.

Before booting original recovery, inspect retained boot-control and recovery commands for an automatic wipe request. Finish the unmounted development snapshot first. A stock-kernel diagnostic with a replacement initramfs is useful hardware evidence but does not prove the original recovery/factory initialization path. See [the restoration-source evidence](../evidence/2026-10-29-original-stock-restore-sources.json).

## Next physical sequence

Keep the current installation until the stock restoration rehearsal passes. From independent RAM recovery with all eMMC filesystems unmounted, finish the consistency checkpoint and audit original versus current provisioning. Rehearse factory-stock initialization using preserved stock data, verify stock operation without a SIM, and restore the development state.

Next qualify the raw-image boot and update path while the original GPT is still intact. Only after those checks, the retained-partition audit, stable power and final host-image validation pass should the phone receive the new layout. Verify both GPT copies, retained data, filesystems, boot, updates and recovery again after migration. Test external SD detection, mount/unmount and removal independently, including normal boot with no card inserted.
