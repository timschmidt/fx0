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

lk2nd is installed as the secondary boot image and supports repeatable fastboot entry and RAM boots. The Nura v26.06 console image passes filesystem, maintained-kernel package and required configuration checks. Its first write to userdata failed; userdata must be treated as partially overwritten, and no installed Nura boot is established. Charger temperature policy, native display/touch, wireless, audio, sensors, both cameras, cellular and the remaining acceptance work stay open. No SIM is available.

Continue with phase 2 of the [bringup plan](docs/bringup-plan.md). Current source pins are in [the manifest](manifests/sources.json), and [full image recipes](docs/building.md) use the public integration branches. The source-subset DTB scripts retain the original dated minimal candidate for historical reproduction; it lacks the later physical bringup fixes.

## Local and public material

Keep reproducible source changes, documentation, sanitized test evidence, and source revisions in public Git repositories. Keep original device dumps, calibration, identifiers, credentials, firmware without redistribution rights, build products, and full source checkouts in ignored local directories. The initial [ignore rules](.gitignore) establish that separation; inspect every staged change before committing.

The root Git working tree is initialized. Public repository URLs and tested revisions are recorded as they are provisioned; upstream submissions remain a separate final step.

## Licensing

Original coordination documentation and helper code use the [MIT license](LICENSE). Third-party patches and recovered device descriptions retain the licenses and copyright notices of their respective projects/files. The root license does not relicense those materials or device firmware.
