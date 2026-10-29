# LG Fx0 Nura bringup

Bring a physical LG Fx0 LGL25 to the current Nura release with all hardware working, reliable updates, and patches prepared for submission to the appropriate upstream projects. Development takes place in this folder.

The device is available for development and flashing. No personal data needs to be retained. Original firmware and device calibration must still be preserved for recovery and hardware operation. No SIM is currently available; cellular acceptance remains pending until it can be tested.

## Project documents

| Document | Purpose |
| --- | --- |
| [Bringup plan](docs/bringup-plan.md) | Ordered implementation steps, dependencies, recovery requirements, and completion criteria |
| [Storage consolidation](docs/storage-layout.md) | Measured root layout, boot-image update preparation and remaining restoration gates |
| [Stock hardware](docs/stock-hardware.md) | Physical inventory and implications for board support |
| [Hardware acceptance](docs/hardware-acceptance.md) | Full hardware inventory and tests required before declaring completion |
| [Upstream development](docs/upstream-development.md) | Public repository structure, patch ownership, validation, and submission preparation |
| [Research](docs/research.md) | Source references, recovered work, and facts that need physical confirmation |
| [Device operations](docs/device-operations.md) | Read-only inventory, verified partition backups, and helper usage |
| [Image builds](docs/building.md) | Full diagnostic kernel/lk2nd recipes and rootfs preparation |
| [Development patches](patches/README.md) | Initial Linux and lk2nd candidates with reproducible DTB checks |
| [Development log](docs/development-log.md) | Observed device/host state, completed checks, and the next executable work |
| [Kernel gaps](docs/kernel-gaps.md) | Maintained-kernel target and missing shared SoC/camera infrastructure |

## Current state

Implementation started October 29, 2026. Stock firmware inventory, 29 critical partition backups, recovery copies, GPT metadata, and a separately verified 1 GiB original-system backup are preserved privately. A complete development-state snapshot of the 15,758,000,128-byte eMMC user area and both 4 MiB boot areas has also been independently reread and verified on two host filesystems; factory-stock restoration remains to be demonstrated. Development and backups use `/run/media/tim/Disk B/fx0` through the space-free bind mount `/tmp/fx0-storage`; re-establish that mount after a host reboot.

Linux 6.18.59 LTS now boots on the Fx0 with all four CPUs online, a framebuffer console, USB NCM networking and an ACM root shell. eMMC enumerates all 39 partitions at 200 MHz in 8-bit HS200 mode. Two complete 1 GiB system-partition reads match the verified backup after correcting the stock firmware memory exclusions. The first userdata image write failed; permitting the eMMC regulator load votes subsequently allowed a fresh 32 MiB write and matching cache-cleared readback without errors. A full image write and independent readback subsequently passed; sustained storage/USB qualification remains pending. The helper's 12 failure-oriented tests pass, and current kernel/DTB/module and schema checks are recorded under `evidence/`.

lk2nd is installed and its filesystem boot path now starts Nura v26.06 from userdata. The verified initial maintained kernel is `6.18.59-00011-gb7575530db2d`; SSH works, all four CPUs are online, root expanded to 3.4 GiB within userdata, and the firewall is active. The image write passed complete device and host readback, with both outer GPT copies unchanged. Normal lk2nd was verified to start that Nura build automatically on warm reboot, and a fresh installed-filesystem test file survives with a matching cache-cleared host readback.

The screen remains unqualified. The experimental IOMMU branch now initializes secure page tables and reaches native DRM scanout with runtime power held active. Kernel 35 receives valid panel replies; matching the stock clock-lane control changes power status from 0x0c to 0x1c, with physical pixels still awaiting confirmation. The original kernel, booted from RAM, displays correct RGB bars after a full display power cycle and records touch events. Candidate Nura boots repeatedly restarted in early systemd; the reset cause remains open. The device has been recovered into RAM diagnostics with a temporary forced-fastboot secondary prefix and read-only Nura mounts. Touch probes as Synaptics PLG430 but owner interaction produced no events. The charger has reported both Overheat/Discharging and Good/Fast/Charging; charging policy and automatic USB current negotiation remain unresolved. Plymouth is disabled after its initial crash. Native display/touch, wireless, audio, sensors, both cameras, cellular, full update/recovery and reliability acceptance remain open. No SIM is available.

A host-only storage preview combines the five adjacent Android payload partitions into one approximately 14.30 GiB modern ext4 root while conservatively retaining earlier firmware/provisioning offsets. Its GPT CRCs, filesystem check and complete embedded-filesystem readback pass. A proposed updater preserves lk2nd’s prefix in the existing boot partition, potentially avoiding a separate boot filesystem; source CI passes, but physical boot/update/recovery and the minimum-partition audit remain pending. No device repartitioning has occurred.

Continue the open bringup work in the [plan](docs/bringup-plan.md). Its required section 2.1 adds verified complete restoration coverage, demonstrated factory-stock rollback, and migration to one large native root filesystem with only necessary extra partitions. External SD remains ordinary removable Linux media. Current source pins are in [the manifest](manifests/sources.json), and [full image recipes](docs/building.md) use the public integration branches. The source-subset DTB scripts retain the original dated minimal candidate for historical reproduction; it lacks the later physical bringup fixes.

## Local and public material

Keep reproducible source changes, documentation, sanitized test evidence, and source revisions in public Git repositories. Keep original device dumps, calibration, identifiers, credentials, firmware without redistribution rights, build products, and full source checkouts in ignored local directories. The initial [ignore rules](.gitignore) establish that separation; inspect every staged change before committing.

The root Git working tree is initialized. Public repository URLs and tested revisions are recorded as they are provisioned; upstream submissions remain a separate final step.

## Licensing

Original coordination documentation and helper code use the [MIT license](LICENSE). Third-party patches and recovered device descriptions retain the licenses and copyright notices of their respective projects/files. The root license does not relicense those materials or device firmware.
