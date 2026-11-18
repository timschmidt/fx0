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

The retained 32 MiB file survived one normal reboot into the installed kernel.
A direct read matched every byte and the expected SHA-256. The eMMC read
counter advanced, ext4 reported zero errors, and the protected boot and
package hashes matched. The checker also rejected the original boot as a
persistence result. Larger storage loads, cold boot, unplugged standby and
the complete reliability matrix remain open.
[Warm-reboot storage evidence](../evidence/2026-11-18-emmc-warm-reboot.json)

## USB bulk transfer

On physical USB port `1-7`, four 16 MiB uploads and four 16 MiB downloads
matched independent SHA-256 checks over the installed high-speed gadget.
Both sockets stayed bound to their USB interfaces. The controller reaped the
receiver, the original route still matched, and neither endpoint recorded
RX or TX errors or drops over the sampled interval. The first two attempts
stopped during harness setup before any test payload transfer. The corrected
receiver used the phone's supported route output format. Physical reconnect
and Fastboot still require separate tests.

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

The maintained MSM8226 MMCC driver already provides the core, AHB and AXI
clocks, a reset and a power domain. The installed Venus Kconfig gate requires
ARM64 for a regular Qualcomm configuration. An initial Clang 21 run compiled
all 18 Venus sources as ARM32 objects. The stock ARM32 configuration compiles
the generic IOVA reservation API to a failure stub, so the codec would still
stop at probe after removing only the Kconfig gate.

