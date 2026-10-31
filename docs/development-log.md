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
Controlled post-cycle gestures record31,488bytes/1,968events,27starts/releases,
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
storage writes. Both exact-ABI W=1 module builds pass. On full44, its known-RAM
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
