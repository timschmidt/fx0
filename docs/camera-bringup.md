# Fx0 camera implementation work

The saved original-kernel RAM log confirms rear ID **0x8179** and front ID **0x0132**, with both sensor probes succeeding on production revision 7. This proves identification under the original driver. Neither stock image capture nor maintained-kernel camera operation has passed.

The implementation has separate sensor, capture-engine, calibration and userspace dependencies. A successful CCI probe will not establish a working CSI/VFE pipeline. The earlier pre-DRM touch observation was saved as incomplete before advancing independent native CCI work; it had no confirmed gestures and is not a completed negative touch result.

## Production board wiring

The [pinned board source](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226-madai/msm8226-madai-camera.dtsi), matching original DTB and selected vendor power arrays describe the following. Voltages here are source constraints, not new electrical measurements.

| Item | Production source description |
| --- | --- |
| Rear sensor | IMX179, CCI master 0; downstream address 0x20 becomes Linux 7-bit address 0x10; 16-bit ID at register 0x0002 |
| Front sensor | IMX132, CCI master 0; downstream address 0x6c becomes Linux address 0x36; ID at register 0x0000 |
| Rear power | L26 digital 1.2 V; GPIO110 enables analogue 2.8 V; GPIO64 enables I/O 1.8 V; GPIO65 is VCM/standby control |
| Rear reset/clock | Active-low reset GPIO114; MCLK on GPIO26 |
| Front power | L5 digital 1.2 V; L15 analogue 2.8 V; shared I/O enable GPIO64 |
| Front reset/clock | Active-low reset GPIO28; MCLK on GPIO27; declared standby GPIO31 is not toggled by the selected production power array |
| Camera EEPROM | Downstream 0xa0 becomes Linux 0x50; word-addressed, configured read starts at zero and covers 0x900 bytes |
| Lens-control candidate | Downstream actuator 0x18 becomes 0x0c; exact part and functional control remain unverified |
| OIS candidate | Downstream 0x7c becomes 0x3e; Madai-specific power sequence uses GPIO63 for OIS enable and GPIO0 for OIS reset; exact installed controller remains unverified |

The vendor transport explicitly shifts the downstream addresses right by one. Do not use the 8-bit addresses as mainline `reg` values. The front `cam_vio-supply` reference to L5 is marked dummy; its actual selected power sequence uses GPIO64 for I/O. Do not describe the front I/O rail as 1.2 V from that dummy reference.

Production rear power uses the Madai-specific array in [imx179.c](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/media/platform/msm/camera_v2/sensor/imx179.c), including OIS reset/enable ordering. Production front power uses the non-rev0 array in [imx132.c](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/media/platform/msm/camera_v2/sensor/imx132.c). Preserve shared regulator ownership and establish which OIS dependencies are actually needed before translating those sequences into independent drivers.

The rear source selects CSIPHY0/CSID0, lane assignment 0x4320 and mask 0x1f. The front selects CSIPHY1/CSID0 and mask 0x03. The inspected two-phase PHY implementation has physical clock lane 1; the corresponding candidate physical data-lane positions are rear 0/2/3/4 and front 0. Verify this translation, lane polarities and actual link frequencies before streaming. Do not copy another board's lane numbering or assume both sensors can stream simultaneously through the selected routing.

## Capture-engine dependencies

The [stock SoC description](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/arch/arm/boot/dts/msm8226-camera.dtsi) gives these resources. SPI values are the device-tree SPI numbers, not dynamically allocated Linux IRQ numbers.

| Block | Physical resource | DT SPI |
| --- | --- | ---: |
| CCI | 0xfda0c000, size 0x1000 | 50 |
| CSIPHY0/1 | 0xfda0ac00 / 0xfda0b000, size 0x200 each | 78 / 79 |
| CSID0/1 | 0xfda08000 / 0xfda08400, size 0x100 each | 51 / 52 |
| ISPIF | 0xfda0a000, size 0x500; clock mux at 0xfda00020 | 55 |
| VFE 4.0 | 0xfda10000, size 0x1000 | 57 |
| VFE VBIF | 0xfda40000, size 0x200 | — |
| VFE IOMMU | 0xfda44000, size 0x10000 | Global 62; contexts 65 |

The selected vendor `madai_defconfig` enables **CSI 3.0 headers**, not the source tree's alternative CSI 2.2 headers. Several inspected CSI 3.0 register offsets match the maintained CSID 4.1 implementation; that is a source comparison, not a hardware compatibility result. A VFE 4.0 compatible name does not select the CSI header generation.

