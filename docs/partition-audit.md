# Fx0 partition reference audit

Section 2.1 step 5 asks for a reason for every retained partition. [`scripts/audit_partition_references.py`](../scripts/audit_partition_references.py) reads the original GPT. It searches the stock SBL1, SDI, aboot, RPM and TZ images for each entry's name (ASCII/UTF-16) and its type GUID, and the stock boot/recovery ramdisks for fstab and init references. It also greps the vendor kernel source. Type-GUID matches are counted only where the GUID is unique to that entry: 15 entries share the generic basic-data type. Only names, offsets and reference sites are recorded.

**Result:** keep the first 34 entries unchanged at their original offsets and replace the five contiguous Android entries (system to grow) with one native root, as in the [storage preview](storage-layout.md). The six entries without a unique reference (pad, pad1–pad4 and rct) are small and sit inside the first region. Removing them would not enlarge the root unless located entries moved, which the boot chain does not allow. Retained: 34 entries, 352.5 MiB.

This audit does not replace the stock-restoration rehearsal or boot-chain testing. Name references show what a loader can address, not that it reads that entry at every boot.

| # | Entry | First LBA | Size | References found | Final layout | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | modem | 16384 | 65536 KiB | name in aboot,sbl1; stock ramdisk (1 files) | Retain at original offset | Remote-processor firmware filesystem; stock init and Nura msm-firmware-loader mount it (WCNSS firmware used now) |
| 2 | sbl1 | 147456 | 1024 KiB | name in aboot | Retain at original offset | Primary secondary bootloader; unique type GUID is the boot ROM lookup key |
| 3 | sdi | 149504 | 512 KiB | type GUID in sbl1; name in aboot | Retain at original offset | Located by SBL1 by unique type GUID |
| 4 | DDR | 163840 | 512 KiB | type GUID in sbl1; name in aboot,sbl1,tz | Retain at original offset | DDR training data; SBL1 unique type GUID, also named by aboot and TZ |
| 5 | aboot | 180224 | 2048 KiB | type GUID in sbl1; name in aboot | Retain at original offset | Holds lk2nd/aboot; located by SBL1 by unique type GUID |
| 6 | rpm | 184320 | 1024 KiB | type GUID in sbl1; name in aboot,rpm,sbl1 | Retain at original offset | RPM firmware; located by SBL1 by unique type GUID |
| 7 | tz | 186368 | 1024 KiB | type GUID in sbl1; name in aboot,sbl1,tz | Retain at original offset | TrustZone; located by SBL1 by unique type GUID |
| 8 | pad | 188416 | 2048 KiB | none found | Retain at original offset | No unique reference; retained because removing it cannot enlarge the root without moving located entries |
| 9 | sbl1b | 192512 | 1024 KiB | name in aboot | Retain at original offset | Backup boot chain named by aboot; retained for boot-chain recovery and stock restoration |
| 10 | rpmb | 194560 | 1024 KiB | name in aboot,tz | Retain at original offset | Named by aboot and TZ; distinct from the eMMC hardware RPMB area |
| 11 | tzb | 196608 | 1024 KiB | name in aboot | Retain at original offset | Backup boot chain named by aboot |
| 12 | sdib | 198656 | 512 KiB | name in aboot | Retain at original offset | Backup boot chain named by aboot |
| 13 | abootb | 199680 | 2048 KiB | name in aboot | Retain at original offset | Backup boot chain named by aboot |
| 14 | persist | 212992 | 32768 KiB | name in aboot,tz; stock ramdisk (1 files) | Retain at original offset | Calibration (WCNSS NV used now, sensors); named by aboot/TZ and stock init |
| 15 | boot | 278528 | 32768 KiB | name in aboot,sbl1,tz; stock ramdisk (1 files) | Retain at original offset | Holds lk2nd prefix plus OS image; required |
| 16 | recovery | 344064 | 32768 KiB | name in aboot; stock ramdisk (1 files) | Retain at original offset | Stock recovery; required for factory restoration path |
| 17 | modemst1 | 409600 | 3072 KiB | type GUID in sbl1 | Retain at original offset | Modem EFS; located by SBL1 by unique type GUID |
| 18 | modemst2 | 415744 | 3072 KiB | type GUID in sbl1 | Retain at original offset | Modem EFS; located by SBL1 by unique type GUID |
| 19 | pad1 | 421888 | 2048 KiB | none found | Retain at original offset | No unique reference; see pad |
| 20 | fsg | 425984 | 3072 KiB | type GUID in sbl1 | Retain at original offset | Modem EFS golden copy; located by SBL1 by unique type GUID |
| 21 | fsc | 432128 | 512 KiB | type GUID in sbl1 | Retain at original offset | Modem EFS cookie; located by SBL1 by unique type GUID |
| 22 | ssd | 433152 | 512 KiB | name in aboot | Retain at original offset | Secure storage; named by aboot |
| 23 | pad2 | 434176 | 2048 KiB | none found | Retain at original offset | No unique reference; see pad |
| 24 | encrypt | 438272 | 512 KiB | name in tz | Retain at original offset | Named by TZ |
| 25 | rct | 439296 | 512 KiB | none found | Retain at original offset | No reference found; LG-specific, retained pending audit of stock writes (no space gain from removal) |
| 26 | misc | 442368 | 16384 KiB | name in aboot; stock ramdisk (3 files) | Retain at original offset | Boot-mode messages; named by aboot and stock/recovery fstab |
| 27 | laf | 475136 | 32768 KiB | name in aboot | Retain at original offset | LG download agent; named by aboot; currently cleared for fastboot entry, original preserved |
| 28 | factory | 540672 | 32768 KiB | name in aboot | Retain at original offset | Named by aboot; LG factory data |
| 29 | fota | 606208 | 32768 KiB | name in aboot | Retain at original offset | Named by aboot; LG update flags |
| 30 | drm | 671744 | 8192 KiB | stock ramdisk (2 files) | Retain at original offset | DRM keys/state; stock init mounts it |
| 31 | pad3 | 688128 | 2048 KiB | none found | Retain at original offset | No unique reference; see pad |
| 32 | sns | 692224 | 8192 KiB | stock ramdisk (2 files) | Retain at original offset | Sensor registry/calibration; stock init mounts it (sensor bring-up uses it) |
| 33 | pad4 | 708608 | 2048 KiB | none found | Retain at original offset | No unique reference; see pad |
| 34 | mpt | 720896 | 32768 KiB | stock ramdisk (2 files) | Retain at original offset | LG data; stock init mounts it |
| 35 | system | 786432 | 1048576 KiB | name in aboot,rpm; stock ramdisk (7 files) | Reclaim into the native root | Contiguous Android space; stock fstab/init only (restorable by stock recovery from preserved images) |
| 36 | cache | 2883584 | 716800 KiB | name in aboot; stock ramdisk (7 files) | Reclaim into the native root | Contiguous Android space; stock fstab/init only (restorable by stock recovery from preserved images) |
| 37 | userdata | 4317184 | 4194304 KiB | name in aboot; stock ramdisk (5 files) | Reclaim into the native root | Contiguous Android space; stock fstab/init only (restorable by stock recovery from preserved images) |
| 38 | sdcard | 12705792 | 8900608 KiB | name in sbl1; stock ramdisk (2 files) | Reclaim into the native root | Contiguous Android space; stock fstab/init only (restorable by stock recovery from preserved images) |
| 39 | grow | 30507008 | 135151 KiB | none found | Reclaim into the native root | Contiguous Android space; stock fstab/init only (restorable by stock recovery from preserved images) |
