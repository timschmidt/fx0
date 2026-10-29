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