The vendor VFE implementation has explicit MSM8226 versions 0x20000013/0x20010014, dedicated VBIF initialization and buffer allocation policy. The maintained target provides VFE 4.1 operations and no MSM8226 CAMSS match. Audit the complete reset, interrupts, write-master, RDI, buffer, bus/QoS and clock behavior before deciding which code can be shared.

The camera IOMMU is separate from the display IOMMU. Stock contexts at 0xfda4c000/0xfda4d000/0xfda4e000 are labelled vfe0/vfe1/cpp with SIDs 0/1/2. The MSM8226-specific prefetch settings differ from the display settings. Camera DMA must not reuse the display tuning table by compatible-name substitution. Power domains, required interface/alternate-core clocks, secure/global setup, DMA mappings and fault handling need their own implementation and tests.

At inspected mainline commit `c339f4010dea8b0d754f84ace70cd1b089878ef8`, the [CAMSS match/resource file](https://github.com/torvalds/linux/blob/c339f4010dea8b0d754f84ace70cd1b089878ef8/drivers/media/platform/qcom/camss/camss.c) has no `msm8226-camss` match, and the [I2C driver Makefile](https://github.com/torvalds/linux/blob/c339f4010dea8b0d754f84ace70cd1b089878ef8/drivers/media/i2c/Makefile) has no dedicated IMX179/IMX132 entry. The local 6.18.59 target also lacks those dedicated sensor drivers. This checked scope does not assert that no external work exists.

## Register-setting evidence

Static inspection of the original system's sensor libraries finds these geometries. It does not execute the libraries, prove a setting is reachable, identify a working frame rate, or qualify physical output.

| Sensor | Register geometry | Frame lines | Line length |
| --- | --- | ---: | ---: |
| Rear | 3280×2464 | 2537 | 3440 |
| Rear | 1640×1232 | 2537 | 3440 |
| Rear | 3280×1848 | 2537 | 3440 |
| Front | 1976×1200 | 1280 | 2248 |

The libraries contain duplicate geometry settings. Do not interpret the number of decoded descriptors as a count of advertised camera modes. Cropping, Bayer order, embedded/optically black regions, pixel/link clocks, exposure and gain relationships still need verification.

The primary Tegra source at `6acf95d4100e2f31a130d84a1de9bb7753e4b8f5` supplies GPLv2 [IMX179](https://android.googlesource.com/kernel/tegra/+/6acf95d4100e2f31a130d84a1de9bb7753e4b8f5/drivers/media/platform/tegra/imx179.c) and [IMX132](https://android.googlesource.com/kernel/tegra/+/6acf95d4100e2f31a130d84a1de9bb7753e4b8f5/drivers/media/platform/tegra/imx132.c) register-table references. Their old misc-device API is not a mainline V4L2 sensor implementation. Keep attribution/licensing when using legitimate code. Notably, the IMX132 table named `mode_1920x1080` writes 1976×1144 geometry; an upstream sensor driver must describe the actual output rather than assuming the array label is the output size.

A further GPLv2 reference is the historical upstream AtomISP IMX driver at
Linux v4.14 commit `bebc6082da0a9f5d47a1ea2edc099bf671058bd4`. Its
[IMX132 definitions](https://github.com/torvalds/linux/blob/bebc6082da0a9f5d47a1ea2edc099bf671058bd4/drivers/staging/media/atomisp/i2c/imx/imx132.h)
and [driver](https://github.com/torvalds/linux/blob/bebc6082da0a9f5d47a1ea2edc099bf671058bd4/drivers/staging/media/atomisp/i2c/imx/imx.c)
provide lane-selection and exposure/gain references. The driver programs
register 0x3301 from the actual lane count and has IMX132 gain behavior dependent
on that count. Its AtomISP platform dependencies and old API need replacement;
this is historical source for review, not current Fx0 camera support. Preserve
attribution and verify board clock/lane assumptions before reuse.

The reproducible [mode inspector](../scripts/inspect_camera_modes.py) reads ARM32 relocation-backed register-setting descriptors or numeric C arrays and reports geometry without executing code:

```sh
python3 scripts/inspect_camera_modes.py --elf /private/libmmcamera_imx179.so \
  --elf /private/libmmcamera_imx132.so
python3 scripts/inspect_camera_modes.py --c-source /private/imx179-reference.c \
  --c-source /private/imx132-reference.c
```

Keep original libraries and calibration private. Publishing this decoded geometry does not authorize redistributing proprietary libraries or automatically copying their complete tables into a public driver.

## Calibration capture and coverage

A signed [temporary GPIO diagnostic](../diagnostics/camera-eeprom-read/README.md)
now reads the separate camera EEPROM on RAM kernel 39 without rebooting or
changing the open touch capture. Native CCI remains disabled. The diagnostic
uses open-drain SDA29/SCL30 and the production EEPROM's I/O enable GPIO64;
its only write is the EEPROM address pointer before a repeated-start read.
It does not program data, initialize OIS or run calibration.

Three independent 65536-byte reads match, including a final read using the
exact published source with its CCI-disabled guard. Each read cycles the I/O
enable and starts with a fresh module buffer. Verified private copies are saved
on two host filesystems. The complete 16-bit word-address space at 7-bit 0x50
repeats every 8192 bytes; this is observed aliasing, not proof of physical capacity
or coverage of other slave banks/security areas. The first 2560 bytes also match
an earlier shorter capture. Maker byte 0x0700 is 0x01, selecting the vendor's old
LGIT path; the 0x0900–0x09ff range contains non-erased data. Actual controller
identity/functionality and coefficient validity remain unverified. All 17
`E2pRed` fields used by the selected old LGIT initialization fit within the
captured first 8 KiB, ending at exclusive offset 0x0940; all lie outside the
original 0x900-byte cache. That consumer reads ascending byte addresses into a
reversed destination, so multi-byte fields decode big-endian on little-endian
ARM. This establishes range and byte-order coverage, not coefficient validity.

After each read the adapter and GPIO claims are released, SDA/SCL return to
inputs, and GPIO64 returns low/input. Final GPIO readback confirms those states
and the touch reset/IRQ state is unchanged. Both diagnostic modules are now
unloaded. The signed external diagnostic sets expected kernel taint 4096;
no signature/version checks were forced. eMMC filesystems remain unmounted.
No sensor streaming, OIS initialization or nonvolatile programming occurred.

The vendor CRC helper verifies pairs of data/checksum map entries. This board's
single-entry map supplies no checksum partner, so its helper cannot establish a
CRC pass. Keep the matching captures and reconcile any actual module-specific
integrity format rather than reporting an absent check as successful.

### Original-kernel fallback preparation

An eMMC backup does not contain this separate EEPROM. Its configured camera range is 0x0000–0x08ff. The vendor OIS implementation reads the maker byte at 0x0700, while LGIT variants reference calibration starting at 0x0900 and fields through at least 0x0940. The original 0x900-byte cached read therefore cannot establish coverage of all those fields. Physical capacity, additional address spaces and actual OIS controller identity still require identification.

The [stock reader](../scripts/stock_camera_eeprom_reader.c) is a freestanding ARM32 executable for the verified `3.4.0-gf0d2a47` RAM kernel. It checks kernel release, subdevice sysfs name, EEPROM name and the exact compiled cache length. It issues only the stock information/size/read commands. The read consumes the kernel driver's cached copy, so capture to a RAM file first, retain that file until transferred and checked, and obtain independent hardware reads on separate stock-kernel boots. The reader does not program EEPROM or invoke OIS initialization/calibration.

```sh
clang --target=armv7a-linux-gnueabi -march=armv7-a -marm -Os \
  -ffreestanding -fno-builtin -fno-stack-protector -fno-pie -nostdlib \
  -fuse-ld=lld -Wl,-e,_start -Wl,--build-id=none -static \
  -Wall -Wextra -Werror -DFX0_EEPROM_BYTES=0xa00 \
  scripts/stock_camera_eeprom_reader.c -o /private/fx0-camera-eeprom-reader
```

Default `FX0_EEPROM_BYTES=0x900` matches the original map; 0xa00 matches the expanded diagnostic. Each rejects the other map size before consuming the cache. The ARM32 structure/ioctl encoding was separately checked against declarations extracted from the pinned vendor header. Both executables run on kernel 39 and reject its release with status78, and reject an eMMC path with status64, without opening a camera device. **A positive stock-kernel EEPROM capture has not been performed.**

The [host image preparation helper](../scripts/prepare_stock_camera_capture.py) accepts the verified original RAM diagnostic, checks its SHA-256 and Android payload checksum, and expands only this EEPROM read length. It preserves all four Fx0 QCDT matches, kernel, initramfs and other DT bytes. The generated image differs at 21 bytes: one changed read-length byte and the 20-byte Android payload checksum. Independent `fdtget` confirms the new map. Wrong-hash and already-expanded inputs are rejected before creating output.

```sh
python3 scripts/prepare_stock_camera_capture.py --input /private/stock-ram.img \
  --sha256 INPUT_SHA256 --output /private/stock-camera-ram.img
```

This expands a diagnostic read to 0x0000–0x09ff, covering the reviewed calibration addresses; it does not establish full physical EEPROM capacity. The image remains unbooted and must only be RAM-booted after completing the current touch observation. No new stock image has been flashed.

For a future independent stock-cache comparison, verify the selected Fx0 identity and image hashes, keep eMMC filesystems unmounted, identify the `msm_eeprom` subdevice, and run the matching reader to a private RAM file. Check exact length/status before transfer. Hash and verify copies on two host filesystems, repeat with a fresh stock-kernel boot and compare, then reconcile CRC, module identity, all required calibration ranges and physical capacity. Keep calibration and full logs private. Source paths used for this audit include [the EEPROM driver](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/media/platform/msm/camera_v2/sensor/eeprom/msm_eeprom.c) and [OIS selection](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/media/platform/msm/camera_v2/sensor/ois/msm_ois.c).

## Native CCI and shared I/O preparation

The public [camera branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-camera)
at `8cfcb0fedcd91c324553872591831ecd5ffaffb4` describes GPIO64 as a shared
fixed 1.8 V regulator, enables the existing MSM8226 CCI controller and explicitly
sets its source to 19.2 MHz. That rate matches the vendor request and maintained
CCI timing counts. No sensor, assumed EEPROM part/capacity, CAMSS or camera DMA
binding is added. The board DT builds and passes targeted CCI/fixed-regulator
schema validation. Checkpatch passes with sign-off checking disabled; contributor
certification remains necessary before submission.

The [native reader](../diagnostics/camera-cci-read/README.md) reserves address
0x50 temporarily and uses eight-byte reads within the native driver's twelve-byte
read limit. It gets the shared regulator through the regulator API and refuses
an already enabled supply. Default preflight performs no transfer or power enable;
capture requires an explicit option. The exact-kernel39 signed module builds
with W=1, passes checkpatch, and rejected the earlier disabled CCI node before
hardware access. Native qualification has since passed: a2560-byte read and two independent65536-byte reads match every byte of the separate GPIO capture, with verified copies on two host filesystems. GPIO64 returns low after each read. CCI suspends before/between/after full reads, resumes for the second, and its source/core/AHB clock counts return to zero. Error unwind, controller unbind and system suspend remain unqualified; see [the runtime evidence](../evidence/2026-10-29-camera-native-cci-qualification.json).

RAM image25 combines the new camera DT with the byte-identical compiled kernel39,
image23 initramfs and command line; its Android payload ID was independently
checked. Kernel and DT source commits are recorded separately in
[the preparation evidence](../evidence/2026-10-29-camera-native-cci-preparation.json).
It has now booted from RAM after the incomplete touch test was saved. Native
probe/reset, matching repeated reads and successful supply/runtime-PM cleanup
are qualified to the scope above. A permanent
read-only NVMEM binding needs adequate part/protocol evidence afterward.

Sensor-driver timing still needs explicit reconciliation. The historical
AtomISP code hardcodes a 19.2 MHz input, while the Tegra driver requests 24 MHz.
Do not transfer their link/pixel-rate values between those configurations.
Read/verify the actual sensor clock-divider and lane settings during controlled
sensor-ID power qualification before advertising rates in a maintained V4L2 driver.
The full-resolution stock modes, controls and actual camera output remain in scope.

## Mainline CAMSS fit (2026-10-31)

Checked against qcom `for-next` (7.4 merge window). MSM8226 has the same
capture topology as mainline's MSM8916 resources: two CSIPHYs (2-phase), two
CSIDs, one ISPIF and one VFE. Mainline's MSM8226 MMCC already provides every
clock those resources name: top/ISPIF AHB, CSI0/1 AHB/core/PHY/pixel/RDI, the
CSIPHY timers, CSI_VFE0, VFE0 with its AHB/AXI clocks, and the VFE GDSC. So
clocks are not a blocker. Three pieces remain:

1. **Camera IOMMU (drafted).** fx0-linux `integration/fx0-camss`
   (`e5ffe165fcc1`, `c8d85e764975`, `df3ff68984d8`) adds
   `qcom,msm8226-vfe-iommu`. Its configuration takes the BFB values from the
   MSM8226 vendor `vfe_iommu` override, with halt and context restore. The DTS
   node (disabled) has the VFE0/VFE1/CPP contexts at `0xfda4c000`, the VFE
   AHB/AXI and CAMSS top AHB clocks (`iface`/`bus`/`tbu`, from the vendor clock
   table) and the VFE GDSC. The vendor gives this instance no secure ID, so it
   is OS-managed like the GPU instance. The driver builds with W=1, and the
   binding and Fx0 DTB schema checks are clean. Not hardware-tested.
2. **MSM8226 CAMSS resources and binding (drafted).** fx0-linux
   `integration/fx0-camss` (`0d9976327548`, `f8a7ccc43396`, `8203cfa85fce`)
   adds `qcom,msm8226-camss`. The vendor description puts every block at the
   same offset within the camera block as MSM8916 (CSIPHY0 `+0xac00`, CSID
   `+0x8000`, ISPIF `+0xa000`, VFE `+0x10000`, clock muxes `+0x20`/`+0x30`),
   with the same interrupts (SPI 78/79/51/52/55/57). The vendor clock tables
   give MSM8226 no counterpart to MSM8916's separate CAMSS AHB clock, so the
   binding has 18 clocks and the resource tables drop `ahb` and its rate slot.
   CAMSS looks clocks up by name only for CSI, VFE and PHY-timer rates, so
   this is safe. The VFE uses the MSM8226 rates (37.5–400 MHz) and the 4.1
   operations under the MSM8916 version, so no version-dependent path changes.
   `camss.o` builds with ARM LLVM W=1, and the binding and Fx0 DTB schema
   checks are clean. The CAMSS node stays disabled.
2a. **32-bit DMA (drafted).** Mainline `VIDEO_QCOM_CAMSS` depends on
   `ARCH_QCOM && IOMMU_DMA`, which 32-bit ARM does not provide; it uses
   `ARM_DMA_USE_IOMMU`, which r8 has. So CAMSS could not be enabled for
   MSM8226 at all outside compile tests. `3a68ec4c8322` accepts either. Whether
   CAMSS's DMA works through the ARM IOMMU mapping is checked by the
   test-pattern run.
3. **VFE 4.0 against the 4.1 operations.** The vendor driver has
   MSM8226-specific VFE versions and VBIF setup. Audit reset, interrupts,
   write masters, RDI and bus/QoS before reusing `vfe_ops_4_1`.

A probe build is ready: fx0-linux `integration/fx0-ram-probes` (APR q6core
probe plus the CAMSS branch, with CAMSS and the VFE IOMMU enabled on the Fx0)
on r8's configuration with only module additions (media core, V4L2,
videobuf2, CAMSS, APR). The built-in differences are menu switches and options
that only affect those modules, so all 17 test modules carry r8's `vermagic`
and load into the running kernel. The probe DTB differs from r8's only by the
three enabled nodes (plus phandle renumbering). The test boots r8 from RAM
with that DTB and does not change the installed system.

The first hardware milestone needs no sensor driver: CSID's test-pattern
generator can feed the VFE through RDI, so capture can be tested even though
IMX179 and IMX132 have no mainline drivers yet.

## First capture through mainline CAMSS (2026-10-31)

On a RAM-booted r8 with the probe DTB, `qcom,msm8226-camss` probed and
created every CSIPHY, CSID,
ISPIF and VFE0 RDI entity. With the CSID0 test pattern ("Incrementing") routed
CSID0 → ISPIF0 → VFE0 RDI0 at SGRBG8 1280×720, five frames streamed:
4,608,000 bytes, exactly 5 × 1280 × 720, starting `00 01 02 …`. So the MSM8226
CSID, ISPIF and VFE RDI write path work with the reused 4.1 operations.
**Correction:** r8 has no driver for the new VFE IOMMU compatible, so CAMSS ran
without an IOMMU, using direct DMA after a deferred-probe timeout. When the
VFE IOMMU does attach, captures complete but stay all zero; that configuration
is not working yet. The VFE pixel path, CSIPHY and sensors remain. The
CSID sink pad must be set as well as its source. See
[evidence](../evidence/2026-10-31-ram-probes-apr-camss.json).

## Rear IMX179 streaming (2026-10-31)

A new mainline-style `imx179` driver (Tegra GPL register table; 3280×2464
RAW10, 4 lanes at 324 MHz, 30 fps) reads chip ID **0x8179**, the value LG's
description expects, once the MCLK is right. Getting there exposed a mainline
clock bug: `mmcc-msm8974`'s MCLK RCGs lack `.mnd_width`, so a 24 MHz request
gave 120 MHz. Declaring the 8-bit M/N counter, as the vendor driver does, fixes
it. Through CSIPHY0 data lanes 0/2/3/4, the sensor's colour bars arrive (data
starts at 0xff), and live frames sit at the black level with varying data.
Open:

- Frames contain data only in their first rows (live: 574 of 2464).
  **Corrected:** this is not bandwidth. Without an IOMMU the VFE writes each
  frame linearly from the first page of a scattered `videobuf2-dma-sg`
  buffer. Only the contiguous start lands in the buffer; the rest overwrites
  unrelated memory. A full-size no-IOMMU run crashed the kernel on test-pattern
  bytes ([evidence](../evidence/2026-10-31-camss-noiommu-corruption.json)).
  CAMSS here must run behind the VFE IOMMU.
- The VFE IOMMU zeroes captures, as above.
- Image content, exposure and gain need checking.

See [evidence](../evidence/2026-10-31-imx179-first-stream.json).

## CAMSS behind the VFE IOMMU (2026-10-31)

- **Stream IDs.** The VFE SMMU is OS-managed, so `qcom_iommu` must program
  its stream-match table. With VFE0/VFE1/CPP mapped to context banks 0/1/2,
  captures translate through the IOMMU, and 720p test-pattern frames arrive
  complete without touching other memory.
- **Frame geometry.** Larger frames stopped part way, per buffer and
  repeatably. MSM8226's VFE 4.0 bounds a frame-based write master by
  `WR_BUFFER_CFG` (words per line, height, burst), which the vendor driver
  programs and mainline did not. Programming it gives complete
  3280×2464 frames in most buffers.
- **Remaining gaps** start on 64 KiB boundaries: whole cache lines of
  level-2 table entries look empty to the IOMMU. The test under way
  invalidates the context after each mapping.

See [evidence](../evidence/2026-10-31-camss-iommu-capture.json).

## Implementation and physical test order

1. Repeat controlled touch observation and preserve its completion conditions. The earlier pre-DRM capture was saved as incomplete; a new native-display capture is open.
2. Reconcile the captured calibration, address-space coverage and any actual integrity format; identify actuator/OIS variant without invoking EEPROM programming or recalibration. The separate positive stock-cache reader path remains optional independent comparison work.
3. Qualify maintained CCI and production power/reset/clock sequencing with sensor-ID reads and balanced unwind. Confirm shared GPIO64 ownership, rail constraints and actual MCLK. Keep capture DMA disabled for this step.
4. Add focused MSM8226 CAMSS binding/resource and hardware-operation changes plus its correct camera IOMMU support. Build/schema-check them separately; establish powered register access, reset completion and fault reporting before capture.
5. Exercise a sensor-independent CSID test pattern through ISPIF/VFE RDI to memory. Verify frame geometry, byte order, buffer completion, repeated start/stop and DMA under load. Distinguish this from a sensor capture pass.
6. Implement current V4L2 IMX179/IMX132 drivers and bindings with checked pixel/link rates, actual output/crop, exposure/gain/blanking controls and runtime PM. Validate modes against this unit rather than substituting a nearby Sony sensor.
7. Capture real rear/front RAW frames, verify Bayer order/orientation/crop, exposure/gain, timing, integrity and switching. Test reopen, error unwind, suspend/resume and charging/load combinations.
8. Implement the actual lens/OIS control where present and preserve factory coefficients. Qualify autofocus/manual controls, stabilization behavior and flash/torch independently.
9. Complete libcamera/Nura integration, processing/tuning, stills/video, user-facing selection and sustained capture. Re-run final acceptance on the maintained installed image and prepare focused upstream series with measured hardware evidence.

No capture-driver or sensor-driver functionality is claimed from this audit or its build/negative-guard tests. See [the sanitized evidence](../evidence/2026-10-29-camera-source-audit.json) for exact inputs, artifacts and remaining gates.
