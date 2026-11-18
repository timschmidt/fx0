# Installed Fx0 peripheral checks on Linux 6.18.64

The native installation was verified over USB on 2026-11-18 UTC. Systemd and
the desktop services ran, kernel taint was zero, and module signature
enforcement was enabled. Boot, package database and repository hashes
matched before and after the tests. Kernel.org listed 6.18.64 as the current
release in the maintained 6.18 series. [Kernel.org release listing](https://www.kernel.org/)

The front and rear cameras completed five capture sessions at 1976×1200,
1640×1232 and 3280×2464. Each session delivered 24 consecutive RAW10 frames.
The worker verified at least 16 consecutive sensor color-bar frames per session.
Both sensor controls returned to their original values and both sensors
runtime-suspended after close. USB remained configured at high speed. The
independent journal check covered the 21.7-second service window and found
zero VFE missing-ready-buffer warnings, display underruns or camera/IOMMU
faults. The worker’s original matcher omitted the VFE buffer warning. Frame files
stayed in phone RAM and the test removed them. Scene quality, sustained
capture and system resume still require qualification.

The NFC generic netlink GET_DEVICE command reported the registered NXP NCI
controller with protocol mask 126 and unchanged powered-off state. One pilot
and ten consecutive DEV_UP/DEV_DOWN pairs passed. The installed NCI startup
path completes RESET, INIT and interface mapping before reporting powered on.
Each repeat produced three startup interrupts and one shutdown interrupt. The
19.2 MHz reference-clock vote and enable GPIO changed with the powered state,
the firmware GPIO stayed low, and the cold state returned after every cycle.
The final IRQ count stayed stable for three seconds. The scoped journal check
found zero NFC or kernel faults. Shutdown reset status was unavailable, and
physical tag operation and suspend remain open.

The microSD controller was bound to sdhci_msm and showed its active-low
detect input high. It had no enumerated media, so the direct SD read was
unavailable.

The larger eMMC test rejected its preflight on the 2 GiB free-space reserve.
The phone had about 414 MiB available. The failed transient unit temporarily
left systemd degraded. Resetting that unit returned systemd to running and
preserved the failed attempt. A distinct test used a 32 MiB file with a
350 MiB reserve. Four write, fsync, close, reopen and direct-read rounds matched
all synthetic bytes and independent hashes. The kernel journal and ext4
error count showed zero matching errors. The completed unit was released.
Removing four redundant diagnostic module staging trees reclaimed about
55 MiB. All 479 files in each copy matched the manifest and a retained on-phone
copy, and the corresponding workstation archives were verified. Recovery files,
stage manifests and installed boot and package hashes were preserved.

The synthetic file remains available for a cross-boot comparison. The checker
verified that the original boot cannot count as persistence. The current
persistent Wi-Fi policy allows startup scanning, so the reboot remains
pending. Larger storage loads, cold boot, unplugged standby and the complete
reliability matrix remain open.

## Sensors and offscreen graphics

The MPU-6515 accelerometer and gyroscope and the HSCDTD008A magnetometer
each returned 16 vectors without read errors. The first probe assumed a
shared scale and failed on the magnetometer’s per-axis attributes. The
corrected reads used the live ABI. All three exported mounting matrices
matched the board device tree, including the magnetometer’s
`in_mount_matrix`. Physical pose calibration and resume remain open.

The EGL test opened the MSM DRM render node and created five offscreen GLES
contexts. Mesa 26.1.6 reported Freedreno FD305. Two alternating shader
patterns matched every pixel across 40 RGBA frames, totaling 163,840
pixel comparisons. The test closed the render node and the scoped kernel
journal showed zero matching GPU, IOMMU or display faults. The installed
boot and package hashes matched after the test. This covers basic rendering
correctness and context recreation. Sustained load and compositor behavior
remain separate.

## Venus video codec

The installed device exposed only the three CAMSS VFE video outputs. The
stock MSM8226 source describes a VIDC engine at `0xfdc00000` and a Venus
firmware-loader wrapper at `0xfdce0000`. No matching DT or platform device
appeared on the installed kernel. The firmware query checked known Venus
filenames under the installed firmware paths. It found none in those paths.

The maintained MSM8226 MMCC driver already provides the Venus core, AHB
and AXI clocks, a reset and a power domain. The installed kernel’s Venus
Kconfig gate is ARM64 in regular Qualcomm configurations. An isolated
Clang 21 Kbuild test directly compiled all 18 existing Venus sources for
ARM32 and linked three relocatable core, decoder and encoder objects with no
diagnostics. The ordinary Kconfig gate remained in effect. ARM32 DMA and
IOMMU behavior, the stock firmware and HFI contract, platform binding, and
actual hardware encode/decode remain open. [Linux Venus source](https://raw.githubusercontent.com/torvalds/linux/master/drivers/media/platform/qcom/venus/core.c)

[Sanitized device evidence](../evidence/2026-11-18-installed-6.18.64-peripherals.json)