The ARM32 diagnostic admits probe only when the active legacy DMA operations
and attached domain provide an allocator that excludes the bottom 600 MiB.
It checks the full bitmap extent, including future extensions, against the
advertised hardware and bus DMA limits. The firmware-described IOMMU alone
is insufficient. The ARM64 control still calls the generic IOVA allocator.
The [host checker](../diagnostics/venus-arm32/check-aperture.py) executes the
actual helpers with synthetic device state. Its 23 checks pass under UBSan.
The fixture also detects five deliberately weakened guard conditions.
[Venus low-IOVA reservation rationale](https://lists.openwall.net/linux-kernel/2026/08/07/603)

A regular Qualcomm ARM32 Kbuild run produced `vmlinux` and 473 modules with
compile-test mode off. Venus entered through its normal Kconfig selection.
The three Venus modules match the linked kernel release and all 379 imported
symbol CRCs. The modules are unsigned host artifacts. A separate `W=1` run
reproduced the same six ARM DMA kernel-doc warnings on the original source.
The first full-build attempt created an ephemeral signing key because lockdown
reselected signature support. That build was stopped and the temporary key
removed. The completed run used the public verification certificate and kept
automatic signing disabled.
[ARM32 DMA and Venus source](https://github.com/timschmidt/fx0-linux/commit/518c05d54ff73e03e86ce8f3b6822511d592b7aa)

The original stock ext4 system image contains the Venus MDT and split firmware.
The [inspector](../diagnostics/venus-arm32/inspect-stock-firmware.py) checks the
image hash, ELF header and split sizes. The three loadable segments fit in
a 5 MiB span from `0x0f500000` to `0x0fa00000` (exclusive). Eight malformed
metadata controls are rejected. The installed device reports that span as
ordinary System RAM. A host-only DTB experiment reserves exactly that range
between ADSP and SMEM. The reservation checker rejects a short range, an
unaligned range and overlaps with either neighbor. Firmware authentication
still requires the device's secure firmware service.

The stock and maintained C definitions agree on 38 initialization constants,
fixed offsets and queue fields. The stock nonsecure IOMMU aperture runs
from `0x40000000` to `0x80000000`
(exclusive). Vendor IOMMU context banks 0–2 and the clock selector have distinct
roles. The codec's stock MMIO resource includes the IOMMU window, so the Linux
binding needs nonoverlapping ownership and a documented clock-selector path.
The binding, bandwidth votes, firmware authentication, and physical video
encode/decode still require qualification.
[Stock IOMMU descriptions](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226-iommu.dtsi)

### MSM8226 device-tree preview

The separate Madai Venus DTB describes seven disjoint codec and IOMMU MMIO
windows. The IOMMU owns the wrapper clock selector. The codec has separate
resources for the wrapper version and the registers above the selector. Linux
binds only the nonsecure IOMMU context. The codec's DMA bus describes the stock
1 GiB aperture, and its firmware phandle points at the 5 MiB `no-map` reservation.
Both hardware nodes have `status = "disabled"`. The normal packaged Madai DTB
matched the rebuild byte for byte.

The driver uses the stock clock rates, codec write presets, IOMMU tuning and
DDR bandwidth vectors. The bandwidth code adds average votes by direction and
takes the larger peak. A host model checks the actual split and legacy MMIO
functions, clock-selector readback, runtime-resume error propagation at attach,
and bandwidth boundaries. It detects five injected faults. Eight invalid DTB
copies exercise the new schema gates, including a missing clock resource, an
extra secure context and codec enablement without interconnect paths.

The preview links on ARM32 and the changed driver code compiles on ARM64.
Runtime PM errors on IOMMU teardown and TLB paths still need qualification
before a device trial of PAS firmware startup and HFI operation.
[Platform source](https://github.com/timschmidt/fx0-linux/commit/b190c7dfd9eeac3588807c39107f2e64d0050ecb)

[Platform preview evidence](../evidence/2026-11-18-venus-platform-preview.json)

### MSM8226 Venus memory interconnect

The expanded preview follows the stock Video P0 route through the multimedia
NoC and the memory controller to DDR channel 0. The application processor
owns both QoS ports. The DDR endpoint uses RPM slave 0. MSM8226's multimedia
QoS ports are spaced 0x80 bytes apart. Other users of the shared legacy NoC
driver retain their 0x1000-byte spacing. The stock video driver requests
bandwidth through its DDR path and uses the Venus interface clocks for CPU
register access. The MSM8226 binding requires `video-mem` for an enabled
codec. [Stock fabric tables](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226-bus.dtsi)
[Stock video vote parser](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/media/platform/msm/vidc/msm_vidc_res_parse.c)

The ARM32 build produced `vmlinux` and 474 modules. All 431 inspected symbol
imports match the linked kernel. Nine checks on the actual backend and
topology pass under UBSan, and five injected faults are detected. The binding
accepts the single stock route and rejects five malformed device-tree copies.
The regular Madai DTB matches the signed package byte for byte. The preview's
two providers, codec and IOMMU are disabled. Before enabling the fabrics,
their shared AXI and DDR clock votes need qualification with the existing
display, GPU and memory users. [Kernel source](https://github.com/timschmidt/fx0-linux/commit/6213d215f298c949e293cfb699c4b8c22716ce31)

```sh
python3 -B diagnostics/venus-arm32/check-interconnect.py /path/to/linux /path/to/results
```

[Interconnect qualification evidence](../evidence/2026-11-18-venus-interconnect-preview.json)

### IOMMU resume and range invalidation

A failed runtime resume now returns its error before an identity attach can
touch the context bank or release a runtime PM reference. Range invalidation
starts each context bank at the original aligned IOVA and combines that
address with the bank's ASID. The host replay exercises four identity-attach
cases and checks all twelve register writes across leaf and walk invalidation.
It detects both faults when the previous implementations are substituted one
at a time. [Linux runtime PM API](https://docs.kernel.org/6.18/power/runtime_pm.html)
[Kernel source](https://github.com/timschmidt/fx0-linux/commit/b7803c465ce017fd98b1f8ce4ac49d775b8cae44)

[Identity attach and range invalidation evidence](../evidence/2026-11-18-venus-iommu-runtime-pm.json)

### Venus teardown and resume

The Venus IOMMU now removes software mappings while suspended because ARM DMA
can release the IOVA immediately after unmap. The runtime suspend path
quiesces the Linux-owned bank before gating its clocks. Resume disables and
invalidates that bank, waits for the TLB to finish, and restores registers
only for a live domain. The runtime PM supplier returns an error if halt or
TLB synchronization times out. Domain release clears the saved owner and
drains its interrupt handler before freeing the tables. [Kernel source](https://github.com/timschmidt/fx0-linux/commit/ce2139f533703bbd60ff1d121d283736e2f541f4)

The ARM32 build produced `vmlinux` and 474 modules. The two Madai DTBs and the
exported symbol CRCs match the previous preview. The host replay covers
online and offline unmap, full and gathered TLB operations, interrupts,
four resume failures, retry and domain release. It detects six deliberate
regressions under UBSan. The preview is disabled on the phone pending shared
clock vote and real PAS, HFI and codec tests. The common driver's active TLB
timeout still logs the error without propagating it to the DMA caller.

```sh
python3 -B diagnostics/venus-arm32/check-platform.py /path/to/linux /path/to/results
```

[Teardown and resume qualification evidence](../evidence/2026-11-18-venus-iommu-offline.json)

### Shared AXI and DDR clocks

The video-only provider leaves the RPM clock controller's boot votes in
place for the DDR clock while the other memory clients still use that
baseline. It sends the video bandwidth request to EBI slave 0 and starts its
managed endpoints at zero, avoiding the interconnect core's initial
maximum-bandwidth request. The multimedia AXI clock uses a per-consumer
minimum. Display and camera can request higher rates, and an idle video
request releases the minimum. The physical clock rate after release depends
on the clock framework's outstanding requests. [Kernel source](https://github.com/timschmidt/fx0-linux/commit/9dc6ed47e56d16a4dbf855974484d7994890dd33)
[Linux common clock framework](https://docs.kernel.org/driver-api/clk.html)

The workstation replay runs the maintained provider and interconnect core
with simulated clock and RPM services. Nineteen checks pass and nine fault
controls are detected. The ARM32 kernel and 474 modules build with both
Madai DTBs unchanged. Concurrent display, camera and video operation still
needs a device trial. The installed firmware inventory has no Venus file at
the driver's requested `qcom/msm8226/venus.mdt` path. The stock and maintained
drivers use PAS ID 9. [Stock PAS ID](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/mach-msm/scm-pas.h)

[Shared clock qualification evidence](../evidence/2026-11-18-venus-shared-clocks.json)

### Stock Venus firmware metadata

The maintained MDT loader recognized the stock image as split firmware and
computed a 5 MiB load span. Its copy of the 412-byte metadata matched the
original bytes. The replay uses SCM stubs to check PAS ID 9, the relocation
base and size, and error propagation from both calls. The handset's secure
firmware service still needs to authenticate the real image.
[Metadata replay evidence](../evidence/2026-11-18-venus-stock-mdt-model.json)

```sh
python3 -B diagnostics/venus-arm32/replay-stock-mdt.py /path/to/linux /path/to/stock/manifest.json /path/to/results
```

### Stock Venus firmware staging

The private stage contains the four files requested at `qcom/msm8226/`.
The three split files match their ranges in the original stock MBN. The
maintained loader read them into the expected 5 MiB span, and the replay
checked payload placement, zero-filled bytes, untouched gaps and guard
bytes. All six missing and short split-file tests returned the expected
errors. [Linux firmware search paths](https://docs.kernel.org/driver-api/firmware/fw_search_path.html)

The ARM32 Venus module declares the four exact firmware filenames. The
driver preserves negative loader and authentication errors and reports
positive secure-service status while returning `-EIO` to the kernel.
Seven simulated boot errors exercise those paths. A separate trial DTB
enables the two interconnect providers, Venus IOMMU and codec. Its only
device-tree changes are those four status properties, and it passes the
three targeted schemas. [Kernel source](https://github.com/timschmidt/fx0-linux/commit/7b3824ec1705cc528ae5567b87d25f3158268aaa)
[Firmware staging evidence](../evidence/2026-11-18-venus-firmware-staging.json)

### Private Venus RAM image

The ARM32 RAM image uses the trial DTB and a dedicated module certificate
embedded in the candidate kernel. Signature enforcement is built in. All
474 module signatures and 26,110 imported symbol CRCs were verified.
Modified and unsigned module controls were rejected. The compressed
ramdisk leaves about 3.5 MiB before the inherited framebuffer.
[Linux module signing](https://docs.kernel.org/admin-guide/module-signing.html)

The independent unpack check verifies the Android image header, both
initramfs archives, all 488 module and index files and the four firmware
files. The firmware is available in the initramfs. The cleanup hook carries
it into the final userspace under `/run` and verifies its contents. The
image includes the early return helper at 420 seconds and the normal
return timer at 360 seconds. The actual ARM scripts passed syntax checks.
The return fixture and six startup hook cases passed with hardware calls
simulated. [RAM image qualification evidence](../evidence/2026-11-18-venus-ram-image.json)

The candidate prevents the WLAN module from loading. The operator permits one
normal startup scan on the installed return boot.

### Initial handset trial

The bootloader accepted one RAM BOOT after exact image readback. The retained
console records the candidate entering the initramfs, arming early return,
and adding the codec to an IOMMU group. The Venus driver then returned
`-ENODATA` during probe. The console ends at 16.4 seconds without identifying
the reset cause. The controller did not reach candidate SSH or run the codec
workload. It independently verified the return to installed 6.18.64 with all
seven protected hashes matching.

The candidate device tree supplies only the required `video-mem` interconnect.
Ten host cases exercise the actual Venus and OF interconnect lookup code.
The fix allows the optional `cpu-cfg` name to be absent on MSM8226 and preserves
lookup errors for supplied paths. A separate replay runs the original
postmarketOS initramfs firmware setup before the staging hook. This reproduces
the original hook's rejection of the active firmware path. The corrected hook
verifies the early path, checks the copied firmware, then switches to `/run`
before the installed root starts. The rebuilt private image passed independent
archive checks and verification of all 474 module signatures.
[Initial trial and corrected image evidence](../evidence/2026-11-18-venus-ram-first-trial.json)

### Corrected handset trial

The second trial transferred the corrected image with exact readback and
issued one RAM BOOT. The candidate reached postmarketOS initramfs stage two
and armed the early return helper. Its matched console ends at 15.2 seconds.
It contains neither the original `-ENODATA` probe error nor enough evidence to
identify the reset cause. The installed kernel returned with matching boot and
package hashes, and the compositor and gesture service were running. Candidate
SSH and H.264 acceptance remain unverified. The next diagnostic needs to
separate initramfs boot from the first Venus probe.
[Corrected handset trial evidence](../evidence/2026-11-18-venus-ram-second-trial.json)

### Coldplug and ordinary-DTB control

The boot arguments for the third trial deferred automatic Venus module
loading through kmod. The candidate returned before USB userspace, so the
controller never asked for an explicit module load. The retained console
ended at 16.8 seconds. The same Adreno firmware warning also appeared during
the successful capped power-management boot.

The next trial used the ordinary signed DTB with the exact same Venus kernel,
ramdisk and boot arguments. It reached USB userspace with signature enforcement,
both automatic return paths and all four staged Venus firmware files present.
The active firmware path was `/run/msm-firmware-loader/target`, which is
managed by the installed MSM firmware loader. The general codec-readiness
check therefore stayed false. The control localizes the early failure to the
diagnostic DTB or its interaction with the kernel. The next driver test needs
to isolate the new device nodes and resolve the firmware-path handoff.
Both tests returned with matching installed boot and package hashes.
[Coldplug and ordinary-DTB evidence](../evidence/2026-11-18-venus-dtb-control.json)

### Interconnect provider controls

With the codec and its IOMMU held disabled, enabling both providers kept the
diagnostic kernel from reaching USB userspace. Disabling both reached USB
userspace. BIMC alone also reached USB userspace and its driver bound. MMSS
NoC alone reproduced the early failure. Each image used the same kernel,
ramdisk and boot arguments. MMSS NoC coldplug is sufficient to reproduce the
observed failure. The retained console reaches early userspace, and the
matched panic records predate the test. The precise reset mechanism remains
unknown.

The stock MSM8226 clock driver makes the MMSS S0 AXI branch depend on the
MMSS NoC AXI branch. The diagnostic provider prepares the shared AXI root
and takes the S0 branch for QoS setup. The maintained clock driver exposes
both branches as children of the root. On the installed kernel, both branches
were enabled in hardware at 100 MHz while Linux held zero references to
either. An opt-in diagnostic held an S0 reference through provider probe.
The retained console shows the reference acquired before probe and retained
after successful probe. The installed kernel returned with all 482 module
files and protected hashes verified. [Stock MSM8226 clock source](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/mach-msm/clock-8226.c)

The next control retained the S0 reference and skipped the Video P0 QoS
register setup at probe. The boot log confirms both conditions and successful
provider probe. A later audit of both RAM images found out-of-tree module
metadata and stale module checksums. Their probe markers establish the
limited execution shown in the console. These packaging differences leave
later USB readiness untested under either intervention.

Deferring only the MMSS module's coldplug allowed the same kernel, ramdisk
and device tree to reach USB userspace with the provider unbound. After the
compositor started, the controller requested the original signed module.
The retained console records the explicit module load starting at 67.6
seconds. The installed kernel returned before the controller received a
completion receipt. The return audit matched all 482 module files and
protected hashes. This reproduces the problem after the desktop starts.
The failing operation within module load or probe remains open.

The instrumented retry first reached USB userspace with both providers
unbound. It required in-tree module builds and a manifest updated for both
signed replacements. The original startup checks stayed in place, and all
488 manifest entries matched. The late load completed bus and interface
clock enable, created both nodes and completed Video P0 QoS setup. The
last retained marker is the start of the interface clock release inside
`qnoc_probe()`. Provider publication did not appear in the trace. This
narrows the failure to the release interval. The exact clock operation and
reset mechanism remain open. The signed installed kernel returned with all
482 installed modules and protected hashes matching.

[Interconnect isolation evidence](../evidence/2026-11-18-venus-interconnect-isolation.json)

### Venus H.264 workload

A static ARM32 FFmpeg build includes the V4L2 mem-to-mem H.264 encoder and
decoder and a software decoder. Under ARM emulation, the software decoder
matched a workstation decode byte for byte across 12 reference frames.
The checker also rejected truncated frames, duplicate frames, swapped chroma,
ambiguous Venus device roles and unexpected device selection. The handset
workload checks that FFmpeg uses the two Venus devices and verifies the
decoded frames from each hardware operation. It still needs a handset run.
[Workload source](../diagnostics/venus-arm32/codec-acceptance.py)
[Host verification](../evidence/2026-11-18-venus-codec-workload.json)
[FFmpeg release verification](https://ffmpeg.org/download.html#releases)

[Venus and USB follow-up evidence](../evidence/2026-11-18-venus-arm32-and-usb.json)

[Sanitized device evidence](../evidence/2026-11-18-installed-6.18.64-peripherals.json)
