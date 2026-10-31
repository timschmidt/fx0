# LG Fx0 Nura bringup

Bring a physical LG Fx0 LGL25 to the current Nura release with all hardware working, reliable updates, and patches prepared for submission to the appropriate upstream projects. Development takes place in this folder.

The device is available for development and flashing. No personal data needs to be retained. Original firmware and device calibration must still be preserved for recovery and hardware operation. No SIM is currently available; cellular acceptance remains pending until it can be tested.

## Project documents

| Document | Purpose |
| --- | --- |
| [Bringup plan](docs/bringup-plan.md) | Ordered implementation steps, dependencies, recovery requirements, and completion criteria |
| [Storage consolidation](docs/storage-layout.md) | Measured root layout, boot-image update preparation and remaining restoration gates |
| [Partition audit](docs/partition-audit.md) | Reference evidence and reason for every retained GPT entry |
| [Audio assessment](docs/audio-bringup.md) | Stock WCD9302/SLIMbus/ADSP design, mainline gaps and ordered audio work |
| [GPU assessment](docs/gpu-bringup.md) | Adreno 305 node, firmware, missing GPU IOMMU and acceleration steps |
| [Stock hardware](docs/stock-hardware.md) | Physical inventory and implications for board support |
| [Hardware acceptance](docs/hardware-acceptance.md) | Full hardware inventory and tests required before declaring completion |
| [Upstream development](docs/upstream-development.md) | Public repository structure, patch ownership, validation, and submission preparation |
| [Upstream status](docs/upstream-status.md) | Every downstream change, its target tree, prepared material and dependencies |
| [Nura integration](docs/nura-integration.md) | Fx0 overrides on the installed system: device-package content versus development fixtures |
| [Research](docs/research.md) | Source references, recovered work, and facts that need physical confirmation |
| [Device operations](docs/device-operations.md) | Read-only inventory, verified partition backups, and helper usage |
| [Image builds](docs/building.md) | Full diagnostic kernel/lk2nd recipes and rootfs preparation |
| [Development patches](patches/README.md) | Initial Linux and lk2nd candidates with reproducible DTB checks |
| [Development log](docs/development-log.md) | Observed device/host state, completed checks, and the next executable work |
| [Battery work](docs/battery-bringup.md) | Stock pack/profile evidence, current sensing, native BMS and charging sequence |
| [Camera work](docs/camera-bringup.md) | Confirmed sensor IDs, wiring, capture-engine gaps and verified private EEPROM readbacks |
| [Kernel gaps](docs/kernel-gaps.md) | Maintained-kernel target and missing shared SoC/camera infrastructure |
| [Wireless work](docs/wireless-bringup.md) | WCNSS supplies, firmware start, Wi-Fi/Bluetooth results and upstream fixes |

## Current state

As of 2026-10-31 the Fx0 runs Nura v26.06 as an ordinary Linux system:

- **Storage:** final layout. Partitions 1–34 (boot chain, firmware, calibration)
  are unchanged, and the former Android system/cache/userdata/internal-SD/grow
  space is one 14.3 GiB native ext4 root with 12.67 GB free. The factory-stock
  restoration was rehearsed first, and a verified whole-eMMC snapshot predates
  the change. See [storage](docs/storage-layout.md).
- **Boot:** a production lk2nd boots the kernel image stored after it in the
  boot partition, unattended from power-on or reboot. Volume Down at power-on,
  or `systemctl reboot --reboot-argument=bootloader`, enters lk2nd fastboot.
  `mkinitfs` updates the image in place (boot-deploy 0.23.0-r1). Twenty
  consecutive warm reboots pass.
- **Kernel:** signed `linux-postmarketos-qcom-msm8226-6.18.59-r8`, taint 0.
- **Working:** native display and touch; a GLES2 Sxmo session on Freedreno
  (Adreno 305, devfreq); Wi-Fi including a 1-hour soak and hotspot (PMF off);
  Bluetooth pairing, RFCOMM and A2DP headphones with AVRCP play/pause; USB
  network gadget; buttons; the ADSP firmware with its sensor and SLIMbus
  services. See the [hardware acceptance matrix](docs/hardware-acceptance.md).
- **Open:** audio codec (no mainline WCD9302 driver), sensors, cameras,
  cellular (no SIM), suspend and power, battery fuel gauge and charging policy,
  Bluetooth headset calls and keyboard, microSD, 20 cold boots, rollback from
  the consolidated layout, and the 24-hour soak (running). Some development
  fixtures remain; see [Nura integration](docs/nura-integration.md).
- **Upstream:** prepared, unsent drafts for remoteproc, wireless, power-supply,
  IIO, PHY, DRM panel, UPower, lk2nd and boot-deploy. Sending waits for the
  owner's approval and Signed-off-by. See [upstream status](docs/upstream-status.md).

Development and backups use `/run/media/tim/Disk B/fx0` through
`/tmp/fx0-storage`; re-establish that bind mount after a host reboot. The
[development log](docs/development-log.md) has the full history.

## Local and public material

Keep reproducible source changes, documentation, sanitized test evidence, and source revisions in public Git repositories. Keep original device dumps, calibration, identifiers, credentials, firmware without redistribution rights, build products, and full source checkouts in ignored local directories. The initial [ignore rules](.gitignore) establish that separation; inspect every staged change before committing.

The root Git working tree is initialized. Public repository URLs and tested revisions are recorded as they are provisioned; upstream submissions remain a separate final step.

## Licensing

Original coordination documentation and helper code use the [MIT license](LICENSE). Third-party patches and recovered device descriptions retain the licenses and copyright notices of their respective projects/files. The root license does not relicense those materials or device firmware.
