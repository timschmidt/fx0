# LG Fx0 Nura bringup

Bring a physical LG Fx0 LGL25 to the current Nura release with all hardware working, reliable updates, and patches prepared for submission to the appropriate upstream projects. Development takes place in this folder.

The device is available for development and flashing. No personal data needs to be retained. Original firmware and device calibration must still be preserved for recovery and hardware operation. No SIM is currently available; cellular acceptance remains pending until it can be tested.

## Project documents

| Document | Purpose |
| --- | --- |
| [Bringup plan](docs/bringup-plan.md) | Ordered implementation steps, dependencies, recovery requirements, and completion criteria |
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

Implementation started October 29, 2026. Stock firmware inventory, 29 critical partition backups, recovery copies, GPT metadata, and a separately verified 1 GiB original-system backup are preserved privately. Development and backups use `/run/media/tim/Disk B/fx0` through the space-free bind mount `/tmp/fx0-storage`; re-establish that mount after a host reboot.

Linux 6.18.59 LTS now boots on the Fx0 with all four CPUs online, a framebuffer console, USB NCM networking and an ACM root shell. eMMC enumerates all 39 partitions at 200 MHz in 8-bit HS200 mode. Two complete 1 GiB system-partition reads match the verified backup after correcting the stock firmware memory exclusions. The first userdata image write failed; permitting the eMMC regulator load votes subsequently allowed a fresh 32 MiB write and matching cache-cleared readback without errors. Full installation and sustained storage/USB qualification remain pending. The helper's 12 failure-oriented tests pass, and current kernel/DTB/module and schema checks are recorded under `evidence/`.

lk2nd is installed and its filesystem boot path now starts Nura v26.06 from userdata. The running maintained kernel is `6.18.59-00011-gb7575530db2d`; SSH works, all four CPUs are online, root expanded to 3.4 GiB within userdata, and the firewall is active. The image write passed complete device and host readback, with both outer GPT copies unchanged. Normal lk2nd now starts Nura automatically on warm reboot, and a fresh installed-filesystem test file survives with a matching cache-cleared host readback.

The installed system currently has a blank screen despite an inherited framebuffer device and active text getty; Plymouth crashed during the first boot and has been disabled; temporary clock/domain preservation flags did not restore the screen. Charging still reports the unresolved Overheat condition. Native display/touch, wireless, audio, sensors, both cameras, cellular, full update/recovery and reliability acceptance remain open. No SIM is available.

Continue the open bringup work in the [plan](docs/bringup-plan.md). Its required section 2.1 adds verified complete restoration coverage, demonstrated factory-stock rollback, and migration to one large native root filesystem with only necessary extra partitions. External SD remains ordinary removable Linux media. Current source pins are in [the manifest](manifests/sources.json), and [full image recipes](docs/building.md) use the public integration branches. The source-subset DTB scripts retain the original dated minimal candidate for historical reproduction; it lacks the later physical bringup fixes.

## Local and public material

Keep reproducible source changes, documentation, sanitized test evidence, and source revisions in public Git repositories. Keep original device dumps, calibration, identifiers, credentials, firmware without redistribution rights, build products, and full source checkouts in ignored local directories. The initial [ignore rules](.gitignore) establish that separation; inspect every staged change before committing.

The root Git working tree is initialized. Public repository URLs and tested revisions are recorded as they are provisioned; upstream submissions remain a separate final step.

## Licensing

Original coordination documentation and helper code use the [MIT license](LICENSE). Third-party patches and recovered device descriptions retain the licenses and copyright notices of their respective projects/files. The root license does not relicense those materials or device firmware.
