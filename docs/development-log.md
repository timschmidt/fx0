# Fx0 development log

## October 29 2026

### Device and host observations

The connected phone appears in host sysfs as LGE LGL25, USB `1004:6341`, at 480 Mbit/s. Initially its configuration exposed CDC ACM, a vendor interface, and mass storage. After the owner enabled debugging, interface class/subclass/protocol `ff/42/01` appeared, identifying an ADB interface.

The task's sandbox does not expose `/dev/bus/usb`; ADB, fastboot, and pmbootstrap are absent. Direct hostname resolution fails. The root `.git` directory is empty and read-only, so commits and repository setup remain pending. A request for host-level inspection was rejected by the session's approval policy. These are execution-environment constraints, not evidence that the phone is disconnected or defective. [Sanitized host probe](../evidence/2026-10-29-host-probe.json).

The owner was given the documented `/permissions` or desktop permission-control route to change host access. Debugging on the phone is enabled; host access still needs revalidation after that change.

### Implemented preparation

- Added `scripts/fx0_device.py` for sanitized host probing, private stock inventory, live partition discovery, binary partition reads, independent rereads, and offline SHA-256 verification. It requires explicit device selection and preserves failed/partial reads without a verified manifest. No flashing operation exists in this helper.
- Added 11 tests covering backup success and important failure modes, including all-byte binary data, disconnects, truncated reads, changed partitions, tampered images, existing backup protection, invalid partition paths, remote quoting, and old ADB exit-status behavior. [Test output](../evidence/2026-10-29-device-tool-tests.txt).
- Pinned upstream Linux MSM8226, lk2nd, and historical Fx0 source commits in [the source manifest](../manifests/sources.json). Retrieved 43 public source files/symlinks needed for DTB compilation and verified their Git blob hashes. The ignored cache is a source subset, not a complete Git checkout.
- Added reproducible source fetch/verification and DTB build scripts. Compiled DTC from the pinned kernel's own compiler sources.
- Restored the historical Fx0 UART/USB DTS and its DTB Makefile entry as a Linux development patch, preserving the original source attribution/license. Added the lk2nd filename-selection candidate using its documented prefix/suffix convention. [Patch scope](../patches/README.md).
- Checked both patches apply and compiled the resulting DTBs. The Linux candidate and unchanged SoC baseline each emit the same four DTC warnings; the lk2nd candidate emits none. [Build report and hashes](../evidence/2026-10-29-device-tree-build.json).

### Remaining validation for the candidates

No complete kernel or lk2nd image has been built. Schema checks, maintained-kernel integration, current submission-base validation, boot-image inspection, and all physical tests remain pending. The initial SoC reference is the pinned 6.16 development tree; it is not the required maintained-kernel endpoint. The Linux candidate enables only the inherited minimal UART/USB board configuration.

No phone partition has been read or modified by these tools. No backup or recovery capability is claimed. No commits, public repositories, pushes, or upstream submissions have been created.

### Next executable work

1. Revalidate host USB/network/Git access after the permission change. Install host tools and establish version control using the configured contributor identity.
2. Connect through ADB to the explicit Fx0 serial and collect the stock inventory privately. Determine root access and the actual partition/board/component details.
3. Back up the actual critical partitions, independently verify them, preserve a second off-device copy, and establish restoration before modifying LAF or boot.
4. Obtain repeatable fastboot access; build and inspect complete diagnostic images; qualify lk2nd and a headless Linux boot.
5. Continue all remaining phases of the bringup plan, including maintained-kernel rebasing, all peripherals, current Nura updates, SIM-based cellular qualification, and public submission-ready history.

The full goal remains active. Current evidence closes preparation tasks only; it does not close the recoverable-device, Linux-boot, current-Nura, full-hardware, or upstream-readiness milestones.

### Maintained kernel followup

Revalidated the execution environment: USB device nodes remain hidden, the host tools are still absent, and root Git metadata remains unavailable. The follow-up USB configuration no longer advertises the ADB interface previously observed; its cause is not established. [Follow-up probe](../evidence/2026-10-29-host-probe-followup.json).

Prepared a Linux 6.18.59 LTS source target at commit `1253a6aa5d104312bf0992afacc15220ae35bdf9`, with separate board-compatible and DTS patches. The default DTB build now selects this maintained target. All 62 cached source files/symlinks pass pinned Git blob verification. Both LTS baseline and Fx0 DTBs compile with the same four warnings; no additional Linux warnings appear, and lk2nd still compiles without warnings. The binding YAML parses and contains the expected three-element tuple. Full schema and image builds remain pending. [Maintained build evidence](../evidence/2026-10-29-maintained-device-tree-build.json).

The early source gap assessment identifies WCNSS definitions in the SoC development branch that are absent from the LTS tree, and a missing explicit MSM8226 CAMSS match. Those require further integration/investigation before full wireless and camera support can be claimed. [Kernel gaps](kernel-gaps.md).

### Host access blocker audit

At 07:00 UTC, the third consecutive goal turn confirmed the same execution restriction: the LGL25 is visible in host USB metadata, but USB device nodes are hidden, ADB/fastboot/pmbootstrap and the ARM GCC toolchain are unavailable, direct DNS fails, and the root folder is not a usable Git worktree. The latest USB configuration does not advertise ADB. The earlier host-inspection escalation was rejected by the configured approval policy.

There are no verified device backup manifests. Existing evidence covers source checks and DTB compilation only. Further board configuration requires stock inventory; destructive device changes require verified backups and recovery; complete image builds and public Git development require the missing host capabilities. The project remains incomplete and requires an execution-environment change to proceed meaningfully.

Resume by enabling host access through the task's permission control, then recheck USB and ADB. If ADB remains absent, re-enable debugging on the phone and inspect its actual USB configuration before connecting. Begin with inventory and backups; do not skip directly to flashing the unqualified candidates.

### Host access restored and physical inventory

After the permission update, USB nodes, network access and Git metadata became available. Installed host ADB/fastboot, pmbootstrap, ARM bare-metal GCC/binutils, dtc and build dependencies. Source checkouts are ignored independent repositories. The host contributor identity is configured; upstream certification/sign-offs have not been invented.

Stock ADB required a compatibility fix: `exec-out` is unsupported, the shell lacks `printf`, and the root interface accepts `su 0 sh -c`. Text commands now use explicit echo-based exit markers and legacy CRLF normalization. Partition bytes use the ADB sync service with root adbd. All 12 helper tests pass.

Physical inventory identifies MSM8926 revision 1.1, a 720×1280 framebuffer, Synaptics S3320 touch, WCD9302 Tapan audio, IMX179 rear and IMX132 front cameras. These are stock observations, not Nura functional passes. The actual layout has 39 named partitions; boot, recovery and LAF are each 32 MiB. Original Android v0 image headers use 2048-byte pages and a QCDT table.

Backed up 29 critical partitions (359,137,280 bytes) with independently matching rereads and verified manifests. Preserved primary/backup GPT metadata. Verified another recovery copy after a round trip through `/sdcard/fx0-recovery/stock-critical-01`. Disk B holds a separately verified host copy. Raw dumps, NV/calibration and serials stay ignored/private.

Built the Fx0-only lk2nd image with the DTB basename filter `LK2ND_DTBS=msm8926-lg-madai.dtb` and forced fastboot for initial testing. The QCDT table contains exactly one Fx0 entry. An earlier incorrectly filtered build must not be used. The correct image is 286,736 bytes, SHA-256 `a3d4ac8860051209796268504e4f266293ea864493ffda5b4c2fd81cd4d349c0`.

Linux 6.18.59 LTS has separate binding and initial UART/USB DTS commits. Its full LLVM ARM kernel/module build is running with a diagnostic USB gadget configuration. No physical Linux boot is established yet. Nura v26.06 rootfs preparation is underway. The stock `adb reboot bootloader` request returned to stock Firefox OS without a fastboot interface.

The owner selected `/run/media/tim/Disk B/fx0` for persistent large files. Its space-free bind mount `/tmp/fx0-storage` is active and required again after host reboot. Do not move an active kernel output directory during a build.

### LAF restore-path qualification

Confirmed the live LAF mapping and size against the backup manifest. Read back the phone's own original LAF copy and verified its SHA-256. Wrote that original image back to LAF, independently pulled the block device, and confirmed the original hash. Then cleared exactly the verified 32 MiB LAF partition, independently pulled it, and checked the hash of 32 MiB of zeros. The partition map is unchanged. Original boot/recovery and the primary boot chain remain intact. The owner has been asked to enter the documented Volume Up plus USB path. Fastboot entry and diagnostic image boot remain unverified.

### Complete Linux image build and public development

The full Linux 6.18.59 ARM LLVM build completed successfully, including zImage, the Fx0 DTB, and modules. Exact artifact/config/compiler hashes are in `evidence/2026-10-29-linux-image-build.json`; the diagnostic configuration and commands are committed. Outputs are now on Disk B. Physical boot and schema qualification remain separate.

Published the coordination repository at https://github.com/timschmidt/fx0 and development branches at https://github.com/timschmidt/fx0-linux/tree/integration/fx0-lts and https://github.com/timschmidt/fx0-lk2nd/tree/integration/fx0. Commits preserve recovered source attribution. No upstream emails or PRs have been sent.

### First physical lk2nd and Linux attempts

The owner entered Volume Up plus USB. Stock fastboot identifies product MADAI, protocol version 0.5, and accepts temporary boot. The stock bootloader loaded the inspected lk2nd image into RAM successfully. lk2nd responds as `lk2nd-msm8226`, detects `LG Fx0`/`lg,madai`, and applies two keymap overrides. Its log reports SCM initialization/fuse-query failures; do not equate a running fastboot with qualified SCM or key handling. Reviewed serial-free evidence is under `evidence/2026-10-29-lk2nd-ram-boot.*`.

The first maintained Linux RAM diagnostic image was accepted by lk2nd but produced no observed USB diagnostic interface. This does not establish whether the kernel stopped early or USB alone failed. The owner has been asked to return to stock fastboot for persistent RAM log inspection. The next diagnostic build adds built-in simpledrm and an inherited framebuffer console to make early failures visible. Retained framebuffer output will remain distinct from native display-driver acceptance.

Installed dtschema 2026.9 and yamllint in a Disk B virtual environment. Qualcomm board binding validation and targeted DTB checks pass. `dt-validate` reports no diagnostics for the Fx0 board against 5,252 processed schemas; the synthetic SoC-only baseline has only the expected missing root model/compatible diagnostics. Schema validation still does not qualify physical behavior.

The Nura v26.06 generic MSM8226 console rootfs installation completed in the isolated build chroot, with a private development SSH key. It is not installed on the phone. Its packaged 6.16.12 kernel is a reference dependency, not the maintained endpoint.

### Maintained Linux reaches diagnostic userspace

Installed lk2nd after a successful byte-identical stock boot restoration test and an independent full-partition verification of the new prefix/unchanged remainder. A normal reboot entered lk2nd; a subsequent owner-triggered reset returned directly to its fastboot interface.

Diagnostic image 02 enables built-in simpledrm and the inherited framebuffer. The owner observed Linux text followed by the initramfs shell repeatedly running `dmesg` and moving `/www/dmesg.txt.tmp` into place. That establishes actual Linux userspace execution on this unit. It is a RAM diagnostic, not an installed Nura system or native display-driver pass. USB remained absent. Retrieved data from the prior reset was not a valid persistent kernel log.

Source review found two concrete PHY issues: the recovered board override used vendor value/absolute-address pairs rather than current offset/value pairs; the current PHY driver uses zero offset as an end sentinel, skipping the valid SoC sequence beginning at offset zero. Added separate count-based driver and board-inheritance fixes, confirmed the sentinel remains in current upstream, and compiled the changed kernel/modules. Added explicit stock PM8226 L10 (1.8 V) and L20 (3.075 V) USB supplies and peripheral mode, matching the stock DTS. These are development changes with physical USB tests pending.

Diagnostic image 03 replaces shell tracing with a compact framebuffer USB/deferred-probe status page. It was accepted by installed lk2nd for another RAM test. Exact image/source hashes are recorded; no Nura rootfs has yet been flashed.

### Automatic log capture preparation

Image 03 still has no observed host USB interface; its on-screen diagnostic details have been requested. Prepared a further image with USB dynamic debugging and a 90-second automatic warm reboot to lk2nd. Discovered the PM8941 power-key driver's reset notifier is modular in the shared config; enabled it built-in for this standalone initramfs. Image 04 was superseded before boot; image 05 contains the reset dependency. Both remain unbooted. The owner has been asked to reset back to lk2nd for the automatic test. Warm RAM retention is not yet qualified.

Exported a reviewed manifest of the completed Nura stable rootfs: 399 packages, Alpine 3.24.3, systemd 261, stable v26.06 branding. Login/SSH host-key files remain private. The rootfs is not installed, and its generic packaged 6.16.12 kernel is explicitly not the endpoint.

Recovered the WCNSS dependency commits and original authors from a sparse shared-kernel checkout on Disk B; documented their purposes and firmware caveats. No remote processor has been enabled on this unit.

### SMEM root cause confirmed on hardware

The owner's exact framebuffer transcription showed qcom-smem failing with -22, followed by RPM/SMD, clocks, SMP2P/SMSM and ci_hdrc deferrals. The stock DT places SMEM at 0x0fa00000 for 1 MiB; the recovered DTS inherited the shared default 0x03000000. Read-only lk2nd register reads confirmed initialized=1, reserved=0 and SBL version 0xb0000 at the stock location, while the default location contains zeros. The firmware's dynamic pointer also reports 0x0fa00000.

Replaced the default reservation with the firmware location in a separate board commit, rebuilt the full kernel/modules/DTB and validated schemas. Image 06 contains that fix, the built-in warm-reset notifier, USB debugging and 90-second automatic return. It was accepted for RAM boot; automatic return and USB behavior are pending. The unbooted image 05 remains recorded as a prepared intermediate.

While in lk2nd, its read-partition/get_staged path successfully retrieved a 512 KiB critical partition and matched the independent original ADB backup. This qualifies that read path only; write/restore offsets still require explicit checking.

### USB and eMMC reach initial hardware operation

Automatic warm return and complete ramoops console/raw retrieval succeeded. The log confirms all four CPUs started and qcom_scm selected the legacy SMC convention. Correcting SMEM allowed RPM and the USB controller to probe. Connecting the controller/PHY to the actual SMBB PMIC VBUS detector then produced a configured NCM/ACM composite USB device. HTTP logs and a root serial shell work. The static BusyBox lacks httpd/cttyhack; replaced those assumptions with a checked nc HTTP handler and getty.

SDHC1 now uses the stock L17/L6 rails and exposes all 39 eMMC partitions in 200 MHz 8-bit HS200 at 1.8 V signalling. Two small Linux block reads matched the original ADB backup. The first large read reset around 690 MiB without a Linux panic. Reserving MPSS/MBA/WCNSS alone still reset around 588 MiB. Auditing the stock `qcom,memblock-remove` entries identified the remaining 4 MiB after SMEM. With both complete stock holes excluded, two full 1 GiB system reads completed with matching SHA-256 and cache clearing between reads. Offline verification passed at Disk B `backups/stock-system-03`. Earlier partial attempts have no successful manifests.

The owner reports the battery is not noticeably above room temperature. Raw VADC measurements and the stock LGE table estimate about 34.3 °C; PMIC die reports 42.1 °C. The generic comparator trips near the measured 35-percent reference level and reports Overheat. The stock build uses a software temperature policy. Charging stays unqualified; no protection bypass or unqualified threshold widening was applied. ADC channels work after loading the matching common/VADC modules; the attempted `QCOM_VADC` setting was an obsolete/nonexistent symbol and did not make them built-in.

Current source `52334e9f84c3e2425819f1ea20aa18eb42453e82` has a complete kernel, modules and 63 DTBs built and schema-checked. Linux source/output moved to Disk B in the standard source/`.output` layout. Public pmaports development fork is provisioned. Kernel APKBUILD/config now target the maintained fork. The first envkernel packaging attempt failed because its Fedora-built signing helper cannot execute in an Alpine/musl chroot; a native Alpine helper is being prepared while preserving module signatures.

The device remains in a RAM diagnostic environment. Boot and LAF were the only flashed partitions so far; original recovery/system/userdata/internal SD and boot-chain partitions remain intact. No Nura rootfs installation, full hardware acceptance or upstream submission is claimed.

### Maintained Nura package and image checks

The envkernel package now builds successfully with module signatures preserved. Native signing required a musl-built helper and a temporary private key copy owned by the buildroot pmos UID 12345; both the host tool and original key permissions were preserved/restored, and the temporary copy removed.

Nura's required kconfig check initially caught legacy xtables symbols dropped by olddefconfig because Linux 6.18 has a new explicit legacy gate. Enabled that gate and its required dependent modules, rebuilt and repackaged, and the required check now passes. Only informational preference messages remain.

The first combined Nura image was generated and inspected: maintained kernel 6.18.59, Fx0 DTB and extlinux configuration with the development framebuffer/ramoops flags, about 1.12 GiB total. Regenerating it after the configuration correction hit a still-mounted old image loop; the retry now shuts down this pmbootstrap workspace's mounts first. No Nura rootfs has been flashed yet. Initial native clean package build and upstream readiness remain separate work.

### First Nura deployment write fails

The final reviewed combined image is 1,201,668,096 bytes, SHA-256 `874af997da361076201d7b74cabf3751429ffaf8586dfa4cbdacbe63ee9720d3`. Its ext2 boot and ext4 root filesystems pass offline checks, the boot/root UUIDs match extlinux, and the maintained kernel and firmware memory exclusion match the reviewed source.

The first attempted write targeted only reidentified userdata (`mmcblk0p37`, 4 GiB). It failed with `mmc0: cache flush error -110`, followed by tuning/recovery failures and block I/O errors. No verified deployment manifest was produced, and no persistent Nura boot was attempted. Userdata is now partially overwritten; original system, recovery, internal SD and host backups remain retained. The GPT comparison after the failed write still needs verification after storage recovery.

A RAM-only DTB variant limiting eMMC to 50 MHz boots and reads a 1 MiB prefix. It still selects HS200 from the SDHCI capability registers even with the explicit board HS200 property removed. Rewriting the same prefix at 50 MHz produces the same cache-flush failure. This disproves a clock reduction alone as a sufficient fix; no temporary speed restriction has been committed as the solution. Next checks cover runtime PM, command/busy handling and bounded write/read verification before another full image attempt.

Forcing the SDHC controller runtime PM state to active before the bounded prefix read/write also fails at 50 MHz. Runtime autosuspend alone is therefore not a sufficient explanation.

### eMMC write dependency: regulator load permission

Command tracing narrowed the failure: 4 KiB and 64 KiB writes and subsequent cache flushes succeed, but a 512 KiB CMD25 transfer times out before recovery emits cache-flush errors. A 64 KiB request limit still produces errors and is not a sufficient fix. The unresponsive large-write tracing run required an owner-triggered reset to lk2nd.

The SDHC driver records regulator demands, but without `regulator-allow-set-load` the regulator core returns success without applying them to RPM. The physical PMIC L17 stayed in idle mode. Added load permission to the eMMC's L6 and L17 supplies in a temporary DTB. At the original 200 MHz HS200 rate, an 8 MiB write/cache-cleared full readback passed; a fresh 32 MiB random-data write at userdata offset 2 GiB then passed an independent cache-cleared readback hash with no MMC errors. Both GPT copies match the pre-install snapshot. The earlier host copy of that random buffer timed out before any new MMC write was issued; serial commands remained available, so this separate transport issue does not invalidate the later MMC result.

Committed the two regulator properties as `b7575530db2d756ba1ad3e6e5757d3ac00494f1c` in the public Linux integration branch. The full host kernel/modules/DTB rebuild, patch style check and targeted schema validation pass. These are initial bounded tests, not sustained storage or USB acceptance. Rebuild the Nura package/image with this exact change before retrying deployment. A clean native build of the preceding integration revision is running separately.

Diagnostic image 15 uses the freshly rebuilt committed source and release `6.18.59-00011-gb7575530db2d`. The 32 MiB random-data hash matches after a warm reboot, establishing initial persistence across that reboot.

The full 1,201,668,096-byte reviewed image was then written using diagnostic kernel 15. After clearing caches, the phone-side SHA-256 matched; an additional complete host readback matched the same image hash. Both GPT copies are unchanged. This qualifies that write/read path with the corrected kernel. The image still contains the earlier board DTB and was deliberately not booted; rebuild its package/image with the regulator fix first. Sustained transfer emitted a GFP_ATOMIC network buffer allocation warning, retained privately for the open memory/USB stress investigation; no MMC error was reported.

The strict native pmbootstrap package build of source `52334e9f84c3e2425819f1ea20aa18eb42453e82` completed successfully in 12m41s, creating `linux-postmarketos-qcom-msm8226-6.18.59-r0.apk`. The pmaports integration now pins `b7575530db2d756ba1ad3e6e5757d3ac00494f1c` and its newly verified source archive checksum. Exact latest-source native clean-build qualification remains pending; packaging and deployment of the corrected host build proceed first.

### First persistent Nura boot

Corrected image 02 (1,201,668,096 bytes, SHA-256 `3e7c0d5b0532330019dc3ccdc1d63d6a50e8e3df29e6069d3d1d03bc4bc83b39`) passes both filesystem checks and verifies L6/L17 load permission. Its write and complete phone/host readbacks match; both outer GPT copies remain unchanged. The diagnostic transfer used min_free_kbytes=32768, dirty_bytes=16777216 and dirty_background_bytes=8388608; no new allocation warning appeared during that retry. These are temporary diagnostic settings.

Warm-rebooted to installed lk2nd and issued `fastboot continue`. Its filesystem path selected the Fx0 DTB and booted Nura from userdata. SSH key login and sudo using the private development credential work. The installed kernel is `6.18.59-00011-gb7575530db2d`; all four CPUs are online. Root is ext4 `/dev/loop0p2`, backed by `/dev/mmcblk0p37`, automatically expanded to about 3.4 GiB. Boot is `/dev/loop0p1`. The firmware loader mounts original persist/modem read-only. Systemd initially reports zero failed units, SSH and nftables active; this does not imply every daemon succeeded.

The owner reports a blank screen. Logs show simpledrm/fb0 and an active tty1 getty, plus a Plymouth segmentation fault without a core dump. Switching to a fresh tty2 and unblanking fb0 did not produce visible text, so the splash crash is not established as the sole cause. Native panel ownership and clock/power handoff remain unresolved. CPU scaling exposes 300000/384000/600000/787200 kHz, two CPU thermal zones read 44/45 °C, and ADC modules enumerate. Charging still reports Overheat/discharging. System time was set from the host after initially starting from the image/build-era time; RTC persistence is unqualified.

### Automatic boot, updates and final storage requirement

The exact latest-source strict native kernel package build passes. Installed package indexes refreshed through a temporary host proxy confined to the USB link and the configured Nura/Alpine repository hosts; `apk upgrade` reports no pending upgrades. Replaced the crashing splash with the distribution's `postmarketos-base-nosplash` provider and regenerated installed boot files.

Built normal lk2nd from the same source with forced fastboot disabled. Verified its one-entry Fx0 QCDT and 286,736-byte image (SHA-256 `5a9660ab359ff9de0d42b92fc109081cf30aa586333a9e8936f759910a1f73d8`). Saved and checked the complete existing boot partition, wrote only the secondary prefix, then independently reread all 32 MiB and verified the expected prefix and unchanged tail. Automatic warm boot into Nura succeeds. A fresh 8 MiB file on the installed ext4 root survives the reboot and cache-cleared host readback matches its original hash. Outer GPT still matches the original after root expansion. Short eight-second SSH command deadlines were insufficient during session startup; authentication succeeds and a longer deadline completes normally.

The owner still observes a blank screen after no-splash boot and temporary `clk_ignore_unused pd_ignore_unused`. The display domain remains off in debugfs despite those flags. They have been removed and installed boot files regenerated; native display/power ownership remains open. No full-hardware or reliability pass is claimed.

The owner requested a final layout with maximum usable space in one Linux partition and as few extra partitions as necessary, with external SD treated as removable media. Added mandatory plan section 2.1: audit full original/restorable state, complete consistent whole-storage/boot-area backups and independent off-device verification, demonstrate factory-stock restoration, validate the minimum sector map, migrate offline to one native root plus only required boot/firmware areas, and requalify rollback/updates/removable SD. Original userdata was not captured before authorized development writes, so current snapshots must not be called untouched stock. No repartitioning has been performed; the restoration prerequisite remains open.

A second automatic warm boot returned to Nura after removing the unsuccessful clock/domain flags. SSH command execution and zero failed systemd units were rechecked with a longer deadline; the installed ext4 test pattern matches after both warm reboots. The normal lk2nd build remains installed. The temporary host repository proxy was stopped after the successful repository/upgrade check.

### Production panel wiring and initial touch probing

Stock command line identifies `lge.rev=rev_10` (property ro.revision=7). The vendor code therefore selects GPIO111 positive bias, GPIO112 negative bias and GPIO113 LCD IO, followed by panel reset GPIO25. The extracted stock DT confirms DSI main VDD=L28 at 3.1 V, VDDIO=L8 at 1.8 V and VDDA=L4 at 1.2 V. Production revision 1.0 uses the separate touch-countermeasure DSI initialization sequence, not the early-board command list.

A temporary touch-only DTB boots Nura and mainline RMI4 identifies Synaptics PLG430, firmware 1769098, with F01/F12 and an evdev touchscreen. The owner performed swipes, corner taps and two-finger interaction; a live capture recorded zero events and the GPIO17/RMI interrupt counters stayed zero. This is probe success only; touch function remains failed/pending further sleep/display-interaction diagnosis. Capture was moved to a transient systemd service so it survives the SSH session.

The configured host USB descriptor permits 500 mA. The charger input limit remained 100 mA; setting the runtime input limit to 500 mA raised measured VPH from 3.637 V to 4.350 V while health remained Overheat and charging/discharging state unchanged. Temperature protection was not altered. Automatic USB current negotiation and actual battery charging remain open.

Added separate panel binding/driver, touchscreen board wiring, native DSI/WLED wiring and a schema naming/label correction in the public Linux integration branch through `9ff315ebc274426f5630265c074c67b44c554f7d`. The driver preserves GPIO state during probe, follows stock reset/bias ordering, uses production DSI commands and LP11 sequencing, and starts the stock single-string WLED at reduced brightness. All five new patches pass checkpatch with signoff checking disabled; the binding check passes and final DTB validation reports no diagnostics. Kernel, modules and DTBs compile; required Nura kconfig check and signed envkernel packaging pass. The exact-source strict native build also passes (10m50s).

Installed the signed candidate APK after verification, retaining known-good kernel/initramfs/DTB and restoring the older matching module directory after package upgrade. Boot files and the installed vmlinuz hash match the candidate build. The first native display test uses DRM driver/KMS logging and panic=60 while retaining warm reboot; physical native display/backlight results are pending.

The exact-source clean native build of the display candidate also passes (10m50s). The first normal Nura attempt with native kernel 16 did not produce a confirmed SSH session; USB re-enumerated and later disappeared, and the owner reported early text freezing, turning partly solid blue and fading to black. The unit appeared off. Recovery entry returned lk2nd fastboot, retained console/raw RAM was saved privately, and known diagnostic image 15 booted again. The retained console is short and partly corrupted; it contains a missing WLED ovp IRQ message but no established panic. Source inspection confirms that WLED treats this IRQ as optional and returns success, so the message alone is not a proven probe failure or root cause. Further diagnosis will separate native module loading from full Nura startup with more complete early logging.

### Controlled native display diagnosis

Copied the persistent Nura journals from read-only filesystems. Eight candidate boots reach early systemd, with the last retained entries around 13 seconds and boot starts about 26 seconds apart. This establishes repeated boots but not their reset cause. A temporary forced-fastboot lk2nd prefix was installed after saving the full boot partition; complete reread confirms its exact prefix and unchanged OS tail. RAM diagnostic 16 uses the candidate kernel/DTB without automatic module loading and keeps USB diagnostics available.

Manually loaded WLED, panel, MSM and RMI4 modules while streaming /dev/kmsg to the host. WLED registers brightness 512; the missing optional ovp IRQ does not prevent it probing. MDP5 identifies hardware v1.1, removes simpledrm, then reports `no IOMMU, bailing out`; panel attach returns -ENODEV. This is a confirmed native-display dependency. The kernel remains responsive after the controlled loads, so this failure alone does not establish the repeated normal-boot reset cause.

The upstream MSM8974 IOMMU series explicitly identifies DRM_GPUVM's IOMMU requirement as breaking MSM8974/MSM8226 display. Its short-descriptor, power-collapse and secured-context handling is being evaluated against stock MSM8226 tables before adapting board/SoC wiring. Reference: <https://lore.landau.one/lkml/20260809-msm8974-iommu-upstream-v1-9-87f5cd492560%40oss.qualcomm.com/T/>. No IOMMU success is claimed.

During controlled diagnostics with the configured USB input limit set to 500 mA, the charger now reports Good/Fast/Charging, VPH 3.789 V and PMIC die 44.003 C. This is one observed state, not battery charging/temperature-policy qualification; the earlier Overheat state and missing automatic USB-current negotiation still require explanation. No protection thresholds were relaxed.

The RAM diagnostic descriptor audit caught a separate current-setting error: its ConfigFS MaxPower was 250 mA, while the earlier Nura descriptor advertised 500 mA. Corrected the live RAM input request to 250 mA (SMBB rounds it down to 200 mA); charging then reports Discharging. The earlier 500 mA RAM observation therefore exceeded that diagnostic descriptor and must not be treated as correct USB negotiation. Updated the diagnostic image recipe to advertise 500 mA explicitly for subsequent configured-host tests. Automatic current tracking still needs implementation.

### Isolated IOMMU integration build

The public `integration/fx0-iommu` branch at `6c99f0648715` preserves the 11 upstream MSM8974 driver/binding dependencies (with two context adaptations for the LTS baseline), the ARM32 DMA-domain detach fix and the MDSS GDSC fix, then adds separate MSM8226 binding/configuration and display-IOMMU wiring. MSM8226 prefetch values come from this unit's vendor source, rather than copying MSM8974's distinct table. The previous integration branch and pmaports pin remain available. Full zImage/modules/Fx0 DTB build and module installation pass; binding/targeted DTB checks report no diagnostics. Checkpatch reports no errors, with imported dependency warnings and new commit-description cleanup still open. RAM image 17 and matching signed modules are prepared; no hardware IOMMU success is claimed yet.

The complete current 15,758,000,128-byte user-area capture is on Disk B. Verification switched from a slow BusyBox phone-side hash to a second cache-cleared full device read hashed on the host, also creating the independent copy on the host's separate filesystem. This verification and boot-area capture are still running. An original-range audit confirms the original system and 20 original critical partitions match; boot/LAF differ as expected and seven other state partitions differ from the first inventory. Both sets are retained, and the original saved copies independently rehash correctly. These differences must be accounted for in the stock-restoration audit rather than assuming every calibration/state image remained unchanged.

The complete development-state snapshot now passes: all 15,758,000,128 user-area bytes and both 4 MiB eMMC boot areas were independently reread after cache clearing, with matching hashes and independently rehashed copies on Disk B and the separate host filesystem. Boot-area read-only protection remained enabled. This supplies current-state rollback coverage, not a claim of untouched stock or a completed factory-stock restore rehearsal. No GPT/repartition operation has been performed.

The isolated IOMMU envkernel APK also builds and is retained with its exact source/hash manifest; it has not been installed as the default Nura kernel.

### Native scanout with runtime power held active

Controlled loading of the remaining automatically resolved modules (CPU frequency, RNG, IADC, evdev, RPM interconnect, reboot mode and RPM stats) returns normally on RAM kernel 16. No reset was reproduced by these sequential loads.

RAM image 17 boots kernel 32 and matching signed modules with configured USB MaxPower/input limit both 500 mA. Default MSM loading reaches DSI PLL initialization, loses USB and returns to forced-fastboot; a separate RAM command-line trial with clock/domain ignore flags also fails. Retained console/raw logs were retrieved successfully. Before another load, forcing runtime power active for both the MDSS platform device and display IOMMU keeps the test responsive: MSM DRM initializes, DSI PLL locks, msmdrmfb/720×1280 become active and frame interrupts arrive. A startup MDP error bit 0x04000000 is recorded. Keeping power active is a diagnostic workaround; proper sequencing and power collapse remain unresolved.

The owner still reports a black screen. A fixed XR24 framebuffer red/green/blue pattern and WLED brightness 2048/4095 produce no visible pixels; the owner reports the backlight appears lit throughout. GPIO25 reset is deasserted and GPIO111/112/113 high; DSI/panel supplies are enabled. Selected WLED registers confirm module/string/current sink enabled, 20 mA full-scale, 50% brightness and fault status zero. This is not a complete backlight qualification. The diagnostic return timer was held to allow observation; installed Nura filesystems stay read-only.

A temporary signed external module reads panel DCS power/pixel-format/ID registers. All reads return zero bytes with invalid-response diagnostics: the initialized output byte being zero is not a valid panel power-status report. The external module sets the expected out-of-tree taint (4096). Exact stock long/short initialization packet replay transmits successfully but still obtains no valid panel response. Standard helpers had shortened several original long packets; that difference remains relevant to a clean driver retest but replay alone did not establish a fix. Native display/touch remain failed/unqualified.

CID, CSD and full EXT_CSD metadata were also captured privately and copied to both off-device snapshot locations. Whole-storage snapshots retain the read-only, unreplayed-journal development state; the final offline restoration audit and factory-stock rehearsal remain open.

### Original-kernel RAM baseline and further display/touch isolation

Built a RAM-only image preserving the original verified kernel and QCDT, with a replacement diagnostic initramfs compressed in the original legacy LZ4 format and independently decompressed for comparison. It boots `3.4.0-gf0d2a47`, provides RNDIS TCP/HTTP diagnostics and mounts only virtual/RAM filesystems. The kernel command line retains production rev_10 and the JDI DSV panel selection. CID/serial/geometry match the selected device; identifiers remain private. This is a historical hardware baseline, not the Nura endpoint or a completed factory-stock restoration.

Holding the stock framebuffer open and writing a fixed pattern produces visible pixels. Its reported fbdev component offsets do not describe the observed byte order; correcting the pattern to RGBA byte order produces owner-confirmed red/green/blue at 128/255 brightness. A full driver powerdown/unblank cycle restores the bars. Stock touch records 4,179 events, X 20–703/Y 14–1280 and up to three tracked slots during owner swipes/corners/multiple-contact testing; palm/accuracy qualification is separate. Stock charging reports Good/Charging, 31.3 C and 27% at the final capture, up from about 20% initially.

After a complete stock display power cycle, the PHY/regulator registers match mainline except data-lane CFG4 values 0/5/a/f versus all zero. A separate candidate applies these values only for the existing MSM8226 quirk. It builds and RAM image 19 boots kernel 33, but the owner still sees black with lit backlight under native scanout, including opaque RGB bars. Clearing the controller's forced-HS clock bit and replaying exact stock packets also yields no valid DCS response. Neither trial establishes a display fix.

Stock F01 control has NOSLEEP set (0x04). Mainline initially reads 0x00; a temporary driver-mediated update to 0x04 persists but owner interaction produces no events or GPIO17 IRQs. Independently driving reset GPIO16 high to match stock, with capture held until the owner replies, also produces no events/IRQs. The temporary modules are signed and mark the expected out-of-tree taint. No permanent firmware changes are made.

Two further dependency corrections are under test: describe the stock secured MDP IOMMU contexts so the driver initializes global secure page tables; and remove the board's incorrectly translated 10 ms post-software-reset override, retaining RMI4's 100 ms default, with NOSLEEP selected in DT. Stock's 10 ms field describes the reset pulse while its boot wait is 60 ms. Prior PHY/control trials remain explicitly unqualified.

Kernel 35 (`abe11294089a`) initializes 90,112 bytes of secure IOMMU tables. Native DRM still initially produces the owner-reported text/blue/fade-to-black sequence. Read-only context-bank inspection shows translation enabled (SCTLR 0x1063), no context fault and no halt request. Unlike the previous candidates, all five panel reads now return a valid one-byte DCS response: power 0x0c, pixel format 0x77, IDs zero. Exact stock packet replay alone leaves power at 0x0c. Clearing the forced-HS clock bit to the working stock value, then replaying, changes power to 0x1c. Physical pixel confirmation is pending; these observations do not yet establish a functional display. The signed external diagnostics retain the expected out-of-tree taint. Mainline charging currently reports Good/Fast/Charging at the correctly configured 500 mA USB input request.

A diagnostic audit then found fbdev blank=4: the earlier framebuffer pattern helpers selected KD_GRAPHICS but did not explicitly unblank afterwards. Unblanking to 0 leaves DCS power status 0x1c. This confounds attribution of the prior power change to clock policy; a fresh controlled boot is required. A separate Python DRM diagnostic now holds master and a fresh dumb RGB buffer, avoiding the inherited stolen framebuffer and console ownership. The active DRM plane uses the new object at a distinct IOVA and completes vblank; physical output remains awaiting owner observation. Its initial msync attempt returned EINVAL before modeset; the corrected test uses the WC mapping without msync and its modeset succeeds. No failed attempt is recorded as a pass.

Clock-lane candidate `51190c24d` builds zImage/modules/Fx0 DTB and passes checkpatch without errors or warnings. RAM image 21 is prepared but not booted while the current physical touch/display observations remain pending. The initial source commit message attributes sleep-out to clock policy; the blanking confound above means that causal claim still requires retesting and submission-message cleanup.

### Wireless source preparation while physical tests remain pending

Created public `integration/fx0-wireless` at `9da98becd8c7461177e2411aa5c21f6f5cb03d1d`, based on clock-lane candidate 36. Recovered the four documented original wireless commits with their authors/co-development/sign-offs intact. Both changed driver objects and Fx0/HTC memul/Samsung milletwifi DTBs compile. Current dtschema 2026.9 exposed a missing bound in the existing WCNSS stop-state phandle-array entry; a separate one-line schema correction removes that diagnostic. Binding examples and the disabled Fx0 target check pass. All five patches pass checkpatch individually without signoff checking. No full kernel from this branch was built or booted, and fdtget confirms Pronto remains disabled. The shared-L24 profile mismatch, exact radio variant, complete enabled board description and physical wireless tests remain open. No firmware or calibration was published.

The running kernel-35 fresh dumb-buffer process remains alive, fbdev blank=0 and the owner gesture capture stays open. No gesture completion reply has arrived, so its zero bytes are not a completed negative test. Charging subsequently returned to Overheat/Discharging with the correctly configured 500 mA input request; sampled VPH is 4.098549 V and PMIC die 41.456 C. The existing stock-thermistor/policy mismatch remains open. No charging protection was relaxed.

### Host storage preview and boot-image update preparation

The original system/cache/userdata/internal-SD/grow entries form one contiguous range, sectors 786432–30777310. A private host disk preview replaces those five entries with one 15,355,330,048-byte root partition, preserving the first 34 entries and all original data from LBA34 to the root start. Both GPT header/array CRCs verify. A fresh ext4 with extents/64-bit metadata/checksums and 1% root-only block reserve passes e2fsck -fn; its complete embedded readback hash matches the standalone filesystem. The final partial filesystem block leaves 3,584 bytes. This is a conservative preview, not a completed minimum-partition audit or phone migration. The original 40-entry GPT capacity and metadata gaps cause recorded sgdisk cautions; 128-entry compatibility and end alignment still need final review/qualification. Raw host images remain private.

The existing 32 MiB boot partition can reserve 512 KiB for lk2nd and leave 31.5 MiB for an Android-format Linux image, potentially removing the separate boot filesystem. Source confirms that installed boot-deploy 0.23.0 and inspected upstream 0.25.0 write from physical byte zero, so enabling that path unchanged would overwrite lk2nd. Prepared public fx0-boot-deploy/integration/fx0-boot-offset and pmaports integration/fx0-storage branches. The new offset option subtracts the prefix from capacity checks, rejects invalid/nonaligned input and preserves the prefix/trailing bytes. All project CI stages pass in Alpine 3.24; real file-based regression writes cover preservation, rejected inputs, overflowing images, exact fit and default-zero behavior. No phone update was performed.

The matching schema accepts a 524288-byte fixture and rejects a negative value. All 296 existing deviceinfo files produce byte-identical output with the original and changed schemas under dint 0.2.1: 305 pre-existing warnings, with nonzero lint/xargs status. This is not a clean full pmaports CI pass. No device profile enables the new write. Hardware boot/update/interruption recovery, latest maintainer-tree integration, final DCO/submission review and stock-restoration prerequisites remain open. The plan now evaluates this raw-image route before adding a separate boot filesystem.

Rechecked the existing original critical/GPT copies on both host filesystems and added a direct, fsynced second-host copy of the original 1 GiB system image. All 29 critical images, system and both GPT files match their original manifest hashes; destination verification discards the file cache before reading. Original userdata remains unavailable. Source-only extraction from verified original boot/recovery images finds ro.debuggable=1 and ADB configuration; recovery init starts adbd for that property. Stock recovery fstab uses original system/cache/userdata labels and external mmcblk1p1 for SD, while normal boot uses internal FAT partition 38. Recovery has not been booted or instructed to wipe; actual ADB/root and factory initialization remain open.

### RMI reset candidate and live in-cell command test

Confirmed that the running LTS transport does not consume reset-gpios; inspected mainline at c339f4010dea8b0d754f84ace70cd1b089878ef8 also lacks that handling. Imported Roman Vivchar's September 2026 proposed GPIO reset patch with original authorship/sign-off and an explicit source link. A separate adaptation asserts reset before regulator cleanup and documents the new descriptor. Current dtschema exposed the LTS binding's missing email bracket; carried upstream Rob Herring commit c75afcb4a8e7 (four metadata-only corrections, original authors/acks retained). Kernel 39 at 341246daef4844c69d8638813bcedfcea35f96f1 builds zImage/modules/Fx0 DTB; changed driver W=1 compilation and all three individual checkpatch runs pass. RMI binding examples and targeted Fx0 validation pass without diagnostics. Signed modules and RAM image 23 are prepared but unbooted; the phone remains on kernel 35.

Stock power_control notifies LCD touch-disable/enable around touch power changes, including production revisions. Its panel enable packets are generic long EC29 then B003; the original-kernel RAM log confirms tp_on commands. Built a separate clean kernel-35 worktree to obtain matching headers/symbol versions for a live diagnostic. That build generated its own certificate, so it was not used for signing: the canonical certificate was explicitly matched to the running kernel trust before signing the module. No version-forcing option was used. The live module loads successfully and sends both packets (host result 8 each). DCS replies remain valid, power 0x1c and pixel format 0x77. Existing error-worker status 5 accompanies reads before and after. No physical fix is claimed; the unchanged input node/capture remain open and the fresh RGB DRM process stays alive with blank=0. A new combined visual/gesture observation is pending. No persistent phone storage was written in this diagnostic.

### Live reset isolation and first kernel-39 hardware boot

Built exact-kernel-35, W=1-clean signed diagnostic modules to apply stock TP-disable commands and a hardware reset without unregistering the input node. The first attempt returned EBUSY before GPIO acquisition/pulse because the guard treated unsupported runtime PM as suspended; corrected the check to apply only when runtime PM is enabled. A repeat suspends RMI successfully, asserts GPIO16 raw low with a requested 10 ms delay, deasserts it raw high, waits 60 ms and invokes the RMI reset handler/resume. All return zero; F01 restores control04/mask77/status00, and the existing evdev capture stays alive.

The subsequent exact panel initialization/TP-enable replay transmits, but DCS reads then time out or fail. Attribution is not isolated between reset and replay. fbdev blank4/0 with an independent DRM master did not produce a native power cycle. Stopped the pattern owner and issued real CRTC disable from a new master; the device lost USB and returned to lk2nd fastboot. The streamed log ends during bridge post-disable/PLL state handling, without establishing the reset cause. Retrieved ramoops console/raw privately. The OEM log request staged a payload, but its download was omitted before boot; that payload is not available from this collection. The old capture was zero bytes immediately before the experiment; there was no confirmed post-reset owner gesture test, so this is not a completed negative touch result.

Hash-verified RAM image23 boots kernel39 successfully. Mounted the installed Nura root read-only/unreplayed, checked and loaded its matching signed module archive, and held the auto-return parent before the deadline. RMI probes PLG430 firmware1769098; GPIO16 is now owned and driven high by the transport itself. Started indefinite event1 capture before loading native DRM, and asked for owner gestures/visual observation. Native display modules are intentionally not loaded during this particular reset-isolation observation. No persistent phone partition writes were performed.

### Unmounted checkpoint and raw-image boot preparation

Kept the kernel39 touch capture open while unmounting all Nura/proc/sys/dev/module binds and detaching the root loop. A new full development-state checkpoint captures the user area and both boot areas with every eMMC filesystem unmounted. The complete 15,758,000,128-byte user area and both 4 MiB boot areas now each pass two cache-cleared device reads and independent host readbacks. Disk B retains raw files; the separate host filesystem retains compressed files verified by full decompression and SHA-256. CID/CSD/EXT_CSD are on both. Boot-area read-only protection remained enabled. The initial raw boot0 TCP transfer stalled at 4,192,128 of 4,194,304 bytes; ping/ACM and later TCP remained responsive with no MMC error/reset. Two framed base64 reads of each boot area subsequently passed. That initial transfer is recorded as a failure, not a pass. The stricter unmounted checkpoint is complete. No recovery boot, factory wipe or repartition has been performed.

A read-only host audit finds empty standard BCB command/recovery fields and no known wipe/update tokens in original or current misc. The cache range matches the older audited snapshot, where recovery command/script paths are absent. Current misc differs from the older development snapshot in one 4 KiB block at offset7MiB; attribution is unproven, both versions are retained. This does not prove every vendor recovery decision or waive a final pre-boot audit.

Prepared public lk2nd branch integration/fx0-rawboot at b106e16d0f3fc0e11c55aa58e4c617b89a0e3ef5. LK2ND_EXTLINUX=0 excludes filesystem boot, keeps the default behavior unchanged and rejects invalid option values. Default/disabled/disabled-with-forced-fastboot Fx0 builds pass; symbols confirm Android/fastboot paths remain and only the disabled builds omit extlinux. All bundle one Fx0 QCDT entry and fit the reserved prefix. Upstream main still matches fd380ac637d1af38598e3f3c5321d4c962b96315. A real regular-file updater write of RAM image23 into a private 32MiB boot-partition preview preserves prefix, payload, suffix and target length. No new bootloader image has been installed, and raw-image hardware boot/recovery are open.

The new snapshot range audit still matches the original system and 20 original critical partitions. Boot/LAF differ as expected; drm/misc/modemst1/modemst2/mpt/persist/sns differ from the first stock capture and both versions remain available. These are recovery/provisioning reconciliation items, not automatically disposable partitions. Kernel39 remains running without external diagnostic modules, with eMMC filesystems unmounted and the pre-DRM gesture capture open. No owner gesture completion reply has arrived.

### Camera source audit and calibration capture preparation

Kept kernel39 and the pre-DRM touch capture unchanged. The saved stock RAM boot log confirms production revision7 rear ID0x8179/front0x0132 and successful probes. Mapped normalized CCI addresses, production power/reset/shared I/O, lane source settings and separate camera-IOMMU resources. Verified the vendor selects CSI3.0 headers, not its CSI2.2 alternative. Mainline at c339f4010dea8b0d754f84ace70cd1b089878ef8 has no MSM8226 CAMSS match or dedicated IMX179/IMX132 Makefile entries in the inspected files. Camera VFE4.0/VBIF/buffer/clock behavior still requires shared-driver work.

A new static ELF/C inspector decodes the actual stock sensor-library register-setting geometry without executing libraries or publishing complete tables. Rear geometries include3280x2464/1640x1232/3280x1848, front1976x1200. Primary GPLv2 Tegra references are pinned separately; their IMX132 array label1920x1080 writes1976x1144. These are static values, not a capture/frame-rate pass.

Camera EEPROM is separate from eMMC. The original driver caches0x900 bytes, while candidate LGIT OIS calibration extends beyond0x900 through at least0x0940. Prepared a freestanding ARM32 reader with exact-release/subdevice/name/size guards, using only query/size/read ioctls. Actual vendor-header ARM32 ABI and register-setting-prefix checks pass; both final reader variants compile with Wall/Wextra/Werror. Current kernel39 executes both wrong-release/status78 and wrong-path/status64 negative cases without camera access. Positive EEPROM reads remain pending. The read consumes the driver cache, so capture to RAM first and compare independent stock-kernel boots.

Prepared an expanded stock RAM diagnostic with only the configured read length changed0x900to0xa00 and the Android checksum updated:21 bytes differ. Kernel, initramfs, all QCDT matches and other DT bytes stay identical. Independent fdtget confirms the map; wrong-hash/already-expanded inputs are rejected without output. The image is unbooted and 0xa00 is reviewed-range coverage, not proof of full EEPROM capacity. No EEPROM programming, camera/OIS initialization, calibration, stream or phone reboot occurred. Added explicit remaining calibration/OIS gates to the plan and acceptance matrix.

### Live camera EEPROM preservation without interrupting touch capture

Read the separate camera EEPROM on kernel 39 with a temporary signed GPIO
I2C diagnostic while native CCI stays disabled. Preflight requires exclusive
input GPIO29/30 and input-low GPIO64; capture uses open-drain lines, enables
only the source-described camera I/O supply and sends address-pointer plus
repeated-start reads to fixed 7-bit 0x50. No EEPROM data programming, OIS
initialization/recalibration, sensor streaming, eMMC write or reboot occurred.

An initial 2560-byte read and three independent 65536-byte reads agree. Each
full read recreates the buffer and cycles I/O power; the final read tests the
exact public source including its CCI-disabled guard. Copies on both host
filesystems were fsynced and checked after discarding host file cache. Data
repeats every 8192 bytes across the full 16-bit word-address space; physical
capacity and other bank/security-space coverage remain unproven. Maker 0700=01
selects the vendor's old LGIT OIS path, and 0900–09ff contains non-erased data.
The actual OIS controller and coefficient validity remain unqualified. The
stock driver's CRC helper checks paired map entries; the board's single-entry
map provides no checksum partner, so it cannot establish a CRC pass.

The adapter and GPIO claims are released after each read; final readback
confirms GPIO29/30 inputs and GPIO64 input-low, with touch GPIO16/17 unchanged. Both
modules are unloaded. Kernel taint 4096 is expected from a signed external
module; no signature/version enforcement was bypassed. The pre-DRM touch
capture remains open awaiting confirmed owner gestures. Published only source,
procedure and sanitized evidence; calibration and capture hashes remain private.
The separate stock-cache reader and expanded stock RAM image are still
positive-test/unbooted fallback preparation, respectively.


### Prepare timed DSI pattern isolation without native takeover

Compared the stock host routine and maintained register definitions and prepared
an exact-kernel39 signed diagnostic for controller-generated fixed-color video.
The physical generator offsets include the host's four-byte shift. Guards
require the selected Fx0, registered panel/active host, expected resource/version,
active video and an unused generator. Default preflight has no register writes;
explicit apply requests a bounded pattern with delayed restoration. The source
pins the host module/runtime-PM reference and synchronizes unload with its work.

W=1 build and checkpatch pass. Final published source is signed with the running
trusted key; insmod returns ENODEV before MMIO because native DSI is absent.
The owner touch capture remains open and unchanged. Active pattern output,
preflight, timeout and unload restoration remain untested. No native takeover,
reboot or persistent phone write occurred. This diagnostic is intended to compare
DSI-generated pixels against framebuffer DMA after the existing touch test;
it is not a display fix or physical qualification.


### Prepare native camera CCI and shared supply qualification

The current kernel39/touch observation remains running and all eMMC filesystems
remain unmounted. Added a public camera branch based on source39 with a shared
GPIO64 fixed1.8V camera I/O regulator, existing CCI enable and explicit19.2MHz
CCI source. Kept sensor/capture-engine nodes and an assumed EEPROM capacity/
manufacturer binding out of this stage. DT compilation and targeted Kbuild/direct
schema validation pass; checkpatch with --no-signoff is clean. Ordinary checkpatch
reports absent Signed-off-by, so contributor certification remains pending.

Prepared a native-adapter calibration reader using fixed0x50, two-byte pointer/
eight-byte read pairs within CCI v1 limits, a temporary dummy client to reserve the
address, real regulator lookup, initial-disabled/voltage checks and checked supply
unwind. W=1/checkpatch pass. Signed final module on current39 rejects disabled CCI
before adapter/regulator/hardware access; the owner touch capture remains open.
Native probe/reset, positive reads, cleanup and runtime suspend are untested.

Unbooted RAM image25 preserves the compiled39 kernel and image23 ramdisk/command
line, replacing only the DT. Parsed output checks and independent Android payload
ID recomputation pass. Public evidence distinguishes kernel source39 from camera
DT source8cfcb0fed. No image was booted or flashed. Sensor timing review identifies
AtomISP's hardcoded19.2MHz versus Tegra's requested24MHz input; actual divider/lane
readback and output qualification are required before publishing sensor rates.

### Native camera control qualification and native39 display mapping

Saved the old pre-DRM source39 observation, events, IRQ/GPIO/module/mount state
and dmesg privately before ending it as incomplete:0bytes without confirmed
owner gestures is not a negative physical touch test. Advanced independent CCI
work by RAM-booting image25. Verified its identity/DT, paused the new generated
return parent102 and configured the negotiated500mA diagnostic limit. No flash
or partition change occurred.

Native i2c_qcom_cci binds and registers Qualcomm-CCI adapter1; its controller
reset completes. A preflight leaves the fixed GPIO64 supply low. A2560-byte read
and two independent65536-byte reads match every byte of the independent GPIO
capture. Verified private copies on both host filesystems are fsynced and
cache-discarded/rehashed. The supply returns low after each read, and CCI resumes
between reads then returns to runtime suspend with source/core/AHB clock counts0.
The final controller IRQ count is33409. Part/capacity/other-bank/integrity and
sensor/CAMSS qualification remain separate; no EEPROM data program or OIS command.

Mounted Nura root ro,noload and loaded exact39 RMI, panel, MSM and WLED modules
with the known MDSS/IOMMU runtime-power holds. WLED must be loaded explicitly in
this RAM environment to satisfy the panel supplier. Native DRM binds at720x1280;
explicitly unblanked fb0 and requested half brightness. Fresh DRM allocation56
holds opaque RGB bars. Without manual replay/clock override, DCS reads1c/77 and
one-byte ID reads return00. The non-continuous-clock source change is present;
this is transport/state evidence, not visible-pixel qualification.

Before active use, corrected the prepared TPG helper: the inherited stock loop
writes physical180, which the maintained host map defines as clock-pre extension.
The original helper had only run preflight, with no writes. Video generation
needs no command trigger. Corrected source builds/checkpatches and runs a120-second
fixed-red request. Error-worker flags5/4 become frequent during generation.
Timer restoration leaves control/color0 and clock-pre extension0 in the KMS
readback; subsequent DCS1c/77 and USB remain valid. No visual reply has arrived,
so the physical result is unqualified. Active unload before timeout is untested.

Read-only DMA0 inspection finds source/current source0039a000,720x1280 and
stride2944, matching the held framebuffer. Software IOMMU mappings contain the
expected RGB values at12 sampled positions, including separate physical pages.
Bounded privileged-read hardware ATOS queries in active context0 match the
software walk for first, next and final pages,3/3. No translation tables/configuration
are changed. These results narrow mapping faults but do not prove actual pixel
fetch, stream routing or visible output. Temporary helpers are unloaded. Native
scanout and a new touch capture stay open; the original CRTC-shutdown reset cause,
proper runtime PM and all remaining hardware acceptance work stay unresolved.

A later capture check finds832bytes/52native input events with five tracking
starts/releases and two GPIO17/F12 interrupts. Raw events are saved privately
and capture remains open. No owner gestures are confirmed, so this establishes
event flow while physical correspondence and ghost/noise behavior remain
unqualified; it is not a completed touch acceptance test.


### First confirmed native visible RGB and controlled multitouch

The owner confirms RGB bars visible on the unchanged image25/source39 native
scanout after the timed pattern ended. Recorded a new byte offset before asking
for swipe/corner/two-finger movement; the owner replied Done. Excluding832old
bytes, the test contains73,760bytes/4,610events,12tracking starts and12releases,
maximum two concurrent contacts, X0–689/Y0–1275. GPIO17/F12 IRQ count increases
from2to441. Reset16 remains high and fb0 blank remains0. This establishes basic
visible scanout and controlled native multitouch, not full edge accuracy,rotation,
noise,installed-system,power or reliability acceptance. The combined tested
source includes IOMMU/secure contexts, PHY lane handling, non-continuous clock
mode and RMI reset support; no single-change cause is isolated by this result.
Saved exact conditions and raw captures privately before further power tests.

### Native display power transition isolation

A controlled CRTC off/on using a duplicate of the live DRM-master descriptor
resets before the off ioctl completes. The pixel owner and framebuffer remain
held, avoiding an owner-close or buffer-release confound. Original panel shutdown
reports a video-completion timeout. Sending display-off/sleep-in in disable()
instead of unprepare() removes that timeout, but does not resolve the reset.
The panel-only change is published on integration/fx0-display-power; W=1 module
build and checkpatch pass. It is not a complete display-power fix.

Extra references to DSI vdda, and then vdda plus the byte PLL, do not prevent the
reset. An exact-ABI signed diagnostic MSM module adds logging without changing
shutdown behavior. Its first run shows PLL save, host/link clocks, runtime put
and host regulator shutdown returning; retained console ends before PHY disable.
The earlier last PLL log line did not establish the fault. Complete retained
console, raw ramoops and staged bootloader logs are saved privately before each
new boot. Installed Nura remains read-only during these RAM tests. Default PM,
power cycling and installed-system native display are still unqualified.


The finer trace reaches PHY control0, internal-regulator shutdown and the write
barrier, then stops at the final PHY vddio supply disable. Stock L8 also supplies
vdd_sr2_pll for a7sspll. An additional L8 reference allows the complete off/on
cycle. Added regulator-always-on for this shared CPU supply in commit476e36e72;
the native CPU PLL currently has no matching supply vote. Image26 preserves the
compiled39 kernel/ramdisk/cmdline and differs only by that DT property. It passes
targeted schemas and checkpatch. With original MSM and fixed panel ordering,
the owner confirms RGB before and after a complete cycle. Three further cycles
complete with MDSS/IOMMU power/control auto and no extra supply/PLL module.
Transient MDP error04000000 occurs during repeated enable, so this is not full
reliability acceptance. Full source44 kernel build started separately.

SMBB again reports Overheat/Discharging with CPU43C,PMIC41.7C and battery-therm
raw31266; recorded VADC calibration channels and turned backlight0. This matches
the previously identified generic-comparator/stock-thermistor-policy gap. No
threshold change or protection bypass. Charging and battery reporting remain
unqualified.


A fifth cycle holds the display off for five seconds with all four devices in
automatic PM. MDSS,IOMMU,DSI host and PHY all report suspended. L8 remains at
usecount1 while both DSI vddio consumers drop to0; L4 drops to0 and touch retains
its L28 vote. Restored half brightness explicitly; owner confirms visible RGB.
Controlled post-cycle gestures record31,488 bytes/1,968events,27starts/releases,
max2contacts,X24–719/Y3–1277,no SYN_DROPPED or active contacts left. One transient
RMI IRQ-read -6 occurred during enable; subsequent reporting works. Owner reports
near-room battery temperature. The earlier three-cycle black-screen reply
overlapped intentional backlight0 and cannot qualify that visual interval.

Prepared the Nura kernel r1 recipe at source476e36e72, with a verified downloaded
source archive and the tested IOMMU configuration. Required kconfig checks pass
using a fresh unprivileged work directory. Existing package/build chroots are
root-owned and sudo currently requires a password; standard native packaging
needs the prepared root helper. Host kernel44 build and RAM qualification can
continue without that access.


### Full display kernel44 and native package

Full source476e36e72527b4115b656117634fb17a4b6e77dc compiles as kernel44 with
no build diagnostics. Matching stripped/signed modules and RAM image27 are
prepared. Kbuild regenerates the copied signing PEM because its x509.genkey
dependency is newer; recorded the resulting44 certificate and verified its
matching PEM. The canonical39 trust/key is unchanged. Kernel44 accepts its own
modules without force options and remains untainted.

Initial DRM load without either power hold resets during MDSS child population.
With the known initial holds, native DRM binds; after releasing both, a5second
off/on cycle completes with all4display devices suspended whileoff. The owner
confirms visible RGB afterward. Separate initial boots show IOMMU-only and
MDSS-only holds each suffice, narrowing the startup issue to a shared resource.
No actual register/clock cause is proven.

A separate DT-only image28 connects the existing MMCC MDSS_RESET line, following
the analogous upstream MSM8916/39 description. Compiled DT differs only by the
reset phandle and passes schema checks. It still resets at the same early stage;
the experimental reset branch remains unpublished. A signed, logging-only MSM
module localizes the reset inside of_platform_populate(), before child probe
trace points. Function-graph capture records power-domain transitions there. A
bounded runtime-PM reference around child population is being tested separately.
All failed-test console/raw ramoops/bootloader payloads were downloaded before
new boots. Firmware/root filesystems remain unchanged and read-only.

The owner runs the prepared standard native package build successfully, then
exports its signed armv7 r1 APK and public signing key from the root-only work
directory. Package source/config checksums match published recipe0b5e31934. Its
PKGINFO commit is -dirty: build launched with the prepared changes atop ae3b33c21,
committed while building. This is recorded explicitly; no clean-Git provenance
is claimed. Native package signature/runtime/install checks remain pending.
Private logs/checkpoints and the APK are copied to Disk B as well as the host
workspace.


### Bounded initial-resource candidates and repeated-startup failure

Taking a bounded MDSS runtime reference around child population progresses to
the asynchronous DSI version-register read, where the trace stops after AHB
enable. An additional bus-clock reference around the version query permits
startup with all display devices in automatic PM and no userspace holds. A
five-second off/on succeeds, all4devices suspend whileoff, and the owner confirms
RGB. Bus-clock-only without the population reference still resets during child
creation.

Published separate focused candidates ad82d2775 and c6ca8a0b0, with trace logging
removed. Exact44 W=1 compilation and individual checkpatch runs pass. The clean
module's first startup and5second cycle pass, but its next startup resets after
MDP probe begins. A subsequent startup succeeds. This is intermittent and remains
unresolved; no final PM qualification or installed-system promotion. Initial
clock-event collection used the old power event group, so only system-PM events
were enabled and no startup trace was recorded. Actual available events are in
clk and rpm; corrected collection records a successful off/on baseline and is
being applied to a new startup. Raw traces stay private.

The exported native r1 APK verifies successfully with installed Nura apk-tools
3.0.8 and its existing trusted keys. This does not install it or add the two newer
initial-resource candidates; the root remains read-only.


Correct clk/rpm tracing captures a further startup reset after MDSS suspend and
resume; recorded AHB/AXI/vsync enable calls return. A DT-only image29 supplies the
binding-supported fourth MDSS core clock and a private module manages it. W=1
and schema checks pass. The trace confirms core prepare/enable,off and re-enable,
but startup still resets. This is not a sufficient fix and the display-core
experiment is unpublished. Next trace also includes clock-parent events, which
run during device setup before the host's probe. The precise fault instruction
remains unknown. No new native package revision is being promoted while this
intermittent startup remains.


### Native r1 runtime and persistent startup trace

The exported native r1 kernel and its own signed modules now boot from RAM.
Their initial MDSS/IOMMU holds permit native DRM binding. After restoring auto,
a five-second off/on completes with all four display devices suspended while off;
the owner confirms RGB afterward. Directly unpacking the APK skipped the normal
kmod installation trigger and exposed empty dependency indexes. Running target
kmod34.2 depmod generates the correct dependencies and loads RMI without taint.
The actual installed kmod trigger performs this step on normal package installs.
No installed Nura filesystem has been modified.

The clock-parent trace captures no parent-setting calls before a failed startup.
IOMMU graph and instruction-probe runs show successful SCM restore and BFB/context
work before a later reset. A bounded PHY reference across PLL/provider creation
passes once and resets on repeat; it is not a fix.

A separate diagnostic kernel adds persistent function tracing, soft-lockup and
hung-task detection, plus atomic-sleep debugging. Its distinct release prevents
module confusion. A diagnostic DT partitions the same reserved 512KiB into
128KiB crash records,128KiB console and256KiB per-CPU function tracing, disabling
lk2nd's fixed-layout DT override. Full raw retained RAM survives a failed startup
and decodes successfully. The final recorded clock callers match the DSI version
query's prepare/enable pairs, immediately before its register-read path. This
narrows the next test to other normal DSI bus clocks; the exact fault instruction
is not yet proven. No lockup-detector report is retained. Full details and limits
are in evidence/2026-10-29-display-start-persistent-trace.json.


Adding core_mmss to the query clock set passes two starts/cycles and resets on
the third startup. A follow-up enabling mdp_core,bus and core_mmss before the
version read resets on its first startup. Neither is a sufficient fix. These
private candidates are not promoted. The persistent trace is being broadened to
include all function paths and capture the loaded MSM text address directly.


The escape-clock query variant passes three starts/cycles and resets on its
fourth startup; it is insufficient. The prepared version-read diagnostic then
boots and captures dsi_version_read_initial immediately followed by do_DataAbort.
The read uses the existing unshifted version offset0x1f0. Error reporting proceeds
through printk into inherited framebuffer drawing before the full report reaches
retained console storage. Detaching that VT framebuffer console before probing
is now being tested for fault capture; the first two such starts succeed.
No missing-clock or unsupported-register fix is claimed.


### Retained-only logging, power snapshot and USB recovery

Detaching the inherited framebuffer VT console allows two starts and then a
third failure; its retained trace still ends at the initial version read and
no complete fault report survives. Image32 keeps the exact diagnostic kernel,
DTB and ramdisk but selects only ramoops as a kernel console. Runtime
/proc/consoles verifies that UART and tty0 are absent. Its first startup passes
and second fails at the same read, again without the full report. Console
removal does not fix the fault.

A read-only diagnostic maps MMCC and snapshots six documented power/clock
registers immediately before the first version read, together with runtime PM
counters. Five startups succeed. Successful cases include MDP/escape gated,
so those clocks are not unconditionally required for this read. The diagnostic
also adds mapping,logging,unmapping and a barrier; isolated ordering/timing tests
are now in progress rather than treating the snapshot as a fix.

Normal software reboot can leave the selected lk2nd USB device enumerated but
unresponsive. USBDEVFS_RESET on the exact selected port/VID/PID/private serial
restores getvar product immediately and preserves retained RAM. Local closure
helpers now attempt one such reset after bounded failed reads, then revalidate
product before log retrieval. No flash/eMMC operation is involved.


### Ordering experiments and abort-value recorder

Isolating the power snapshot's barrier does not yield a startup fix. A write
barrier passes two starts/cycles then resets on the third. A100us delay fails
its first startup. A full barrier passes three starts/cycles and resets on the
fourth. These private candidates are not promoted or installed.

A board/release-guarded diagnostic probes ARM do_bad and encodes fault arguments
as named functions in the existing retained trace, without display accesses or
storage writes. Both exact-ABI W=1 module builds pass. On full 44, its known-RAM
read succeeds, an invalid address is safely rejected, and all four synthetic
frame values plus end markers decode exactly. Probe registration/unload pass.
This validates the encoder, not a real exception. Four later pmdebug1 starts
fail/pass/pass/fail. Both failures stop at the initial version read and preserve
no abort-value markers. Full real argument capture remains open. The decoder's
three host protocol tests pass, covering interleaved CPU streams, truncation,
wrapped rings, symbol bounds and invalid headers.

All543 selected session/artifact files in the next checkpoint were copied to
Disk B and SHA256 verified. Raw logs, addresses, identifiers and keys remain
private. Root has remained ro,noload throughout these experiments; the installed
native16 kernel, r1 installation status and GPT are unchanged. The next breadth
step is a RAM-only Nura initramfs with explicit temporary initial display power
holds, releasing automatic PM after native DRM binding. This is a development
workaround and does not satisfy the kernel startup or suspend acceptance gates.


### Native Nura initramfs RAM boot preparation

A native initramfs was regenerated with mkinitfs2.11/boot-deploy0.23 from the
installed Nura root mounted read-only, binding RAM copies of configuration,
release metadata and native modules. Explicit tmpfs boot/tmp mounts resolve
BusyBox df rejecting a plain diagnostic-rootfs bind. Ordinary boot-deploy
free-space checks pass with flashing disabled. Archive inspection verifies the
wrapper/original init, cleanup hook, native ABI and Fx0 panel/backlight/input
modules. The wrapper holds MDSS/IOMMU before udev and requests auto only after
native framebuffer binding. It is temporary development policy, not a kernel fix.

Image33 is accepted by lk2nd and exposes Nura USB NCM networking. SSH remains
refused throughout observation and no other diagnostic shell is exposed. This
does not establish framebuffer/hook success or root-mount progress. The installed
kernel package and boot configuration were not replaced; normal Nura startup may
have written mutable root state. A physical return to lk2nd is requested so
retained logs can be captured before the next boot.

Image34 is prepared with a pre-root-discovery PMOS debug shell and a complete
matching native module tree. A cleanup hook moves a tmpfs copy of those modules
over the target root's existing directory for this RAM boot. It avoids mixing the
new kernel with older installed modules without replacing that package. Two
concatenated archive members, every native module-tree file and all hook bytes/
executable modes were inspected. Image34 is not yet booted. Missing root modules
are a known test-environment limitation, not a proven explanation for image33.
See evidence/2026-10-29-native-nura-ram-initfs.json and the native-display-boot-hold
diagnostic guide for exact inputs, hashes and remaining checks.


The owner subsequently reports visible systemd emergency-console text and an
unsupported Arbitrary Executable File Formats File System Automount Point.
This establishes later boot progress than USB alone. It does not identify the
framebuffer driver or prove missing matching modules caused emergency mode.
The prepared complete-module overlay and debug shell will permit checking both.


### Native Nura console and SSH confirmed

Image34 reaches the PMOS debug shell with msmdrmfb bound and the intended
initial holds active. Its complete-module ramdisk is too large for lk2nd's
forced 32 MiB load slot and overlaps the inherited framebuffer, producing a
reservation failure and simpledrm memremap warning. Image35 changes only the
header address, but the live chosen initrd-start remains32 MiB: this LK target
ignores header addresses. Both runs were closed with retained logs preserved.

Image36 omits 36 identical module files from the appended newc member and uses
XZ/CRC32 across both members. All 438 native module-tree file and all hooks
were verified. Its 17,819,112-byte ramdisk ends below the inherited framebuffer;
the debug shell confirms the actual end, msmdrmfb and taint 0. The image helper
now rejects overlaps at LK's actual forced address. Three host placement tests
pass, and the existing small native diagnostic30 reproduces byte-for-byte.

Continuing image36 reaches Nura/systemd and SSH. The complete native module
tree is mounted from tmpfs after switch_root, the cleanup hook releases both
initial holds, all four display controls are auto, and taint stays0. The owner
confirms readable login/text output. No failed units are observed, while
systemd time synchronization waits without upstream networking. The old
installed kernel package and boot configuration are unchanged. Next is the
installed boot/module backup and trigger/DTB audit before persistent r1 update.
This remains a temporary workaround; intermittent driver startup, suspend and
all remaining hardware/recovery/storage acceptance gates remain open.


### Native r1 installed and booted from eMMC

The pre-update boot, old modules and configuration archives were copied to the
host and independently verified on Disk B. The exact old dated APK is preserved,
and raw boot/GPT fingerprints were captured. The r1 dry run changes only the
kernel package, reporting a semantic downgrade from the earlier dated build;
its tested source is newer. The APK is trusted without signature overrides.

Persistent configuration installs the tested initial-hold prefix and cleanup,
adds Fx0 panel/backlight/input modules to mkinitfs, selects the single Fx0 DTB,
and explicitly disables raw flash-on-update. Existing command-line generation
preserves the tested parameters. A detached launcher exited before mutations;
a supervised systemd job is used. The live RAM module mount is busy, so a
separate bind preserves its active mappings while lazy detachment exposes the
underlying ext4 module path. Only the unexecuted package stage is resumed.
Normal APK/kmod/mkinitfs/boot-deploy processing succeeds. Old native16 boot files,
modules and a fallback entry remain available; that entry is not yet rehearsed.

Readback verifies the kernel and DTB against the native APK, initramfs source
bytes/module ABI/size and explicit extlinux paths. The 11,955,740-byte initramfs
has no RAM-module overlay hook and fits below the inherited framebuffer.
Raw boot SHA256 and both complete GPT copies match their pre-update values.

A normal systemd reboot returns to lk2nd; retained logs are saved and fastboot
continue boots the installed filesystem. A changed boot ID confirms a fresh
native 6.18.59 boot. SSH works, msmdrmfb is active, taint is 0, the module tree is
on persistent ext4, and all four display controls are auto after initial holds
are released. No failed units are reported; time synchronization still waits
without upstream networking. The owner completes the requested screen/gesture
test. It records 2,468 events, 252 frames, 23 matched contact starts/releases,
max 2 contacts, X19–719/Y0–1278,zero SYN_DROPPED and no remaining contacts.

This is one installed boot with temporary initial-power policy. It is not
unattended/cold/repeated startup, full suspend, complete UI/hardware or final
recovery acceptance. Current evidence is in 2026-10-29-native-r1-installed-boot.json.


Reverse USB internet now works through the selected host connection. The original
host and phone profiles are saved privately; the host USB profile shares its
existing upstream link, and the phone's USB profile gains gateway/DNS with a low
route priority. HTTPS and trusted repository-index updates pass. The upgrade dry
run reports no pending packages, and the existing local-kernel checksum pin
retains the tested r1 build. NTP synchronizes and no boot jobs remain. No Wi-Fi,
SIM or modem functionality is inferred from this development network path.


### Native Wayland console and touch orientation

Sxmo's packaged dependencies install through reverse USB internet. A controlled
TinyDM/Sway session uses native DRM and Pixman, with a foot terminal and wvkbd.
The owner confirms both are visible. This is a software-rendered console test;
the full Sxmo session and GPU are not yet qualified. Kernel taint stays 0.

The apparent loss of keyboard taps is a coordinate orientation problem. Concurrent
raw/libinput records contain 1,432/382 events and the interrupt count increases
431 to 694. A Y-only calibration helps; the owner identifies the remaining X
inversion. Both inversions make taps match keys. Source 87d953b4 adds the two
standard touchscreen inversion booleans to the board's RMI Function12 node. Its
DTB passes build/schema/checkpatch checks, with only three existing DT warnings.
The semantic DTB difference is exactly those booleans. A RAM boot with native r1
kernel/modules verifies both live properties, identity compositor calibration,
and owner-confirmed correct keys on both sides. The signed r2 recipe is committed
and published at f50eb6893; configuration checks pass. Package build/install and
an installed boot are still required for persistent correction.

The test fixture and inspected generic-prompt screenshot are public under
diagnostics/native-wayland-console and evidence/2026-10-29-native-wayland-console.*.
Full logs, input captures and boot data remain private.


### First full Sxmo session and incomplete battery telemetry

The packaged Sxmo session starts through normal TinyDM with Pixman, scale1.5,
idle/suspend disabled and unsupported audio/modem integration disabled for this
test. The owner confirms typing, touch and horizontal gestures opening menus.
Bottom-edge keyboard open/close does not pass; gesture diagnosis remains open.
The expected missing lg,madai device-profile notice remains visible.

The system then returns to lk2nd. Retained console bytes are corrupted; raw
ramoops and LK logs are saved privately. Recovery uses the already verified
DT87 RAM image and leaves the UI first-start gate closed. The persistent journal
identifies a normal power-off requested by upowerd at21:02:09. UPower repeatedly
rejects a NaN percentage before requesting shutdown. The only battery-class
supply is smbb-bif: present/status/health/design minimum exist, but capacity,
voltage_now and charge/energy measurements are absent. Native fuel-gauge and
charging policy are still unimplemented. This establishes a userspace-triggered
shutdown; it does not prove the battery was physically empty or qualify its
state of charge. Do not bypass thermal or low-voltage protections to hide it.

Before r2, boot files, native r1 modules, configuration, exact signed r1 APK and
raw boot/GPT fingerprints are backed up and verified on both host filesystems.
Both GPT copies and raw boot still match their earlier fingerprints. The r2
source builds in the existing root-owned pmbootstrap chroot; package export
is automatic when that build finishes.


### Native r2 installed filesystem boot

The signed r2 build completes and exports automatically. Its DTB exactly matches
the physically confirmed RAM orientation candidate. Abuild still embeds `-dirty`
for the recipe commit despite the clean committed host tree; external hashes and
that limitation are retained. Trusted verification and a one-package upgrade dry
run pass. Normal APK/kmod/mkinitfs/boot-deploy processing succeeds. A final wrapper
assertion fails because the manual native16 fallback entry is absent; old boot
files/modules remain. Restoring only the saved entry repairs the postcheck without
repeating the package transaction. Generator support and fallback rehearsal remain
open. Readback verifies the new kernel/DTB and initramfs, unchanged raw boot/GPTs
and preserved old fallback files.

Normal reboot, log capture and selected lk2nd continue boot r2 from eMMC. A new
boot ID, both live DT axis flags, persistent ext4 modules, msmdrmfb, taint 0 and
automatic controls for all four display devices are verified. The minimal Wayland
console starts while full Sxmo/UPower stay stopped. The owner confirms the visible text/keyboard and correct taps on both sides in
this installed boot.

Separately, a GPIO-button DT candidate follows the stock source and GPIO inventory:
volume down/home/volume up on106/107/108, active low, 15ms debounce, default pull-up
and sleep bias disabled. W=1 DTB, GPIO-keys schema and checkpatch pass. Source
d80fe9931 is published on integration/fx0-buttons. Its RAM test image uses the
matched r2 kernel and initramfs. Physical button and wake tests are still pending;
the installed r2 DTB does not include this candidate.


### UPower missing-charge regression and rootless validation

The source archive for installed UPower1.91.0 matches the Nura recipe SHA512.
A UMockdev fixture reproducing smbb-bif's Battery/present/status/health/design
minimum fields, with no charge information, makes the unchanged backend reject
a NaN percentage and exit under strict test settings. The private journal had
already established the resulting physical system power-off request.

A candidate checks attribute presence before constructing either battery backend,
skipping interfaces without any consumed capacity/energy/charge field. This keeps
legitimate zero readings eligible and provides no invented capacity. Six focused
tests and two critical-action tests pass; all90 tests in the configured Linux
build also pass. Tests run with mocked sysfs/D-Bus in a rootless Alpine3.24
container, with iDevice support disabled. No physical power action is used.
The patch applies cleanly to pristine source.

The r3 UPower recipe is published at fc7aceb404 on integration/fx0-upower. A separate
rootless pmbootstrap build is being prepared, with a disposable source clone and
new work directory. The original root-owned pmbootstrap work and signing keys
are untouched. Native package installation and physical qualification are still
pending; the phone's installed UPower remains unchanged/inactive. Native BMS,
correct charging/thermal policy and the full Sxmo acceptance gates remain open.


### GPIO mapping, UPower native install, and update-safe development menu

The owner presses each button once, then twice. The RAM d80 capture contains
three presses and three releases for each Home102/VolumeDown114/VolumeUp115,
18 frames and no dropped/stuck/repeat events. Its36 raw events are preserved
privately and independently verified on both host filesystems. Wake and long
presses are not tested.

The rootless UPower build completes for armv7 using qemu-only compilation. Core
and noarch lang/systemd APKs pass direct signature checks with the new development
public key, and the trusted dry run selects exactly three upgrades. Before the
update, old package files/configuration/database and repository archives are
backed up on both host filesystems;23 payload files match the downloaded archives.
Those old archives use a local build signer absent from the phone's standalone
key list, while normal repository trust uses the authenticated index. No untrusted
install override is used. The exact file snapshot provides offline rollback.

Native UPower r3 installation succeeds and its daemon matches the build. It skips
the unsupported charger battery interface, reports unknown/missing battery and no
warning, and stays active through full Sxmo testing. This does not provide capacity
or qualify charger/thermal behavior. A missing USB type property is still reported.

Normal package processing regenerates boot files again. Existing supported
`deviceinfo_generate_extlinux_config=false` lets us retain a managed menu with
stable versionless kernel/initrd/DTB paths while normal DTB copying continues.
The saved native16 entry is restored once. Two normal mkinitfs runs preserve the
menu byte-for-byte. Root UUID/cmdline changes now require an explicit menu update;
this development policy does not replace final boot-layout/recovery qualification.

### Native r3 package and installed boot

The r3 recipe at0a7b0e9fa packages d80 and passes configuration checks. Rootless
LLVM cross-native compilation succeeds. A checked wrapper verifies the clean
recipe snapshot and passes its commit/SOURCE_DATE_EPOCH to abuild before signing,
avoiding the copied-APKBUILD path lookup problem behind earlier `-dirty` metadata.
The signed r3 APK embeds the expected commit and its DTB exactly matches the
physically tested RAM candidate. Signing inputs stay private; this metadata check
is not a claim of byte-identical builds with different signing keys.

Pre-r3 boot/modules/configuration/tuned Sxmo profile/world/keys and the exact r2 APK
are verified on two host filesystems. The trusted one-package upgrade succeeds.
It preserves the managed menu, copies the new DTB, retains native16 files/modules
and produces a11,955,671-byte matched-ABI initramfs. Raw boot and both GPTs remain
unchanged. Normal reboot/log capture/lk2nd continue boots r3 from eMMC with a new
boot ID, GPIO node, both touch flags, native framebuffer, real ext4 modules and
taint 0. Full Sxmo/UPower start; the combined physical input retest is pending.

### Physical gesture data and measured-trace replay

The physical attempt records52 contacts,337 frames and2,254 events, with continuous
X/Y updates and no drops/stuck contacts. Durations are below200ms, so the800ms
timeout is not responsible. Under defaults, long motions stop outside the50px
edge band and near-edge motions are shorter than125px. Some paths also slant
about20 degrees from vertical.

A replay of two measured trajectories reproduces the failure with the default
profile. Fx0 settings60px distance and a120px band make that replay close/reopen
the keyboard. A device hook allows25-degree slant; a further replay including
a measured slanted trajectory also passes on installed r3. These are synthetic
replays, not physical acceptance. The initial tuned replay aborts before injection
because the keyboard was already closed; after explicitly reopening, the test
passes. Temporary recognizer/debug logging remains until the installed physical
test is complete. See the gesture-profile evidence for the distinction.


The installed r3 owner test passes typing and both keyboard gestures. Independent
recording contains one press/release for each GPIO key and475 touch events across
72 frames/nine contacts, with no drops or stuck states. Taint remains0. Verbose
recognizer tracing is removed, and the running60px/120px/25-degree settings are
verified unchanged. Full idle/suspend/audio/modem policy stays restricted while
those components remain unqualified. Public development fixtures now document the
Fx0 profile, checked rootless recipe identity and managed extlinux menu.

### Saved fallback rehearsal and recovery to r3

The saved native16 entry was selected through a temporary managed-menu default.
It reaches systemd with its expected kernel release and exposes USB networking,
but SSH is not observed before an automatic return to lk2nd. The persistent
journal stops during early systemd startup; retained console data is insufficient
to identify the failure. This is a failed recovery acceptance test, not a
qualified fallback. The original boot files/modules remain preserved.

An image assembled from the exact installed-r3 kernel, DTB and initramfs is then
RAM-booted and reaches SSH with taint 0. It permits restoring the original menu
byte-for-byte. A subsequent normal filesystem boot returns to installed r3,
msmdrmfb and persistent matching modules, followed by active Sxmo and UPower.
The initial observation window missed the rescue's later SSH availability; no
second rescue boot was needed. Raw boot and both GPT fingerprints remain
unchanged. The successful rescue depends on the current root/module tree;
independent recovery, native16 diagnosis and factory-stock restoration remain
open. See evidence/2026-10-29-native-recovery-rehearsal.json.

### IADC signed current and unit correction

The running r3 IADC reports raw 40/36 at scale 0.001 mA. Its diagnostic log shows
samples below offset wrapping through an unsigned 16-bit intermediate. Source
review also finds a missing factor of one million when converting microvolts
and microohms to the microamps expected by the IIO scale. The same code remains
in the reviewed upstream driver. A dedicated Linux branch through
5c3efd4c7fa8a8d2bec768d826b5daac57a45e76 corrects both and rejects int overflow.

The standalone fixture compiles the actual read_raw function with only hardware
and IIO plumbing mocked. Thirteen vectors on each channel plus the unchanged
scale pass under undefined-behavior sanitization; the original driver fails.
A W=1 ARM module build with Alpine Clang 22.1.3 passes, all 34 common imported CRCs
match the packaged module, and patch-only checkpatch reports zero errors/warnings.

A brief unsigned external-module RAM test records negative sensed current around
214–298 mA across two sample sets. Six logged conversions are retained; the
three external-channel calculations match exactly. These results use the
original board/default resistor configuration and do not establish calibrated
battery current or charging direction. The module is restored immediately to
the original packaged driver, whose persistent file hash is unchanged. Temporary
diagnostic taint 12288 clears on the next normal installed-r3 boot (taint 0).
Sxmo and UPower are restarted. USB enumeration is checked before restoring the
previously used 500 mA input limit; automatic current negotiation remains open.
No battery voltage/current safety threshold is changed. Signed package integration,
stock resistor/temperature compensation, BMS and charging qualification remain
next steps. See evidence/2026-10-29-iadc-current-conversion.json.

### Non-VM PM8226 BMS identity and output observed

A bounded read-only module performs 16 regmap reads totaling 46 bytes without
setting output hold, resetting counters or changing charging policy. It confirms
BMS1 type 0x0d/subtype 1 (digital major 2) at 0x4000 and companion IADC
type 0x08/subtype 5 (major 4) at 0x3800. Voltage, VSENSE and counter bytes are present.
These unlatched multi-byte observations are not coherent counter samples and do
not establish capacity or absolute accuracy. The module is unloaded immediately;
its temporary unsigned/external taint 12288 clears on the subsequent standalone
rescue boot. W=1 module compilation and checkpatch pass. The native non-VM BMS
driver remains to be implemented. See evidence/2026-10-30-pm8226-bms-observation.json
and docs/battery-bringup.md for the implementation sequence and stock references.

### Independent rescue survives the signed r4 update

A frozen r3 initramfs with a replacement second-stage script embeds all 22
original signed modules, removes root UUID arguments, and stops before root
lookup/mount/switch_root. Its first RAM boot reaches the development USB network
shell with taint 0, zero disk mounts and all 42 exposed internal block devices RO.
Direct raw boot and GPT readback hashes match. Host modem probing corrupts the
serial trace; independently framed network commands provide the verified data.

The signed native r4 package builds in 11m14s with the expected clean recipe
commit. Direct trusted signature and normal upgrade dry-run pass, followed by
an actual r3-to-r4 package transaction. Readbacks match the exact APK kernel/DTB;
all 22 initramfs module payloads match the APK. The managed menu and frozen rescue
files survive unchanged, and raw boot/GPT comparisons pass.

A normal filesystem reboot then selects the frozen r3 rescue entry, despite
persistent modules now belonging to r4 with a different signing key. It again
reaches the independent shell with taint 0, no disk mounts and 42 internal RO
nodes. A bounded repair validates the boot menu through a read-only loop/mount,
then restores the normal menu through a temporary-file/rename on a boot-only
writable mount. It unmounts/detaches and restores every RO flag. Raw boot and both
GPTs still match. No root mount or factory restoration occurs. The subsequent
normal installed-r4 boot passes, with sensing and Sxmo results recorded below. See
evidence/2026-10-30-standalone-rescue.json.

### Installed r4 native sensing and Sxmo

Normal filesystem startup reaches the r4 kernel build 5, its new trusted module
set, msmdrmfb and persistent ext4 modules with taint 0. An initial verification
asks for a srcversion sysfs attribute this configuration does not emit; the
assertion is corrected and the same boot is validated through kernel build,
packaged module signature and native conversion logs. No extra reboot is needed.
The installed APK database confirms 6.18.59-r4 plus UPower 99991.91.0-r3.

Twelve logged voltage conversions and six external-channel current conversions
match the corrected arithmetic. This warm boot already retains 500 mA; repeating
that configured input request is not evidence of improvement. The charger changes
Charging/Good to Discharging/Overheat during sampling, with the external IADC
later reporting 22.3 mA. Absolute accuracy, direction, sensor freshness and board
compensation remain unqualified. No charge/temperature threshold is changed.

Full Sxmo, terminal and keyboard are restored. The running recognizer is verified
at 60px distance, 120px edge band and 25-degree tolerance with verbose tracing off;
a reviewed Wayland screenshot shows the expected UI. Physical input was last
confirmed on r3 with the same DTB. The display startup workaround, idle/suspend
restrictions and software rendering remain. Native BMS/thermal/charging work is
next; see evidence/2026-10-30-native-r4-installed-boot.json.

### Coherent BMS output and stock comparison

A focused BMS1 diagnostic now sets/verifies the output-hold bit, reads the fixed
output list twice, decodes signed 36-bit counters, and restores/verifies hold on
every exit. Actual-helper tests cover 30 single-operation faults, four ownership/
consistency/permanent-failure cases and nine decoder vectors under ASan/UBSan.
W=1 ARM compilation and source checkpatch pass. Two native three-sample sets show
changing counters and restored control, without counter resets or charger writes.
The second capture's final active-service assertion fails because the UI gate is
closed after reboot; capture and unload succeeded. UI is subsequently restored.

The original stock kernel/QCDT is RAM-booted with the existing diagnostic initramfs
and its return timer. No disk filesystem is mounted. Three samples report
Charging/Good, 31°C and 76%, providing a stock baseline rather than native capacity.
The stock companion-IADC channel/sense setup is 1/2, versus native 0/0. Trim banks
match each other within each mode but differ between modes; those private values
do not prove mirror-address write support. Stock BMS current is negative while
charging, while its manually sampled IADC is positive. Native direction and
absolute current accuracy still need qualification.

Stock BTC control uses extended hardware limits, but the madai V1_8 software
charging scenario adds stop/derating/hysteresis. The vendor thermistor table maps
the nominal extended comparator voltages to limits outside the stock software
-10°C/55°C stop envelope. Native extended range remains disabled until a real
sensor/fault and charging-control implementation preserves that protection.
This stock RAM run is not the factory restoration rehearsal required by the
storage-consolidation plan.

### IIO battery reference and voltage preparation

The separate Linux integration/fx0-bms branch at0280620f6 adds three focused
commits: binding descriptions for gain/zero references, raw IADC reference
channels with hardware-number translation, and VADC scaling for battery and
thermistor voltage. Three RAM-only sample sets pass for each ADC module. The
reference fixture checks 23 actual-function cases with ASan/UBSan; the prior
13 current vectors on both channels still pass. Both W=1 ARM module builds,
binding document validation and each patch's checkpatch pass.

The VADC samples yield about3.94V battery voltage and660–661mV thermistor voltage,
approximately31.3°C under the vendor table. These are plausible/model-based
observations, not external accuracy qualification. The existing SCALE_DEFAULT
path returns microvolts for absolute calibration and millivolts for ratiometric
calibration. That difference is explicitly recorded; processed-voltage ABI/consumer
units must be resolved before freezing an upstream series. Per-unit calibration
stays private. Firmware consumer routing, native BMS configuration/calibration,
counter-to-charge conversion and profile identification remain open.

Each test restores its packaged ADC module. A subsequent normal installed-r4
reboot clears unsigned diagnostic taint to0, reaches msmdrmfb, leaves all four
display controls automatic and starts Sxmo/UPower. USB input returns to100mA;
after verifying online/configured state and the sole500mA gadget configuration,
the prior500mA development limit is restored and read back. This is supervised
runtime configuration, not automatic negotiation. No charger voltage/current/
temperature thresholds change. Installed r4 and its canonical source remain
unchanged; the new IIO branch is public but not packaged or submitted upstream.
See the coherent-stock-comparison and battery-adc-references evidence files.

### Battery input units and calibration write ownership

Linux deec41b85 corrects the two new battery voltage inputs to IIO millivolts.
Absolute values use FRACTIONAL/1000 so a consumer can recover microvolt precision;
ratiometric values already have millivolt units. The actual callback and IIO
multiplication pass84 ASan/UBSan cases, while the earlier version fails. W=1 ARM
compilation, patch checkpatch and RAM reads pass. Existing processed/raw interfaces
are preserved; firmware consumer routing remains open.

A separate bounded experiment saves the BMS sense controls and both mirrored
trim readbacks, then applies the stock external-sense configuration and a measured
zero reference through protected primary-IADC writes. The primary0x3600 path
changes trim and passes readback; the attempted0x3800 mirror write fails with I/O
error and exact original settings are restored. The failing bus transaction was
not traced, so the precise failure stage is not claimed. The production driver
must keep trim writes inside the IADC provider, serialized with conversions and
its calibration cache. A mirror read is insufficient evidence of a writable API.

Sense-only leaves the observed idle manual current about17.9mA; trim-only moves it
near0.5mA, and both changes near0mA. Reloading the ADC cache does not explain the
small current. An added2ms conversion delay also makes no useful change and is
rejected as an integration patch. Each phase restores settings and packaged ADC
modules. These observations alone do not establish a sensor failure: USB can
power system load without appreciable battery current.

### Controlled input-budget/load response and counter epoch

A single sha256sum worker runs under an18-second systemd limit with CPU accounting
and a conservative thermistor-voltage stop guard. At500mA input, manual battery
current remains near0 and BMS sense does not transition. Repeating with100mA input
produces roughly-0.20..-0.24A manual current, an approximately30mV battery voltage
drop, changing BMS VSENSE and reversed counter direction. Restoring500mA returns
manual current near0. No charger voltage/current/temperature threshold changes.

The documented stock100us clear pulse is tested as an explicit new-source epoch,
rather than as part of ordinary telemetry reads. Counters are already flat before
the optimized-update attempt and remain flat afterward, despite a zero command
readback. A forced-write helper recovers both main and shadow counting under load.
Source inspection and a read-zero command model identify how optimized deassertion
can be skipped; no bus-write trace or cause for the initial stopped state is
claimed. The final238-case actual-helper fixture covers this regression, protected
writes, isolation modes, rollback, ownership and transient/permanent bus faults.
The optimized helper fails that regression. W=1 ARM/checkpatch pass.

In the final18-second load window, the provisional BMS VSENSE conversion is about
-190..-214mA after sign inversion, resistor-adjusted manual IADC about-197..-215mA,
and counter-derived averages about-213..-218mA. They share calibration and sense
hardware, and samples are sequential: this qualifies response and provisional
conversion consistency, not external accuracy or idle/charging compensation.
Current and charge-counter conversion need the BMS direction inverted to align
with positive charging. Counter contents are intentionally lost in the explicit
epoch tests; control/trim settings are restored, not historical counter values.

A normal installed-r4 reboot again returns to kernelbuild5, taint0, msmdrmfb and
active Sxmo/UPower. The configured500mA development limit and terminal/keyboard are
restored. The new source remains a separate un-packaged candidate; no upstream
messages are sent. The next implementation is provider-owned calibration plus the
native non-VM BMS driver/binding with actual IIO firmware references, safe charge
conversion and supplier lifetime handling. Stock-pack thermal/profile and charger
policy follow; no native capacity or completed all-hardware bringup is claimed.
See evidence/2026-10-30-bms-calibration-epoch.json.

## October 30: required MPU-6515M DMP wake and native BMS prototype

The owner requires MPU-6515M driver support, DMP access and DMP interrupt wake.
Plan section6.1 and separate hardware acceptance rows now require verified
silicon/topology, firmware provenance/execution/FIFO output, real system suspend,
a causally identified retained DMP event, at least20 consecutive DMP wakes and
battery standby/false-wake evidence. Raw IIO support alone is insufficient.
Linux6.18.59 has MPU6515 matching/raw support but no DMP loader in the audited
directory. A pinned historical InvenSense implementation is a reference, not
proof of this unit's wiring or firmware compatibility. These gates are unverified.

Four Linux candidate commits implement provider-owned protected calibration,
a native non-VM BMS binding/driver and Fx0 IIO firmware references. The source
is published at35743f198 on integration/fx0-bms; installed r4 remains unchanged.
The original r4 kernel/initramfs RAM-boots with the new DTB and unsigned modules
(taint12288). Native power_supply registration, actual firmware-channel lookup,
provider unbind/consumer teardown/rebind, periodic calibration and bounded
discharge response pass. The driver supplies a relative counter, not capacity.
UPower remains finite and ignores this incomplete interface without a false
critical warning. Host tests pass20033 math,70 BMS I/O fault,34 calibration and
27 reference/cache cases under sanitizers; ARM W=1 and targeted schema checks pass.

A required longer observation finds an idle transition failure: after the
charger's conservative overheat indication, manual current is0 while BMS current
and counter accumulation still indicate about+155mA. Recalibration does not fix
it. A bounded100mA input/single-core load yields about-0.21A on BMS and manual
IADC, with counter-derived average-208.6mA; restoring500mA returns both near0.
No kernel warnings or charger threshold changes. Stale sampling, analog coupling,
BATFET state and missing transition configuration are hypotheses, not findings.
This failure prevents promotion and current/counter acceptance. Next capture
BATFET/charger/BMS freshness around a matched charging stop and compare stock.

The first reboot request was blocked by the temporary validation inhibitor.
Stopping an already-expired transient unit also returned an error; the helper
now checks for active units before retiring them. The subsequent reboot request
succeeds and lk2nd continues the installed r4. Final boot/UI verification is
recorded in evidence/2026-10-30-native-bms-prototype.json after it completes.
No repartition, package upgrade, upstream mail or submission occurs.

## October 30: current sources and BATFET IRQ experiment

Linux31061619c separates live IADC CURRENT_NOW from the background BMS
CURRENT_AVG and fixes initialization error reporting now that their errors are
independent. The exact source builds with ARM LLVM22 W=1/checkpatch0/0;33 actual
getter cases pass sanitizers. A new RAM boot and bounded500/100/500mA test show
charging, discharge and return-to-USB responses. During USB idle, IADC reaches0
while background current/counter still indicate about212mA. Under load both
respond around-0.2A, and afterward IADC0/background1.5–2.1mA. UPower remains finite
and leaves capacity unknown. Electrical correctness of either source is not
established by their shared-hardware agreement or disagreement.

A proposed instantaneous BATFET guard encounters cached/raw state disagreement.
Adding a both-edge BATFET IRQ exceeds the100-events/second test guard. The driver
is unloaded. An exact controlled variant disables periodic polling and IRQ
refresh, yet records13616 interrupts in2.0025seconds (~6799/s), with edge/high/low
configuration read back enabled and no IADC current-debug/calibration events in
the next3seconds. No ADC conversion phase is attempted after the rate guard.
The electrical/controller cause remains unresolved. The observer is unloaded;
these guard/IRQ changes are rejected and retained as reproducible source patches
under experiments/pm8226-batfet-irq. Only the current-source distinction is pushed
to integration/fx0-bms. Canonical r4 and its package remain unchanged.

The owner reports no current-measurement fixture or oscilloscope available.
Continue source/stock analysis while leaving independent electrical accuracy
unverified. The full vendor source is now checked out at the pinned03aba4427
revision on Disk B. Its normal charging_enabled setter also forces operation
on battery, so that control cannot reproduce a USB-bypass stop. The factory
charge attribute instead routes to charge-only chg_status_set; runtime existence
and behavior must be verified before using it. No stock charge-control write
has yet been performed.

Stock DT inspection finds qcom,msm-adsp-sensors and no direct MPU6515 compatible;
the complete vendor tree supplies sensors_adsp.c but no MPU6515 driver match.
This is a topology lead, not chip identity or proof of DMP use. DMP access and
DMP-generated system wake remain required; DSP software fusion alone does not
satisfy on-chip DMP execution.

A normal eMMC boot restores installed r4 build5/taint0 with no BMS prototype,
active UPower/Sxmo, all4display controlsauto and a reviewed private terminal/
keyboard screenshot. Physical UI retest is not claimed. No repartition, package
upgrade or upstream communication occurs. See current observation evidence.

## October 30: stock charge-only stop and calibration trace

Two bounded stock RAM captures use the verified factory `bms/charge` endpoint.
Charge-enable readback is `0x80 → 0x00 → 0x80`, with forced-battery mode off.
BATFET opens, manual current becomes zero and background current settles near
zero. Stock reports Full and resets its counter. Targeted dynamic debug in the
second capture confirms charging-ended/Full messages, IADC calibration/trim
writes and EOC handling. Source inspection explains the Full-triggered reset
and open-BATFET calibration path; exact binary/source identity remains unknown.
Do not transfer the SOC reset into native merely to hide a current discrepancy.

The capture script restores charge control, permissions, debug selectors and
selected print flags. It does not mount disk filesystems or change charger
limits. Both supervised runs return automatically to installed r4/taint0.
Preceding attempts abort before charge writes when debugfs selector readback
fails; using `echo` for selector writes succeeds. The underlying syscall-level
reason has not been established. Raw calibration and logs stay private; the
public exporter has six checks for values, sign, privacy and incomplete input.
Independent electrical accuracy remains unverified without measurement equipment.
See [stock charge-only evidence](../evidence/2026-10-30-stock-charge-only.json).

## October 30: native temperature and calibration isolation

Provider-only recalibration does not resolve the background current discrepancy.
The live reading stays zero while background current/counter indicate discharge.
Input current is restored from the temporary 500 mA baseline to its original
100 mA. A subsequent fresh/cached-reference comparison aborts at the initial
thermistor guard without running either arm. Both return to installed r4.

The temperature branch adds the generic ADC thermal binding's optional IIO
provider reference and 83 attributed stock LG thermistor points in a separate
GPL-2.0-only include. ARM module/DTB builds, binding documentation and targeted
compiled-DTB schemas pass. The actual interpolation passes 1,803 inputs plus
passthrough under sanitizers; the actual BMS getter suite grows to 37 cases.
RAM reads agree around 32.6–32.7°C through IIO, thermal and BMS interfaces.
Three provider-removal cycles remove BMS safely and recover it after explicit
consumer reprobe. The first test's stronger automatic-rebind expectation fails;
the corrected test uses the same image and the established explicit reprobe.
No charging policy or limits change. Normal installed r4 returns with taint 0,
native framebuffer and active UPower/Sxmo. Independent sensor accuracy, thermal
fault/policy/suspend behavior and package integration remain open.

The owner's console photograph matches the running r4 boot warnings. Source
inspection identifies QUP's non-DMA fallback, optional WLED OVP handling and the
USB PHY preferred-voltage fallback; both L20 rails report 3.075 V enabled.
MDP5 bit26 is INTF1 underrun. The BPF LSM is active but kernel BTF is absent;
its relation to the systemd warning needs direct verification. The audit records
remaining messaging/device-link, display and kernel-configuration work without
publishing the photograph or claiming complete hardware acceptance.

## October 30: reference conversion comparison

The corrected input-only comparison runs base/cached/base arms at 100 then
500 mA, followed by an unchanged-base reload at 500 mA. The initial and read-time
thermistor guard is 630 mV and no synthetic CPU load runs. Background readings
settle near zero in every arm, including the unchanged base; the earlier large
frozen-current symptom does not recur after the first reprobe. This does not
establish cached references as a fix. The separate diagnostic patch and hashes
are retained for review. Initial sense/calibration/counter sequencing and a
first-probe transition remain the next targets; independent accuracy is open.
Cleanup restores 100 mA. New installed r4 identity/taint 0 is observed, then a
later SSH command times out. An idempotent bounded finalizer verifies the same
boot, restores UPower/Sxmo and checks all four display controls remain auto.
No additional reboot is used for that recovery and no integration code changes.

## October 30: isolate the comparator window

A staged native comparison keeps the signed r4 IADC and removes BMS/thermal
consumers. Swapping VADC or reading battery voltage preserves charging. Reading
the thermistor exposes the hardware HOT flag and reduces live current near zero.
Reference mode is already forced (`0xc0`); repeating the stock awake request does
not help. Switching the mux back to battery voltage does not clear the trip.
Five minutes with the backlight off changes inferred temperature by less than
1°C, insufficient to exclude comparator hysteresis.

The original stock kernel then reproduces HOT at a reported 31.6°C when its
25%/80% comparator range is temporarily tightened to native's 35%/70% range.
Restoring stock's range clears HOT and charging resumes. Stock supply health
remains Good during the raw hardware trip; the source uses LG software-policy
health. A DT `btc-disabled` flag is also insufficient to infer runtime state:
the enabled factory-pseudo-battery build path enables the comparator in normal
mode, matching observed `0x82`. This comparison points to range/profile and
missing native software-policy work, rather than a proven VADC conversion bug.
Do not introduce an unproven reference/mux fix or widen native hardware limits
alone. Every test restores normal installed r4 with taint zero.

## October 30: standard native charge-control actuator

The separate kernel commit 05bec5027 exposes auto/inhibit-charge while preserving
forced-battery mode and other charger control bits. Its actual helper/property/
status tests pass 1,051 ASan/UBSan cases; strict checkpatch has zero diagnostics.
A full ARM LLVM22 W=1 kernel build passes, all 14,228 shared module symbol CRCs
match, and the patch applies to pinned current upstream SMBB source.

The full kernel boots from RAM with original r4 DTB/initramfs and a verified GNU
build ID. Three inhibit/resume cycles pass with USB online, unchanged limits,
Not charging while inhibited, and live IADC about 249 → 18.4 → 230–290 mA.
The residual reading is not proof of electrically measured zero current. Invalid
modes are rejected without a control change. Cleanup restores the actual initial
100 mA budget and original mode. Normal installed r4 returns automatically with
taint zero, active UPower/Sxmo and all four display controls auto. No persistent
package change, wider BTC setting, gauge reset or upstream communication occurs.

Source review finds that current upstream Charger Manager needs sensor-failure
handling and an appropriate power-supply actuator before reuse here. No complete
native thermal policy has yet been enabled. Temperature accuracy, sensor faults,
thermal hysteresis/derating, charging across suspend and current/gauge accuracy
remain qualification gates.

## October 30: Charger Manager fault prerequisites

Actual upstream decision/regulator functions reproduce two hazards: an enabled
charger remains enabled after a temperature-read error, and an expired duration
can bypass a hot-temperature stop through the redundant-enable shortcut. Two
separate experimental commits prevent duration override and make runtime sensor
errors inhibit monitored charging with health Unknown. Existing unmonitored
configurations remain compatible. The actual thermal/duration/target/monitor/
regulator/property functions pass 8,330 ASan/UBSan cases, including boundary and
fault recovery. Both patches apply to pinned current upstream and its patched
file passes the same suite. The LTS module builds for ARM LLVM22 W=1 with no
diagnostics, and strict checkpatch is clean.

The module is not loaded on the phone. Probe-time strict sensor requirements,
actuator failures, independent inhibition and suspend protection remain necessary
before choosing Charger Manager for the Fx0. Installed r4 and hardware comparator
limits are unchanged; no upstream submission is sent.

Separate submission branches now base directly on the actual power-supply
maintainer's for-next f0f400459bf6a037e70768de623fff3f8920b8bb (7.3-rc1),
rather than carrying the LTS/Fx0 integration history. Both host suites pass on
those branches. Both changed drivers compile as ARM LLVM22 W=1 objects from
multi_v7_defconfig plus their dependencies, with zero warnings/errors. These
are current-tree object checks, not full current-kernel boots or module links.
The two independent draft patch series and exact hashes are exported under
submissions/power-supply and manifests/power-supply-submissions.json. Author
sign-off and final submission review remain; nothing is sent to maintainers.

After all RAM diagnostics return, normal r4 is observed Charging/Good with a
500 mA input budget matched to the configured host USB interface, live IADC
about +281 mA, taint zero and active UPower/Sxmo. No thermistor read or broader
hardware comparator setting is used for that development-budget restoration.

## October 30: runtime battery-profile handoff

The first-stage bootloader supplies exactly one ISL6296_L type argument, matching
the stock vendor's TOCAD Madai selection; native Linux filters that argument.
New GPL lk2nd code generates standard battery data and charger/BMS references
for the known selection, without putting a replaceable pack into the Linux board
DTS. It preserves all 155 vendor OCV points, five temperatures and percentages,
and distinguishes KDDI's rated 2370 mAh from vendor nominal/measured FCC. Unknown
or duplicate types select no assumed fallback. No PMIC writes or new charging
temperature limits are added.

The first RAM firmware recognizes the pack but returns to original fastboot
before Linux SSH. Its ordinary malloc workspace is a real defect: LK ARM32
guarantees pointer alignment, whereas libfdt requires eight bytes. A stronger host
allocator regression reproduces FDT_ERR_ALIGNMENT. The corrected source requests
memalign(8); 128 real-libfdt selector/data/rollback cases pass ASan/UBSan and all
vendor values match. The exact initial physical failing address was not captured.
Full GCC15.2 firmware builds pass with no new-source diagnostics and one linker
RWX LOAD warning.

The aligned firmware boots installed r4 with the profile. A separate bounded
UPower probe initially mistakes an activatable name for an owned name; masked
activation triggers a CLI SIGSEGV. Correct ownership checking, a Type=dbus
transient and direct D-Bus calls fix the test readiness race. CLI failure handling
after unavailable activation remains an open userspace issue. The final RAM run
verifies all 155 OCV points in the kernel, rated 2,370,000 µAh and charge 4,350,000 µV,
unchanged configured charger limits, and no kernel capacity attribute. UPower's
DisplayDevice is absent/stateUnknown with warningNone; this is not a usable
battery interface or a valid state-of-charge estimate.

Each run returns to original firmware/r4 with taint zero and matching readbacks
of the installed bootloader prefix and both GPT regions. The test-owned UPower
mask is removed, normal UPower/Sxmo return, and the configured 500 mA development
budget is restored. No firmware is flashed or package upgraded. Core results,
failed attempts and raw logs remain separately captured; unit data stay private.

SMBB and experimental BMS bindings now allow the standard reference. Documentation
and generated R4/BMS DTBs pass with complete dependencies; baseline schemas reject
the new references. A separate SMBB binding draft is based directly on the
power-supply maintainer's pinned for-next and passes its own documentation/DTB
checks. It joins the existing two independent draft series; nothing is mailed.

Charger-local policy with managed IIO suppliers and independent inhibition is the
selected next implementation. The legacy Charger Manager binding discourages
new users, so its generic fault fixes remain independent contributions. Early
profile/sensor gating, faults, warm current/voltage behavior, suspend protection,
gauge accuracy, capacity, replacement and the rest of hardware acceptance remain
open. See [profile evidence](../evidence/2026-10-30-battery-profile-handoff.json).

## October 30: verified charger-control foundation

The separate Linux `integration/fx0-charge-guard` branch adds a charger mutex,
independent setup/user/fault restrictions, readback of enable/limit writes and a
managed inhibition attempt after later probe failures or removal. A failed bus
operation can follow an effective write; the recovery therefore forces another
charge-only write and verifies it while retaining the original error and fault.
User auto cannot clear the fault. Cached limits remain unavailable until
reinitialization after a control fault, rather than returning an untrusted old
value. Persistent bus failure can still prevent physical inhibition.

At source `25d7524a6fbb3008c7c72be53f1cd5c38ecc2d68`, 6,242 actual-function
ASan/UBSan cases pass, including 2,000 concurrent requests. Five deliberately
broken implementations fail assertions. The complete ARM driver object passes
W=1 and the full zImage builds without diagnostics. Strict no-signoff style
checks report zero errors/warnings/checks; no new DCO certification or upstream
submission is claimed. The branch is published separately from the installed
package and submission branches.

Two-filesystem preflight preserves exact original boot files, bootloader prefix,
GPT regions and RAM candidate. The candidate boots with verified GNU build ID
e6323421f4d4023f2a3376c2d1a07fdf14a3c134 and original r4 DTB/initramfs. Three
inhibit/resume cycles, six unchanged limit writes, three unsupported mode strings
and two negative limits pass with USB online and the actual 500 mA budget
unchanged. BTC remains 0x81; forced-battery and reference settings are preserved.
The RAM observer is used with force_on=0, and taint is explicitly 12288.

Inhibited status is Not charging, whereas auto remains Discharging/Good. Live
IADC stays 22.2 mA in both states. This qualifies control-register/API behavior,
not a charging-current response, electrical accuracy or state of charge. No
bus error is injected on hardware. Full probe-error/cleanup execution is not
covered by the extracted helper tests.

The controller retains reset logs and returns to installed r4 build5 with taint
zero, active UPower/Sxmo and all four display controls automatic. Bootloader
prefix and both GPT copies are byte-identical; ordinary OS writes are outside
those comparisons. No persistent kernel/firmware install or repartition occurs.
Early firmware gating, profile/sensor authorization, thermal hysteresis/derating,
stale inputs, suspend, pack replacement and actual charging/gauge qualification
remain open. See [evidence](../evidence/2026-10-30-smbb-charge-guard.json).

## October 30: early firmware charge inhibition

An isolated lk2nd branch adds opt-in charge inhibition before native driver
dependencies can defer probe. The existing checked SPMI APIs are suitable for
error propagation, but their shared command polling is unbounded. Bounded
1,000-poll waits now return a nonzero error rather than waiting forever. Two
compiled SPMI layouts pass 2,048 complete transfer/delay/error cases. This does
not retrofit old byte/void APIs that discard errors or measure physical timing.

The GPL gate validates the exact Fx0, sole charger node, PM8226 SID/address and
runtime PMIC model before writes. Its aligned FDT clone completes fallible tree
operations before PMIC access. It clears and verifies only charge enable,
preserving forced-battery mode; a proposed handoff marker is published only on
success. Error recovery attempts inhibition again but still aborts the boot.
Current aboot asserts on DT-update errors; a hard bus failure may need manual
reset and cannot be described as verified physical inhibition.

The first RAM firmware a154a55 successfully hands off control 0x00 before any
native charger probe, with a deliberately disabled native charger and a read-only
initramfs observer. It nevertheless fails the diagnostic's expected BTC 0x81
assertion: inherited BTC is 0x82 and reference 0xc0. The exact boot stage or reset
mechanism restoring 0x82 is untraced. Source comments and public records distinguish
that observation from an attribution to first-stage firmware.

The revised gate at dbdb98a verifies inhibition first, then selects and verifies
BTC mask0x83/value0x81 without changing unrelated bits or the reference. Its 307
actual libfdt/SPMI/fault/rollback cases pass ASan/UBSan. Full GCC15.2 builds have
one existing linker RWX LOAD warning and no new-source diagnostics. The existing
128 profile cases and all 155 source OCV values still pass. A later commit changes
only an explanatory comment; the exact physically tested commit/image remain
separate in the manifest.

The same observer image boots under the revised RAM firmware and records the
marker, no native charger supply, control 0x00, BTC 0x81 and reference 0xc0. It mounts
no eMMC filesystem, marks available block devices read-only and reboots
automatically. The RAM observer has taint 12288. Both runs retain their exact
images, logs and outcomes, then return to original firmware/r4 build5 with
taint 0, normal UPower/Sxmo, automatic display controls and matching bootloader/
GPT readbacks. No firmware is flashed or package replaced.

The properties are a development protocol proposal, not accepted bindings.
Actual fw_devlink supplier deferral and the Linux handoff/profile/sensor/thermal
worker remain unconnected; an older native driver can re-enable charging after
normal setup. The disabled-driver test does not qualify that later interval,
runtime removal, suspend, current accuracy or SOC. See
[early-gate evidence](../evidence/2026-10-30-firmware-charge-gate.json).

## October 30: managed native charging policy

The Linux integration now validates the firmware marker and actual charge-off/
conservative BTC state. A separate policy child waits for managed IIO suppliers
while SMBB keeps USB/extcon bound and charging inhibited. Firmware generates the
runtime TOCAD Madai policy identity only for the existing known selection and
explicit opt-in. This remains boot-time selection, not direct pack authentication.

The worker converts all 83 stock thermistor points without endpoint clamping and
implements the original LG V1_8 normal/reduced/stop rules, including 450 mA warm
current, the 4.0 V cutoff and recovery hysteresis. Independent user, thermal,
sample, handoff, pack, suspend and I/O-fault restrictions combine under the
actuator mutex. User caps cannot exceed active thermal/board ceilings. Every
enable checks sample age, and an independent age worker also inhibits stale
operation. Observed pack identity loss survives parent reprobe until reboot;
the prototype policy is built in. Quiesce verifies inhibition and cancels both
jobs before supplier suspend/removal; resume waits for fresh data.

Actual-source sanitizer tests pass 21,496 model/stock-comparison cases, 2,604
policy cases (including 2,500 concurrent requests), 6,242 existing control cases,
41 firmware policy-identity/FDT rollback cases and 84 voltage ABI cases. ARM W=1
driver/module checks, the complete kernel and static/generated-runtime DT
validation pass. Strict style checks omit DCO and the generic new-file notice;
subsystem MAINTAINERS patterns already cover the files. No sign-off is invented.

The dependency check catches installed r4 VADC's raw-code interface before the
first prepared candidate is booted. The branch carries the previously tested
processed-voltage and millivolt-precision patches, builds matching modules, and
prepares a separate candidate. The rejected preparation remains captured as
unbooted. An initial module build targets the read-only source by mistake;
correct in-tree output targets then build successfully without diagnostics.

The qualified RAM run verifies the kernel notes and runtime-profile firmware,
keeps charging off with the ADC absent, and proves real USB HTTP packets during
that deferral. Module load binds the policy automatically with readings around
30.8 C/4.287 V. The user inhibit request remains effective while sampling runs;
auto releases only that vote. Managed supplier unbind stops/removes the policy
and inhibits charging while the parent and USB HTTP stay available. Rebind needs
explicit drivers_probe; automatic recovery from forced unbind is not claimed.
Fresh operation then returns. BTC remains 0x81 and reference 0xc0 throughout;
diagnostic taint is 12288. No eMMC filesystem is mounted.

USB interface rename creates duplicate temporary host profile names within one
second. Both profiles are successfully deleted, but the extra deletion fails and
stops the final return before continuing original lk2nd. Actual profile absence
is verified; the same return resumes without repeating hardware testing. Names
now use finer uniqueness and cleanup tolerates duplicate/already-deleted names;
that idempotence regression passes. Original firmware/r4 returns with taint zero,
active normal services, automatic display controls and matching bootloader/GPT
readbacks. No temporary host profile remains and no firmware/APK is installed.

Current accuracy/SOC, physical thermal boundaries, a hard hardware-watchdog
deadline, real system suspend, termination, live identity, USB negotiation and
broader hardware acceptance remain open. These proposed bindings and RAM tests
are not a completed production charging solution. See
[native policy evidence](../evidence/2026-10-30-smbb-native-policy.json).

## October 30: UPower review regressions and installed r4

Current UPower master is pinned at `91ec33a` (version 1.91.5). Its existing `78466b1`
already fixes the CLI NULL device-list paths. New mock-service coverage injects
a real EnumerateDevices error in enumerate, monitor, monitor-detail, dump and
battery modes. Old 1.91.0 reproduces SIGSEGV in the first three; all five exit 1
with the accepted backport. Original authorship and cleanup prerequisites are
preserved; no new upstream CLI C fix is claimed.

Charger-only, design-only and design-plus-measurements/lifetime-counter fixtures
all expose false empty/critical battery state on unchanged current master. The
existing Nura guard ports cleanly and rejects them. A genuine zero remaining-
charge control remains present with a normal low-battery warning. All 103
configured current-master tests and all 94 backport tests pass, including existing
critical actions. Black 24.10 passes; final current formatting preserves the
tested AST. These tests use host UMockdev/isolated D-Bus and do not exercise
physical power actions, ARM error injection or every malformed measurement.

The Nura r4 recipe replaces its earlier guard patch with expanded tests and the
accepted CLI backports. All six new patches apply without offsets/fuzz; the
unchanged Nura history-timing patch retains a seven-line offset. Applied runtime
and test files match validated source. The recipe is committed and pushed.

The rootless package clone initially lacks the required upstream remote and
channel refs; those are restored from the existing pinned clone. A signed ARM
build completes but retains extra-repo -dirty metadata. It is not installed.
A separate rebuild passes a verified clean recipe/epoch to abuild before signing
and checks the embedded commit. Both candidates and failed setup logs remain
separate. The final ARM ELF/package identities and signatures pass validation.

Trusted r3 rollback APKs and package/config/database snapshots are verified on
two filesystems; 23 installed payload files match. The offline dry run selects
exactly the three expected upgrades. Native r4 installation succeeds with a
temporary owned service mask, which is removed before restart. Read-only
verification corrects scalar D-Bus JSON handling and selects the exact four PM
paths, then resumes on the same boot. CLI/daemon bytes match the package,
enumeration/dump/battery modes succeed, UPower/tinydm are active, taint is zero
and all four display controls are auto. No physical UI retest is claimed.

APK triggers regenerate boot files. The exact signed r4 kernel/DTB and 22 module
files, original prefix/init/cleanup, absent RAM overlay and initramfs memory fit
are verified. Managed menu, frozen rescue, raw boot and both GPTs are unchanged.
No reboot or new charging/SOC acceptance is claimed. The daemon is byte-identical
to r3; installed runtime changes concern the CLI and correct package provenance.
Current-upstream drafts remain unsent. See
[UPower evidence](../evidence/2026-10-30-upower-telemetry-r4.json).

## October 30: original sensor registry and guarded ID trial

The native inventory has no active remote processors and only touch/CCI I2C
adapters. Stock source's sensors_adsp driver supplies timing/OCMEM support;
its DT node does not identify the MPU. Original system inspection finds the
sensor HAL, sensor1/registry libraries, daemon and defaults file. The daemon
names `/sns/cal/sns.reg`, found in the backed-up sns partition at `/cal/sns.reg`;
persist has only sensors_settings. The registry is preserved privately with
source files and independent-filesystem copies.

The pinned sns-reg map decodes a 256-byte group 2690 at 0x1700. All 72 shared
static keys match stock defaults after correct field-width masking. Accel/gyro
select bus 2/address 0x68/GPIO69; the defaults call the driver MPU6500. Magnetometer
selects 0x0c/GPIO66 and is named HSCD008. These are configuration facts, not
physical chip identification. The new inspector emits only wiring/comparison
data, rejects mismatched/unresolved defaults, and passes 270 boundary/selector/
output-isolation cases without printing calibration or driver UUIDs.

Vendor source maps smd_sns_adsp to SENSOR on SMD_APPS_QDSP. Modern libssc uses
QMI_SERVICE_SSC/Protobuf. The proposed QRTR/SMGR IIO path still needs compatibility
review against this old firmware/transport; software fusion cannot substitute
for the owner's explicit on-chip DMP requirement.

A fixed-register GPIO ID diagnostic passes 800 actual DT/message/identity cases
under ASan/UBSan and ARM W=1 compilation against canonical r4. Its 37 imports match
the build's symbol CRCs. Exact source/module and current boot/transport recovery
inputs are verified on two filesystems before upload. The physical read-only
preflight passes and reports GPIO6/7 control/IO zero. Capture successfully calls
ADSP PAS1 shutdown before requesting pins. Both released lines remain low, so it
returns -EBUSY before adapter registration or any I2C transfer. Original control/
output readbacks match; no sensor rail, reset, configuration or IRQ69 is changed.

Synchronous oneshot launch returns the module's refusal before the supervisor
saves its terminal result. The existing recovery path still completes. The exact
previous-boot kernel/unit journals recover PAS success and idle-low refusal;
the read is not repeated. Future supervision uses no-block plus explicit result
polling and pre-return capture; that revision is not hardware-retested. Original
failed logs and the controller as used remain separate.

Fresh normal r4/UPower r4 returns with taint 0, native framebuffer, active services,
all four display controls auto, no diagnostic/remoteproc and matching bootloader/
GPT readbacks. This adds a real userspace-update return boot; no physical UI
retest, chip ID, raw sample, DMP or suspend-wake pass is claimed. Low lines do not
identify the cause. Next, obtain a bounded stock runtime baseline with original
system/modem read-only and sensor registry/state copied to RAM, then verify
physical pin mapping and exact regulator votes before further native transfers.
See [sensor evidence](../evidence/2026-10-30-sensor-ownership-and-id.json).

## October 30: first native WCNSS start and two shared fixes

The recovered WCNSS series now sits on the exact r4 source as
`integration/fx0-wireless-r4`, with original authors retained. Stock board data
resolves the earlier L24 question: L24 is limited to 1.30–1.35 V and L16 to
3.0–3.35 V. The mainline WCN3660 Iris profile thus gives the stock 1.3 V
RFA/digital and 3.0 V PA points. WCN3660A would request 3.3 V PA and is not used.
TLMM40–44 use the stock active 5-wire setting. The installed
msm-firmware-loader already exposes the original partitions' `wcnss.mdt` and the
calibrated persist NV, so nothing is packaged or published. The new DTB passes
dtschema 2026.9 without diagnostics.

A RAM boot of the installed r4 kernel/initramfs/command line with only that DTB
starts Pronto. It reports `WCN v2.0 RadioPhy vIris_TSMC_3.0 with 48MHz XO` and
CRM `CNSS-PR-1-4-1-c3-00062`, matching the retained stock log. `wlan0` scans 20
BSSes on 2.4 GHz channels 1–11 and 5 GHz channels 36/44. `hci0` is a Qualcomm
HCI v6 controller and discovers nearby devices. Taint stays 0.

Pronto's only regulator supplier is a dummy `vddcx`. The 6.18.59 backport of
mainline `3dbc90b9c22e` routes Pronto v1/v2 tables into its v3 branch, so MX/PX
are never requested. A source-extracting host model fails six of ten unfixed
cases and passes all ten with the fix. A module from an exported tree, with
matching vermagic and 73 matching import CRCs, makes Pronto consume L3 `vddmx`
and L6 `vddpx` on the phone.

That restart then exposes a second defect. wcn36xx forces level-high DXE
interrupts while the MSM8226 node declares rising edge, so a re-probe fails with
an IRQ type mismatch. A separate level-high SoC fix lets the second RAM DTB
restart WCNSS with the fixed module and re-register Wi-Fi/Bluetooth with a
working dual-band scan. The PMIC readback shows L16 at 3.3 V while active; the
firmware's own RPM vote, within stock limits, explains this.

The current `02:00:…` addresses are lk2nd serial-derived. NV slot 0 holds an
LG OUI address, but no stock runtime reading confirms which address stock used.
Values stay private. The phone returns to installed r4 with build 5, taint 0,
native framebuffer, automatic display controls and the documented UI start.
Association/traffic need an owner-designated test network. Pairing, MAC source,
suspend, packaging and submission material remain. See
[wireless work](wireless-bringup.md) and
[evidence](../evidence/2026-10-30-wcnss-first-start.json).

The regulator fix is now prepared against remoteproc `for-next` 7.3-rc1
(`23d0516587f8`), where the bug is unchanged. Before writing it, the kernel's
coding-assistants, generated-content, submitting-patches, coding-style,
development-process, threat-model and stable-rules documents were read in full.
The patch has `Fixes: 3dbc90b9c22e`, `Cc: stable` and `Assisted-by`. It has no
Signed-off-by, which is for the owner to add after review. The model fails 6 of
10 cases on the base and passes 10 of 10 fixed. ARM/arm64 W=1 object builds are
clean, and `git am` reproduces the branch. The changelog states MSM8974,
MSM8916 and MSM8939 impact, and the notes say exactly what was and was not
tested. Nothing was sent. See [remoteproc draft](../submissions/remoteproc/README.md).

## October 30: installed WCNSS kernels and a cfg80211 scan-block fix

The owner approved installing the wireless kernel and supplied a test network.
The network credentials are kept only in ignored local files and the phone's
root-only NetworkManager profile. Signed r5 (recipe `4eebb215c`) went through
the established sequence: verified two-filesystem rollback checkpoint, trusted
dry run, supervised install, exact readbacks and installed boot. The packaged
DTB is byte-identical to the RAM-tested one. WCNSS runs on eMMC boot with the
fixed L3/L6 consumers and taint 0. The rootless build container needed
`python3` added; the r4 launch command had never been recorded. Two of my r5
boot checks were wrong (`apk info -v` and an on-device `zstd`) and were replaced
by `apk list -I` and APK `.ko.zst` hashes.

The first association worked: 20/20 gateway pings. Every later scan then
failed with `-EBUSY`. Tracing put the block in cfg80211: no `rdev_scan`
or `drv_hw_scan` events, and no wcn36xx activity. Mainline
`dab68a74e90b`, also in 6.18.59, stopped flushing the scan-done message
parked when an interface goes down mid-scan, if the driver still owns the
request. NetworkManager's stable cloned MAC triggers that interface cycle on
reconnection. The fix queues `scan_done_wk` when the message is parked.

A first control run was invalid: after `cfg80211` reload, wpa_supplicant fell
back to Wireless Extensions. It is kept privately, and the test now restarts
wpa_supplicant. In the valid control, the unfixed module blocks from the first
disconnect. The fixed module, and then the installed signed r6
(recipe `a725b57f8`, source `34c341b90`), pass 10/10 connect/scan/disconnect
cycles with no wpa_supplicant scan failures.

A disassembly check confirms the fix is in the packaged `cfg80211`. On r6 with
taint 0, the test associates with WPA2 on 5 GHz channel 36 at a 270 Mbit/s link.
DHCPv4/IPv6 and DNS over `wlan0` work, and 20/20 gateway pings return. Downloads
reach 48–62 Mbit/s and the upload 57 Mbit/s. 250 MB sustained transfer
completes on the fixed r5 module. 5/5 reconnects pass, radio off/on reconnects,
and no kernel errors appear. The phone stays connected with autoconnect.

The cfg80211 fix is prepared against wireless `main` 7.3-rc7. The model and
checks are W=1 x86_64/ARM builds, KUnit 57/57 on UML, `git am` and checkpatch.
It is not sent. The owner has asked that all upstream submission wait for
explicit approval; pushing to the owner's GitHub forks is fine. Forced 2.4 GHz,
Bluetooth pairing, MAC policy, suspend, hotspot and soak remain open. See
[wireless work](wireless-bringup.md) and
[evidence](../evidence/2026-10-30-wifi-r6-qualification.json).

With owner approval, the phone was paired against the host's Bluetooth adapter
and the pairing was then removed. Outgoing ACL (`l2ping`) works 10/10. The host
finds the phone by inquiry only intermittently and cannot page it at all, so
host-initiated pairing fails. Phone-initiated SSP numeric comparison bonds both
sides, with matching passkeys. After bonding, the link resets within seconds and
a 4 MiB RFCOMM transfer fails. The phone logs no kernel errors. Several attempts
failed because of my test harness: the agent never started, discovery was not
confirmed, and prompts went unanswered. They are kept privately and described
in the evidence. Both sides are restored: the phone has 0 bonds and is neither
discoverable nor pairable, and the host is back to its original 9 bonds. HCI
tracing is next. See [Bluetooth evidence](../evidence/2026-10-30-bluetooth-host-pairing.json).

With owner approval, `bluez-btmon` and `bluez-deprecated` 5.86-r2 were
installed on the phone, and paired sessions were traced. The traces correct
the first Bluetooth reading: paging works, and host-initiated pairing failed
only because my scripted agent did not answer the MITM confirmation. With WLAN
up on 2.4 GHz, pairing and 16-byte-key encryption succeed. A bonded RFCOMM
transfer then dies with link supervision timeout after about 20 KB. With the
WLAN radio off, every phone connection gets Connection Accept Timeout. With
WLAN on 5 GHz, the phone is neither found nor able to connect. Bluetooth thus
depends on WLAN holding the shared radio on 2.4 GHz: a coexistence or
antenna-sharing configuration problem, not a transport fault. Stock
`WCNSS_qcom_cfg.ini` has no BTC overrides, so the firmware defaults in
`WCNSS_cfg.dat` (extracted privately) are the comparison point for wcn36xx's
BTC table. Pairings were removed and the Wi-Fi band setting restored after
each run.

Correction: the WLAN-state explanation for the Bluetooth failures is withdrawn.
Clean-boot runs at 2.4 GHz, a host-first 5 GHz run and a WLAN-idle run fail in
the same way, with connection timeouts in both directions. A plain unpaired
phone-to-host `l2ping`, which passed 10/10 early in the session, now fails even
after a clean phone reboot. The earlier single runs, and my reading of prima's
BTC message, were wrong. Host-side state is a likely confound. Separating it
needs an independent Bluetooth peer. The experimental wcn36xx BTC module was
only loaded by a swap and is not installed.

The owner provided a Plugable Bluetooth 4.0 USB adapter (Broadcom BCM20702A0)
as an independent peer. Once the peer was discoverable, unpaired `l2ping`
passed 10/10. Phone-initiated pairing then bonded on the first attempt, after I
fixed the harness to confirm both sides on every attempt. Three bonded RFCOMM
connections each delivered 4 MiB with matching SHA-256 at about 1.2 Mbit/s,
with WLAN on 5 GHz. The earlier failures came from peer acceptance policy and
my pairing harness, not from the phone. The pairing was removed; the phone has
0 bonds and the owner's existing peer pairings are untouched. HID/audio
profiles, address source and resume remain.

With the WLAN radio off, pairing to the independent peer still bonds and two of
three 4 MiB RFCOMM transfers pass; the third connection was reset by the peer.
Bluetooth does not require WLAN, despite the Iris rails reading off in that
state.

The Wi-Fi hotspot starts and beacons on installed r6 (WPA2-CCMP, 2.4 GHz ch6,
seen by the host). This works only with `wifi-sec.pmf disable`: wcn36xx
advertises no BIP cipher, so NetworkManager's default hotspot fails with
`key setting validation failed`. Client association needs a second Wi-Fi
client. `iw` was installed on the phone for this.

While an 8-hour Wi-Fi soak runs on the phone, a host-only partition reference
audit covers section 2.1 step 5. The stock SBL1 contains the unique type GUIDs
of SDI, DDR, aboot, RPM, TZ, modemst1/2, fsg and fsc. aboot and TZ name the
backup boot chain and most LG entries. Stock init mounts persist, drm, sns and
mpt. Keeping all 34 leading entries at original offsets is justified entry by
entry; only system, cache, userdata, sdcard and grow are reclaimed. This does
not replace the stock-restoration rehearsal. See
[partition audit](partition-audit.md).

Audio gap assessment (source-only): the Fx0 uses a WCD9302 Tapan codec over an
MSM8226 SLIMbus NGD with ADSP Q6 routing. Mainline has MSM8226 ADSP
remoteproc support and generic QDSP6 drivers. It has no Tapan codec driver and
no MSM8226 machine driver, and its NGD controller matches only v1.5.0/v2.1.0.
Audio is a substantial new-driver workstream. ADSP enablement and protocol
checks come first. See [audio assessment](audio-bringup.md).

Section 2.1 migration tooling (host only): `scripts/fx0_storage_migrate.py` plans,
verifies and, behind strict guards, applies the single-root GPT. Its 8
synthetic-GPT tests pass. The real target generated from the original GPT
passes `sgdisk -v` with the known table-size and alignment cautions. Nothing was
written to the phone; the restoration rehearsal remains the prerequisite.

GPU assessment (source-only): mainline describes the MSM8226 Adreno 305 node,
and Nura already installs its a330 firmware. 6.18 removed the VRAM carveout
fallback, so the GPU needs its IOMMU (stock `kgsl_iommu`, msm-smmu-v1 at
0xfdb10000) described the way the display IOMMU was. The obsolete
`msm.allow_vram_carveout`/`msm.vram` command-line parameters should be removed
when packaging. ADSP enablement is committed (`6fb0c0cae80b`) and its RAM test
is prepared to run after the Wi-Fi soak. See [GPU assessment](gpu-bringup.md).

After a clean one-hour Wi-Fi soak, two RAM tests ran. With the ADSP enabled, the
stock ADSP firmware starts and exposes APR audio channels, the SLIMbus QMI
service and the Sensor Manager. A new MSM8226 GPU IOMMU description
(`integration/fx0-gpu`) then gives the first accelerated rendering on the Fx0:
A305B 3.0.5.18, freedreno FD305 with GLES 3.0, and kmscube at 60 fps locked to
vsync, with no IOMMU faults. My kmscube harness initially failed only because
kmscube exits when stdin is readable. Devfreq, the compositor, owner visual
confirmation and packaging remain. The phone is back on installed r6 with
taint 0.

Signed r7 (recipe `68600046a`, source `4598182e1708`) is installed by the
standard checkpoint, preflight, supervised-install and readback sequence. It
adds the ADSP, the MSM8226 GPU IOMMU and GPU, and devfreq: the GPU devfreq
failure was only the missing `CONFIG_PM_DEVFREQ`. Installed boot build 8 has
taint 0, the ADSP running, freedreno FD305, simple-ondemand at 19–450 MHz,
Wi-Fi and Bluetooth, and the UI active. My first verification check matched
the GPU's harmless dummy-vddcx notice and was narrowed. See
[r7 evidence](../evidence/2026-10-30-native-r7-gpu-adsp.json).

The Sxmo session now composites on Freedreno: the wrapper's `WLR_RENDERER` is
gles2, with the Pixman copy kept for rollback. Sway uses the render node and
Mesa gallium with no GPU faults, using about 11 MB more RSS. A screenshot of
the lock screen is correct. `systemctl restart tinydm` is cancelled by the
development drop-in, so use reset-failed and then start. The owner's physical
check is pending.

With the owner present: the GLES2 Sxmo session looks normal and touch/keyboard
stay responsive on the GPU renderer. With the owner's JLab Studio headphones,
Bluetooth A2DP plays correct left/right tones (confirmed by ear) once
PipeWire/WirePlumber run. The Sxmo wrapper's `SXMO_NO_AUDIO=1` had left them
stopped. AVRCP play/pause events arrive. The pairing was removed afterwards.
GPU devfreq held 450 MHz under a vsync-bound load.

The Sxmo wrapper no longer sets `SXMO_NO_AUDIO`. On systemd, Sxmo leaves
PipeWire to socket activation, and its sound monitor activates PipeWire and
WirePlumber. After a clean r7 reboot, all three audio services are active
without manual steps.

### Factory-stock restoration rehearsal

The rehearsal ran with the owner present:

1. A fresh whole-eMMC snapshot of the r7 state was taken from the RAM rescue.
   The rescue now opens a raw shell with BusyBox `tcpsvd`.
2. It confirmed that only boot, LAF and seven runtime-modified partitions
   differed from stock. Those were rewritten from the originals, and a
   `--wipe_data` boot-control request made stock recovery recreate userdata and
   cache. Firefox OS booted to its first-run wizard and the owner found
   display, touch and keys normal.
3. With the original LAF, LG download mode worked. LAF was cleared again.
4. The return went through stock fastboot, a RAM-booted lk2nd and the RAM
   rescue. The verified snapshot was written back (826 s) and its full readback
   matched. Nura r7 booted with Wi-Fi, GPU session and audio services.

Stock's own first boot changes one byte of system: the ext4 unsigned-hash flag.
`adb reboot recovery` powers the stock phone off rather than entering recovery.

The raw boot-image path booted on hardware for the first time. The installed
lk2nd wrote a 17.5 MB r7 Android image at its 512 KiB offset, and a RAM-booted
lk2nd without extlinux support booted Nura r7 from it (marker in
`/proc/cmdline`). The prefix was intact and the payload read back
byte-identical. Normal boots still use extlinux.

boot-deploy now updates the raw boot image on the phone. The offset change was
backported to 0.23.0 and built as a signed `boot-deploy-0.23.0-r1`;
`/etc/deviceinfo` enables an Android image at offset 524288. `mkinitfs` wrote it
with the lk2nd prefix and all other bytes unchanged. The image matches the
installed kernel, DTB, initramfs and extlinux command line, and the
extlinux-disabled lk2nd booted it.

The production-candidate lk2nd (no extlinux, no forced fastboot) honours
Volume Down: chain-loaded with the key held, it stayed in fastboot, and
`fastboot continue` booted the raw image. Its log confirms Fx0 detection and
the GPIO key overrides. The owner confirmed the menu responds to the key.

The production lk2nd is installed: no extlinux and no forced fastboot. The Fx0
now boots Nura unattended from the boot-deploy raw image, after a warm reboot or
a cold power-key start. Volume Down at power-on (no LG reset prompt) reaches lk2nd fastboot.
`systemctl reboot --reboot-argument=bootloader` does not; the one apparent
success was a key still held from the previous step, and LG aboot consumes the
IMEM restart reason. The positional `systemctl reboot bootloader` form fails on
systemd 261.

The owner decided to keep the original 40-entry GPT capacity for the final
layout instead of testing a 128-entry table. SBL1 parses the GPT before any code
we control, and without EDL a parse failure would be unrecoverable.

### Final storage layout

The owner asked for a normal Linux system with as much usable space as
possible. Partitions 1–34 stay at their original offsets. System, cache,
userdata, internal SD and grow are now one 14.3 GiB native ext4 root (p35), with
no boot filesystem and the original 40-entry GPT capacity. The migration ran
from the RAM rescue after a fresh verified snapshot: both GPT regions and the
3.8 GB root image (same filesystem UUID) were written and read back exactly.
Nura booted unattended in 44 s and the initramfs grew ext4 to the whole
partition. With a 1% reserve, 12.67 GB is free (1.4 GB before). Wi-Fi,
Bluetooth, remoteprocs, firmware lookup, the GPU session and audio work, and
the owner confirmed the display.

All 20 unattended warm reboots on the final layout passed: 69–72 s to SSH,
running, taint 0, no failed units, Wi-Fi and both remoteprocs up, root on
nura-root. For remote fastboot entry, a test DTB with PON reboot modes showed
that the PMIC spare register keeps the bootloader reason (0x08) across the LG
bootloader. lk2nd now has an optional reader for it, and kernel r8 adds the
modes to the Fx0 DT.

Remote fastboot entry works again. Kernel r8 records `reboot bootloader` in
the PMIC PON spare register, which the LG bootloader leaves alone, and the
installed lk2nd now reads and clears it. `systemctl reboot
--reboot-argument=bootloader` reaches lk2nd fastboot in about 29 s with no key;
plain reboots boot Nura unattended.

### First DSP audio protocol and camera capture results

The 24-hour soak was stopped after 130 clean minutes (kept as a partial
record) so the unattended RAM probes could run; it then restarted on the
installed system. On a RAM-booted r8 with the probe DTB:

- APR bound to the ADSP and q6core reported its service API versions. The
  vendor driver uses the same AFE/ADM/ASM opcodes as mainline's QDSP6 stack.
- The drafted MSM8226 CAMSS probed through the new VFE IOMMU and captured five
  CSID test-pattern frames (4,608,000 bytes, incrementing data) through ISPIF
  and VFE RDI0. Mainline CAMSS needed its Kconfig widened to accept 32-bit
  ARM IOMMU DMA.

The rear IMX179 streams on mainline. A new sensor driver reads chip ID 0x8179
once the MCLK is right. That needed a fix in mainline `mmcc-msm8974`, whose
MCLK RCGs lacked an M/N width and produced 120 MHz instead of 24 MHz. Sensor
colour bars and live RAW10 frames pass through CSIPHY0 lanes 0/2/3/4. Frames
hold data only in their first rows, which looks like VFE bandwidth.
Correction: the earlier "first capture through the VFE IOMMU" ran without the
IOMMU (r8 lacked its driver). With the IOMMU attached, captures are all zero.

The microSD slot works with a small DT addition (SDHC2, L18/L21 supplies,
card detect on GPIO37). On a RAM boot the owner's 8 GB card was detected at
50 MHz high-speed, formatted, written and verified, unmounted cleanly, and
hot-removed and reinserted with its data intact. It is not yet in the
installed kernel.

The SLIMbus question is settled. After a QMI power vote, the MSM8226 controller
reports version 0x0101. Its NGD sits at 0x1000, the mainline v1.5.0 layout,
and its message queues use BAM pipes 3 (RX) and 4 (TX). The probe ran on
the installed kernel with the owner present and did not hang.

Mainline SLIMbus runs on MSM8226. New SoC nodes give the NGD (v1.5.0
layout, pipes 3/4) and its BAM. With them, `qcom-ngd-ctrl` registered the
bus after an ADSP restart, and the Tapan codec enumerated. The new
`wcd9306` driver identified the codec once register access used the 0x800
SLIMbus offset: major 0x0103, minor 0x0001, version 0x21. The owner
deferred the 24-hour soak; it is stopped.

Correction to the camera notes: the "truncated" frames came from running
CAMSS without an IOMMU. The VFE then writes past the first page of each
scattered buffer into unrelated memory. A full-size run crashed the kernel
on test-pattern bytes, and the phone rebooted itself into the installed
system. CAMSS must run behind the VFE IOMMU.

The rear camera produced its first real image on mainline: a complete
3280x2464 RAW10 frame through the VFE IOMMU, after mapping the IOMMU's stream
IDs and programming the RDI frame geometry. Some buffers still lose 64 KiB
regions to IOMMU translation faults; a TLB invalidate after mapping did not
change that.

The motion sensors and vibrator work on mainline. BLSP1 I2C2, which the
vendor left to the ADSP, comes up once LVS1 powers the sensor I/O and bus
pull-ups; the IMU then identifies as an MPU-6515 (0x74). L19 powers an ALPS
HSCDTD008A magnetometer (0x49). LVS1 needs about 5 ms before the bus answers,
so its DT node carries a 10 ms enable delay. `inv_mpu6050` probes at boot, and
running the PM8226 vibrator at the vendor's 2.4 V shows up clearly in the
accelerometer and gyro. (A host reboot unmounted Disk B, which holds the work
trees behind /tmp/fx0-storage; nothing was lost.)

Kernel r9, then r10, are installed. r9 adds the microSD slot, the motion
sensors and the vibrator, plus the ak8974 magnetometer driver. Its kernel
and DTB were RAM-booted before installing. With the SD slot live the card
became mmcblk0 and the eMMC mmcblk1. Nothing broke, since root mounts by UUID
and boot-deploy uses partition names, but r10 pins the order with mmc
aliases. Both boot unattended with taint 0. A first torch driver for the
PM8226 flash block programs its registers as the vendor does, with no
faults. Battery current can't show the LED, because enabling the flash
module pauses USB charging; light output still needs checking.

The flash LED works as a torch. A new driver for the PM8226's
first-generation flash block lights it at up to 200 mA without the 5 V boost.
The rear camera, next to the LED, sees the scene brighten from a mean of 67
to 366 (black level 64).

Kernel r11 adds the torch to the installed system. Sxmo's flashlight toggle
already looks for `white:torch`, so it switches the LED on and off unchanged.
r11 was RAM-booted before installing and boots unattended with taint 0.

The camera's missing regions are fixed. A fault-time diagnostic compared the
IOMMU's hardware walk with the kernel's page table: both said the faulting
addresses were never mapped. On 32-bit ARM, the IOMMU DMA layer splits a
buffer into separately placed chunks of at most 64 KiB unless the device
allows longer segments, and CAMSS assumed one contiguous range. With the
maximum segment size raised, every full-size frame arrives complete.

The rear camera is in the installed kernel (r13). Packaging it exposed a
bus-clock limit: at the default 100 MHz multimedia AXI clock only 46% of
each full-size frame arrives. CAMSS now raises that clock to 266.67 MHz
while the camera runs, and full frames complete on a normal boot.

Audio reached the speaker amplifier. On a probe kernel with mainline QDSP6,
mainline SLIMbus and a new WCD9306 codec component, the "LG Fx0" sound card
plays a test tone with no errors: AFE port, SLIMbus channels, codec clocks,
RX3 interpolator and speaker amplifier all switch on. The fix that made it
work: the codec must report only its DAI's two SLIMbus channels. Whether
the speaker is audible still needs a listen.

The speaker is silent so far. In listening tests the owner heard nothing,
although the DSP streams at 48 kHz and the codec's clocks, boost and
amplifier enable are on. A fresh-stream diagnostic shows both codec SLIMbus
RX ports overflowing: data arrives and the codec's RX path never reads it,
whether clocked from the external MCLK or its internal oscillator. The
vendor port setup and the WCD9302 routing are confirmed. Next: capture the
codec registers while stock firmware plays and diff them.

The speaker plays. With the owner's approval, the stock system was booted
once from the verified snapshots, and its codec state was captured while it
played a ringtone. Nura was then restored byte for byte. The capture gave
the missing speaker-driver defaults, the RX bias and the stock gain. A mono
experiment then found the real blocker: in a two-port SLIMbus group the codec
stalls unless every port is read. Feeding both stereo channels into the
speaker mixer fixed it. The owner heard clean tones.

Speaker audio works on the installed system. Kernel r14 carries QDSP6,
SLIMbus, the WCD9306 codec and the sound card. A new UCM profile makes the
speaker PipeWire's default sink, and the owner hears clean playback through
PipeWire. At WirePlumber's default 40% the speaker is too quiet with the
stock codec gain, so the volume range still needs tuning.

Twenty cold boots passed on kernel r14, each from a full power-off with no
warm-reset reason: running system, taint 0, no failed units, both remote
processors and the sound card up. Power-on to SSH took 67–75 s. With USB
attached the PMIC powers the phone back on by itself (charger-insertion
reason). The owner's power-key boot without USB and without a microSD also
passed, so the card is optional for boot.

The display startup fault is fixed, and the initramfs display hold and the UI
gate are gone. lk2nd's running display depended on the MDSS power domain and
bus clocks, which no Linux driver claimed. The built-in MDP IOMMU suspended,
the domain switched off, and msm's first DSI register read aborted. A board DT
framebuffer node, which lk2nd fills in, now lets simpledrm hold the domain and
clocks until msm takes over (kernel r15). Hold-free RAM boots went from 2 of 2
resets to 6 of 6 clean. The installed system then started Sxmo unattended on
20 of 20 boots, and the owner confirmed the screen and touch.

The Fx0 now runs its own device package. `device-lg-madai` replaced the
generic `device-qcom-msm8226` in one apk transaction. It carries the
deviceinfo for the raw boot image after lk2nd, the kernel cmdline (including
the lk2nd framebuffer handoff the display fix depends on), the initramfs
display and touch modules, and the speaker UCM. The hand-placed deviceinfo,
cmdline and module overrides are gone, along with the display debug
cmdline. Ten unattended boots (5 warm, 5 power-off) passed.

System suspend works. The Fx0 has s2idle only, and the first attempts all
failed in the touchscreen. The Synaptics controller is part of the in-cell
panel: once msm switches the display off at the start of suspend, every I2C
transfer to it stalls for 15 s. The RMI driver then left it powered off and
in reset after the aborted suspend. The touchscreen now follows the panel
through the DRM panel-follower API (as i2c-hid does), so it sleeps before
the panel goes dark and wakes after it comes back. The second suspend then
failed in msm's PM prepare: drm_atomic_helper_resume() restores plane
states that still name hardware pipes the MDP5 global state no longer
records. The plane check now reassigns such pipes. With kernel r19, 20 of 20
suspend/resume cycles pass, and the owner confirmed display and touch after
resume. Still open: power-key wake, the Sxmo lock and screen-off states, an
intermittent sway screen-on failure, and CPU idle states for real power
savings.

The main microphone works (kernel r21) and became the speaker's objective
detector. The speaker does play: a 1 kHz tone reaches the mic at -52 dBFS
on every play, tracks the codec gain, disappears with the speaker DAC off,
and drops 20 dB when the grille is covered. But it is roughly 30 dB too
quiet to hear. Along the way: the MSM8226 ADSP refuses 16-bit SLIMbus
ports, which made PipeWire drop the card (back ends now pinned to 24-bit),
and the codec's RX port sample format was never programmed (now set per
stream). The stock line-out 2 path was added from the stock DAPM state but
adds nothing acoustically. The speaker level problem remains open.

The rear camera's exposure and preview path moved forward. libcamera now has
an IMX179 sensor helper (fx0-pmaports `temp/libcamera` r1), the driver reports
crop rectangles, and the DT marks the camera as rear-facing (kernel r26). A new
2×2 binned 1640×1232 mode (kernel r27) runs at 30 fps and keeps the RGGB
mosaic, despite a third-party driver comment claiming the opposite. On the
binned preview, auto-exposure settles in about 4 s instead of about 50 s
([camera notes](camera-bringup.md#exposure-and-preview-mode-2026-11-01)).
Real-scene colour and orientation need the owner.

The sway screen-on failure is solved. On re-enable, wlroots re-applies the
gamma LUT by adding a "reset gamma" to the commit. Its test drops the unchanged
field, but the real device commit keeps it, and on MDP5, which has no gamma
table, the legacy gamma fallback fails without a log message. Treating that
reset as a no-op fixes it: 5 of 5 power-on cycles instead of 0 of 5
([evidence](../evidence/2026-11-01-sway-power-on-gamma.json),
[wlroots draft](../submissions/wlroots/README.md)). The patched wlroots0.20
r1 is installed.

The front camera works. A new IMX132 driver (kernel r28) identifies the sensor,
streams one CSI-2 lane at the predicted 14.37 fps, and its colour-bar test
pattern decodes correctly. With a libcamera IMX132 helper it gives a real,
colour-balanced image ([evidence](../evidence/2026-11-01-front-camera-imx132.json)).
Both cameras now list in libcamera. Orientation checks need the owner.

Correction to the speaker investigation: the microphone capture used for the
"30 dB too quiet" readings was mis-packed. The codec's SLIMbus TX ports stayed
in 16-bit format while the stream ran at 24 bits, so only 8 bits of each
sample arrived. Kernel r29 sets the TX port format like the RX one. With it,
the speaker's 1 kHz tone reaches the mic at about -4.5 dBFS and tracks the
digital volume, so the amplifier path can be loud. Capture is still not
clean, and playback dropped out after a few play/record cycles, so the
speaker level needs a listening check by the owner
([evidence](../evidence/2026-11-01-mic-tx-port-format.json)).

## November 2

A second stock session compared the whole audio state while stock Firefox OS
plays loudly with Nura r29, where only one of three tones is heard and faint.
The TLMM and PMIC pins agree. Stock runs the codec buck supply S4 at 2.075 V
and the buck helper L25 on, in high-power mode; matching both on Nura changed
nothing. In the codec, stock feeds the speaker interpolator from SLIMbus RX1
alone, and its RX ports carry 16-bit samples. Mainline's DSP port start
rejects 16-bit, which is now the main lead
([evidence](../evidence/2026-11-02-stock-speaker-comparison.json)). The return
to Nura restored the snapshot byte for byte. On stock, a warm reboot from the
rescue hung on the au logo until the battery was pulled.

With the owner, both cameras' image rotation (270, no mirroring) and the
magnetometer's mounting matrix were measured and are in the DT since kernel
r30 ([evidence](../evidence/2026-11-02-camera-rotation-and-compass.json)).

The speaker problem is now located in SLIMbus stream setup. With the
microphone as a clean 16-bit detector, each playback stream either delivers
audio for its whole length or nothing, and most starts deliver nothing. Two
fixes so far: the NGD controller now removes a stream's channels at the
ADSP when the stream stops, so a stream at a new sample width no longer
fails; and a stock-like mono stream into RX1 alone reaches the speaker for
the first time. Reliable channel activation is the next step
([evidence](../evidence/2026-11-02-speaker-slimbus-delivery.json)).

CPU idle: with the owner restarting the phone when needed, a test DTB that
registers the standalone power collapse state but never selects it boots fine,
so the TrustZone warm-boot call at driver load works. Allowing the state on one
secondary core (CPU3) hangs the phone, so entering power collapse is the
problem. The power-collapse sequence matches stock; stock additionally sets
bit 3 of the SAW2 SPM_CTL register, the next thing to try
([evidence](../evidence/2026-11-02-cpuidle-spc.json)).

CPU idle works. The hang was a missing broadcast timer: MSM8226's Cortex-A7
cores lose their architected timer in standalone power collapse, so the idle
state must be marked local-timer-stop and the always-on memory-mapped timer
takes over. The owner spotted the decisive "possible timer handling issue on
cpu=3" message on the console. With the fix, all four cores spend about 90% of
idle time power-collapsed, suspend still works, and the UI is normal (kernel
r44, [evidence](../evidence/2026-11-02-cpuidle-spc.json)).

## November 6

A host-validated SLIMbus NGD candidate now returns `-EIO` when the DSP manager
rejects a command instead of treating every generic acknowledgement as success.
It covers port connection/disconnection and channel activation/removal/reconfiguration,
leaves address replies alone, clears stale status before each synchronous command,
and preserves response-handler runtime-PM ownership. The ARM driver object compiles,
checkpatch has no findings, and an extracted-C helper harness passes 1,792 cases.
See [evidence](../evidence/2026-11-06-ngd-ack-status.json) and the
[reviewable diff](../patches/linux-integration/fx0-ngd-ack-status.diff).
The local Linux branch is `development/fx0-ngd-ack-status`, based on the r44
cpuidle integration branch. It has not been installed.

This closes an error-reporting gap, not the intermittent speaker problem: the
r45 measurements already found accepted ACKs for both audible and silent plays.
Next audio work remains the AFE-to-SLIMbus attachment sequence. Physical tests
currently cannot run: USB metadata shows `18d1:d001`, but fastboot lists no
accessible device and the USB HTTP service refuses connections. The built-in
host Wi-Fi interface `wlo1` was identified and left untouched; both USB Wi-Fi
adapters are present. Restore phone communication before RAM-boot qualification
or hotspot client tests. No phone writes or network configuration changes were made.

### Stream error propagation and phone access correction

The stream core and WCD9306 trigger also discarded errors, so manager rejection
could still look like successful playback to ALSA. The candidate now rolls back
partially connected ports, frees failed preparation state, propagates controller
disable and port-disconnection errors, and returns preparation/activation errors
from the codec trigger. Start failure attempts teardown; stop attempts every
disconnect and preserves the first failure. Both affected ARM objects compile,
checkpatch remains clean, and all 25 host tests pass, including fault injection
against the actual C function bodies. See [evidence](../evidence/2026-11-06-slimbus-stream-errors.json),
[patch](../patches/linux-integration/fx0-slimbus-stream-errors.diff), and
[tests](../tests/test_slimbus_error_paths.py). These are uninstalled candidates,
and do not yet resolve the accepted-but-silent playback problem.

Correction: `18d1:d001` is labelled fastboot by the host USB ID database, but
full interface descriptors show the running Linux CDC NCM gadget, not fastboot.
SSH is reachable on the direct USB link; the available host keys are rejected
for root and tim. The owner says the prior setup was on another machine and
authorizes wiping/reinstallation if needed. A dedicated local development key
and a public-key setup script were prepared under ignored `local/ssh-access/`;
the private key is never served. The script is served only on USB address
172.16.42.2, port 8765, pending execution in the phone terminal. No phone writes
or built-in Wi-Fi configuration changes have been made.

### Candidate cleanup ownership and full device build

Review found that returning a negative manager ACK would make the existing
callers release an already completed transaction ID again. Synchronous NGD
pre-response error cleanup now lives in the helper; response-side release
remains owned by the receive callback. An extracted-C regression covers every
ACK value plus missing status, power-up failure, send failure, timeout and
address replies with mocked TID/PM counters. All 26 existing host tests pass.
The ARM controller object rebuild passes. Concurrent receive/timeout races
are not covered by this harness.

A full kernel/DTB/module build is running at `/tmp/fx0-r44-candidate` using
the pmaports device configuration, GCC 15.2.1 and local version
`-fx0-ngd-candidate`; the log is `/tmp/fx0-candidate-build.log`. It is not
yet a completed or installed build. The Fx0 DTB has compiled.

A portable PCM16 tone analyzer and three synthetic tests were added to
recreate the unavailable private audio detector on this machine. See the
[audio notes](audio-bringup.md#repeated-playback-measurement-on-the-new-host-2026-11-06).
The public-key setup server is still running on the USB network, with no
request received at the last poll. Phone login/key setup is still needed
before live hardware experiments.

### USB Wi-Fi test peers

Read-only `iw` inspection confirms that the RTL8188CUS USB adapter
(`wlp0s20f0u4`, phy0) supports managed/AP modes on 2.4 GHz, and the second
Realtek adapter (`wlp0s20f0u2i2`, phy2) supports managed/AP modes on both
2.4 and 5 GHz. Neither advertises concurrent hardware interface combinations,
so use the separate adapters for simultaneous AP and client roles. This is
capability evidence only, not an association or phone Wi-Fi pass. No network
configuration changed; built-in `wlo1` remains untouched. See
[peer inventory](../evidence/2026-11-06-usb-wifi-peers.json).

### Clang/CFI object coverage

The full GCC build resolves the device configuration without CFI because GCC
does not implement the configured Clang protection. Treat that build as
supplementary coverage, not an equivalent replacement for the configured
Clang/CFI kernel. A separate Clang 21.1.8/LLD 18.1.8 build of all three changed
ARM driver objects succeeds with `CONFIG_CFI=y` and integer normalization
retained. The input pmaports configuration records Alpine Clang 22.1.3, so this
is not an exact distro toolchain reproduction. See [object hashes and command](../evidence/2026-11-06-audio-clang-cfi-build.json).

The USB network interface is in the existing FedoraWorkstation firewall zone,
which permits TCP ports 1025–65535, including the public-key setup server on
8765. This read-only check required no firewall changes. The full GCC kernel
build is still active at the time of this entry; SSH authorization is still
pending the phone terminal step.

### Full GCC candidate completed; access gate

The full GCC kernel, Fx0 DTB and modules build completed successfully.
Module installation/signing/compression and depmod also succeeded. All 464
staged modules report the same candidate release. The 15,095,533-byte archive
under ignored `artifacts/2026-11-06-ngd-gcc/` contains the raw kernel, Fx0 DTB,
matching modules, resolved config and exact source diff; archive readback
verifies the kernel/DTB/config/source hashes and module count. Build logs have
no compiler warnings or errors. It is not a complete boot image/rootfs and
has not been installed. GCC lacks the configured CFI protection; retain the
separate Clang/CFI object check and that limitation. See
[build manifest](../evidence/2026-11-06-ngd-full-build.json).

The two stream/codec fault regressions also reject the unmodified r44 baseline,
confirming they detect the original ignored-error paths.

Access remains the immediate hardware gate across repeated development turns:
the direct USB SSH server is reachable but rejects the prepared key for tim,
and the public-key setup server has received no phone request. The existing
server remains available at `http://172.16.42.2:8765/setup.sh`, bound only to
USB. Run `curl -fsS http://172.16.42.2:8765/setup.sh | sh` (or wget equivalent)
in the phone terminal and report its printed login name. If the UI cannot
provide a terminal, physical bootloader entry is needed for a recovery path.
Owner authorization permits reinstall if necessary, but no wipe, phone writes,
network-profile changes or built-in Wi-Fi changes were performed. Further
implementation and acceptance need live hardware access; do not infer any
new functional pass from the host builds.

### Fastboot access recovery

The owner made lk2nd fastboot available. `getvar product` confirmed
`lk2nd-msm8226`; `fastboot boot` accepted a 5,607,424-byte RAM-only diagnostic
image using the new GCC candidate and Alpine's static ARMv7 BusyBox. USB ACM
provided a root shell. The root filesystem was identified live as ext4
`pmOS_root` on eMMC partition 35 and first mounted read-only with journal
replay disabled. The installed OS is postmarketOS v26.06 and its normal
account is `user` (UID/GID 10000), not tim.

After inspection, the root filesystem was mounted writable. The previous
user authorized-key file was backed up in place, the dedicated host public
key was appended, and a root authorized-key file was created under the
existing SSH policy. Its SHA-256 matched the host public-key file. The
filesystem was synced/unmounted before reboot. Root key-based SSH now works
on the installed kernel `6.18.59`, taint 0. There are no failed systemd units;
Sway, PipeWire and WirePlumber are running and the sound card exposes two
playback/capture front ends. This is an access and boot check, not an audio
functional pass. The temporary public-key HTTP server was stopped.

No partition was flashed, wiped or resized, no OS reinstall was needed, and
the host's built-in Wi-Fi remained untouched. See
[recovery evidence](../evidence/2026-11-06-fastboot-access-recovery.json).

### Goal resumed; audio excluded; hotspot startup fixed

The owner resumed development and directed that audio testing be skipped
until notified. This restriction remains in force; this work changed/tested
only Wi-Fi and temporary test networking.

On the installed r44 kernel, the phone's default-PMF hotspot still failed
with key-setting validation and AP-initialization errors. A wcn36xx-specific
NetworkManager connection default (`wifi-sec.pmf=1`) fixes activation while
the profile itself remains `pmf=0` (default). The config was deployed to its
intended package path and reloaded without restarting NetworkManager. The
local pmaports branch `development/fx0-hotspot` contains the device-package
r2 candidate and SHA-512 entry. Native APK build/install is still pending.

The first USB adapter was an independent WPA2 client on 2.4 GHz channel 6.
It received DHCP and passed 10/10 baseline pings, a 16 MiB direct transfer,
and a 16 MiB Wi-Fi-to-USB forwarded transfer. Five reconnect cycles using
the default-PMF profile each passed 3/3 pings and a SHA-256-verified 16 MiB
forwarded transfer. Because both test interfaces are on this host, a narrow
phone-side DNAT fixture forced the request through Wi-Fi and then USB; the
server observed the phone's USB source address after NetworkManager NAT.
This is not an Internet-backhaul test. External DNS queries timed out with
no usable upstream resolver; suspend, power and long soak remain open.

Temporary phone/client profiles, HTTP servers and firewall/DNAT test rules
were removed. Phone forwarding was restored to its original zero value,
and both host USB adapters returned to idle. The phone's WLAN returned to
disconnected. Host default route and resolver-file contents matched their
pre-test snapshots after each reconnect and after cleanup. The built-in
host Wi-Fi was not changed. See [evidence](../evidence/2026-11-06-hotspot-default-and-client.json).

### Hotspot fix packaged and installed

The host's registered QEMU binfmt and rootless Podman provided an Alpine
ARMv7 build environment. `devicepkg-dev-0.22.2-r0` was built first from the
checked-out pmaports source, then the unchanged candidate recipe produced
`device-lg-madai-1-r2.apk` with abuild 3.16.0. Both builds completed; the helper
emitted existing metadata/rmdir warnings. Dependency resolution was skipped
in the container after installing the helper; the phone's offline apk
simulation independently confirmed a one-package r1-to-r2 upgrade.

The dedicated signing public key was installed, `apk verify` passed, and
normal apk installation completed. Before installation all eight package
files already matched their phone counterparts, so no existing device-file
content changed. A full 32 MiB boot-partition backup matched an independent
device hash. mkinitfs and boot-deploy triggers ran normally; readback matched
the new boot image exactly, with the 512 KiB lk2nd prefix and unused partition
tail unchanged.

The phone rebooted into the same r44 kernel with taint 0. The r2 package owns
the hotspot default, NetworkManager loads it, and the ordinary `nmcli device
wifi hotspot` command now starts an AP while its generated profile remains
at PMF default (0). The smoke-test profile was removed and forwarding restored
to zero afterward. All package files still match the built APK. No audio
behavior was tested or changed; host built-in Wi-Fi was untouched. See
[package evidence](../evidence/2026-11-06-hotspot-package-installed.json).

### MPU6515 DMP firmware and RAM transport

The manufacturer AOSP MPU6515 HAL supplies a 2,943-byte image matching the
manufacturer kernel driver's `0xa7e2110d` Linux CRC32. The new extractor pins
source/agreement/image hashes, preserves the agreement and writes only a new
private local directory. Firmware bytes are not added to the public repository.

The first physical memory trial failed image and restoration verification
because sequential debugfs register reads did not preserve memory-pointer
auto-increment. Its initial RAM snapshot existed only in the failed process,
so exact restoration to that first pre-test volatile RAM state is unproven.
The DMP never ran, no reserved or OTP addresses were written, and raw sensor
access and normal service/power state remained available. A four-byte indexed
control isolated the read-transaction issue and verified scratch restoration.

The corrected, tested diagnostic explicitly addresses every byte and saves a
private pre-write snapshot. It uploaded/read-verified all 2,943 reference-image
bytes across twelve RAM banks, then restored/read-verified the retry snapshot,
in 66.73 seconds. Service/power state and register selection were restored;
sensor proxy active/unmasked, power policy auto and taint 0 were checked.
Seven targeted tests pass, including nonincrementing transaction behavior.
No DMP execution, algorithm, userspace ABI or interrupt-wake pass is claimed.
The next step is a maintained IIO loader/lifecycle and decoded DMP data/events,
then the required real system-suspend interrupt wake. Audio remains excluded;
no audio work or host built-in Wi-Fi changes were performed. See
[evidence](../evidence/2026-11-06-mpu6515-dmp-memory.json) and
[reproducer](../diagnostics/imu-dmp-memory/README.md).


## Bounded DMP execution (2026-11-06)

The corrected `check_execution.py` diagnostic ran the pinned image for two
seconds with interrupts masked. It decoded 44 accelerometer packets and 44
six-axis quaternion packets (1,056 bytes), with a maximum observed FIFO count
of 192 bytes and no partial packet remaining. The run counter advanced to 421;
it stayed at zero before enabling and at 422 after disabling. Cleanup verified
all 3,040 writable RAM bytes and functional registers, restored power/service
state, and canonicalized the memory cursor. This is an execution/output pass,
not an accuracy, native IIO, stability or suspend-wake pass.

An earlier execution produced packets but failed its final cursor readback.
Independent controls established that reading MEM_START_ADDR advances it;
the corrected diagnostic verifies functional controls and sets the cursor
without reading it. The earlier trial remains an overall failure.

A later reboot cleared the private captures and recovery snapshots in `/tmp`
before archival. The execution result survives in diagnostic stdout only.
The prior journal ends without a shutdown explanation and pstore is empty;
the owner subsequently confirmed a manual reboot after an apparent black-screen
lockup. The lockup and any relationship to the diagnostic remain unverified.
Sensor proxy is active on the new boot.
See [execution evidence](../evidence/2026-11-06-mpu6515-dmp-execution.json).
Audio remains excluded. Native IIO firmware lifecycle, parsed channels/events,
and real DMP interrupt suspend wake remain required.


### Native DMP transport foundation (2026-11-06)

Created `worktrees/linux-dmp` on `development/fx0-dmp` from the maintained
cpuidle integration branch, independent of earlier audio modifications. Added
MPU6515-only RAM helpers with explicit bank/address selection, 16-byte bounded
no-increment transfers, bank-boundary splitting and write readback. Full-range
validation excludes reserved RAM/OTP; live DMP/FIFO rejects transfers. Caller
lock and runtime power are prerequisites. ARM W=1 compilation of the complete
IMU driver objects passed without diagnostics; new-file checkpatch and diff
whitespace checks passed. These helpers have no userspace entry point yet and
are not installed. Fault-injected and physical native transfer tests, firmware
lifecycle, native channels and DMP interrupt wake remain required. See
[build evidence](../evidence/2026-11-06-mpu6515-native-transport-build.json).


### Native DMP firmware-loader stage (2026-11-06)

The isolated DMP worktree now requests `invensense/mpu6515-dmp.bin`, validates
its manufacturer size/CRC contract before writing, verifies all uploaded RAM,
and writes/read-verifies entry point 0x0400. It requires stopped DMP/FIFO and
masked interrupts and never enables execution. Always reloading avoids a stale
RAM-valid cache after reset/power loss. Firmware bytes remain private.

The complete ARM IMU object build with W=1 passed without diagnostics, and
checkpatch reported zero issues on the new file. Eighteen targeted DMP tests
pass. A new host C harness compiles the actual transport and injects each of
1,472 transfer-operation failures, with bank-boundary, lost-cursor, corrupt-
readback, bounds, busy and wrong-device controls. This models transport only;
physical native bulk transfers and loader failure paths remain unqualified.
The initial sanitizer link failed because the host UBSan library is missing;
the passing host harness uses compiler warnings as errors without sanitizers.
The loader remains staged, with no userspace entry point or installation.
Native execution lifecycle, buffered channels, IRQ parsing and actual DMP
suspend wake remain open. No audio testing or host Wi-Fi changes were made.
See [loader evidence](../evidence/2026-11-06-mpu6515-native-loader-build.json).


### Native DMP configuration and decoding (2026-11-06)

Ported the physically exercised 25 Hz accel/six-axis quaternion configuration
into the native driver, with verified bounded RAM patches. Added a one-packet
wire decoder: signed accel XYZ and Q30 quaternion XYZ, partial-packet retry,
header flag extraction and explicit corruption failure without publishing
partial/stale output. Caller-side FIFO draining/tail retention, overflow/reset,
quaternion scalar conversion and timestamped IIO output remain to implement.
Neither helper starts execution or enables interrupts.

Nineteen targeted tests pass. The actual C configuration helper stops at each
of 184 injected operation failures; the actual decoder passes every packet
fragment length, signed extremes, header flags and unknown-header controls.
Transport's 1,472 fault controls still pass. ARM W=1 driver object compilation,
checkpatch and diff whitespace checks pass. This stage is not installed or a
physical native FIFO/ABI/wake qualification. Audio and host built-in Wi-Fi
remain untouched. See [evidence](../evidence/2026-11-06-mpu6515-native-config-decode.json).


### Native DMP buffered IIO candidate (2026-11-06)

Connected the loader/configuration/decoder to an exclusive quaternion scan on
the maintained MPU6515 device. Existing raw scans remain selectable. Added
PM-held startup, raw register snapshot/restoration with readback and retry,
DMP IRQ dispatch, FIFO overflow/count guards, partial-tail retention, batch
validation, positive-W Q30 output and IRQ-anchored 25 Hz timestamps. Ordinary
WoM/rate changes reject active DMP operation. System suspend is temporarily
rejected during DMP capture rather than invoking raw FIFO resume; required
DMP event retention/wake remains unfinished.

Twenty-one targeted tests pass, including actual-C model tests for 1,478 loader,
207 startup and 25 stop failures, missing/bad firmware, partial FIFO packets,
quaternion reconstruction, invalid-batch rejection and overflow. Loader test
uses the private extracted image; no firmware bytes are published. Object
compilation and style checks passed. A full kernel/DTB/module build is running;
no complete build or hardware qualification is claimed yet. The phone still
runs 6.18.59 with sensor proxy active and taint zero. No installation occurred.
See [candidate evidence](../evidence/2026-11-06-mpu6515-native-iio-candidate.json)
and [provisional ABI and reader](../diagnostics/imu-dmp-native/README.md).
Audio remains excluded and host built-in Wi-Fi untouched.


Native reader restoration now clears the exclusive quaternion scan before
restoring a saved raw mask; kernel IIO checks each enabled bit against available
scan masks, so restoring raw bits first would fail. Two modeled reader tests
bring the targeted total to 23 passing tests. The full candidate build remains
active, with no warnings/errors observed. Live boot-partition identity and
SHA256 match the preserved 32 MiB rollback image. Examined and hash-verified
mkinitfs 2.11.0 source: `-no-bootdeploy` allows off-side candidate generation;
kernel modules are selected by `/usr/share/kernel/*/kernel.release`. No boot
image or installed kernel has been changed.

The manufacturer reference includes a distinct DMP significant-motion status
(0x39 bit 0x04), separate from pedometer and raw motion. Recorded source-backed
[implementation notes](mpu6515-dmp-wake-design.md) for the required native event
and suspend-wake path. No SMD or wake qualification is claimed. Audio remains
excluded and host built-in Wi-Fi untouched.


### Complete native DMP candidate build and RAM-boot preparation

The full GCC zImage/Fx0 DTB/module build completed with zero warnings/errors.
All 464 staged modules match the candidate release and depmod -e against the
matching System.map reports no diagnostics. Preserved the complete source
[patch](../patches/linux-integration/fx0-mpu6515-dmp.diff), which applies cleanly
to the integration base (including the separate source checkout with unrelated
earlier changes). Build logs/manifests are in ignored candidate artifacts.

Staged matching modules under a separate release directory and the pinned
private firmware on the phone. The first no-bootdeploy initramfs attempt failed
its output check: mkinitfs 2.11.0 removes temporary archives without a deployment
copy step. Corrected the helper to intercept boot-deploy in a private mount
namespace with an archive-copy-only shim. The resulting 11,494,064-byte archive
passed hash and module-version inspection; installed kernel metadata stayed
unchanged. Boot-partition SHA256 still matches the preserved rollback image.

Assembled a 16,472,064-byte RAM image from the new kernel/DTB and initramfs,
preserving working Android header parameters. Unpacked payload readback matches.
Reboot-to-bootloader was accepted and USB disconnected; fastboot product query
is waiting. No candidate boot, native output or wake pass is claimed yet.
Audio remains excluded and host built-in Wi-Fi untouched.


The software reboot-to-bootloader instead enumerated Qualcomm 05c6:f006 with
HID interfaces and a single interrupt IN endpoint. Neither fastboot nor ADB
detects it. The DMP candidate has not been sent or booted. Asked the owner to
restore lk2nd fastboot using the earlier physical method; a read-only fastboot
product query remains live waiting for the private device serial. No blind USB commands
or flashing were attempted. This does not establish a cause for the unexpected
mode, and the native candidate cannot have caused it because it never ran.


### Pending-restoration recovery follow-up

While the physical native trial awaited lk2nd fastboot, identified a gap in
the prepared candidate: raw buffered capture retries failed DMP restoration,
but direct raw reads/scale/calibration accesses can bypass pending cleanup.
Created an independent `development/fx0-dmp-recovery` worktree so the prepared
RAM image/source stay unchanged. Direct operations now invoke recovery under
the existing lock/runtime-PM reference; active DMP rejects access, and pending
restoration must pass before ordinary data access or mutation. WoM threshold
updates also reject active/pending DMP state.

The actual-C model verifies active-mode rejection without bus traffic, failure
propagation, preserved pending state and verified raw scale restoration before
access. Targeted total is 24 passing tests. ARM W=1 IMU object compilation and
style/whitespace checks pass. Follow-up [patch](../patches/linux-integration/fx0-mpu6515-dmp-raw-recovery.diff)
applies cleanly over the candidate; it is not installed or included in that
prepared RAM image. See [evidence](../evidence/2026-11-06-mpu6515-pending-restore-recovery.json).
Audio remains excluded and host built-in Wi-Fi untouched.


The phone subsequently returned to normal Linux NCM USB (18d1:d001). SSH
confirms original kernel 6.18.59, boot ID d8e46abf-d8db-4a03-a3a9-991f47ab0f4c,
sensor proxy active and persistent candidate directory present. No owner text
response established the reason for this transition. The candidate still has
not run, and a physical lk2nd fastboot entry remains necessary for the RAM
trial. The read-only fastboot query is still waiting.


### Native kernel boot, crash diagnosis and corrected physical stream

Used the existing authorized offset-aware update path after software fastboot
entry proved unreliable. Saved/read-verified a fresh full boot backup, invoked
the installed boot-deploy partition writer at 524288 bytes and verified the
entire expected partition, preserved lk2nd prefix and tail. Normal reboot booted
the candidate and SSH; all changes remain reversible via the preserved original.

The first native capture caused a stack-protector panic in DMP FIFO handling.
Ramoops was preserved privately. My allocation was 24 bytes, but IIO rounds the
quaternion repeat=4 plus timestamp scan to 32 bytes and writes the timestamp at
byte 24. The earlier host sink failed to model that real alignment. Corrected
allocation/reader stride to 32, zeroed padding, used the size-checked IIO push
and corrected the model. Reloaded only the updated IMU modules.

The corrected physical trial captured 125 native DMP quaternion samples over
five seconds, with strictly increasing IRQ-anchored timestamps about 40 ms apart.
Raw acceleration worked after cleanup, buffer was disabled, sensor proxy active,
taint zero and boot ID unchanged. Capture is archived off-phone. This is bounded
execution/output proof, not accuracy, stability, recovery-soak or wake proof.
See [evidence](../evidence/2026-11-06-mpu6515-native-capture.json).

Physical metadata also exposed zero Q30 scale from IIO's nine-decimal formatter.
Added a companion core formatter fix for subnanounit power-of-two fractions,
with exact Decimal host tests and KUnit vectors. Twenty-seven targeted host
tests pass; added KUnit vectors have not been run. Targeted ARM core W=1 build
passes. A global W=1 build was intentionally cancelled because it unnecessarily
rebuilt unrelated objects and exposed preexisting security/keys warnings; final
kernel build is proceeding with normal project flags. Audio work/testing remains
excluded and host built-in Wi-Fi untouched.


### Exact-scale kernel and repeated native switching pass

The normal-flags kernel build and targeted ARM IIO-core W=1 compilation pass.
Installed the scale-fixed boot image using the same offset-aware writer with
full readback; prefix and tail remain unchanged, original rollback retained.
The corrected IMU modules load from root and are absent from the reused
initramfs. New boot 78f624e5-8b48-4821-8f64-44d6b6905f90 reports exact Q30 scale
0.000000000931322574615478515625.

The strict reader passed three raw/DMP/raw cycles, each capturing 75 samples
in three seconds with increasing timestamps. Raw acceleration worked before
and after every capture, buffer returned disabled, proxy returned active and
unmasked/static, runtime power auto, taint zero, boot ID unchanged and no DMP
reset/panic messages observed in current-boot filtered logs. Captures and
per-cycle manifests were fsynced and copied off-phone. Twenty-seven targeted
host tests pass; KUnit vectors were added but not executed.

This proves bounded native streaming and normal mode switching, not mounting/
accuracy, fault/overflow recovery, long-run stability, DMP event wake or battery
standby. Proper kernel package integration is also still required: this is a
development boot image with a separate versioned module tree. Original distro
boot assets remain for rollback. Audio work/testing stays excluded and host
built-in Wi-Fi untouched. See [evidence](../evidence/2026-11-06-mpu6515-native-stream-and-scale.json).


### Native DMP significant-motion event, awake physical pass

Added an activity/still CHANGE/FALLING IIO event with event-only firmware
configuration, independent PM vote, stale status clearing, single-shot/rearm,
exclusive raw/streaming modes and managed teardown. IRQ attribution requires
manufacturer status 0x39 bit 0x04; ordinary data-ready/FIFO and pedometer status
do not qualify. All 28 targeted host tests pass, including 280 injected SMD
startup-operation failures and PM/status/cleanup controls. ARM modules build
without diagnostics; checkpatch/diff checks pass. Updated signed IMU modules
were reloaded, preserving the working kernel and rollback images.

Physical register readback verified event-only USER_CTRL=0x80, INT_ENABLE=0x02,
FIFO_EN=0 and empty FIFO with runtime power active. A ten-second observation
saw zero IRQs/events, remained armed and disarmed cleanly; quaternion capture
afterward returned 75 samples. The owner then confirmed readiness and moved
the phone after the armed marker. Exactly one IRQ produced event code
0x05021e1300000000 (activity/still CHANGE/FALLING), automatically disarmed, and
raw reads plus a 74-sample quaternion capture worked afterward. Boot ID stayed
unchanged, proxy active, buffers/event disabled and taint zero. Files are saved
on persistent phone storage and archived off-phone.

This is an awake algorithm-event pass, not real system suspend/wake. Power/state
retention, bus-safe IRQ sequencing, retained wake status, physical masked
controls, 20 consecutive event wakes and battery standby remain required.
No audio work/testing or host built-in Wi-Fi changes. See
[evidence](../evidence/2026-11-06-mpu6515-dmp-smd-awake.json) and
[awake SMD follow-up patch](../patches/linux-integration/fx0-mpu6515-dmp-smd-awake.diff).


### DMP suspend retention, physical wake pilot and masked control

Implemented SMD-specific system-suspend/resume with IRQ synchronization outside
the driver mutex, an IRQ-thread suspended guard, retained power/RAM/clock,
checked IRQ-wake arming/unwinding, pre-entry event abort/attribution and status
read only after the parent I2C adapter resumes. Retained events are delivered
with a resume-attribution timestamp. Streaming suspend still rejects. ARM
modules build without diagnostics and style checks pass; model tests cover
IRQ depth/PM balance, aborts, wake API errors and status read errors.

RTC control: 12.39 s traced machine sleep, DMP counter advanced 3679 across
the whole 18.35 s call, zero IMU IRQ/events, RTC IRQ +1, SMD remained armed.
Positive owner-assisted pilot: 32.21 s traced s2idle, retained status 0x04,
IMU IRQ +1, RTC IRQ +0, fallback still pending with 12 s remaining. Raw reads
and 75 quaternion samples recovered. Masked-motion control: 30.01 s sleep
until RTC, no IMU IRQ/event despite requested motion, normal recovery. Owner
confirms display/touch after positive wake. MDP5 error 0x04000000 is still logged
during resume and remains a separate tracked warning.

Settings, services and alarms restored; boot ID unchanged and taint zero. All
trace/capture files are archived off-phone. See
[RTC evidence](../evidence/2026-11-06-mpu6515-dmp-suspend-rtc-control.json),
[pilot](../evidence/2026-11-06-mpu6515-dmp-wake-pilot.json) and
[masked control](../evidence/2026-11-06-mpu6515-dmp-wake-masked-control.json).

Prepared a durable consecutive-cycle runner with independent evidence checks;
it accepts the real pilot and rejects the masked control as a DMP success.
Four verifier tests reject missing sleep, wrong IRQ/RTC attribution, bad event
or hardware modes, missing retained status and malformed scans. Targeted host
total is 32 passes. Required 20-cycle run awaits operator availability; full
50-cycle, unplugged standby/false-wake/latency and packaging gates remain open.
Audio work/testing remains excluded and host built-in Wi-Fi untouched.

### 2026-11-06: repeated DMP retention across RTC suspend

Five consecutive USB-powered s2idle cycles passed with native significant-motion
detection armed and a 12-second RTC fallback. Trace intervals were 12.20–12.43 s;
every cycle had one RTC IRQ and zero IMU IRQs, retained DMP execution, no event,
and 74–75 valid quaternion samples afterward. Boot ID stayed unchanged, taint
remained zero, and proxy/wake/alarm/event state was restored. One MDP5 INTF1
underrun appeared per resume; display stability is still open. These are RTC
retention checks, not the pending 20 physical DMP wakes or a completed 50-cycle
peripheral qualification. No audio testing or host built-in Wi-Fi changes.
See [reviewed evidence](../evidence/2026-11-06-mpu6515-dmp-rtc-series.json).

The separate Clang/CFI kernel build remains active. ARMv7 APK tooling and local
payload staging/signing helpers are prepared; no new APK or phone installation
is claimed until their actual build and verification finish.

### 2026-11-06: signed DMP kernel development APK

The full host Clang/CFI build passes for zImage, DTBs and all modules without
compiler warnings. Explicit `LOCALVERSION=` fixes the Git-worktree plus suffix
so kernel release is exactly `6.18.59-fx0-dmp`. All 464 staged modules match
that release. A local binary-wrapper APK, `6.18.59-r47`, was signed using the
existing development key; `apk verify` passes and all 545 packaged file hashes
match the staged payload. This uses host Clang 21 / LLD 18; the separate
maintained source recipe has not been built using Alpine's exact toolchain.
No installation or new boot is claimed. The phone's legacy metadata and boot
regeneration still need integration after the pending motion-wake run.
See [package evidence](../evidence/2026-11-06-mpu6515-dmp-package-preparation.json).

### 2026-11-06: r47 initramfs preview without installation

The phone verifies the signed APK, and all 545 privately extracted payload
files match the staged manifest. Extended the initramfs helper to expose a
private module tree inside its mount namespace. Native mkinitfs successfully
generates an 11,945,465-byte archive for `6.18.59-fx0-dmp`; all 19 archived
module files match the APK and no legacy module release is included. Complete
before/after hashes match for the boot partition, `/boot`, installed modules,
kernel metadata and APK database; boot ID is unchanged. Boot-deploy remains
intercepted, so this proves archive generation rather than real boot-image
generation or installation. Audio and host built-in Wi-Fi remain untouched.
See [preview evidence](../evidence/2026-11-06-mpu6515-dmp-initramfs-preview.json).

### 2026-11-06: native boot-image generation preview

Installed boot-deploy generates a 17,549,312-byte Android v0 image using the
r47 kernel, appended Fx0 DTB and verified initramfs in a private `/boot` mount.
Both flash functions were replaced with explicit no-ops. The image fits after
the configured 524,288-byte lk2nd prefix; used load addresses, 2048-byte page
size and command line match the working image. The absent second payload has
a different unused address; second size is zero in both images. Kernel plus
DTB and initramfs match their verified inputs byte-for-byte, checked on the
phone and again after host download. Full live state hashes remained unchanged.
No APK installation or new-kernel boot is claimed. See [boot-image preview
evidence](../evidence/2026-11-06-mpu6515-dmp-boot-image-preview.json).

### 2026-11-06: r47 installed and booted through normal package hooks

Verified a full pre-install rollback on phone and host (working 32 MiB boot
partition, signed cached r44 APK, `/boot`, metadata and all four module trees).
Installed signed r47 using normal APK hooks. All 545 payload files matched,
and the boot image exactly matched the preview. Full partition readback
verified both lk2nd prefix and trailing bytes unchanged. Normal reboot now
runs `6.18.59-fx0-dmp` with matching installed release metadata and CFI enabled.

Post-boot raw acceleration/angular-rate reads, exact Q30 scale, three native
captures of 75 quaternion samples each, awake SMD arming, and a real 12.17 s
RTC suspend pass. RTC IRQ +1, IMU IRQ +0, retained status zero/no event, and
DMP counter delta 3639 were observed. Boot ID stayed unchanged through these
checks; taint zero, sensor proxy active and event/buffer/wake/alarm state clean.
The MDP5 underrun persists. Owner UI confirmation and 20 physical DMP wakes
remain pending on this new build. Earlier GCC pilots remain image-specific.
No audio tests or host built-in Wi-Fi changes. See [installed evidence](../evidence/2026-11-06-mpu6515-dmp-r47-installed.json).

### 2026-11-06: locate the display underrun during resume

Read-only r47 snapshot: 720×1280 at 60 Hz, pixel clock 70.17 MHz, MDP core
200 MHz, AXI 100 MHz, DRM active and display power controls auto. There are
no interconnect provider nodes and MDP5 logs missing interconnect support.
A private, filtered function trace across one RTC suspend has no overruns
or dropped events. Its sole underrun occurs in the first post-resume MDP5
IRQ, with the first vblank callback, 117 µs after encoder enable and 90 µs
after encoder-state setup. This narrows investigation to startup/prefill
ordering, without proving causality or excluding bandwidth. No clocks, votes
or display sequencing changed. The private trace instance was removed and
the sensor wrapper completed cleanup. See [trace evidence](../evidence/2026-11-06-mdp5-r47-resume-trace.json).

### 2026-11-06: experimental MDP5 flush-before-enable module

The pinned vendor driver flushes CTL state in mdss_mdp_display_commit before
calling the video kickoff, which enables the timing engine. Mainline enables
the engine before its encoder flush. Prepared a separate source worktree
(`linux-mdp5-prefill`) that flushes staged state before enabling video timing.
The unchanged r47 DMP source worktree and running phone are preserved.

The experimental MSM module compiles with r47's Clang/CFI configuration without
warnings. All 631 imported symbol CRCs, vermagic and signature key match r47;
the module has no exported symbols. Signed/compressed candidate and standalone
patch are retained. This is a build result, not an installed or demonstrated
underrun fix. Generic MDP5 video-mode regression review remains required.
See [candidate build evidence](../evidence/2026-11-06-mdp5-prefill-build.json).
Audio testing and host built-in Wi-Fi remain untouched.

### 2026-11-06: r49 display startup ordering trial

Packaged the single MSM module change as r48 and verified normal update hooks,
new module presence in initramfs, all 545 payload files and exact boot readback.
That first module used Kbuild's external-module path: it loaded with its expected
build ID and no startup underrun but tainted the kernel O (4096). It is retired
and excluded from qualification. A first in-tree single-module modpost attempt
lacked the dependency modules; building MSM with its seven dependency targets
resolved that and produced an authentic in-tree module. No marker was forged.

Signed r49 retains the r47 kernel and changes only MSM. All 631 import CRCs,
vermagic and signature key match r47. Installation verifies the module inside
the generated initramfs and preserves the lk2nd prefix/tail. Reboot loads ELF
build ID 51f26d8cb53c1ae2884aba5540f6afd667337623 with taint zero. An SSH client
disconnection did not reboot the phone: saved complete result, unchanged boot
ID and absent live test process were checked before retrieving the evidence.

Startup and three traced RTC suspends (11.86–12.40 s) show zero underruns; r47
recorded one at startup and each observed resume. Each RTC cycle has RTC IRQ
+1 and IMU IRQ +0, retained DMP state and counter rate about 200.5 Hz over the
whole suspend call. Five quaternion captures contain 74–75 valid samples.
Final state is DRM active, proxy active, taint zero, event/buffer disabled and
wake/alarm policy restored. Owner visible display/touch confirmation, physical
DMP wakes, battery/longer-load tests and shared MDP5 regression review remain
open; missing interconnect support is not fixed. No audio tests or host built-in
Wi-Fi changes. Experimental source APK recipe is in pmaports-mdp5-prefill; it
reproduces all ten changed files and passes six local checksum checks but has
not been built as an Alpine source APK. See [r49 evidence](../evidence/2026-11-06-mdp5-prefill-r49-trial.json).

### 2026-11-06: twenty consecutive r49 DMP motion wakes

The first attempt expired to its RTC fallback with no event; the owner reported
missing the armed cue. It was stopped, cleaned up and excluded. A fresh run
then passes all 20 consecutive owner-assisted DMP wakes. Every actual trace
shows real s2idle (2.64–14.24 s), one GPIO69/IRQ76 IMU interrupt, zero RTC IRQs,
retained status 0x04 and one correct IIO event. Every event auto-disarms with
RTC still pending, followed by recovered quaternion streaming (1,498 samples
total). All downloaded records independently pass the actual cycle verifier.
Boot ID stays unchanged, taint zero and no MDP5 underruns occur. Owner confirms
display and touch work normally after the run.

A matched-build disabled-SMD movement control then sleeps 29.86 seconds to
its RTC alarm, with RTC IRQ +1, IMU IRQ +0 and no IIO event; 74 quaternion
samples follow. This supports motion-wake attribution without conflating it
with raw WoM. Proxy/wake/alarm/event/buffer state is restored. This closes the
20-consecutive-DMP gate only: overall 50-cycle/peripheral, battery/overnight,
false-wake and calibrated-accuracy work remains. Audio excluded; built-in host
Wi-Fi untouched. See [positive run](../evidence/2026-11-06-mpu6515-dmp-20-consecutive-wakes.json)
and [matched control](../evidence/2026-11-06-mpu6515-dmp-r49-masked-control.json).

### 2026-11-06: r49 concurrent hotspot clients and resume gap

Both USB Wi-Fi adapters independently associate with the default-PMF r49
hotspot and get distinct DHCP addresses. Four baselines each pass two
simultaneous SHA256-verified 16 MiB transfers and 5/5 pings per client (128 MiB
total). Phone reports two authorized stations; all transfers bind their USB
interface and disable proxies. This is local IPv4 data, not Internet backhaul.

Direct kernel suspend completes real s2idle but clears AP stations while NM
continues reporting the AP active. Immediate pings fail; a fresh bounded
25-second polling run also sees no recovery on either client. An ordinary
system suspend comparison initially failed because the test asked root to
ignore its own sleep inhibitor and polkit refused. No policy was relaxed:
the fixture was changed to inhibit idle only and ordinary systemctl suspend
then worked. NM receives sleep/wake notifications and deactivates the AP;
it remains disconnected afterward with the temporary profile's autoconnect=no
setting. This does not qualify hotspot resume/recovery. The installed Sxmo
suspend script ultimately calls rtcwake -m mem; surrounding hooks and desired
AP resume policy need review before an integration/driver change is selected.

All profiles, HTTP services and narrow firewall rules are removed, forwarding
restored to zero, WLAN disconnected and USB client adapters idle. Host default
route, resolver bytes and built-in Wi-Fi UUID remain unchanged throughout and
after cleanup. Audio not exercised. See [Wi-Fi evidence](../evidence/2026-11-06-hotspot-r49-two-clients-and-suspend.json).

### 2026-11-06: explicit hotspot suspend coordinator candidate

The installed Sxmo autosuspend hook blocks hotspots by a `Hotspot` name prefix,
so renamed AP profiles can bypass the intended block. Preserve that policy in
future integration. The suspend script uses direct rtcwake, and its default
postwake hook does not restore Wi-Fi. No production Sxmo changes were installed.

Added a narrowly scoped coordinator candidate that disconnects active wcn36xx
AP profiles, refreshes wakeup_count after preparation, runs the blocking sleep
command, and restores profiles on return or handled failure/signal. Nine
transaction regression tests pass. Using the ordinary phone user and existing
doas permissions, two real RTC suspend cycles on r49 restore the same AP
without changing autoconnect=no. Both USB clients automatically recover and
pass 5/5 pings plus concurrent SHA256-verified 16 MiB transfers after each
cycle; including baseline, six transfers total 96 MiB. This qualifies only the
explicit candidate path, not production autosuspend or uninterrupted Wi-Fi.

Cleanup removes temporary profiles/services/firewall rules and restores phone
forwarding to zero. Kernel taint remains zero; host default route, resolver
and built-in Wi-Fi connection remain unchanged. Audio excluded. See
[coordinator evidence](../evidence/2026-11-06-hotspot-coordinated-suspend.json).

### 2026-11-06: Sxmo hotspot policy source fix

Retrieved Sxmo 1.18.1 at 61ade447e7c033421df8f248835d0f51daaf58c3
and created worktrees/sxmo-hotspot on development/fx0-hotspot-suspend.
The maintained patch replaces name-prefix matching with active wireless
profile mode checks, preserving AP blocking regardless of profile name and
allowing station-only connections. NetworkManager query failures keep
suspend blocked conservatively. Other blockers remain unchanged and were
not exercised. Five predicate tests and all nine coordinator tests pass;
the patch applies to the exact upstream release and shell syntax passes.
The phone's production hooks remain unmodified pending packaging and
integration; this source fix alone does not close the suspend feature gate.
See [policy evidence](../evidence/2026-11-06-sxmo-hotspot-policy.json).

### 2026-11-06: Sxmo Fx0 suspend integration source package

Added an Fx0-only Sxmo suspend branch that invokes the tested AP coordinator,
refreshes wakeup_count after network preparation, and uses the original
absolute RTC wake deadline so teardown does not shift scheduled wake time.
Other devices retain the original relative RTC path. The source Makefile
installs the coordinator executable. Four integration tests cover the deadline,
preparation failure, imminent-cron hold and other-device behavior; combined
with predicate and transaction tests, all 18 pass.

Built signed ARMv7 sxmo-utils 1.18.1-r6 and its subpackages from the verified
upstream archive using Alpine abuild offline. Initial payload inspection
caught that fetched .diff files were not automatically applied. The corrected
recipe explicitly applies both patches; the rebuilt coordinator/suspend script
and AP predicate match source exactly, hook configversion validates, and all
14 APK signatures verify. Artifacts and manifest are under
artifacts/2026-11-06-sxmo-hotspot-r6. No phone production files have changed:
rollback capture, complete payload comparison, installation and installed-path
hardware qualification remain open. Audio not tested; built-in Wi-Fi unchanged.
See [source package evidence](../evidence/2026-11-06-sxmo-hotspot-source-package.json).

### 2026-11-06: Sxmo r6 installed and bounded hotspot recovery qualified

Captured all 330 owned files from the eight installed r4 Sxmo packages, APK
database/world and cached original APKs; mirrored and verified the rollback
on the laptop. Full candidate comparison caught an unwanted patch .orig
file, corrected by disabling mismatch backups in the explicit prepare steps
and rebuilding. Final payload removes no files and adds only the coordinator.
Other changes are the two intended scripts, four rebuilt C helpers (matching
ARM ABI/shared-library requirements), and equivalent symlink spelling. Audio
file payload is unchanged; the audio dependency-only metapackages advance
revision with the matching package closure. No audio tests were performed.

An offline simulated transaction selected only the eight already-installed
Sxmo packages. Installed them as one local signed transaction and preserved
world bytes. All 331 installed payload files/links verify after accounting
for APK's normalization of equivalent symlink targets. Udev triggered
mkinitfs/boot-deploy, but the entire boot partition is still exactly r49
SHA256 e41931a266fa8d521db8e86fc991355465b055ff4159303f5700b76347143b86;
Android image readback matches and the original lk2nd prefix is intact.

The live Sway session exports lg,madai and SXMO_NO_MODEM=1, matching the test
branch. Exercising only the installed hotspot predicate confirms idle WLAN
allows suspend and a renamed active AP blocks it. Two bounded explicit calls
through installed sxmo_suspend.sh and the installed coordinator then pass
17.63/19.18 seconds of real s2idle, automatically restoring the AP and both
USB clients. Each phase passes 5/5 pings and two simultaneous SHA256-verified
16 MiB transfers: six transfers/96 MiB including baseline. Test mnc=30 bounds
the original absolute RTC deadline to 20 seconds; a fixture wakelock hook
records two expected cron-hold requests without leaving a persistent hold.
This does not exercise audio blockers or qualify the complete UI/autosuspend
loop, Internet backhaul, power behavior or longer AP soak.

Cleanup removes test profiles/services/rules and temporary hooks, restores
forwarding=0 and disconnected WLAN, clears RTC alarm, and verifies IMU event
and buffer off, IMU wake disabled, sensor proxy active, same boot and taint=0.
Host default route, resolver and built-in Wi-Fi connection stay unchanged.
See [installed Sxmo evidence](../evidence/2026-11-06-sxmo-hotspot-installed.json).

### 2026-11-06: microSD suspend test exposes card-detect wake abort

Added a bounded microSD diagnostic that refuses mounted/non-SD/non-FAT media
and failed read-only FAT checks. It uses a unique test directory and 64 MiB
random payload, fsync/cache-discard/hash checks, traced RTC suspend, remount
persistence checks, and cleanup restoring wake/alarm/mem settings. It never
formats or repairs the card. No audio or host Wi-Fi changes are involved.

Two fresh r49 attempts pass initial 64 MiB write/read hashes but rtcwake
returns a write error during freeze; neither enters machine_suspend. The
second trace captures mmc1 wake activation from GPIO37 card-detect IRQ63
just before suspend_enter. Its wakeup count increments and the freezer
aborts in 2 ms. This is a demonstrated pending wake event, not proof that
105 tasks are faulty or that the card filesystem is corrupt. GPIO37's
accumulated interrupt count is large (723618), but a separate three-second
idle, 16 MiB direct read and three-second idle control sees no new CD IRQs
and the read succeeds. Root cause remains unproven; next isolate read/write/
sync transitions and compare live pin/debounce configuration before a fix.

Both failed trials remove only their test data and leave the card unmounted.
A final read-only FAT check succeeds with unchanged original file/cluster
counts. RTC alarm clears, original s2idle/USB-wakeup-disabled settings restore
and taint remains zero. MicroSD suspend remains failed/open, with zero
qualified cycles. See [abort evidence](../evidence/2026-11-06-microsd-r49-suspend-abort.json).

### 2026-11-06: SD card-detect interrupts isolated to writeback

The new owned-file phase probe samples SD/CD IRQ counters around a 4 MiB
write, fsync, sync, cache-discarded read and idle periods. GPIO37 IRQ63
increments by 22675 in about 0.29 s during fsync, by 9 during global sync
and by 12 during deletion/unmount; read and idle phases show no increments.
The payload hash and final read-only FAT check pass. Live GPIO37 is input
low with pull-up, matching the current DT. Card remains unmounted afterward.

The generic MMC GPIO handler schedules debounced rescan but does not mask
repeated IRQs; every CD IRQ can create a five-second wake event. This explains
how writeback-associated CD activity can abort the wakeup_count-protected
freezer, but does not establish the electrical root cause. No polling fallback
or generic driver change was installed. Owner reports back-cover access
requires USB disconnection; a clean shutdown/reseat is offered and awaits
physical coordination before further card tests. Audio and host Wi-Fi unchanged.
See [phase evidence](../evidence/2026-11-06-microsd-writeback-cd-irqs.json).

### 2026-11-06: bounded CPU load and thermal recovery

While card-reseat coordination remains pending, performed an independent
non-audio CPU check without touching SD or host networking. Four CPUs are
online under one schedutil policy, limited to 300/384/600/787.2 MHz. The
source explicitly reserves higher OPPs for speed-bin support. Both CPU thermal
zones report passive 75°C and critical 110°C trips.

A new bounded helper samples 5 s baseline, 30 s pinned SHA256 load on all four
cores, and 15 s recovery, with a conservative 65°C stop and no policy writes.
All four workers pass 3063 known one-MiB hashes in total, consuming about
29.5–29.9 CPU seconds each. Reported temperature peaks at 47°C; frequency
stays at 787.2 MHz under load and reaches 300 MHz during recovery. All workers
terminate, policy remains identical, boot ID remains the same and taint is zero.
This is not a long CPU/RAM stress, calibrated temperature or throttling pass;
higher speed-bin/voltage support and performance/power qualification remain
open. SD stays unmounted and audio is not exercised. See
[bounded CPU evidence](../evidence/2026-11-06-cpu-thermal-bounded-r49.json).

### 2026-11-06: CPU speed-bin/supply integration audit

Read-only live inventory identifies MSM8926 ID 200 revision 1.1 and the
corrected-region qfprom0 NVMEM provider. No unverified fuse offsets were read.
Current CPU nodes expose only conservative OPPs without a CPU supply; the
qcom-cpufreq-nvmem and CPR match tables lack MSM8226 support. Retrieved a
Qualcomm clock-a7 revision explicitly matching MSM8226 after rejecting a
newer source as the sole reference because it no longer lists that SoC.
Its CPU supply and per-bin/version plan selection show that a higher PLL
frequency alone is insufficient for a safe OPP implementation.

Added a diagnostic uint32 speed-bin/version decoder with five passing tests
for validity, redundant selection, reserved bits and input bounds. It accesses
no hardware and makes no claim about this unit's actual fuse grade. The
implementation plan requires stock resource/voltage-corner provenance,
APC/CPR supply control, tested OPP transitions and rollback before higher
frequencies. No clocks, voltages, fuses or thermal settings changed. Audio
remains excluded; host built-in Wi-Fi untouched. See
[audit evidence](../evidence/2026-11-06-cpu-speedbin-audit.json).

### 2026-11-06: actual Madai CPU corner-plan provenance

Recovered the pinned peremen/android-kernel-lg-madai source through GitHub
and followed the Madai -> LGE MSM8926 -> MSM8926 v1 -> MSM8926 -> MSM8226
include chain. Its v1 ID list includes the live ID 200 revision 1.1. MSM8926
overrides declare raw clock efuse resource 0xfc4b80b0 and version-1 corner
plans, distinct from the MSM8226 v2/version-2 tables. No guessed translation
to the corrected QFPROM provider and no live fuse read was performed.

The vendor CPU rail is CPR-controlled PM8226 S2 via direct SPM, plus MX/L3
voting; literal corner values are not microvolts or RPM voltage requests.
Recorded five source plans in a provenance manifest and extended the host
decoder with diagnostic corner preview/conservative-plan fallback. Eight
tests pass, including version-dependent 998.4 MHz votes and out-of-plan
rejection. This prepares concrete data for supply/bin integration without
raising clocks or changing voltages. Original stock DTB comparison, fuse
mapping and MSM8926 CPR implementation remain open. Audio and built-in Wi-Fi
unchanged. See [Madai plan evidence](../evidence/2026-11-06-madai-cpu-corner-plans.json).

### 2026-11-06: compiled recovery CPU data and live fuse selection

Older original stock images are absent from this checkout. Read the current
recovery partition without modifying it, capturing hashes and its separate
174080-byte DT section privately. One valid DTB identifies Qualcomm MSM8926
Madai, board ID 150 and the ID 200/revision1.1 tuple. libfdt validation and
independent dtc decompilation pass. All five compiled CPU corner plans match
the vendor-source manifest; supply phandles resolve through CPR to direct
PM8226 S2 and the MX/L3 rail. This does not prove whole-image originality
against the unavailable original backup.

The compiled efuse resource validates raw address 0xfc4b80b0. Direct pread
returned EFAULT for MMIO; a read-only mmap accesses only its four documented
bytes and a matching reread. No protection settings changed and no guessed
corrected-provider offset was used. Raw bytes remain private. The decoded
unit has valid primary speed bin 0/PVS version1, selecting speed0-bin-v1
without fallback, with a 1.1904 GHz plan ceiling. No clocks/voltages changed:
CPR/APC/MX supply implementation and high-frequency qualification remain open.

Added a libfdt-backed CPU DTB inspector with private output directories and
resolved supply links; four malformed/embedded-data tests pass alongside
eight bin/plan tests. Final phone state retains the same boot, taint0,
schedutil and 300–787.2 MHz limits; SD remains unmounted. Audio and built-in
host Wi-Fi untouched. See
[compiled CPU/fuse evidence](../evidence/2026-11-06-cpu-recovery-dtb-and-bin.json).

### 2026-11-06: native read-only CPU/CPR raw fuse provider candidate

Inspected the pinned Madai CPR regulator source against mainline CPR. The
existing QFPROM raw path is tied to the programming-resource setup; CPU/CPR
needs raw calibration without that interface or a global corrected/raw switch.
Created isolated linux-cpu-cpr with the r49 baseline and added a standalone
MSM8926 raw provider. It enforces one resource, root-only/read-only NVMEM and
no writer callback. The Madai DT exposes only CPU/PVS and primary/redundant
CPR cells; corrected calibration consumers and CPU frequencies stay unchanged.

ARM QFPROM object and board DTB compile. Nine actual-C-probe contracts pass
for raw permissions/resource rejection, legacy behavior and failures; seven
DT schema tests validate real compiled raw/corrected nodes, negative raw
configurations and legacy writable schema. Binding meta/example validation
and YAML lint pass. Exported binding, driver and DT patches separately pass
checkpatch with zero warnings/errors and reproduce the candidate exactly.
QFPROM is built-in: no full replacement kernel/package or boot trial exists
yet. CPR calibration/voltage/MX sequencing, OPP transitions and hardware
qualification remain open. Running r49 unchanged, audio excluded and host
built-in Wi-Fi untouched. See
[raw NVMEM candidate evidence](../evidence/2026-11-06-cpu-raw-nvmem-candidate.json).

### 2026-11-06: CPR APC/MX ordering and failure component

Compared the pinned Madai CPR source with mainline. Compiled recovery policy1
uses the APC fuse-corner ceiling for MX, and mainline has no MX coordination.
Added a private regulator-sequencing helper and routed existing CPR APC-only
requests through it. The optional MX path raises MX before APC, lowers APC
before MX, retains high MX on APC failure, and treats a failed MX reduction
as a deferred optimization after successful APC change, avoiding clock rollback
against an already lowered APC voltage. Requests below the required floor or
without initialized MX state fail before any regulator call. Bootstrap votes
cover all possible boot corners and cannot lower an existing vote.

The actual C helper passes eighteen ordering/fault/bounds contracts; ARM CPR
object compiles and checkpatch has zero errors/warnings. Four exported CPU
foundation patches reproduce all five candidate files exactly. Regulator
activation/handoff, MSM8926 PVS/quotient calibration, supply/binding/OPP and
PM integration remain open; no current compatible enables MX and no kernel
was installed. Phone clocks/voltages unchanged; audio excluded; built-in
Wi-Fi untouched. See
[CPR sequencing evidence](../evidence/2026-11-06-cpr-mx-sequencing-candidate.json).

### 2026-11-06: native legacy secure-fuse read prerequisite

Calibration review found a compiled secure conditional-floor rule: row54
bits42–47 expected7, with a 1.14 V minimum on mismatch. Captured44compiled
parameters and preserved the secure method and comparison direction. The
pinned Madai SCM header defines service8/command7; the legacy two-word request
and three-word response match current SCM legacy marshalling. Added a guarded
read API with alignment/convention/status checks and unchanged output on error.
Thirteen actual-C contracts, ARM SCM object compile and checkpatch pass.
No native secure read or CPU voltage/frequency request has occurred.

Prepared r50 source packaging with ten patches, eleven local checksum checks
and exact reproduction of eighteen candidate files; no Alpine source APK
build is claimed. A complete diagnostic host kernel build is live, retaining
disabled CPR and conservative OPPs. Current r49 boot/full module tree/package
state is backed up and the laptop copy hash-verified. Before any boot/pilot,
restrict raw reads to validated CPU/CPR windows; the conditional secure fuse
requires SCM. Packaging, native readback and complete calibration/PM integration
remain open. Audio excluded; host built-in Wi-Fi unchanged. See
[secure API evidence](../evidence/2026-11-06-cpr-secure-fuse-api-candidate.json).

### 2026-11-06: bounded native raw-fuse view before hardware pilot

Stopped the verified active diagnostic kernel build with SIGINT to apply
the required raw-read boundary correction, confirmed terminal exit 130, then
resumed incrementally. The provider now uses keepouts for every offset except
CPU/PVS row22 (8 bytes) and CPR rows138/139 (16 bytes). Protected conditional
row54 returns a redaction without MMIO; it must be read through secure SCM.

A host harness executes the actual NVMEM core keepout routine against the
actual candidate match data. All 28,577 bounded ranges pass; a full 4 KiB read
accesses 24 hardware bytes in two callbacks, with zero protected-row access.
Existing nine probe contracts and checkpatch pass. Source recipe/checksums
are synchronized:11 local files verified,10 patches reproduce18 source files.
The source-packaging export is available. The original module signing key
is unchanged. Resumed build uses version 51 for recipe r50; no full artifact,
signed package or runtime pass is claimed. Phone remains r49, audio excluded
and host built-in Wi-Fi unchanged. See
[keepout evidence](../evidence/2026-11-06-cpu-raw-keepouts.json).

### 2026-11-06: CPU calibration r50 package built, awaiting native pilot

The resumed full kernel build completed with terminal status0. Verified ARM
image/build51, the GPL secure-read export, the filtered raw provider and
unchanged 300–787.2MHz OPPs; CPR remains disabled. All464 staged modules have
matching release and in-tree metadata. OpenSSL independently verified each
detached module signature using the preserved r49 certificate. The locally
signed r50 APK passes apk verification and all545 payload file hashes match
staging. This wraps a host Clang/LLD build; the Alpine source recipe was not
built. No phone installation or new hardware qualification is claimed.

Prepared and built a separate manually loaded conditional-fuse pilot. It
reports status and selector equality only, exposes no raw row, and changes
no voltage. A failed read remains an error; successful loading alone is not
a pass. Its external-module taint requires a reboot before later zero-taint
checks. The phone stays on r49 and the SD remains unmounted pending owner
readiness for a clean shutdown/reseat requiring USB disconnection. Audio
remains excluded and host built-in Wi-Fi unchanged. See
[r50 build evidence](../evidence/2026-11-06-cpu-calibration-r50-build.json).

### 2026-11-06: r50 installed and native CPU fuse prerequisites verified

Installed the signed r50 kernel with exact545-file payload and full boot
readback checks; lk2nd prefix and unused tail are unchanged. The first new
build51 boot is untainted. Native root-only0400 raw NVMEM CPU reads match the
prior bounded MMIO capture; primary/redundant CPR rows reread consistently.
The protected row is redacted without using it as calibration data. The
separate legacy SCM pilot reports status0 and selector match1, confirming
that the mismatch-only1.14V minimum rule is inactive on this unit. Raw words
stay private and CPU voltage/frequency limits remain unchanged.

Unloaded the external diagnostic and rebooted to clear expected taint4096.
The clean r50 baseline verifies the matching loaded MSM build ID, raw IMU
reads,74 quaternion samples, awake SMD arming, and retained DMP state across
12.328135s traced s2idle. RTC IRQ delta1 and IMU delta0 establish the control
scope;75 quaternion samples recover afterward. Final taint0, no MDP5
underruns, sensor proxy active, SMD/buffer/wakeup disabled and RTC clear.
The SD remains unmounted, WLAN disconnected, CPU schedutil300–787.2MHz, and
boot readback unchanged. Full CPR calibration/control, higher OPPs and the
broad hardware acceptance gates remain open; no r49 motion-wake pass is
transferred to r50. Audio excluded, host built-in Wi-Fi unchanged. See
[native evidence](../evidence/2026-11-06-cpu-calibration-r50-native.json).

### 2026-11-06: Madai calibration decoder and APC range prerequisite

Added an unpackaged C calibration helper and45th compiled parameter: the
CPR speed-bin selector is independent of clock redundancy/validity. The
helper preserves PVS redundancy, primary-row control flags with backup CPR,
minimum/uplift rules, all32 PVS table entries, turbo ceiling expansion and
virtual quotient interpolation. Five tests pass4060 vectors plus six failed
read/selector contracts with unchanged error output; ARM compile and header
checkpatch pass. The exported patch includes header ownership and reproduces
both files; its one generic new-file ownership warning is documented.

Private r50 rows decode to PVS21/version1, speed0, valid primary copies,
quotients798/931/1188 and nominal1075/1075/1140mV initial voltages. A bounded
read-only PMIC inventory (six registers reread,12 hardware reads, no full
bank dump) proves FTS2 S2 uses fixed range1 at1150mV with taint0. Vendor
range1 is fixed after power-on and uses10mV steps. Existing mainline SAW
rejects range1 and does not return poll/read errors, so regulator support
and quantized APC/MX voting are necessary before live CPR/OPP integration.
No voltage/frequency/audio/host built-in Wi-Fi changes occurred. SD remains
unmounted pending physical reseat readiness. See
[calibration evidence](../evidence/2026-11-06-msm8926-calibration-decoder-candidate.json).

### 2026-11-06: fixed-range PM8226 S2 SAW candidate

Implemented a separate opt-in fixed-range S2 path, preserving the immutable
power-on FTS2 range, per-instance operation/map ownership and legacy range 0
behavior. The driver validates initialized Madai L2 controller ownership and
propagates real command, acknowledgement, getter and SMP errors. Rising
voltages use PWM and conservative settling. Failed AUTO restoration after a
confirmed voltage transition is reported/deferred and retried instead of
causing a clock rollback. Uncertain command outcomes still need CPR/OPP
consumer handling. No live voltage transition is claimed.

Two actual-C harnesses pass 514 hardware selector candidates and 321 valid
roundtrips,11 initialization faults,10 transaction faults and retry/legacy/
getter/SMP contracts. Eight compiled schema cases pass, as do binding
meta/examples/lint and ARM W=1 compile. Separate binding and driver patches
reproduce three files; driver checkpatch has only mutable per-instance ops
and generic file-ownership warnings. Candidate remains unpackaged.

Bounded read-only SAW inventory confirms major version 2 and PMIC arbiter with AVS
disabled, but r50 CFG and PMIC data slots are zero. The L2 SPM owner must
initialize the compiled Madai master configuration and provide its regmap
before the fixed-range provider can activate. Installed r50, CPU limits and
voltage remain unchanged, taint 0, no audio tests or host built-in Wi-Fi
changes. Full hardware goal and SD physical-reseat coordination remain open.
See [SAW evidence](../evidence/2026-11-06-pm8226-saw-fixed-range-candidate.json).

### 2026-11-07: r51 L2 owner trial failed; r50 recovery prepared

Implemented the opt-in L2 master owner and verified setup/publication ordering
with18 I/O failure points, retries and4096-address access checks. The owner
leaves voltage commands and the low-power sequencer untouched during its
initialization function. Eight schema cases and compiled Madai phandle/OPP
checks pass. Source recipe r51 verifies17 checksums and16 patches reproducing
27 files. Full build52, linked constants, all464 module signatures, all545
payload hashes, signed APK, snapshot consistency and boot readback pass.

After installation/reboot, the phone enumerated as Qualcomm9008, with no
Linux USB network or fastboot. Native boot failed; no L2/S2 or postboot
acceptance is claimed. Root cause is unknown. Quarantined r51 and requested
physical power-off/Volume Down entry to lk2nd fastboot. No EDL loader is
verified. Extracted the r50 Android boot image from the verified rollback,
matching both archived /boot and the known partition payload. All464 r50/r51
module files are identical. A prepared recovery script requires r50 RAM boot,
restores package/files from the verified snapshot and writes only the boot
payload/tail, preserving the lk2nd prefix. Recovery has not run yet. Future
first power-controller trials will use RAM boot before persistent installation.

Source review found fixed S2 still inherited generic PMIC enable/disable
callbacks. Core always-on registration can invoke enable; the vendor SAW
provider does not use that generic gate. This is a protocol mismatch, not a
proven explanation of the reset. Added an unpackaged no-gate correction and
mandatory always-on binding. Actual provider/core enable-dispatch tests,
nine binding cases and ARM W=1 compile pass. No correction was booted and no
post-failure voltage state is known. Audio remains excluded; host built-in
Wi-Fi unchanged. Full hardware goal remains open. See
[failed r51 evidence](../evidence/2026-11-07-l2-master-r51.json).

### 2026-11-07: offline voltage planner while recovery awaits physical entry

USB still enumerates Qualcomm 9008 with no fastboot device. The physical
power-cycle request remains pending; no EDL loader or further phone writes
were attempted. Verified r50 RAM boot and bounded restoration remain ready.

Added an unused C APC/MX planner that queries only provider metadata and
commits no output on failure. Exact rounded points must exist; the global
APC ceiling and MX cap cannot be exceeded. The initial MX floor includes
actual boot APC voltage, not a clock-derived guess. Six tests pass 512
nominal combinations and all 1608 metadata failure positions, plus holes,
invalid handles/bounds and representability checks. ARM W=1 compilation and
header checkpatch pass. The earlier captured unit’s nominal 1075mV point maps
to 1080mV APC and 1087.5mV MX; no voltage was applied or measured on the phone.
Fixed range 0 rejects the compiled 1280mV ceiling. There is no package or
live CPR consumer for this helper.

Reviewed the pinned RPM driver: L3’s `_ao` supply uses active-only requests,
not an inferred always-on constraint. Suspend vote lifetime remains open.
Audio and host built-in Wi-Fi remain untouched. See
[planner evidence](../evidence/2026-11-07-msm8926-voltage-plan-candidate.json).

### 2026-11-07: reconnect allowed r51 inspection and complete r50 recovery

The owner reconnected the phone; USB networking/SSH returned with r51
build 52, boot 6178455a-f4db-464f-b60f-c6da8dee27e2 and taint 0. Native
bootstrap checks pass: L2 owner bound, stock CFG/DLY/DATA, unchanged VCTL 0
and PMIC status 0, named APC provider at 1150mV/range1/PWM, conservative OPPs.
No pstore files were present. This changes the evidence from no successful
boot to one successful bootstrap after reconnection. It does not identify
the earlier failure stage or establish reliable r51 startup. Quarantine
remains, and future first controller trials will be RAM-only.

Performed the prepared r50 restoration over SSH. The first apk command
rejected unsupported --allow-downgrade before package/boot changes; inspected
installed help, simulated direct local-file downgrade, archived that failed
attempt and retried successfully. Restored and verified all archived files,
package state and world. Only boot payload/tail was written; lk2nd prefix
was untouched. Full partition readback matches 3790f14d... from the r50 backup.
Normal reboot succeeded into r50 build 51, boot f7e2e340-96eb-4265-b72d-292e36ec8bfe,
taint 0, same 1150mV APC target and 300–787.2MHz policy. L2 registers returned
to zero and the r51 owner is absent. Sensor proxy is active, raw IMU works,
SMD/buffer 0 and RTC clear; no MDP5 underruns. SD remains unmounted. Owner
display/touch confirmation is pending. No audio tests or host built-in Wi-Fi
changes occurred. Full hardware implementation/qualification remains open.
See [recovery evidence](../evidence/2026-11-07-r50-restored-after-r51.json).

### 2026-11-07 — CPR MX activation candidate

Added explicit MX bootstrap activation and blocked APC changes before a successful enable. Cached requests, enable failure/retry and idempotence pass the actual-header C harness; ARM W=1 CPR object compilation and six planner tests pass. Exported the fifteenth CPU-series patch. No package or native voltage trial; r50 remains installed. See evidence/2026-11-07-cpr-mx-activation-candidate.json. Audio excluded; host built-in Wi-Fi unchanged.

### 2026-11-07 — CPR attachment retry

Fixed premature CPU attachment publication and ignored ACC register errors. Actual callback fault injection covers ten initialization failures and successful retries; CPR regressions, ARM W=1 compilation and checkpatch pass. Exported CPU-series patch 16, uninstalled. Fx0 CPR/OPP integration remains open; no audio testing or built-in Wi-Fi changes. Evidence: evidence/2026-11-07-cpr-attach-retry-candidate.json.

### 2026-11-07 — Vendor clock-to-CPR mapping

Added the vendor fmax selection/fallback mapper connecting calibration and quantized rail metadata. All five reference tables match pinned source/hash; bin/version/boundary C tests, 13 calibration/planner regressions and ARM W=1 compilation pass. CPU patch 17 is uninstalled, with no native trial. CPR domain/OPP and suspend integration remain open. Audio excluded; built-in Wi-Fi unchanged. Evidence: evidence/2026-11-07-msm8926-corner-map-candidate.json.

### 2026-11-08 — Calibration loading and restored-r50 suspend regression

Re-established the missing storage alias and reconstructed a CPU validation
checkout from the available local Linux base plus all 17 exported CPU patches.
This is a subsystem validation tree, not a complete r50 source-image rebuild.
Outside-sandbox SSH confirms r50 build51, taint0, no failed services and the
unchanged 300–787.2MHz policy. The owner confirms normal display and touch.
ModemManager still finds no modem; only WCNSS and ADSP remote processors run.

Added CPU patch18: full-row NVMEM/secure-SCM calibration acquisition. The CPU
cell must expand from four to eight bytes to include uplift bit53. Failed reads
preserve output, all cell references are released and read buffers are freed
with `kfree_sensitive()`. Four error types at each acquisition stage, 18 bad
lengths, upper-row/redundancy/conditional cases and all earlier CPU foundation
tests pass:46 tests, zero skips. ARM W=1 loader/CPR object and DTB compilation,
full processed-schema validation and exact two-file patch reproduction pass.
Checkpatch reports only the generic new-file ownership warning. No package,
native loader execution, regulator activation or higher OPP is claimed.

Five RTC-controlled suspends with DMP armed pass on the unchanged r50 boot.
Each trace shows real s2idle for11.69–12.49s, RTC IRQ+1 and IMU IRQ+0; DMP
execution is retained and373 quaternion samples recover. No MDP5 underruns or
taint. SSH observations timed out during repeated USB disconnects; host USB
records show reconnects, and the existing unit later completed with exit0.
No test restart, recovery or power cycle was performed. Downloaded traces,
IRQ records and samples independently reverify all five cycles. Final proxy,
SMD/buffer/wakeup/RTC state is restored; SD stays unmounted. Post-test physical
display/touch confirmation, motion-wake qualification on r50, battery standby
and full hardware/reliability acceptance remain open. Audio excluded and host
built-in Wi-Fi unchanged. See [CPU acquisition](../evidence/2026-11-08-msm8926-calibration-load-candidate.json)
and [native regression](../evidence/2026-11-08-r50-rtc-regression.json).

### 2026-11-08 — MSM8926 CPR domain integration candidate

Rechecked the same restored r50 boot: build 51, taint 0 and only the existing
300/384/600/787.2MHz OPPs. No device write or new physical test ran in this
source work. Audio remains excluded and host built-in Wi-Fi is unchanged.

CPU patches 19–20 add the MSM8926 binding and connect the calibration loader,
voltage planner and fmax mapper to CPR probe/OPP construction. The path avoids
QCS404-specific fuse/ACC assumptions, validates actual clock support and OPP
references, initializes the always-on genpd as on, and activates/retains MX
before the logical APC reference. Attachment publishes only after successful
initialization and resets stale corner pointers on retry. Feedback waits for
a confirmed nominal request; errors and PM quiesce it. The builtin-only opt-in
defaults off, manual binding is suppressed, and deeper PM is rejected until
sleep-state voting exists. Debug reads now handle an unattached domain safely.

All 54 CPU foundation/domain/schema tests pass with no skips. The actual-C
tests cover calibration failures, seven OPPs, malformed/unsupported descriptions,
16 attachment failures and retries, and performance/PM ordering. ARM W=1
builds pass with the option on and off; the legacy object has no reference to
the new secure-fuse API. Binding meta/lint/example checks and exact three-file
patch reproduction pass. Driver checkpatch is clean with existing uV naming
checks ignored; binding checkpatch is clean without exclusions.

This candidate has no board consumer, CPUfreq attachment, enabled higher OPP,
package or native pass. Voltage-error handling still needs a complete caller
audit: an uncertain APC write can leave hardware changed while OPP/genpd retain
the old cached state. Feedback quiescing does not solve that clock-ordering
problem. Complete recovery/fault tests and CPUfreq bin filtering before the
first RAM-only trial, then rebuild the complete current DMP/display integration
with verified r50 rollback. Full hardware qualification remains open. See
[domain evidence](../evidence/2026-11-08-msm8926-cpr-domain-candidate.json).

### 2026-11-08 — Transactional APC/MX recovery and correlated RPM replies

Reproduced the stale-performance-state failure with actual OPP/genpd/CPR
callbacks and the old SAW provider: four changed-on-error cases permit four
unsafe clock increases in the host model. The new provider restores and
verifies the old physical selector before returning an uncertain write error;
eight patched cases produce no unsafe increase. Recovery uses PWM, acknowledged
idle state, slew/mode delays and PMIC readback, with one bounded retry. Failed
restoration stops the kernel to prevent further clock changes at an unknown
CPU voltage. No host/device kernel was stopped by the tests.

Found and fixed the corresponding MX uncertainty. A failed RPM reduction may
already have applied; force the old consumer request through actual regulator
sync/RPM callbacks before retaining the old floor. That exposed a transport
prerequisite: SMD RPM ignored response IDs and did not retire completion state.
Added per-channel IDs, pending-request locking/retirement, bounded unaligned
TLV parsing and matching acknowledgements, including fast/late/duplicate/NACK
and timeout-boundary cases. Reply matching precedes the new MX recovery patch.

With transactional recovery, CPR now restores feedback for the old confirmed
corner after a failed performance transition. It keeps an initial failed
nominal request unarmed. This avoids leaving an adapted old voltage without
feedback when genpd's cached state skips the next same-corner request.

CPU patches 21–24 export these changes. All 58 targeted tests pass without
skips, including 248 before/after-effect I/O cases, 12 recovery retry and 12
permanent-failure no-return controls, plus 111,537 protected-page packet cases.
ARM W=1 regulator/RPM/CPR object builds and all-24-patch reproduction of 23 files
pass. Checkpatch has no errors/warnings; the only suggestions are the required
atomic-context delay and existing uV field spelling. No full kernel or package
was built. These are fault-model results, not physical voltage/firmware evidence.

The phone remains on the same r50 build 51 boot with taint 0 and unchanged
300–787.2MHz limits. No device write, native fault injection, audio test or host
built-in Wi-Fi change occurred. CPUfreq attachment/bin filtering, reconstruction
of the complete current DMP/display source, RAM bootstrap/recovery qualification
and the full hardware objective remain open. See
[transaction recovery evidence](../evidence/2026-11-08-cpu-voltage-recovery-candidate.json).

### 2026-11-08 — Owner confirms restored-r50 interface

The owner answered the restored-r50 boot check: “Display and touch work.”
This closes the physical interface check for that recovery boot; it does not
by itself establish a separate post-RTC-run observation or full display/touch
acceptance. Updated the [recovery record](../evidence/2026-11-07-r50-restored-after-r51.json).

### 2026-11-08 — CPUfreq filtering and opt-in CPR board candidate

Exported CPU-series entries 25–27: one immutable supplier mask filters both CPU
and CPR tables before parsing, the explicit MSM8926 CPU OPP type selects the
calibrated driver, and ordinary boards retain their generic route. The provider
owns its clock across virtual-CPU detach/retry; a boolean records successful
shared initialization. Invalid feedback leaves only the four conservative rates
and sanitized feedback metadata. Hard acquisition/rail-plan errors still fail
or defer, rather than guessing voltages.

Pinned vendor source exposes a missing reference check: APCS+0x64 bit 0 selects
XO versus AHB. Added syscon readback before publication/configuration and on
resume, rejecting AHB/read errors without writing the selector. The separate
qualification DTB describes 14 matched CPU/domain states, four CPU attachments,
SPI15/rising, APC/S2, MX/L3 and complete raw rows. The ordinary board DTS is
unchanged by this candidate.

All 71 targeted tests pass without skips; affected ARM objects compile with the
MSM8926 option enabled/disabled, and symbol checks match. Binding meta/lint,
examples and compiled candidate schema/link checks pass. Three inherited common
DTS warnings remain. All 27 patches reproduce 31 changed files exactly. The first
/tmp reproduction scratch copy hit quota; workspace scratch succeeded. No
source or artifact was changed to bypass verification. Checkpatch has only its
reviewed generic ownership reminders with existing uV naming ignored.

Final read-only SSH shows the same r50 boot 8a837db4..., taint 0, four original
rates and no failed services. No native voltage/frequency test or installation.
Complete current-source reconstruction and RAM-only controller/recovery
qualification remain next; full hardware/reliability closure remains open.
Audio excluded and host built-in Wi-Fi unchanged. See
[candidate evidence](../evidence/2026-11-08-msm8926-cpufreq-candidate.json).

### 2026-11-08 — Reconstruct complete r50 and CPU/CPR kernel inputs

Recovered the pinned pre-DMP commit 4b800b920c7d locally. Compared with the old
CPU validation base, it restores standalone power collapse and preserves the
pre-experiment peripheral files. Added a hashed integration manifest, exact
running-r50 configuration, separate candidate fragment and a preparer that
preflights the whole series before source edits. Real Git/patch refusal/order
checks pass. r50 uses ten patches; the complete CPR profile uses 32 and matches
all 31 CPU-series source files already validated. All 41 candidate changes are
accounted for; the five differing base files retain pinned source bytes.

The r50 DTB rebuild matches installed evidence exactly: 1658cb8c.... Full Clang/
CFI builds with explicit LLD 18.1.8 link both kernels and produce 464 modules
each. Native versus host configuration differences are compiler/Rust probe
metadata; the candidate additionally has its explicit built-in CPR/CPUfreq and
separate release. Module staging/signing passes; all 928 CMS signatures verify
against the explicit certificate embedded in their kernel. Payload/signature
corruption and the other build's certificate are rejected. No private key is
published. These remain host builds, not Alpine abuild results.

Updated source-test selection and stale stream/recovery harness boundaries for
the full DMP source. All 109 combined tests pass with no skips, including the
real loader and fault cases; three image-placement checks also pass. Automatic
approval review rejected a proposed private firmware export from the phone;
that action did not execute. Instead retrieved the pinned public AOSP source
and agreement, verified both hashes and used the existing private extractor.
No device firmware export or firmware publication occurred.

A moduleless r50-source RAM baseline image is prepared with a 180-second return
timer. Its header/load addresses, exact kernel/DTB bytes, gzip/newc, GNU cpio
listing and shell syntax independently pass. No eMMC mount/flash commands. It
has not booted. Final read-only SSH still shows boot 8a837db4..., r50, taint 0,
no failed services and the original four rates. First RAM baseline/recovery,
controller/OPP/thermal/suspend/peripheral qualification, source packaging and
all broader hardware gates remain open. Audio excluded; host Wi-Fi unchanged.
See [rebuild evidence](../evidence/2026-11-08-kernel-reconstruction.json).

### Reconstructed-r50 RAM boots and inherited CPU clock (2026-11-08)

The rebuilt r50-source image passes two physical RAM boots and returns to the
unchanged installed r50 after each. Both keep four CPUs online, taint zero,
only pseudo-filesystems mounted and the original boot-partition SHA-256.
The first lacks HTTP evidence because the host attempted DHCP against a
static-only diagnostic gadget. The second uses an identified, temporary
NetworkManager USB profile, captures 22 HTTP status/dmesg pairs and continuous
serial logs, including the return message at 181.641642 kernel seconds.
The profile is removed afterward; default routes and resolver match before.
The owner reports restored-r50 display and touch working. Native sensor proxy
and Sway run, with no failed services; time synchronization still delays full
systemd startup.

An initial 40-second host action timeout interrupted the image download before
any boot command reached lk2nd. A reset limited to the identified phone's USB
device restores fastboot. Later successful image uploads take about 30 and
58 seconds; exact staged readback precedes each boot. Public helper scripts
preserve that sequence and the temporary USB addressing, with eight boot-tool
host tests. The consolidated boot wrapper itself is not hardware-tested.

The moduleless baseline has no CPUfreq policy because CPUFREQ_DT is a module.
CCF reports its inherited CPU clock as 800 MHz. A host harness of the actual
CPR corner lookup confirms the candidate rejects this unlisted frequency
before MX/APC bootstrap. The notifier's source-4/divider-3 configuration uses
the logged 600 MHz GPLL0 to give 300 MHz; its generic 400 MHz comment does
not describe this board. Vendor clock-a7 also declares a 300 MHz safe rate.
CCF ignores provider set-rate callback errors, so clock programming needs
hardware-state verification before any voltage reduction. No candidate source
fix is applied yet. A safe clock/rail handoff is now the next CPU source
gate; no candidate-controller boot, voltage transition or higher OPP request
occurred. Installed limits remain 300–787.2 MHz. Full bringup, source packaging
and hardware/reliability qualification remain open. Audio and host built-in
Wi-Fi are unchanged. Three host USB-network controls verify selected-device
matching, own-UUID removal and cleanup after activation failure. See
[RAM evidence](../evidence/2026-11-08-r50-ram-baseline.json).

### Host startup-clock handoff draft (2026-11-08)

Preserved the validated 32-patch checkpoint and created a separate startup
source/build. Three split patches add the auxiliary-clock binding, startup
handoff and qualification-DT dependency. The helper keeps boot APC unchanged,
activates the prepared MX floor, takes one APC reference, requests 300 MHz and
checks settled hardware mux registers before initial-corner lookup. Errors
retain the floor/references and do not complete attachment or arm feedback.

All 16 targeted host/binding/DTB tests pass, including 24 handoff faults and
seven attachment failures/retries. Two unsafe source mutations compile but fail
the executing harness. The CPR ARM W=1 object and both DTBs build; the ordinary
DTB is identical to the earlier CPU candidate. The 35-patch manifest reproduces
all 41 files, schema validation passes and split checkpatch is clean with uV
naming ignored. No complete kernel/module link or hardware trial is claimed.

Runtime clock-error handling and fresh PLL/mux verification before lowering
APC remain the next source gate. Keep controller trials RAM-only after full
link/module verification and staged recovery. This turn performs no device
write, clock request, audio test or host Wi-Fi change. Full bringup and wider
hardware/reliability qualification remain open. See
[startup evidence](../evidence/2026-11-08-msm8926-startup-clock-candidate.json).

### Runtime CPU-clock guard and complete build (2026-11-08)

Created a separate runtime source profile: 39 patches reproduce all 48 changed
files. CPR now owns both parent clock references and refreshes them before an
uncached CPU mux query at every APC change. An unknown or too-fast clock blocks
the voltage change. MSM8226 CPU PLL/mux programming errors stop execution before
CCF can ignore the callback error and continue reparenting. Success requires
rate/mode/lock and settled mux readback. Provider probes restrict the strict
failure/cache policy to MSM8226; legacy probe behavior is covered separately.

All 114 selected source/rail/DMP/calibration/binding/preparation tests pass
against the final source with no skips. Actual-function models cover 76 PLL,
25 mux and 28 CPR-query I/O/unstable-state controls, plus lost writes, timeouts,
stale topology/caches, ARM32 overflow and startup. Five unsafe source mutations
compile but fail at execution. Split checkpatch is clean with inherited uV
naming ignored; six ARM W=1 objects, both DTBs and the schema document pass.

The complete kernel/module build succeeds. During the first attempt, the new
wide post-divider arithmetic was found to reference ARM's unavailable compiler
division helper. The identified task build was explicitly stopped, quiescence
verified, the operation changed to do_div(), source replay repeated and the
build resumed incrementally to success. All 464 staged ARM module signatures
match the exact kernel-embedded certificate; corrupt payload/signature and
wrong-build certificate controls reject. The kernel has the same two BPF and
three weak EFI undefined symbols as the twice-booted r50 reconstruction, with
none introduced. Signing keys remain private. A host /tmp quota prevented
sandbox startup; approved local checks used workspace temporary storage without
removing other work's files.

The moduleless L2/S2 image uses the ordinary DTB and a 180-second return timer;
payload/header, gzip/newc/GNU cpio, exact BusyBox and init syntax checks pass.
It has not booted. The current native phone remains on unchanged r50, taint zero,
300–787.2 MHz, running systemd startup, Sway and sensor proxy. Read-only Python
MMIO snapshots verify the existing APCS command/PLL mode/status layout after
BusyBox devmem was found absent; no register write or package install occurred.
The next step is RAM-only staged controller bootstrap/recovery, then controlled
governor/OPP trials and actual rail/feedback/thermal/suspend qualification.
Audio and host Wi-Fi remain untouched. Full bringup remains open. See
[runtime evidence](../evidence/2026-11-08-msm8926-runtime-clock-candidate.json).

### First native L2/S2 RAM bootstrap and input-dependent USB stall (2026-11-08)

The ordinary-DTB runtime kernel passes its first moduleless RAM bootstrap and
timed return. Four CPUs are online, taint is zero, all five SPM controllers
including L2 bind, APC reports its 1.15 V programmed target, CPU0 records 344
cpu-spc uses at the snapshot, and CCF reports inherited 800 MHz. Only pseudo
filesystems are mounted; no modules/CPUfreq governor or CPR node is active.
Twenty-two successful HTTP status/dmesg pairs and serial logs capture return
at 181.611751 kernel seconds. A fresh r50 boot retains the original boot hash,
limits, zero taint, Sway and sensor proxy. The temporary USB profile is removed
and host routes/DNS match before. Time sync still delays full systemd startup;
the owner's physical display/touch check is pending.

The initial standard-fastboot download blocks for minutes. Attaching a syscall
trace interrupts its USB write with EINTR before boot; this avoidable diagnostic
interference is recorded. Phone-only USB reset restores command state. A new
data-only synchronous transfer tool passes ten host checks and exact 1,000-byte,
1 MiB and paced 6 MiB controls. The original image still fails after 5,783,552
confirmed bytes, including with pacing, request-aligned padding and exact-6-MiB
padding. Its isolated 32 KiB block fails after 16 KiB at a different staging
address. The root cause is therefore still an open input-dependent preboot USB
defect. No failed transfer here sends boot or writes phone storage.

Re-encoding the identical initramfs at gzip level 1, with exact unchanged
kernel/DTB/cmdline/unpacked contents, stages and reads back in 8.72 s and then
boots successfully. The image builder now accepts --gzip-level, preserves
default9 output and exactly reproduces the booted level1 variant. Its earlier
source is archived and the revision/reproduction checks recorded explicitly.
The combined boot/network/transfer suite passes all 21 checks. The original
image remains unbooted; encoding is a workaround, not a USB repair.

No persistent candidate installation, deliberate frequency/voltage transition,
CPR feedback, audio test or host Wi-Fi change occurred. The r51 EDL cause remains
open. Next qualify separate moduleless CPR bootstrap/MX/clock normalization,
then controlled governor/eligible OPPs, analog rails, recovery, thermal, suspend
and the remaining peripherals/reliability. See
[native evidence](../evidence/2026-11-08-l2-s2-ram-bootstrap.json).

### Settled r50 return and prepared CPR bootstrap (2026-11-08)

A later read-only check confirms that the same r50 return boot has finished
systemd startup: running, no failed services or pending jobs, one Sway process,
active sensor proxy, taint zero and the unchanged boot-partition hash. The
earlier restored-r50 display/touch confirmation remains scoped to its original
recovery record; the separate physical check after this RAM trial is pending.
All 139 recorded trial input/private and runtime input/source hashes verify;
whitespace and Python syntax checks pass.

Prepared a separate moduleless CPR-bootstrap image with the built qualification
DTB and the exact compressed initramfs and command line of the successful L2
trial. Independent Android header/digest/load-address, gzip/newc/GNU cpio and
shell checks pass; all four CPUs name the CPR domain, have no CPU-level default
required OPP, and cpufreq-dt remains an absent module. Source review confirms
that the built-in calibration driver attaches the domains before registering
the unloaded cpufreq-dt device, so this test can exercise 300 MHz clock
normalization and MX startup without a CPUfreq policy. Feedback is gated by a
later positive performance-state request. No new image is staged or booted,
and these native behaviors remain unqualified. See
[preparation evidence](../evidence/2026-11-08-cpr-bootstrap-preparation.json).

### Complete Alpine runtime source package (2026-11-08)

Added a local source-package exporter with seven passing integrity/preparation
checks, a tracked shared-SoC recipe template and the exact runtime configuration.
The exported recipe pins the complete base and all 39 ordered patches with
SHA-512 checksums. An isolated workspace pmaports clone records the source and
recipe composition in two local commits; the cached source archive stays
read-only on the recovery disk. All 48 actual abuild-prepared source files match
the frozen host candidate before and after compilation.

The initial r53 source build succeeds in 15m39s and its signed APK verifies.
Its noninteractive oldconfig retains the intended settings but emits EOF
diagnostics for newly visible compiler-dependent choices. Updated preparation
explicitly runs olddefconfig. The normalized r54 source build succeeds in 2m30s
using dependency/compiler caches after fresh source unpacking, without those
diagnostics. Alpine Clang/LLD 22.1.3 retains CFI, the existing no-LTO choice,
module CPUfreq and built-in CPR. Compiler/Rust/helper capability differences are
recorded; the actual normalized community configuration passes.

The initial abuild default cleanup removes vmlinux after packaging because
pmbootstrap's substitution misses commented cleanup assignments. The corrected
private fixture sets CLEANUP/ERROR_CLEANUP explicitly and retains the r54
outputs. Signed metadata identifies exact recipe commit
4f17b6905c75da8a35f220b1f80724d2d07e997b. The 18,475,505-byte APK, exact kernel,
both DTBs, exact embedded certificate and all 464 module signatures verify.
Corrupt payload/signature, wrong-build module certificate and modified signed
recipe metadata reject. The offline APK simulation passes in a fresh initialized
usermode workspace database; this is not a phone/root-mode update test. The
five undefined symbols match the accepted baseline. Signing keys stay private.

The package is unbooted and uninstalled. Read-only phone postflight confirms
installed r50 on the same boot ID, taint zero, running systemd, no failed units,
Sway, sensor proxy, four rates/schedutil and original boot-partition hash.
Physical display/touch after the earlier L2 trial remains a separate pending
check. No audio or host built-in Wi-Fi test/change occurred.

Automatic approval review rejects the GitHub push before execution: export of
the complete commits and destination ownership lack explicit authorization in
trusted user instructions. No publication is attempted indirectly. The exact
local branch and public recipe diff are preserved for explicit owner approval.
Native RAM/CPR/OPP/rails/thermal/suspend, installed update/recovery and the wider
bringup remain open. See
[package evidence](../evidence/2026-11-08-runtime-kernel-source-package.json).

### Reconstructed and checked runtime integration history (2026-11-08)

Built a local 39-commit integration draft through a separate Git index,
preserving the frozen source checkout, HEAD and original index. All final blobs
match the tested 48-file composition. The historical CPR binding audit finds
four invalid prefixes: 33/34 require an auxiliary clock before DT supplies it,
and 37/38 require the PLL before its DT addition. Including the generic nvmem
consumer schema first resolves a checker setup omission, so only genuine clock
count failures are attributed to the history.

Retained that draft and formed a 35-commit review branch by grouping each
binding/provider/DT clock transition atomically. Its full final tree is identical.
All exposed CPR DTB prefixes now pass their own schemas. An independent local
git-am replay produces the same final commit ID and tree; bundle verification
and unbundle pass. Expanded only the isolated replay checkout and compiled the
20 affected ARM objects at every one of the 35 prefixes with W=1: all pass with
zero compiler warnings. No full intermediate links or new hardware claims are
inferred from those object builds.

Saved the ordered mail drafts, base-aware cover letter, source-patch mapping and
tentative pinned-tree maintainer routing. Original file notices/base history are
preserved; no DCO, reviewed or tested tags are added. Current receiving-tree
rebases/splits, contributor certification and physical gates remain open.
Publication is still pending the earlier explicit approval request; no external
message or push is attempted. See
[history evidence](../evidence/2026-11-08-runtime-integration-history.json).

### First CPR RAM trial and stage diagnostics (2026-11-08)

After the source-history checks, fresh preflight finds the same running r50
boot, original hash/four rates, charging online and CPU zones at 43/44 C.
The prepared gzip-level-1 qualification image stages and reads back exactly
in 5.63 s; fresh serial/HTTP/network observers precede one acknowledged RAM
boot. Diagnostic USB is live, four CPUs online and taint zero, but CPR probe
returns -EINVAL. The provider never binds, the CPU calibration supplier defers,
CPU stays at inherited 800 MHz and APC reports 1.15 V. No CPUfreq policy loads.
The bootstrap gate fails, and no specific root cause is inferred from the
generic calibration message.

Twenty-two HTTP status/log pairs and serial capture the 180-second timer at
181.623794 kernel seconds. Both observers terminate cleanly. The phone returns
to r50 boot 82018c60-6d13-4af3-afae-8c3e4a3d9306 with running systemd, no failed
units/jobs, Sway, sensor proxy, four rates/schedutil and the original boot hash.
The owner confirms display/touch on that return. The temporary profile is gone
and host default routes/resolver match before. No flash, package installation,
higher OPP, audio test or host built-in Wi-Fi change occurs. See
[trial evidence](../evidence/2026-11-08-cpr-bootstrap-first-ram.json).

Prepared an isolated diagnostic commit, def9620bc91efe46b441ff399c60f6c4c45a1be2,
adding only initialization-stage error context and no raw calibration output.
Its 40 source patches replay independently to the exact tree. All 116 selected
checks, including the original separate attachment case and two new executable
diagnostic checks, pass without skips. Error values, output ownership and
cell/buffer cleanup remain covered; ARM cpr.o builds with W=1 and no warnings,
and checkpatch is clean with inherited naming/path notices ignored. Prior
test-fixture versions are archived before the logging/header stub adaptation
and linked explicitly to the old reconstruction record.

A separate -fx0-cpr-probe built-in RAM kernel and both DTBs are building from
the clean diagnostic source. Modules are not part of this moduleless diagnostic
build and no follow-up image has booted. The actual failing stage, correction
and repeat RAM startup gate remain next, followed by controlled governor/OPPs,
real rails/feedback, thermal/suspend, Alpine artifact and wider bringup work.
Publication still awaits the earlier explicit approval request; no rejected
push is retried or bypassed. See
[diagnostic preparation](../evidence/2026-11-08-cpr-probe-diagnostics-preparation.json).

### Reference selector isolated by the diagnostic RAM trial (2026-11-08)

The diagnostic kernel and both DTBs link successfully in 3m29s, with the same
five undefined symbols as the accepted baseline and none introduced. Both
DTBs match the tested runtime versions. The new moduleless image preserves the
known initramfs/command line and stages/reads back in 4.60 s before one boot.
Its exact stage message is -EINVAL from the CPR reference-source check.

The serial collector opens before udev settles permissions and terminates with
EACCES, before sending a snapshot command. HTTP still captures 22 status/log
pairs. After return, systemd's archived pstore supplies the diagnostic kernel
identity, failure line and timer message at 181.601496 kernel seconds. Native
boot a4972450-fe12-4a03-bb68-2a7f5b6d1055 is running with taint zero, no failed
units/jobs, Sway, sensor proxy, four rates/schedutil and the original boot hash.
The owner confirms display/touch on this newest return. Host routes/resolver
match before and the temporary profile is deleted. Missing RAM taint, CPU-clock
and regulator snapshots are not inferred from the earlier trial.

A read-only native mmap of just APCS+0x64 returns 1. The pinned stock driver
defines bit0=1 as AHB and bit0=0 as 19.2 MHz XO; its DT names the word at
0xf9011064 and its initialization explicitly selects XO. This connects the
stage failure to the missing reference setup work while retaining the guard:
implement owned/quiesced selection and verified readback before CPR use,
including relevant failure/resume paths. No selector or voltage is changed by
this investigation, and no startup/feedback/higher-OPP acceptance is claimed.
The original images, history and source package remain unchanged. See
[diagnostic trial evidence](../evidence/2026-11-08-cpr-reference-first-diagnostic.json).

Prepared a fresh future observer template for the observed udev race. It retries
only PermissionError before opening the serial node, checks physical port and
RAM VID/PID/serial each time, and stops after ten seconds. Three host controls
verify successful settling, the bound and device-change rejection before any
serial command. No device permissions or current trial records are changed;
hardware use of the corrected collector remains to verify.

### GitHub publication authorized and package branch published (2026-11-08)

The owner states: “Pushing to github is approved for all fx0 development.”
This authorizes future fx0 development pushes as well as the previously prepared
package branch. The earlier automatic rejection is historical and no longer
blocks this explicitly authorized action.

Published `integration/fx0-cpu-runtime-package` to
[timschmidt/fx0-pmaports](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-cpu-runtime-package).
The push exits zero and an independent `ls-remote` verifies commit
`4f17b6905c75da8a35f220b1f80724d2d07e997b`. The clean package checkout and
reviewed source payload are unchanged. The Alpine r54 artifact remains unbooted
and uninstalled; publication does not qualify it for deployment.

CPR source inspection confirms that the reference guard runs before controller
disable in both initialization and configuration. The next change must mask
interrupts, stop and verify the controller, select XO while preserving other
APCS bits, and retain the reference readback/error guard before use. No new
controller code or device trial is included in this publication action.

### CPR XO handoff and retained BUSY result (2026-11-08)

Published the isolated XO handoff source at `a9c68b1b25b6`, with a 41-patch
manifest and exact independent replay. The frozen diagnostic checkout remains
clean. The new source passes 118 selected checks, its ARM W=1 object and
checkpatch. A fresh full built-in kernel/both DTBs links in 7m09s; the RAM
image retains the known moduleless initramfs, command line and 180-second timer.
The audit checks this tree's CONFIG_CFI and actual KCFI type/failure symbols
and changed-object compiler flag, correcting initial checks for obsolete names.

One RAM boot reaches serial/HTTP with all four CPUs online, taint zero,
800 MHz CPU clock and APC's reported 1.15 V target. The new stopped-engine
BUSY poll returns -ETIMEDOUT after both zero IRQ/CTL readbacks and before the
APCS selector write. CPR remains unbound and no CPUfreq policy appears. The
udev-settling collector succeeds; serial captures the return at 181.597437
kernel seconds. Both observers exit zero and host routes/resolver/profile
cleanup verify. Installed r50 returns with its original boot hash, four
rates/schedutil, Sway and sensor proxy; the owner confirms display/touch.
Time synchronization is still pending in the first native snapshots, so
complete systemd startup is not claimed. See
[trial evidence](../evidence/2026-11-08-cpr-xo-handoff.json).

The primary stock driver selects XO and disables the controller without a
BUSY wait. Stock and upstream IRQ paths consult BUSY only after confirming
LOOP_EN. On this hardware BUSY remains set while CTL is clear before XO
selection, so treating that result-readiness bit as a stopped-controller idle
acknowledgement prevents initialization. A separate follow-up keeps the
original XO readback guard, checks disabled IRQ/CTL before and after selection,
and omits that invalid prerequisite. Its 42 patches replay exactly; all 118
selected checks and a separate ARM W=1 object/checkpatch pass, including
retained-BUSY and failed pre/post-handoff readbacks. The source is published at
`86a9e78ce4b6`; its separate full kernel is building. This is not CPR startup,
feedback, higher-OPP or analogue rail acceptance. See
[follow-up evidence](../evidence/2026-11-08-cpr-disabled-reference.json).

The separate follow-up kernel links in 6m13s and passes the linked-release/CFI,
source, undefined-symbol, DTB and image-layout audits. One RAM boot passes the
startup gate: CPR initializes seven OPPs, all four virtual CPU consumers attach
and the verified CPU mux reaches 300 MHz through GPLL0/2. APC's reported target
remains 1.15 V; MX has an active bootstrap vote. LOOP_EN is zero, including
while RESULT_0.BUSY remains one. The planned 1.08 V corner cache appears under
the old debugfs current_volt label; it must not be interpreted as programmed
APC voltage and needs a diagnostic correction before runtime qualification.

Four CPUs, taint zero, five SPM bindings, CPU-SPC use, no deferred probes/modules
or CPUfreq policy are captured. Serial records return at 181.782488 seconds;
23 HTTP attempts and both observers finish, own-profile deletion and host
routes/resolver restore. Native r50 boot 474246de-a397-44a1-84ce-efd9f4d3ae95
has the original hash, four rates/schedutil, taint zero, Sway and sensor proxy.
Only the existing time-sync target/service remain pending. Exact-status
resolver probes are recorded separately rather than inferring the root cause
from an earlier empty lookup stdout. The Alpine r54 package stays unbooted and
uninstalled. Controlled module/governor/pstate/feedback, analogue rails,
thermal/suspend, installed update/recovery and broader bringup remain open. See
[successful startup evidence](../evidence/2026-11-08-cpr-disabled-reference.json).

The owner confirms display and touch on the successful startup trial’s newest
r50 return, closing that physical recovery check. Native time-sync remains
open; bounded supported hosts lookup exits 124 and timesyncd has no server
address/packets. The underlying DNS/network/service cause is not yet established.

### Signed CPU modules and first fixed-corner performance requests (2026-11-08)

Prepared isolated observation source b721ebaecd7d and 43-patch manifest, adding
read-only planned/cache/applied/feedback/APC-target distinctions while preserving
legacy output. All 120 selected C/schema/DMP checks, a separate ARM W=1 object
and checkpatch pass. Two real-shell registration tests and two first-step tests
exercise load ordering, preconditions, exact request limits and rejection after
failed observations. The full kernel/both DTBs/all 464 modules build in 6m06s.
Every staged module signature verifies against the certificate exactly embedded
in the ELF trust list; corrupt contents/signatures and the prior certificate
reject. Source publication is verified on the owner's observation branch.

The first image's data-only transfer times out after 3,588,096 bytes, within
the compressed kernel and before any BOOT. Only after terminal failure and
confirmed process exit is the identified phone USB transport reset. XZ preset
3 re-encoding preserves decompressed Image, ELF, certificate and symbol-version
bytes exactly. This image stages/reads back and boots once; the underlying
content-dependent USB defect remains open.

Enforced signatures and checked userspace-first load order register both CPU
modules at 300 MHz with APC held at 1.15 V, no positive performance state and
feedback disabled. Taint is zero. The 181.722188-second timer returns to r50
boot 48ddf314-a3e3-407b-bd8f-b330ede124e6, with running systemd, original hash,
four rates/schedutil, Sway/sensor proxy and owner-confirmed display/touch.
Host network state restores. See
[registration evidence](../evidence/2026-11-08-cpr-voltage-observation.json).

A separate RAM trial caps userspace at 300–384 MHz, requests 384 then 300 MHz
and passes quiet holds at both. APC reads 1.08 V and the positive performance
state is applied; LOOP_EN remains clear at the fixed-voltage corner. The PLL
reads 768 MHz for the 384 MHz point, and return uses the 300 MHz auxiliary
path. Active MX requests 1.0875 V while another L3 view remains at 1.2875 V;
these are digital targets/votes, not analogue measurements. The timer returns
at 181.756403 seconds to r50 boot d745a11f-71fa-4f23-9e0a-d1d7914d2927. Its
original hash/policy, zero taint and Sway/sensor proxy verify; narrow dense-map
PMIC reads confirm S2 range/VSET 1/115 and the 1.15 V target restored after the
low-voltage warm return. Initial time-sync jobs and latest physical UI follow-up
remain recorded separately. Later feedback/rates, physical rails, sustained
load/thermal/suspend, distribution/install and wider bringup gates remain open.
See [first fixed-corner evidence](../evidence/2026-11-08-cpr-first-fixed-corner.json).

Native startup subsequently reaches running with no failed units/jobs, and the
owner confirms display/touch on this newest first-fixed-corner return. The
restored PMIC target, boot hash and physical UI checks close that bounded warm
recovery gate; all broader qualification remains open.

### First bounded 600 MHz CPR feedback response (2026-11-08)

Added a guarded userspace 300→600→300 MHz RAM script and three real-shell host
tests covering 22 simulated modes. Feedback requires interrupt progress plus
a voltage adjustment or handled clamp; LOOP_EN or an interrupt alone remains
inconclusive. All host tests pass. The new 6,899,712-byte RAM image keeps the
qualified observation kernel, DTB, two signed modules, command line and timer
unchanged; exact staging/readback precedes one BOOT.

All fifty samples pass with the uncached CPU at 600 MHz, APC/cache/planned
target 1.08 V, CTL 0x20000469 and one CPR interrupt. The unit starts at its
second-corner floor, so the handler enables auto-NACK-DOWN rather than changing
voltage. The active MX floor request is 1.1875 V. Explicit return to 300 MHz
restores the fixed-corner target, MX floor 1.0875 V and CTL 0x20000428/LOOP_EN
clear. No panic/Oops/BUG/lockup is recorded; temperatures remain below the
script's 60°C cutoff. This is quiet floor-response evidence, not load or
voltage-adjustment qualification.

The timer fires at 181.741527 seconds. Both observers exit zero, host routes
and resolver match before, and the temporary profile is absent. R50 boot
8eda2570-36e5-43aa-a35c-6c531fdd349c has the original hash, four-rate schedutil
policy, zero taint, Sway and sensor proxy. Two exact PMIC rows read S2 range/VSET
1/115, restoring the native 1.15 V target. Initial startup has only the prior
time-sync jobs pending. Latest physical UI/startup follow-up is tracked in
[feedback evidence](../evidence/2026-11-08-cpr-feedback-600.json). Two host query
format errors stop read-only verification before proceeding and are corrected
without phone or network changes; their original records remain private.

Higher rates, controlled load/thermal/suspend, repeated transitions, physical
rails, stable/edge packaging, installed update/recovery and wider hardware
qualification remain open. The content-dependent USB staging defect persists.

The owner confirms display and touch on this newest 600 MHz trial's r50
return, closing its physical recovery check. Follow-up retains the same boot
ID, zero taint, Sway and sensor proxy; the two existing time-sync jobs remain
pending, so running systemd startup is not claimed for this boot.

### Repeated 600 MHz transitions and bounded four-core load (2026-11-08)

Added a static ARM checksum worker and a guarded repeat/load RAM controller.
Four Clang undefined-behavior-sanitized worker tests and six real-shell tests
covering 17 controller modes pass, including failed mid-trial observations,
worker affinity/accounting/deadline failures and cleanup after termination.
The exact production ARM binary passes fifteen independent digest cases and
its 30-second affinity/accounting lifecycle under emulation. The runtime
worker uses the production 30-second default, not the host test's short variant.

The 6,993,920-byte RAM image preserves the qualified kernel, DTB, two signed
modules, command line and timer. Exact staging/readback precedes one BOOT.
Five 300→600→300 MHz round trips pass, followed by four pinned workers at
600 MHz and another verified 300 MHz return. Workers on CPUs 0–3 check
362/365/365/371 one-MiB hashes, totaling 1,463 hashes and 113.737 process CPU
seconds in approximately 30 elapsed seconds each. All workers terminate
before the final request. All 90 state checks pass, including 37 during load;
temperatures span 38–44°C. APC remains 1.08 V with one handled floor-clamp
interrupt and no observed voltage adjustment. Return clears LOOP_EN and
restores the first-corner MX floor.

The timer fires at 181.714515 seconds. Both observers exit zero, the temporary
profile is removed and host routes/resolver match before. R50 boot
28db1c68-3b08-4a53-8e5a-3397b8315813 retains the original boot hash, four-rate
schedutil policy, zero taint, Sway and sensor proxy. Two known PMIC rows confirm
the native 1.15 V target restored. Latest physical UI/startup follow-up is
tracked in [repeat/load evidence](../evidence/2026-11-08-cpr-load-600.json).
The existing native time-sync wait is diagnosed separately with read-only
service/DNS/route snapshots. Higher rates, long stress/whole RAM, physical
rails, thermal throttling, battery, suspend, stable/edge/install/recovery and
wider bringup remain open.

On this same newest r50 boot, the bounded `getent hosts` probe succeeds.
`resolvectl` is absent (status 127), so it cannot diagnose the active resolver;
the first broad snapshot also used an unsupported JSON route invocation.
Follow-up uses supported commands, captures stderr and records each status.
Timesyncd subsequently contacts a public pool server and synchronizes
naturally. The exact boot ID, zero taint, Sway/sensor proxy and running systemd
startup with no failed units/jobs are verified. No network/time/unit settings
are changed or services restarted. This closes startup for this boot, without
claiming earlier intermittent DNS/startup delays fixed. See
[time-sync follow-up](../evidence/2026-11-08-r50-time-sync-followup.json).

### Prepared 787.2 MHz PLL transition/load trial (2026-11-08)

Prepared a separate guarded userspace 787.2 MHz RAM controller and image,
retaining the exact qualified kernel, DTB, signed modules, static worker,
command line and timer. Three 787.2→600→787.2→300 MHz cycles precede the
bounded four-core 787.2 MHz load and a 600→300 MHz return. All checks now
include the uncached CPU PLL rate/enable state; high-rate feedback must be
observed at 787.2 MHz. Both 600 and 787.2 MHz map to virtual corner 4/fuse
corner 2 with APC bounds 1.08–1.18 V and MX floor 1.1875 V.

Six real-shell tests covering 22 modes pass, including wrong CPU/PLL rates,
wrong PLL enable state, worker faults and termination cleanup. Three new tests
execute the actual PLL/mux selection functions with the board PLL OPP table,
checking 42 canonical decisions and two negative parent controls. Four actual
corner-mapper tests pass. The new 6,993,920-byte image verifies its header,
digest, unchanged kernel/DTB/modules/worker and exact request list.

No phone reboot, transfer or BOOT is performed. Native r50 boot
28db1c68-3b08-4a53-8e5a-3397b8315813 remains running, NTP-synchronized and
untainted. Its physical display/touch result is still pending. The actual
next stage entry is tested to reject that result before any phone command
or transfer/controller creation. This turn advances host preparation and
verification; no 787.2 MHz hardware or broader qualification is claimed. See
[preparation evidence](../evidence/2026-11-08-cpr-787-preparation.json).

### Independent Alpine r55 observation source package (2026-11-08)

Updated the isolated pmaports recipe from 39 to 43 patches, retaining the
original patch bytes and explicit olddefconfig. The new input changes only
LOCALVERSION to `-fx0-cpr-observe-alpine`, keeping this module family separate
from the Fedora artifacts. Seven exporter integrity tests pass. R54's full
source/build tree, ELF/certificate/config/symbols and original log are preserved.

The first build attempt stops before compilation because a nonrecursive sysfs
bind fails in the rootless container. Disposable controls reproduce ordinary
bind failure and recursive success; recursive sysfs prebinds resolve the fixture.
The recorded retry completes its full Alpine Clang 22.1.3 source build in
9m24s of abuild time. All 48 actual prepared files match b721ebaecd7d. The actual
normalized config passes the official community check; its 19 compiler-related
differences exactly match the prior Alpine run, with CFI/LTO policy retained.

The signed 18,481,234-byte r55 APK embeds the exact recipe commit, kernel and
both DTBs. Its explicit certificate exactly matches the ELF trust list; all
464 signed ARM modules and vermagic verify. Actual KCFI compile flags/linked
symbols, zero introduced undefined symbols and 0600 module-key mode verify.
Corrupt module payload/signature, modified signed APK metadata and certificates
from both r54 Alpine and the qualified Fedora build reject. Offline simulation
needs an initialized empty usermode database and explicit armv7 architecture
on the x86_64 host; both fixture errors are retained, and the normal signed,
offline ARMv7 simulation then passes. No trust or architecture guard is bypassed.

Published the source-only recipe commit b234cd8bb1de3add3450c0ca86bcdcb9cc797bd9
to the owner's existing package branch under standing GitHub authorization;
the remote ref matches. Compiled packages, private keys, firmware and device
logs remain private. Read-only postflight confirms the same native r50 boot,
original boot hash/1.15 V target, zero taint, running startup/NTP, Sway and
sensor proxy. The latest physical UI check remains pending. This Alpine
artifact is unbooted and uninstalled; independent RAM, stable/edge, installed
update/recovery and wider hardware qualification remain open. See
[r55 package evidence](../evidence/2026-11-08-cpr-observation-source-package.json).

### Prepared independent Alpine startup/signed registration (2026-11-08)

Selected only the two r55 CPU modules, verifying their exact packaged payloads,
Alpine release, empty dependency lists and detached CMS signatures against the
certificate exactly embedded in the APK kernel. Added a separate release/permit
guard and before/after bootstrap checks for four CPUs, taint, two thermal
sensors, CPU mux/PLL, MX consumer, unapplied state, disabled feedback and the
1.15 V APC target. Userspace must load successfully before cpufreq-dt; no
explicit frequency/performance request occurs.

Three real-shell tests cover 36 instrumented modes. Incorrect build families,
preconditions, failed/silent loads and post-registration drift reject, with
post-drift failures matched to the intended guard. The exact ARM BusyBox parses
the script. Built a 6,240,256-byte RAM image preserving the original APK kernel
encoding and exact DTB/modules, with only five registration-related initramfs
entries changed from the qualified template. Init, BusyBox, HTTP, command line
and 180-second timer remain unchanged. Header/digest and kernel/BSS footprint
below the forced ramdisk address verify; the actual observer prefix emits the
expected status and the complete command passes shell syntax.

The actual stage entry rejects the previous native boot's pending physical UI
result before any phone command, transfer or BOOT. Its checks bind the Alpine
build controller, release, kernel and certificate instead of the Fedora family.
No device operation is performed in this preparation. Independent Alpine
startup, registration, recovery and later OPP/load tests remain open; the
existing 787.2 MHz Fedora trial is also still unbooted. See
[Alpine preparation](../evidence/2026-11-08-alpine-cpr-registration-preparation.json).

### Corrected RAM transfer short-write handling (2026-11-08)

Inspected the exact installed lk2nd source while investigating the recurring
pre-BOOT content-dependent download stall. The host helper incorrectly
continued after a positive short data write, although the bootloader's actual
USB-read/download functions reject a short download. It also initialized
confirmed progress to the full payload size, making an identity or first-write
failure report misleading.

The helper now rejects short/invalid data writes without sending a remainder,
upload or BOOT, and initializes confirmed bytes to zero. Full writes, optional
pacing, partial readback and exact final comparison retain their behavior.
Fourteen transfer tests, eight boot tests and three actual-C framing tests
pass without skips. Controlled C completions cover full/first-short/later-short/
read-error/oversize paths; both extracted source files match installed commit
`079eebe745de650df02e92fd9ca8d9fec5110c56`. Three new regression tests fail
against the previous published helper, including real main-entry report checks.

This is a host correctness fix. It does not exercise USB DMA/interrupts,
identify the observed stall's cause, alter bootloader/image bytes or qualify a
new transfer. No phone command or configuration change occurs; both prepared
RAM trials remain gated on the newest native return's physical UI result.
See [transfer framing evidence](../evidence/2026-11-08-ram-transfer-framing.json).

### Native r50 eMMC direct-file integrity (2026-11-08)

Ran a bounded filesystem integrity trial on the existing native p35 ext4
root without rebooting or entering either prepared CPU RAM trial. Fresh
preflight confirms the same r50 boot/hash, schedutil 300–787.2 MHz limits,
untainted running startup, UI services, USB input and space reserve. Four
host tests first exercise actual direct-file I/O and deliberately corrupt,
misdirect, stale and truncate fixtures; all pass without skips.

The phone then completes four 512 MiB write/fsync/close/reopen/direct-read
rounds in 417.83 seconds. Every 512-byte sector binds its run, round and
absolute position. All four SHA256 results match the host's precomputed
values: 2 GiB written and 2 GiB directly read. The 512 guard samples report
39–45°C, with the 2 GiB free-space reserve retained. Whole-device read/write
counters rise by 4,194,416/4,266,240 sectors, including metadata/background I/O.
Filesystem errors remain zero and the new kernel log has no storage errors.

The exact service and worker PID reach successful terminal state before
postflight. Original boot hash, native boot ID, policy, zero taint, running
startup/NTP and Sway/sensor proxy are retained. Its temporary sleep inhibitor
is released and only the finished transient unit is stopped/unloaded. The
final 512 MiB synthetic file and host hash remain for a future changed-boot
read; 7,615,930,368 bytes remain available. No raw block write, reboot, audio
test or host Wi-Fi change occurs. The previous native physical UI question
still belongs to this same boot. Same-boot integrity passes; cross-boot,
power-loss, long soak and final-candidate regression remain open. See
[worker](../diagnostics/emmc-integrity/README.md) and
[native integrity evidence](../evidence/2026-11-08-emmc-native-integrity.json).

### PN547 NFC reference-clock and board preparation (2026-11-08)

Audited the pinned production PN547 C2 configuration, GPIO mapping and vendor
clock driver. QUP3 uses address 0x28 and pins 10/11; VEN/FIRM use 20/22 and
IRQ21 is requested rising despite the old DT flag. The selected PMIC path
uses `cxo_d1_pin`, matching maintained RPM XO buffer ID 2 and clock binding 54.
Native r50's read-only baseline confirms disabled QUP3, unclaimed relevant
pins, no NFC stack and `AF_NFC` rejection without module-list changes.

Created a separate sparse source branch from the clean conservative ancestor
that exactly matches all 18 reconstructed-r50 changed files. Four commits add
IRQ-failure NCI unregister, the optional reference-clock binding, balanced
mode-dependent clock/error handling and the board wiring/cold states. Published
`integration/fx0-nfc` at `94010ddccf9aaa212870ecd0ea0058e33de482c9` under the
standing fx0 push approval; its remote ref and exact four-patch replay verify.
All four patches pass strict checkpatch without sign-off checking.

Twenty ARM objects/composites build with W=1 and KCFI retained, with no compiler
warnings. Twelve actual-C/schema checks pass without skips, including nine
mode/probe cases, clock-shape rejection and legacy controls, compiled
GPIO/clock/pin/bus bindings and unchanged four-rate CPU semantics. Three new
failure controls reject the unmodified driver. The rebuilt baseline DTB is
byte-identical to original r50; all three DTC warnings are pre-existing.
Sparse header/syscall/vendor-prefix fixture omissions were corrected, and the
DT uses supported flat cold pin states with TLMM `output-disable`.

The qualified source/index and build artifacts remain unchanged. Read-only
postflight confirms the same native r50 boot/hash/policy, zero taint, running
startup and UI services; QUP3 remains disabled and no candidate modules load.
No full kernel/module/package/image or hardware NFC trial exists yet, and no
firmware/library/calibration is exported or programmed. The latest native UI
gate, controller/tag/RF/userspace/suspend and broader bringup remain open. See
[NFC work](nfc-bringup.md) and
[preparation evidence](../evidence/2026-11-08-nfc-source-preparation.json).

### Complete NFC host kernel and signed module family (2026-11-08)

Built the published conservative NFC source into a complete
`6.18.59-fx0-nfc-prep` ARM kernel, all 468 modules and the exact schema-checked
Fx0 DTB. The successful run finishes in 355.87 seconds. Linked KCFI and
nonpermissive configuration verify, with no added undefined symbols beyond
the baseline's two BPF and three weak EFI entries. The embedded certificate
matches the new private mode-0600 signing key's 1,324-byte certificate, and
kernel/BSS placement remains below the forced ramdisk address.

The first process terminates on the per-user tmpfs quota. After confirming its
exit/PID disappearance, the workspace retry changes only the DWARF section
encoding to lossless zlib compression. Actual ELF debug streams fully
decompress and retain DWARF5. Seven regenerable top-link objects are verified
into lossless archives before removing those originals, freeing 1.13 GB.
All 46 recorded prior final kernel/config/DTB/symbol/certificate hashes and
the protected indices remain unchanged; the archive receipt provides exact
restoration paths/hashes before any old incremental relink. Recovery storage
is read-only throughout. Initial failed output and logs are preserved.

All 468 staged modules pass architecture/release/in-tree and explicit-kernel
certificate CMS verification, with embedded CMS certificates ignored. All
25,562 imported CRCs match the current complete `Module.symvers`; modified
payload/signature/import and wrong-certificate/export-map controls reject.
The complete NFC dependency order includes matching `rfkill`, `nfc`, `nci`,
`nxp-nci` and `nxp-nci_i2c` modules. No module is loaded or forced.

Read-only postflight retains the same native r50 boot/hash, conservative
policy, zero taint, running startup and UI services, with QUP3 disabled and
no NFC candidate modules. The retained eMMC test file is untouched by this
work. The exact native UI question remains pending, and no package install,
RAM image/staging/boot, GPIO/clock/bus/RF/firmware operation, audio test or host
Wi-Fi change occurs. Distribution/independent Alpine packaging, bounded RAM,
controller/tag/userspace/PM and full bringup remain open. See
[full-build manifest](../manifests/kernel-nfc-full-build.json) and
[evidence](../evidence/2026-11-08-nfc-full-build.json).

### Independent conservative PN547 Alpine package (2026-11-08)

Exported and independently source-built r56 from the ten conservative r50
patches plus four published NFC changes, excluding the later CPU/CPR series.
All 16 source checksums verify and the raw recipe payload replays to the exact
published Git tree. The distinct `6.18.59-fx0-nfc-alpine` family retains
nonpermissive KCFI, module signing and full losslessly compressed DWARF.
Its actual configuration passes the official community checker and has exactly
the 19 known Alpine compiler/capability differences. All 468 packaged modules
pass explicit embedded-kernel-certificate CMS and current `Module.symvers`
import-CRC checks; corruption and wrong-family controls reject. APK signatures,
modified signed-metadata rejection and normal offline ARMv7 resolution pass.

The initial APK's BusyBox depmod metadata has 468 empty dependency lists.
Requiring kmod in the canonical template and committed NFC recipe fixes that
real defect. An authenticated `abuild rootpkg` run reuses the unchanged compiled
kernel/configuration/key and repeats only packaging/signing/dependency
generation. The final 391 direct and 577 transitive edges match every module's
metadata. The new generic audit rejects the actual initial bad APK; two graph
regression checks pass. The preserved uninstalled r55 package has the same
464-entry defect and needs correction before distribution.

Lossless archives of 26,941 regenerable objects recover 3,895,319,084 bytes
while preserving 5,842 recorded final-artifact hashes. Each file is independently
decompressed and SHA256-checked before removal, with private restoration
receipts retained. The previous r55 Alpine build is preserved by rename and
1,394 final-file hash checks. Setup attempts stop before compilation on missing
shared objects/upstream/channel metadata; each terminal attempt is retained,
and the corrected build attempt uses the identical initial recipe commit. An
audit harness sparse-file lookup is corrected to compare published Git objects. Module verification initially stops on ENOSPC; after verified small
batch archiving, only the remaining checks resume. One exactly reproducible
old corrupt-APK control is retired while retaining its original signed package
and test evidence. No recovery-disk write or root-index change occurs.

Read-only phone postflight retains the original r50 boot/hash, conservative
CPU policy, zero taint, running startup/Sway/sensor proxy, disabled QUP3 and
no NFC modules. The retained eMMC file's size is unchanged; its cross-boot
content check remains pending. The exact latest-boot UI question remains open.
No package install, RAM entry, NFC GPIO/clock/bus/RF/firmware action, audio test
or host Wi-Fi change occurs. Hardware, installed update/recovery and broader
bringup qualification remain open. See [NFC work](nfc-bringup.md) and
[package evidence](../evidence/2026-11-08-nfc-alpine-package.json).

### Corrected CPU/CPR compressed-module package r57 (2026-11-08)

Fixed the original r55 APK's 464 empty BusyBox dependency lists by requiring
kmod and incrementing the package revision to r57. All 43 source patches and
the input configuration are unchanged. Authenticated `abuild rootpkg` runs
in the retained source-build tree, reusing the exact kernel/DTBs/configuration,
embedded certificate and private mode-0600 signing key. This is packaging-only;
the original kernel release and compiled build number are retained.

All 464 signed module files and payloads match r55 byte for byte. All 25,294
imported CRCs, signatures and corruption/wrong-family/ABI controls pass. The
new graph verifies 385 direct/567 transitive edges and rejects the actual
original bad r55 metadata. Dry-run modprobe checks all 464 packaged binary-index
resolutions and dependency orders; the same audit passes all 468 NFC modules.
No modules load or host configuration changes. APK signature/tamper and offline
ARMv7 checks pass. An isolated workspace usermode r55-to-r57 replacement with
hooks disabled produces 546 regular files matching the signed r57 payload.
Actual phone update hooks, autoload, boot and recovery remain untested.

All 1,394 retained r55 final-file hashes, 48 published source-file comparisons,
CFI flags/link/config and original APK remain intact. Separate NFC artifacts
and the protected root index are unchanged. The prepared r55 RAM registration
image remains unchanged/unbooted; its exact native-UI gate is still pending.
No device entry, install, GPIO/clock/bus/firmware action, audio test, host Wi-Fi
change or recovery-disk write occurs. See
[r57 manifest](../manifests/kernel-cpr-package-r57.json) and
[correction evidence](../evidence/2026-11-08-cpr-package-dependencies.json).

### Prepared first moduleless NFC RAM startup (2026-11-08)

Built a 6,207,488-byte RAM-only image from the exact verified Alpine NFC r56
APK kernel/DTB without changing their encoding. It contains no modules,
firmware or CPU registration payloads. All ten qualified base initramfs
entries retain their original BusyBox/init/USB/HTTP/180-second timer bytes.
The conservative family's schedutil default replaces the earlier CPU trial's
userspace command-line override; enforced signatures remain requested.

The new read-only checker pins the release and exact 84-byte kernel-note
fingerprint, signature flag, empty module list, zero taint, four CPUs, two
bounded temperatures, absence of CPUfreq policy/CPR/block mounts, and one
unbound PN547 client on enabled QUP3. Two tests execute 28 fixture modes,
including 27 faults, without fixture changes or module/GPIO/I2C commands.
Independent actual-image parsing verifies header addresses/checksum, all 14
CPIO entries and module/firmware absence. The exact ARM BusyBox parses init,
HTTP and the checker and executes compatible-string NUL conversion.
Review catches procfs zero-size semantics and aliased block-mount gaps before
publication. The final checker reads module-list contents and permits only
expected RAM/pseudo filesystem types. Both new cases are accepted by the
retained earlier unpublished checkers and rejected by the final version;
none of those images is staged.

The real pending-UI stage process and instrumented pending/wrong-boot cases
stop before phone-client imports or subprocesses. There is no physical entry,
transfer or BOOT state. Read-only postflight retains the same native r50 boot,
original hash, conservative policy, zero taint and active UI services; the
latest display/touch result remains pending. The previous CPU RAM image,
CPU/NFC packages, kernel artifacts and protected root index are unchanged.
No recovery-disk write, audio test or host Wi-Fi change occurs. These host
checks qualify neither real startup/return nor runtime signatures, cold NFC
ownership, NCI commands, tag/RF/userspace/PM or broader bringup. See
[trial procedure](../diagnostics/nfc-startup/README.md) and
[preparation evidence](../evidence/2026-11-08-nfc-startup-preparation.json).

### NFC teardown lifetime/locking fixes and source-built r58 (2026-11-08)

Cold module-lifecycle preparation exposes a pending-IRQ use-after-free window
and `info_lock` recursion through NCI unregister/close. Two isolated source
commits drain the IRQ before releasing NCI state and unregister without holding
the mode mutex, then finalize cold mode and unlock before free. Firmware-work
handling is unchanged and concurrent firmware download remains unqualified.
Nine tests execute actual C in 16 callback modes; restoring either old defect
alone fails its intended check. Raw patches replay exactly and strict style
checks pass after restoring sparse-tree reference markers.

The separate 16-patch r58 Alpine family source-builds completely in an isolated
pmos home. Its distinct release/certificate preserves CFI and full compressed
DWARF, with the same 19 known configuration capability differences. All 468
CMS signatures, 25,562 imported CRCs, 577 dependency edges and 468 binary-index
loader requests verify. The two changed ARM objects compile with W=1 without
warnings and match the full-build object bytes; original command/object bytes
and mtimes are restored. APK signatures and isolated usermode r56-to-r58
replacement pass, including all 549 payload files and old module removal.
The DTB and symbol ABI remain identical to r56, without transferring runtime
acceptance across the distinct signing families.

Prior build/source/package/key state, the prepared moduleless image and protected
root index remain intact. Read-only postflight retains native r50's exact boot,
original hash/policy, zero taint and active Sway/sensor proxy; its latest physical
UI check is still pending. No device entry, candidate module load, firmware/RF
operation, audio test, host Wi-Fi change or recovery-disk write occurs. A matching
corrected-family startup/return and cold-module lifecycle remain open before
controller/tag/RF/userspace/PM and broader bringup gates. See
[build manifest](../manifests/kernel-nfc-teardown-build.json) and
[fix/build evidence](../evidence/2026-11-08-nfc-teardown-source-package.json).

## November 8: r58 startup prepared and native UI confirmed

The owner confirms working display and touch on native r50 boot
`28db1c68-3b08-4a53-8e5a-3397b8315813`; its original boot hash, zero taint,
running systemd, Sway and sensor proxy are rechecked. The corrected r58
NFC family now has a separate moduleless RAM image and checker, passing 30
fixture cases including rejection of the older r56 release and marker.
Kernel/DTB bytes match the signed r58 APK; qualified init/USB/HTTP/BusyBox
and the independent 180-second return timer remain unchanged. The image
is unstaged and unbooted at this checkpoint. See [r58 startup details](../diagnostics/nfc-startup/teardown-startup.md)
and [preparation evidence](../evidence/2026-11-08-nfc-teardown-startup-preparation.json).

Fresh byte comparisons also correct an earlier audit count: each r56/r58
build has 21 changed source files matching its published commit. The old
field reported ELF symbol-string-table bytes. Original reports and all
linked artifact hashes are preserved; [the erratum](../evidence/2026-11-08-nfc-source-comparison-correction.json)
adds no runtime or hardware qualification.

## November 8: r58 moduleless startup, recovery and eMMC persistence

The corrected r58 family passes one moduleless RAM startup and timed return to
installed r50. Its original packed image first times out before BOOT; after
terminal transfer recovery and an owner-confirmed native boot, isolated XZ
preset-3 encoding preserves the exact runtime Image/ELF/notes/certificate/ABI.
The new image reads back exactly, the actual startup checker passes, and its
84-byte notes match the linked r58 build. Four CPUs, no modules and one unbound
PN547 client at QUP3 `1-0028` are observed. The timer returns at 181.610626 s,
with serial and 22 complete HTTP pairs. Original r50 hash, zero taint, 1.15 V
PMIC target, policy and UI services are restored; owner confirms display/touch
on boot `98ab64c6-01c6-4c1e-91a2-433fc3afc4cf`. See
[startup evidence](../evidence/2026-11-08-nfc-moduleless-startup.json).

The preceding intermediate native reboot also verifies the retained 512 MiB
eMMC pattern with direct reads, full pattern and hash checks, and no ext4
errors. Its exact synthetic files are archived/removed after the later RAM
return. This is warm-reboot persistence, with power-loss/endurance qualification
still open. See [storage evidence](../evidence/2026-11-08-emmc-cross-boot-persistence.json).

Signed module runtime checks, NFC GPIO/clock ownership/teardown, controller/RF/PM
and wider bringup remain open. Original build/package/image artifacts and the
protected root index are unchanged. The USB transport fault remains unresolved;
native systemd currently waits on time synchronization with no failed units.

## November 8: signed NFC cold registration and cleanup

A matching r58 RAM image rejects same-ELF unsigned and altered-CMS rfkill
controls with key errors/status 129, then loads all five signed modules in
dependency order. Four cold probe/removal cycles include three explicit
unbind/rebind rounds and final ordinary reverse module unload. Twelve
snapshots verify VEN/FIRM low, IRQ21 input/pull-down, pinmux ownership and its
release, NFC/rfkill parentage and zero reference-clock votes. All NFC IRQ
counters are zero; 48 temperature samples are 38–39°C. The final state has
no modules, class/rfkill child, IRQ handler or pin owner. The independent timer
returns at 181.622714 seconds to original r50 with zero taint, programmed
1.15 V APC target, running systemd, synchronized time and UI services. Latest
owner display/touch status is recorded separately in
[the evidence](../evidence/2026-11-08-nfc-cold-lifecycle.json).

The checker passes 43 host modes, detects three isolated weakened guards and
preserves the qualified kernel/DTB/command line plus all fourteen original
CPIO entries. See [procedure and limits](../diagnostics/nfc-startup/cold-lifecycle.md).
NCI reset/init, tag/RF/userspace/PM, open-device or pending-IRQ teardown and
firmware concurrency remain unqualified. The candidate is RAM-only; installed
update/recovery, intermittent USB/time-sync faults and broader bringup remain open.

## November 8: bounded controller startup prepared and host-verified

A separate r58 RAM image is prepared for one NCI up/down pair. It retains the
qualified kernel/DTB/command line, fourteen base CPIO entries and 180-second
init timer, with the same five signed modules plus a static ARM get/up/down
helper. The helper validates kernel sender, sequence, family, attributes, ACK
and fresh powered state; failed/short/interrupted mutations are not resent.
The shell requires reset/init/mapping response traces and identity fields,
active/cold GPIO and clock votes, then cold module cleanup. No polling, RF
discovery, vendor, secure-element or firmware request is exposed.

Thirteen host tests cover 105 cases and detect five weakened guards. Host
sanitizers and ARM emulation each pass 16,384 packet byte/length variants;
all 79 helper cases match under ARM emulation. Independent image and exact
ARM BusyBox checks pass. These are preparation/model results, with real NCI
controller communication still unqualified. See [procedure](../diagnostics/nfc-startup/controller-startup.md)
and [preparation evidence](../evidence/2026-11-08-nfc-controller-preparation.json).

The image is unstaged/unbooted. Its actual entry refuses the pending physical
UI result before importing the phone client. Native r50 boot
`2e6126b9-498e-4d89-b23e-f08fe6ccc361` retains the original hash, zero taint,
running synchronized services, low VEN/FIRM, released NFC pins and zero
reference-clock votes. New native pre/postflight also checks those pin/clock
conditions. Current exact-boot display/touch confirmation remains pending.

## November 8: preserve receive through the closing NCI reset

An expanded actual-C teardown test finds a gap in the prior r58 open model:
real NCI unregister sends CORE_RESET, but the driver already released its IRQ.
The response is lost and the request times out even though close returns zero.
A new transport stop callback leaves receive available through unregister and
drains it outside the mode mutex before state free. Successful IRQ registration
is tracked so error unwind cannot release an unowned IRQ.

Five tests / ten cases pass with address/undefined behavior sanitizers; the
r58 open failure and five isolated defects are detected. Three fresh ARM
objects compile with W=1 and CFI; strict checkpatch and all seventeen patches'
exact replay pass. The first isolated tool run fails on read-only /dev/null;
its logs are retained and the corrected run passes. Publish the source, patch,
new profile and [evidence](../evidence/2026-11-08-nfc-open-teardown-source.json).
No new linked kernel, package or image exists, and hardware teardown remains
unqualified. Preserve earlier source/build/image evidence and the protected
root index. Native r50 remains the installed family; the latest physical UI
check is pending separately from the earlier moduleless return confirmation.

## November 8: build the matching open-teardown NFC family

Build r59 in a new pmos home from the unchanged seventeen-patch profile. The
first attempt stops before compilation on missing cached upstream metadata;
the second passes input config checks but cannot retrieve public indexes with
network disabled. A full pinned checkout and normal builder network allow a
third fresh-home attempt to complete. Retain all three controllers/logs/homes.

The APK embeds the exact recipe commit; all 22 changed source files match the
published Linux tip. Its actual normalized config passes the community checker
and differs from r58 only in LOCALVERSION. The new certificate matches the
whole kernel trust list. All 468 modules and 25,562 imported CRCs verify; the
new I2C module rejects the old nxp_nci_probe CRC. All 577 transitive dependency
edges and 468 loader dry-runs pass. APK signing/tamper and isolated r58-to-r59
replacement verify 549 payload files, with hooks disabled. Recheck 294 earlier
input hashes and the protected root index before documentation updates. Publish
the [measured manifest](../manifests/kernel-nfc-open-teardown-build.json), recipe
patch and [evidence](../evidence/2026-11-08-nfc-open-teardown-package.json).
No phone trial or installation starts; the exact latest-native UI result
remains pending and full bringup continues.

## November 8: prepare matching r59 moduleless startup

Recode the r59 decompressor in isolated scratch, including all thirty thin
EFI archive members. Original link and assembler replay reproduce the source
zImage; XZ preset-3 output independently decompresses to the exact runtime
Image. Build the fourteen-entry moduleless RAM image, retaining eleven r58
CPIO payloads/modes plus its init timer, serial/HTTP support, command line and
DTB. Change only the family permit, note hash and read-only checker.

Add RAM boot-ID and moduleless pin/GPIO/clock guards. Fifty fixture cases pass
on host and exact ARM BusyBox, and three isolated weakened guards are detected.
Independent header/digest/payload/CPIO, syntax and BSS bounds checks pass. The
actual pending entry and instrumented pending/wrong-boot cases stop before
phone-client import. A valid future entry requires a separate one-use native
preflight before reboot; that directory is still absent. A separate read-only
preparation baseline confirms the same r50 boot and NFC/PMIC/service state.
Reverify 873 earlier input hashes and 53 original encoding inputs before
documentation updates; retain earlier artifacts and the protected root index.
Publish [preparation evidence](../evidence/2026-11-08-nfc-r59-startup-preparation.json).
No physical trial or installation starts; full bringup continues.

## November 9: identify battery telemetry validity and recovery defects

Inventory the unchanged r50 native supplies, ADC bindings, firmware property
names and remote-processor/class interfaces without changing policy or
starting a radio. Confirm missing battery measurements and profile handoff,
and verify the installed r4 UPower CLI/daemon plus original boot hashes. A
follow-up resolves IIO drivers through canonical ancestor devices; initial
class-path nulls did not mean unbound drivers. USB input setting and descriptor
both read 500 mA; actual current/negotiation remain unqualified.

Build pristine copies of the two pinned UPower guard/backport trees with the
original tool rootfs mounted read-only. Add twelve validity probes, leaving
production C untouched. Matched sixteen-case runs each show eleven failing
contracts and five passing controls: nine false 0% critical/action states on
1.91.5; eight plus a NaN fatal-diagnostic abort on 1.91.0. Infinity becomes
100%; ignored supplies stay invisible after valid telemetry arrives. An
unavailable coldplug read and real-zero-charge protection pass. The read
error shim targets libudev, covering GUdev string and numeric paths; it is not
a kernel fault injection.

Retain the initial setup failures, missed numeric injection and earlier
backport partial-metadata diagnostics separately. Actual public preparation
replay matches both final tested fixtures; production C and recovery-disk
sources remain unchanged. Preserve previous NFC/CPU artifacts and the root
index. Publish the probes and [evidence](../evidence/2026-11-09-battery-telemetry-validity.json).
A production validity/recovery correction and its native qualification remain
open; no phone reboot or package/policy change occurs.

## November 9: fix UPower telemetry validity and later-availability recovery

Implement strict uncached numeric parsing and shared usable-charge validation
in fresh current/backport source clones. Keep library read failure, empty text,
malformed/non-finite values and out-of-range capacity distinct from valid zero.
Capture charge fields once per refresh, retain prior properties/update time on
unusable data, and retry initially ignored supplies through the existing removal
and registration paths so sibling links remain consistent. Prefer real charge
over approximate levels, preserve peripheral/MacBook behavior and avoid replacing
zero energy with a stale average. Bring the backport denominator guard in line
with current source.

All 28 new validity cases pass per tree. Full regressions expose an approximate
level precedence error, which is corrected; the old NaN test is updated to reject
false-empty reporting. Retain the initial missing-USB-metadata fixture failure.
A repeated Wacom mock event-send failure reproduces with unchanged pinned
production C; paced identical records pass there and with the fix, keeping all
final assertions. Host scheduling also exposes the fixed-per-loop simulated
power assumption; use elapsed monotonic time while retaining charging/discharging
assertions. Retain failed/misselected attempts separately. Final complete runs
pass all 131 and 122 configured tests with normal zero exit status; no skips or
expected failures are substituted. The public verifier rejects seven invalid
report controls.

Export reviewed mail patches and replay them at their exact bases to identical
clean source trees. Preserve earlier CPU/NFC/battery artifacts, original diagnostic
reproductions, the protected root index and the newest pending physical UI record.
Publish [evidence](../evidence/2026-11-09-battery-telemetry-fix.json) and
[review instructions](../submissions/upower/README.md). No native install, reboot,
charging, radio or audio operation occurs. ARM packaging, deployment and full
bringup remain unfinished.

## November 9: build and verify the ARM UPower r5 candidate

Prepare a fresh recipe checkout from r4, adding only the tested backport patch
and pkgrel bump. All eight patches apply; seven after the inherited Nura timing
patch have no fuzz or offsets. Publish recipe `4c5db910dd68205cc26303325186ccb39cb17521`.
Retain two terminal setup failures caused by missing upstream remote/tracking
metadata in the fresh clone; repair metadata without changing source HEAD/tree.
The first ARM QEMU-only build succeeds and exports six signed APKs. Its default
cleanup removes source, so enable retention and repeat with the same recipe,
target/toolchain and warm cache. All six original APKs are byte-identical; the
retained compiled source matches all 159 expected files. This is bounded repeat
build evidence, not independent-environment reproducibility.

The workspace build key is absent from the phone's existing trust store. Use
the existing native-trusted key only inside a network-disabled signing container,
keeping original package control/data gzip bytes identical and exporting no
private key bytes. Native public-key checks accept all six candidates and reject
modified signed recipe metadata. Offline simulation against a fresh read-only
r50 database snapshot upgrades exactly the three installed UPower packages.
The existing ARM core test passes under QEMU; five bodies run and two system-bus
bodies return early. The recipe's inherited automatic-check policy is unchanged;
Linux integration remains the separately validated host suite.

Stage only three verified ELF files and their local library symlink in a phone
temporary directory. Force eager symbol resolution and run unprivileged CLI
version/enumeration/dump/battery plus updated-daemon help. All pass; installed
binaries/database, original boot hash, boot ID, taint and running r4 daemon PID
match before/after. Remove probe files after verifying their hashes again. CLI
and shared-library bytes equal the original r4 APK; daemon help is loading
coverage, with no new daemon service or native battery-logic qualification.

Preserve earlier artifacts and the protected root index, publish the
[candidate manifest](../manifests/upower-telemetry-r5.json) and
[evidence](../evidence/2026-11-09-upower-r5-arm-candidate.json). Rollback/current
config/database/boot backup, deployment, native daemon acceptance and full
bringup remain unfinished. No reboot, charging, radio or audio operation occurs.

## November 9: approved native UPower r5 deployment and boot readback

Freeze the 1,820 earlier evidence hashes and collect the current r50 baseline.
The broad initramfs firmware-directory export guard stops at regulatory.db and
its signature. Verify both exact files against a signed public ISC wireless-regdb
APK, then audit all six boot/ramdisk images: only those verified public regulatory
files are allowed, native GPL kernel components match, and private-key markers
are absent. No proprietary firmware export occurs.

Preserve trusted r4 rollback and r5 candidate APKs plus the complete current
UPower/config/state/database/world, boot tree, module tree and GPT metadata on
both host and phone persistent eMMC. The fsynced archives match exactly
(114,387,299 bytes), and 21 captured payload files match the original r4 APKs.
In an isolated host root, execute r5 installation and r4 downgrade with scripts/
hooks disabled; all captured payload/config bytes and package versions return.

Initial automatic approval review rejects the live native transaction for lack
of exact authorization. The owner explicitly approves the UPower r5 install
before its only launch. Run one persistent monitored unit with current backup/
package/boot checks, an owned runtime mask and a temporary sleep/shutdown
inhibitor. Native APK installation retains normal scripts/hooks. Only the three
UPower package versions change, with recipe `4c5db910dd68205cc26303325186ccb39cb17521`.
The expected r5 executable hash runs and eight startup samples/CLI modes pass.
No automatic rollback is needed.

Normal mkinitfs/boot-deploy hooks regenerate initramfs and rewrite the existing
r50 boot image while preserving 524,288 bytes before it. This write should have
been called out explicitly before launch; the owner had approved normal hooks.
Independent readback verifies all 99 boot paths/bytes, complete raw partition,
both GPTs, all 478 module paths/bytes and all 243 initramfs payloads/modes match
the backup. Its 19 module payloads match installed r50; overlay hook is absent
and memory fit remains valid. No new kernel package or reboot occurs.

After inhibitor release, seven samples over 31.59 seconds keep the same new
daemon PID, no warning and finite unknown/absent battery state. Services stay
active, Sway retains its PID and display power controls are auto. Remove owned
mask/inhibitor, stop the completed unit and remove verified temporary transfer
files; keep persistent rollback copies. Archive the new package database/world
and [native evidence](../evidence/2026-11-09-upower-r5-native-install.json).
Physical UI, native malformed telemetry/stale-data policy, measured battery/
charging behavior, live package/root rollback and full bringup remain open.

## November 9: r59 transfer timeout, r50/r5 return verified

A fresh explicit display/touch answer passes for r50 boot
`2e6126b9-498e-4d89-b23e-f08fe6ccc361` after UPower r5 installation. The
older cold-trial UI ledger stays unchanged. A new entry directory checks that
exact question, answer, software checkpoint and boot; six altered UI controls
fail before phone-client import. Fresh native preflight verifies r50/r5,
original boot hash, running services, 1.15 V programmed APC target, 40–41 C
temperatures, released NFC pins and zero reference-clock votes.

The unchanged 6,809,600-byte r59 image download times out after 524,288
completed bytes. No complete readback, BOOT, RAM startup checker or NFC action
occurs. Both transfer and stage terminate with status 1 and their PIDs are gone
before recovery. Reset only the identified USB transport, verify lk2nd, and
send one standard reboot to installed r50. Do not retry the RAM entry. The
intermittent USB fault remains unresolved; lossless XZ encoding does not cure it.

Native boot `c3ac8f04-888e-493c-bb5d-a1729a275f7d` returns with the original
raw boot hash, zero taint, 1.15 V programmed target, low VEN/FIRM, released NFC
pins and zero clock votes. UPower r5 starts automatically; all three package
records, installed ELF hashes and running daemon hash match. Three samples
keep absent/unknown battery state, finite unknown percentage 0, no warning and
OnBattery false. This is not measured zero charge. Final systemd state is
running with no jobs; Sway and sensor proxy are active, temperatures are 41 C,
and initramfs/kernel/package database/world hashes are unchanged. Host routes,
resolver and protected index match; no temporary USB network was started.

A local return-helper filename collision initially stops at an assertion before
probing the phone. A separate waiter state filename fixes it; the successful
read-only postflight and the failed wrapper records are both retained. No
additional reboot or device action follows from that correction.

The new return has its own pending physical display/touch question. r59 startup,
NCI communication/open teardown, RF/PM/firmware behavior and full bringup remain
unqualified. See [trial evidence](../evidence/2026-11-09-nfc-r59-transfer-timeout.json).

## November 9: trace the next preboot transfer failure

Preserve all 2,001 prior inputs and inspect the installed lk2nd USB source:
fastboot, HSUSB and its descriptor header exactly match installed commit
`079eebe745de650df02e92fd9ca8d9fec5110c56`. The selected host kernel journal
shows no disconnect or reported controller error during the latest stalled
download; its first later reset is the recorded terminal-only recovery. This
limited log does not establish electrical/controller health or a root cause.
Kernel r59 never ran, and encoding-dependent observations do not establish a
content-specific failure mechanism. No bootloader change is justified here.

Add an integrated payload-free per-I/O frame journal to the synchronous host
helper. It flushes a start before each command/status/data I/O and records a
returned count or error with exact phase/offset/requested length, duration and
errno. Failed requests retain an unknown byte count rather than inventing zero;
positive short OUT counts remain visible and still abort. Identity probing and
all acceptance/timeout/chunk/pacing/no-retry rules retain their existing path.
Journal I/O adds host timing overhead; no physical transfer fix is claimed.

All 29 targeted checks pass. Ten injected protocol failure boundaries include
partial data delivery before error and partial readback. The real CLI retains
confirmed progress, releases its USB claim, never retries and leaves no verified
readback. Successful transfer still compares exact bytes. The previous helper
fails the new metadata contract for data-write/status-read timeouts; two isolated
mutants (unknown-count zero and missing flush) are rejected with no harness
errors. Actual extracted lk2nd C functions remain covered in five completion
modes; DMA/cache/IRQ behavior is not simulated by them.

The phone is untouched this turn. Its newest UI question remains pending on
native boot `c3ac8f04-888e-493c-bb5d-a1729a275f7d`. No new reboot, transfer,
BOOT, flash, radio/audio operation, host Wi-Fi change or recovery-disk write
occurs. r59 startup, reliable transport and full bringup remain open. See
[trace evidence](../evidence/2026-11-09-ram-transfer-journal.json).

## November 9: identify the modem gap and prepare an inactive MSM8926 description

Read-only inventory on the unchanged r50/r5 boot finds only ADSP and WCNSS
running. MSS at fc880000 is disabled and inherits the MSM8226 compatible;
active ModemManager has no objects. The installed MSS module exists but is not
loaded. rmtfs and several optional support tools are absent. Firmware names
mba.b00/modem.mdt are present through the actual configured runtime search path,
with original modem/persist read-only. No firmware/calibration bytes, identifiers,
QMI/location requests or radio controls are exported or executed.

Resolve the unit's private stock DTB supply phandles: MX L3, PLL L8, MSS S5,
with S5 fixed at 1.15 V. A separate patch against exact r50 source selects
MSM8926 resources, removes the inherited MSM8226-only BHS property and describes
those supplies. Modem and new S5 both remain disabled; no kernel recipe, package
or RAM image changes. The existing driver requests a minimum voltage with
INT_MAX upper bound and has remoteproc auto_boot false; runtime ownership and
filesystem/calibration handling still need qualification before activation.

Baseline/candidate DTBs compile with the same three inherited warnings; the
baseline matches the retained installed-r50 DTB hash. Stock-derived checks
reject the old description, wrong same-type supply and unexpected S5 enablement.
The first schema applicability assertion catches disabled nodes relaxing required
properties. Preserve that failed attempt; separate enabled host copies then
validate without MSS/RPM regulator diagnostics. Old missing supplies and stale
BHS controls are rejected. The actual candidate remains disabled and unbooted.

Final native checks preserve boot, taint, raw image, package database/world and
UPower/ModemManager/Sway PIDs, with systemd running and no jobs. The newest
physical UI answer remains pending. Modem startup/control, GNSS, SIM/RF and full
bringup are unfinished. See [status](modem-bringup.md) and
[evidence](../evidence/2026-11-09-modem-control-description.json).

## November 9: native-family offline modem probe image prepared

Extract only GPL kernel/map/config and a five-module dependency closure from
the previously audited retained backup. Public helper replay reproduces all
bytes. Verify the exact installed kernel's entire 1,324-byte certificate list,
11,709 exports and all 197 imported CRCs across five signed modules. Per-module
payload/signature/CRC controls reject. A fresh family replay derives Image,
notes and certificate from the retained kernel/map/config without pre-derived
files. The original native XZ encoding stays unchanged.

Create a probe derivative of the inactive MSM8926 description: enable modem/S5,
disable the BAM-DMUX child that probe otherwise creates. Full property comparison
finds only those three changes. Bindings pass. Audit auto-boot, offline crash/
shutdown, domain attach, IRQ setup and child creation in existing source. The
RAM image contains no firmware or loader service and uses the original independent
180-second init/USB/BusyBox bytes. Its guarded worker requests one offline
load/remove cycle only, with no remoteproc-state write or firmware request.

Host and exact ARM BusyBox pass five methods/44 subcases each; ten operation
failures, eight dynamic failures, one-use refusal and two weakened guards are
covered. The initial global shell-counter collision is caught by the full
positive workflow and its frozen baseline remains rejected. Image parsing,
header checksum, all 23 CPIO entries and three ARM script syntax checks pass.
The final rebuild reproduces the 6,301,696-byte image exactly on this host.

A read-only native pre-entry baseline confirms the same boot/hash/services,
APC target 1.15 V, and S5 target1.15 V with mode0x40/enable0 using nine exact
register preads. This is programmed state, not analogue voltage. No kernel/
package/firmware/radio change or RAM entry occurs. Fresh pre/postflight and
observer controllers plus the pending current-boot physical UI check remain
required before use. See [preparation](../evidence/2026-11-09-modem-offline-probe-preparation.json).


## November 9: offline modem entry and return controls prepared

Prepare a one-use staging, serial/HTTP observation, single-BOOT and native-return
controller set for the verified native-r50 offline probe image. Preserve the
pending current-boot UI gate before phone-client import. Fourteen staging and
fourteen BOOT cases pass with instrumented sources; six native phase cases,
twelve recovery refusal cases and nine changed-register controls pass. No test
opens a real USB device or sends a phone command. An uncertain BOOT reply blocks
a second attempt. Recovery requires the known terminal pre-BOOT timeout and
absent PIDs; no live transfer is killed/reset/retried.

One real read-only preparation check confirms the same native boot, r50/r5
hashes, taint0, CPU/NFC/MSS baseline, nine APC/S5 raw controls, Sway and three
UPower samples. Host routes/resolver/protected index remain unchanged. The
future postflight permits normal startup observation for up to 120 seconds;
that return path remains unexercised. Exact ARM BusyBox `od -v` preserves all
84 native kernel-note bytes for serial capture.

Add a pure artifact return verifier and three passing test methods using actual
mocked-worker output and synthetic handoff/native receipts. Bad operation order,
state, identity, timer, IRQ, raw controls, UPower and host restoration are rejected.
Physical display/touch is never inferred. The new structured reply repeats the
already-recorded older post-UPower-install pass; the current native-return UI
question remains pending. The image is unstaged/unbooted; no reboot, transfer,
BOOT, module load, package or radio change occurs. Full bringup remains active.
See [evidence](../evidence/2026-11-09-modem-probe-entry-preparation.json).


## November 9: modem firmware layout checked and missing RMTFS memory described

The prior turn is progress: entry/return controllers and their host guard checks
were published at ee777d5; the one-use slot remains unconsumed. Revalidate all
2,241 prior evidence hashes and the protected root index. The current native UI
question remains pending, so no RAM entry occurs.

Inspect firmware entirely on the phone and export numeric layout/digests only.
The 27-header MDT has 21 bounded, nonoverlapping MPSS segments (three zero-fill),
an 81,788,928-byte aligned span in the 81 MiB carveout, exact split payload sizes
and packed 916+904-byte authenticated metadata. The 295,824-byte MBA fits its
1 MiB carveout. Four synthetic-fixture methods/22 cases cover fixed/relocatable
layout, all metadata sources and malformed/range/size/path refusals. No firmware
is authenticated, loaded or started by these checks.

Native has the RMTFS memory driver built in but no matching DT/device instance.
Stock DTB/vendor source agree on 0x0fd80000+0x180000. Prepare a separate host
description that partitions the existing exclusion without changing its union,
leaves MSS disabled and changes no other existing property. The first manual
patch hunk length is rejected and preserved; generated patch/compiled candidate
and real binding checks pass, with four description controls plus a missing-client
schema control. The candidate is neither packaged nor booted and does not alter
the earlier prepared offline-probe image.

Pin seven RMTFS source files to b30a3eb and verify their Git blob hashes. Audit
storage shadow mode and the default unit's remoteproc start/stop ownership;
read-only backing storage does not imply an inactive daemon. No RMTFS code is
installed/executed. Rehash all six original private firmware/provisioning images
and compare live partition digests: modem/FSG/FSC match, persist/modemst1/modemst2
differ. Cause/time and current matching rollback coverage are unproven. Preserve
old backups and require current verified snapshots/independent copies before
startup. No provisioning/firmware payload is exported in this turn.

Final read-only native acceptance retains the same boot, r50/r5/raw boot hash,
Sway/UPower and other services, CPU/NFC/MSS baseline, taint0 and raw APC/S5
controls. Host state/index and installed files remain unchanged. No reboot,
USB transfer/reset, module load, firmware/radio/package change or recovery-disk
write. Full bringup remains active. See [evidence](../evidence/2026-11-09-modem-firmware-layout.json).


## November 9: current provisioning captured privately on phone and host

The previous turn is progress: firmware layout and the separate unbooted RMTFS
description were published at 8be6165. Revalidate 2,324 prior hashes and the
protected index. Keep the current native physical UI gate pending; no RAM entry.

Capture five fixed provisioning partitions into a fresh mode-700 phone rootfs
directory, excluding modem firmware. Check labels/offsets/sizes, disabled MSS,
absent storage daemons/writer descriptors and read-only/unmounted sources. Every
source is opened read-only, and all five before/copy/after digests agree. Fsync
and reread five images plus metadata. Transfer only those private provisioning
snapshots and capture metadata to mode-600 files on encrypted workstation
storage. Independent post-transfer phone snapshot/source reads and host rereads
match; the capture PID is absent. Original card identity matches privately.

The two persistent copies contain 43,515,904 bytes across persist/modemst1/
modemst2/FSG/FSC. The phone copy shares the source eMMC; this establishes one
off-device current copy, not two. Factory-era originals remain preserved. No
provisioning bytes, per-partition digests, card identity or firmware payload are
published. The private manifest and verifier bind those images without listing
their individual digests in the public evidence map.

Four methods/25 synthetic cases pass for exact bounded copying, no-clobber,
changed/short/oversized/symlink/nondevice sources and eighteen bad snapshot
metadata/map/hash/permission/controller cases. A host round-trip into disposable
regular files verifies all five image payloads; temporary copies are removed.
No physical provisioning restore or power-loss durability is tested.

Final read-only native checks retain the same r50/r5 boot, files, raw boot hash,
taint0, Sway/UPower and other services, CPU/NFC/MSS baseline, nine APC/S5 controls
and unchanged host state/index. Phone writes are confined to seven new regular
backup files on rootfs. No source partition write, flash, reboot, USB reset/RAM
transfer, module load, firmware/radio/package change or recovery-disk write.
Full bringup remains active. See [evidence](../evidence/2026-11-09-modem-provisioning-backup.json).


## November 9: ARM RMTFS storage defects reproduced and candidate verified

The previous turn is progress: current private provisioning snapshots published
at a66f965. Reverify 2,362 prior hashes and the five raw private payloads through
their pinned manifest/verifier. The current native UI gate stays pending.

Pin RMTFS b30a3eb and QRTR 29e36ae inputs. Blob checks reject two source writes
that normalized trailing bytes; restore exact fetched text before compilation.
Retain failed incomplete-header, sanitizer/runtime and static-link attempts.
Build the full daemon for host and ARM using read-only compiler/target inputs
in a network/device/key-home-isolated sandbox. A signed exact-version public
libucontext development archive resolves the static libudev link. No key bytes
or firmware are exported and recovery storage stays read-only.

Exercise actual upstream storage APIs with synthetic files and guarded syscalls.
Final baseline fails 15/20 Clang sanitizer cases and 13/20 static ARM cases;
three ARM cases segfault. Reproduce invalid/closed handles, signed/32-bit range
errors, incomplete snapshots, failed-read leaks, suppressed errors, uninitialized
growth and incorrect errno. A focused storage-only patch passes all twenty cases
on each runner, including a positive backing-write control and zero backing
writes in shadow mode. These are storage tests, not QMI/shared-memory/physical
qualification. Exact patch replay and full host/static ARM rebuild pass; only
an early invalid-option daemon path is executed.

Record the retained target systemd/libudev provider's `-dirty` recipe metadata.
The archive is hashed, but clean dependency source closure remains unresolved,
so the full daemon is not promoted, uploaded, installed or started. Draft the
storage correction for upstream review; no upstream message/MR is sent.

Final read-only phone checks preserve the same r50/r5 boot/files/services,
taint0, original raw boot, CPU/NFC/MSS baseline and all nine APC/S5 controls.
Fresh provisioning source/phone-copy rereads and the host private verifier pass.
Host routes/resolver/protected index remain unchanged. No reboot, RAM entry,
source write, module load, firmware/radio/package change or recovery-disk write.
Full bringup remains active. See [evidence](../evidence/2026-11-09-rmtfs-storage-candidate.json).

## RMTFS packet-handler candidate

The actual dispatcher/QMI/storage harness now passes 25/25 synthetic cases on
host Clang ASan/UBSan/leak detection and static ARM/QEMU. The storage-patched
baseline fails 11/25 on both runners, including four ARM segmentation faults.
The handler patch corrects GET_DEV_ERROR handle validation, verbose CLOSE,
wide sector multiplication, sync error reporting and initialization/formatting.
Far reads and writes check actual 64-bit storage offsets. Transport and memory
are mocked; guarded synthetic backing files remain unchanged.

This does not close malformed QMI decoding, shared-memory span checks, large
counts, lifecycle, dependency provenance or physical modem operation. The OPEN
request encoder has an unresolved descriptor mismatch; tests construct its
string TLV directly. All decoding and remaining encoding use the pinned codec.
No phone commands or hardware changes occur; the latest UI gate remains pending.
See [packet procedure](../diagnostics/modem-control/rmtfs-packets.md) and
[evidence](../evidence/2026-11-09-rmtfs-handler-candidate.json).

## QMI bounds and required-field candidate

The corrected codec and OPEN C buffer pass 52 codec cases plus 32 actual
RMTFS dispatcher cases on host Clang ASan/UBSan/leak detection and static
ARM/QEMU. Baseline codec failures are 35/52 host and 24/52 ARM. Six malformed
dispatcher cases fail on each: missing fields or incomplete arrays can close a
live handle, allocate or transfer data. The candidate rejects those requests
before effects. The 256-byte OPEN wire maximum is preserved with room for NUL;
empty/ordinary/maximum OPEN encoding now works.

This is finite synthetic qualification. Generator integration, shared-memory
spans, huge counts, ownership/lifecycle, dependency provenance and physical
modem operation remain open. No phone commands or hardware changes occur; the
latest UI check remains pending. See [procedure](../diagnostics/modem-control/rmtfs-qmi.md),
[unsent QRTR draft](../submissions/qrtr/README.md) and
[evidence](../evidence/2026-11-09-rmtfs-qmi-candidate.json).

## Pinned QMI generator regeneration

The matching qmic kernel-output patch now preserves the OPEN terminator byte
through regeneration and emits optional string validity markers. All 28 pinned
qmic files match upstream Git blob hashes. Direct generation and the actual
RMTFS Makefile target agree; RMTFS descriptor C bytes remain identical to
upstream. Sixteen normal wire-byte/round-trip cases pass on host sanitizers and
static ARM, including both current-generator 32-bit RMTFS count fields.

This verifies source regeneration, not distribution packaging or full daemon
qualification. Legacy 256-byte nested-string length encoding remains unresolved;
RMTFS uses only a top-level path string. Shared-memory/lifecycle, dependency
provenance and physical modem work remain open. No phone command or hardware
change occurs; the current UI check remains pending. See
[generator procedure](../diagnostics/modem-control/qmic-generation.md),
[unsent draft](../submissions/qmic/README.md) and
[evidence](../evidence/2026-11-09-qmic-generation.json).

## Verified libudev provider and runtime link inputs

A new ARM diagnostic build uses signed Alpine eudev 3.2.14-r6, whose source
archive matches its clean recipe. Every persistent linker input matches a
verified signed package member with a clean recipe commit. Five real libudev
API cases pass against read-only synthetic sysfs; only early CLI rejection is
executed for the full daemon. The old dirty-metadata library and builds remain
unchanged. No phone operation occurs.

The link audit also found dirty recipe metadata on the cross compiler's bundled
runtime files; the final build selects clean target GCC runtime files instead.
The compiler executable's own recipe identity remains unqualified. Distribution
packaging, full startup, shared-memory spans, lifecycle and physical modem work
remain open; the native UI gate stays pending. See
[provider procedure](../diagnostics/modem-control/rmtfs-libudev.md) and
[evidence](../evidence/2026-11-09-rmtfs-libudev-candidate.json).


## 2026-11-10 — RMTFS shared-memory bounds and IOVEC preflight

Added a common memory-span validator, 64-bit physical helper parameters, backend representability checks, and complete IOVEC preflight before storage/memory I/O. Valid empty-write flush behavior is preserved. Thirty-five actual-helper/handler cases and fifteen selected existing functional regressions pass under host ASan/UBSan and ARM/QEMU, using synthetic backing only. The complete 785,876-byte ARM static PIE builds with the same eleven authenticated runtime inputs and passes only early CLI execution. Public patch replay matches the candidate. Constructor paths are compiled, not exercised; full daemon lifecycle, physical modem acceptance, compiler recipe identity and packaging remain open. No phone action occurs. See [evidence](../evidence/2026-11-10-rmtfs-memory-candidate.json); full bringup remains active.


## 2026-11-10 — RMTFS Linux memory discovery

Fixed duplicate fd closes and incomplete discovery cleanup. Linux RFSA/UIO validate metadata before taking ownership; only a missing device permits fallback. DT parsing uses explicit cell counts and rejects absent, incomplete or ambiguous regions before `/dev/mem` opens. Forty-six discovery and thirty-five memory cases pass on each of host ASan/UBSan and ARM/QEMU. The rebuilt static ARM candidate preserves the eleven authenticated persistent link inputs. Actual device mapping, Android-specific discovery, remoteproc/service lifecycle and physical operation remain unqualified. No phone action occurs. See [evidence](../evidence/2026-11-10-rmtfs-discovery-candidate.json).


## 2026-11-10 — RMTFS daemon lifecycle

Serialized remoteproc state writes in one worker, balanced successful start with one stop across QRTR reconnects, and handled shutdown signals without racing the poll wait. Nineteen lifecycle cases and fifty selected regressions pass on both host sanitizers and ARM/QEMU. The complete ARM binary preserves eleven authenticated persistent runtime inputs. A read-only native sample confirms r50/r5, the expected boot hash and rails, active Sway and disabled MSS. Physical driver and modem qualification remain open. [Evidence](../evidence/2026-11-10-rmtfs-lifecycle-candidate.json)


## 2026-11-10 — r59 alternate RAM encoding

The r59 timeout followed 524,288 confirmed bytes inside the compressed kernel. Relinked an XZ4 candidate with the same decoded kernel, DTB and compressed initramfs. The new 16 KiB frame differs in 16,325 bytes. The exact ARM decompressor produces the same Image from the signed, XZ3 and XZ4 streams. Six image refusal checks and the offline entry checks pass. The one-use trial is prepared, with current display/touch confirmation and physical USB transfer still pending. [Evidence](../evidence/2026-11-10-nfc-r59-xz4-encoding.json)
