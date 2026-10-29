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

Implementation started October 29, 2026. Host USB, network, build tools, and Git access are available. The stock phone has been inventoried through root ADB. All 29 selected critical partitions have independently matching rereads, verified copies on Disk B, and a verified recovery copy on the phone's internal SD storage. GPT metadata is also preserved privately.

The inventory/backup helper passes 12 failure-oriented tests, including the stock KitKat ADB fallback. Linux 6.18.59 LTS board DTBs compile without adding warnings over the SoC baseline; the full kernel and module build has succeeded. The Fx0-only lk2nd image has booted in RAM and from the installed boot partition, detecting the board correctly. Linux has reached its framebuffer console and diagnostic userspace. USB diagnostics and the remaining Nura hardware qualification remain open. Raw device logs and images remain private.

Persistent build and backup storage is `/run/media/tim/Disk B/fx0`, accessed by build tools through the space-free bind mount `/tmp/fx0-storage`. Re-establish that mount after a host reboot. Keep development documentation and scripts in this repository.

An archived vendor-kernel port, a minimal earlier mainline device tree, and lk2nd recognition exist. These provide a starting point; they do not establish complete current Nura support. See the research document for the exact sources and their limits.

Start with phase 0 of the bringup plan: establish host access, version control, original-system inventory, backups, and recovery. Shell access and a Wi-Fi handheld are intermediate milestones. Cameras, cellular, power management, and the remaining hardware stay in scope through final acceptance.

## Local and public material

Keep reproducible source changes, documentation, sanitized test evidence, and source revisions in public Git repositories. Keep original device dumps, calibration, identifiers, credentials, firmware without redistribution rights, build products, and full source checkouts in ignored local directories. The initial [ignore rules](.gitignore) establish that separation; inspect every staged change before committing.

The root Git working tree is initialized. Public repository URLs and tested revisions are recorded as they are provisioned; upstream submissions remain a separate final step.

## Licensing

Original coordination documentation and helper code use the [MIT license](LICENSE). Third-party patches and recovered device descriptions retain the licenses and copyright notices of their respective projects/files. The root license does not relicense those materials or device firmware.
