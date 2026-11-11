# Linux 6.18.63 maintenance preparation

This candidate updates the r50 feature baseline to stable Linux 6.18.63.
It has complete host and Alpine source-package builds with selected
regression coverage. The later r1 package now passes a full native-OS RAM boot,
including owner-confirmed display and touch; persistent installation remains open.
The installed phone remains Linux 6.18.59-r50 with Sxmo r7. A later
6.18.63-r1 package includes the vibrator fixes and passes a separate RAM test;
it has not replaced the installed kernel. See the native-OS RAM section below.

The [manifest](../../manifests/kernel-maintenance-6.18.63.json) pins the
[published source](https://github.com/timschmidt/fx0-linux/tree/29edb2b9893edd18c445a648081b12038a033d51),
configuration, artifact hashes and scope. The source merges 1,989 stable commits
into the complete reconstructed r50 overlay. Both upstream tags verify with
Greg Kroah-Hartman's fingerprint from
[kernel.org](https://www.kernel.org/signature.html); an altered tag fails.
The only manual conflict preserves r50's secured/configured IOMMU exclusion and
adds stable runtime-power/error handling to the legacy context-probe fault clear.
CAMSS overlaps are reviewed and compiled with ARM `W=1`.

The integration preparer now uses `git apply --numstat -z` to inventory all
patch destinations. The previous inventory missed an appended plain unified
header addition, although it was applied and compiled. A mixed-format regression
fails the old helper; the complete overlay's 18 files match the original bytes.

## Build and validation

Use a fresh checkout at the pinned source revision and an empty output directory.
Copy `configs/linux-6.18.63-fx0-r50-maint.armv7` to its `.config`. The recorded
build uses Clang 21.1.8 (Fedora build 6), LLD 18.1.8, `ARCH=arm LLVM=1 LLVM_IAS=1`,
`CC=HOSTCC=/usr/bin/clang`, `LD=HOSTLD=/usr/bin/ld.lld-18`,
`CROSS_COMPILE=arm-linux-gnueabi-` and explicit empty `LOCALVERSION=`.
Run `olddefconfig`, then `zImage modules qcom/qcom-msm8926-lg-madai.dtb`.
The build identity is `fx0@maintenance`, version `1`, timestamp
`2026-11-11 00:00:00 UTC`. Use workspace temporary storage and disable ccache.
Compiler/Rust probe metadata can differ on another host; review changes.

Stage modules with `INSTALL_MOD_PATH` in a new private directory and
`INSTALL_MOD_STRIP=1`. Kbuild generates and uses a fresh private module-signing
key; preserve it privately with mode 0600. The audit inspects the public
certificate and private-key mode, without reading or exporting private contents.
Do not expect byte-identical modules or kernels with another signing key.

Recorded checks pass:

- Full ARM kernel and 464 signed/compressed modules; all direct/transitive
  dependencies and imported-symbol metadata match.
- Actual linked runtime trust list equals the public build certificate, all
  module signatures match it, and a different build's certificate rejects.
  Altered payload and signature controls reject.
- ARM32, zImage header, CFI type IDs/handler/object flags, unchanged undefined
  symbol baseline and load-footprint bound. These are static checks.
- 7 integration-preparer cases, 5 IOMMU PM/MMIO cases, 12 selected MPU/SCM/QFPROM
  cases and 7 compiled binding cases, with no skips. The old unpowered IOMMU
  block and a removed-guard mutant fail independent controls.
- The ordinary Fx0 DTB matches r50 byte for byte. The binding fixture uses
  `FX0_QFPROM_CPU_BIN_BYTES=4` for this baseline; its default of 8 remains for
  later CPR candidates. Schema cache is regenerated from this source.

Select this checkout through `FX0_KERNEL_SOURCE`. For bindings, also set
`FX0_CPU_BUILD`, `FX0_DT_SCHEMA_CACHE` and the explicit CPU-bin size, using
dtschema 2026.9. Later CPR activation tests require their own source profile.
This baseline does not incorporate or qualify later CPR, NFC or vibrator work.

## Userspace currency audit

[Nura's installation page](https://nura.eco/install/) advertises stable v26.06.
The native inventory contains 775 packages. Four stable and five edge indexes
are fetched over HTTPS and independently verified against the native public
keys before use in isolated, host-only dependency simulations. Local APK
catalog availability and exit status are not signature-acceptance proof;
the independent verification is required for these results.

| Projection | Upgrades | Installs | Removals | Downgrades |
| --- | ---: | ---: | ---: | ---: |
| Stable v26.06 / Alpine v3.24 | 30 | 0 | 0 | 0 |
| Current edge | 441 | 31 | 13 | 1 |

Stable includes Alpine 3.24.4 and updates to APK, OpenSSH, compression/XML
libraries, timezone data and Xwayland. Edge changes systemd, NetworkManager,
resolver and USB-tethering packages; its single downgrade is libsixel.
The ten native `package><Q1…` world constraints are exact signed-control
checksum holds, not merely version pins. Both projections retain them,
including the custom kernel, cameras and UPower. Thus solver success cannot
establish a fully current edge hardware baseline. The same wlroots version
also has a different repository signed-control checksum; payload equivalence
has not been checked.

The [earlier systemd startup issue](https://nura.eco/edge/2026/10/04/System-may-not-boot-on-kernels-older-than-7.2-with-recent-systemd-update/)
is reported fixed since 262-r3. Current edge is 262.2-r0; that old warning is
not evidence that it is blocked. Fx0 edge runtime remains unqualified.
No native index refresh, repository/trust change, package installation or
reboot occurs in this phase. A base-system upgrade still needs complete rollback preparation and runtime
qualification. The later owner phone-update approval and completed Sxmo r7
transaction are recorded separately; no broad stable/edge upgrade has run.

The [evidence](../../evidence/2026-11-11-kernel-maintenance-6.18.63.json)
preserves prior input hashes and fresh build/audit receipts. Guarded RAM
qualification and wider hardware acceptance remain ahead. Audio testing remains
excluded.

## Alpine source package (2026-11-11)

The separate [Alpine manifest](../../manifests/kernel-maintenance-6.18.63-alpine.json)
pins `6.18.63-r0`, release `6.18.63-fx0-r50-maint-alpine`, and the published
pmaports recipe. Standard pmbootstrap cross-native compilation uses Alpine
Clang/LLD 22.1.3, normal source checksums, community rules and package signing.
The input changes from the host baseline are the distinct release and full
DWARF zlib compression. The actual normalized configuration also passes the
official community checker, retaining nonpermissive CFI and schedutil.

The downloaded archive and all 91,269 compiled-tree source files/symlinks match
the published Git tree. The exact APK kernel and Fx0 DTB match the build; the
DTB also matches r50. The linked runtime certificate, CFI, load-footprint bound,
full compressed debug information, 464 module signatures, every imported-symbol
CRC and dependency graph pass. Modified import/export CRC, payload, signature,
wrong-certificate and APK signed-metadata controls reject. Offline APK
resolution uses an empty initialized ARMv7 database; native upgrade hooks,
world-hold changes and physical module loading remain untested.

Two pre-build setup stops are retained: the new sparse clone initially lacked
standard upstream metadata, then omitted the systemd recipe directory required
by the already-cached systemd buildroot. The successful attempt supplies both
and uses a fresh build home, preserving earlier source trees and signing keys.
The existing buildroot/dependency caches are reused; this is not a fresh-bootstrap
or reproducibility claim. No native package, kernel or service changes occur.
See [package evidence](../../evidence/2026-11-11-kernel-maintenance-6.18.63-alpine.json).

## Stable vibrator integration and first package-kernel RAM boot

Three separate [source commits](https://github.com/timschmidt/fx0-linux/tree/c69b017cd9af9c589aeb921f901987fb26c55a4d)
select the PMIC range from register layout, clamp the inclusive maximum and
replace cached drive bits on active intensity changes. The resulting driver
is byte-identical to the physically tested r50 candidate. On the stable source,
768 host ASan/UBSan speed/layout cases pass; the original and each independently
reverted correction fail. Strict checkpatch reports no warnings.

The [normal Alpine recipe](https://github.com/timschmidt/fx0-pmaports/tree/b32a54f534c38103b935a30a324ae1d1aa08e74a)
builds `6.18.63-r1`, release `6.18.63-fx0-vibrator-alpine`, in a fresh build home.
The exact archive and all 91,269 compiled source paths match published Git.
Actual community configuration, nonpermissive CFI, full compressed DWARF,
embedded certificate, APK signature and altered-metadata rejection pass.
All 464 signed in-tree modules match the kernel's ABI and dependency graph.
A log-prefix parser initially stops artifact collection; correcting that
read-only audit resumes after the already-passed config/debug check.

The RAM image uses the signed APK's exact kernel, DTB and matching evdev/vibrator
modules, with signature enforcement and expected taint zero. Full file-based
worker capture records 152/303/602 ms for 150/300/600 ms requests, active codes
24 → 17 → 22, final off holds and ordinary removal of both modules. The worker
exits zero and the independent snapshot finds no modules or worker. The exact
original 180-second timer remains before worker and USB setup; it starts after
the baseline pseudo-filesystem mounts, so it is not hard-lockup recovery proof.
The first image-verifier attempt incorrectly assumed a newer timer syntax and
placement; the corrected verifier checks the frozen baseline without modifying
its image. Installed-kernel update hooks, full native Sway boot, final combined
CPU/NFC integration, suspend and reliability remain open.
[Package and physical evidence](../../evidence/2026-11-11-stable-vibrator-and-nfc-r59-startup.json)

The isolated source build signs its output with a builder key absent from the
phone's trust store. A separate phone-installation copy uses standard
`abuild-sign` and the development key already trusted by the phone. Its
compressed control and data streams remain byte-identical; only the signature
header changes. The original build APK is retained. Independent RSA and APK
checks against the freshly rechecked native key set pass and altered control
metadata rejects. No trust key is imported and key storage stays read-only.
Signing setup initially needs an explicit build architecture, then the existing
mapped rootless namespace to access its owned key; those stops are retained.
The host-only native-database plan replaces only the kernel's exact control
hold and selects one kernel upgrade. It does not install the package or run
native hooks. Both APK identities are recorded in the manifest.


## Native-OS RAM trial

The same signed `6.18.63-r1` kernel and DTB now boot the installed native root
with Sway, Superd, gestures, UPower and the sensor proxy. Signature enforcement
remains enabled and taint stays zero. The owner confirms display and touch
while SSH still identifies the candidate boot. All 478 module/metadata files
(464 signed modules) match the APK in a temporary 64 MiB RAM mount over the
module search path. This verifies their bytes and the modules needed at startup;
it does not physically load every module. Installed boot files, kernel metadata,
APK database and world remain unchanged. The native root remains writable for
normal logs and session state.

Normal mkinitfs runs in a private mount namespace against the candidate module
tree. A capture-only boot-deploy shim prevents a flash. The resulting native
initramfs retains its ordinary init scripts, root discovery and 19 matching boot
modules. The complete compressed ramdisk ends below the inherited framebuffer.
A small prefix arms a static return helper before ordinary init; a cleanup hook
verifies and mounts the RAM module copy and places return units only in `/run`.
The exact helper survives switch_root, and the runtime timer is active at the
six-minute deadline. The seven-minute helper is a fallback, without a hard-lockup
recovery claim. Its actual deadline is not exercised by a normal timer return.

Two early attempts return before native startup. Instrumented pstore proves
that the exact kernel and foreground helper check pass, but BusyBox cannot
launch a background process with an initially absent `/dev/null`. Creating the
character device before that launch fixes the wrapper. A QEMU regression uses
the actual native ARM BusyBox: the missing-device case exits 2, and the present
case succeeds. Earlier archived r50 panic buffers are unrelated to this failure.
The return helper has 13 host cases; the module overlay has four tests covering
six success/failure fixtures, including corruption before and after copying.

Real packaged notifications pass enabled, muted and re-enabled cases with
corrected drive code 24 (2.4 V programmed target), final PMIC off and cleaned
notification/mute state. CPU policy, thermal readings, raw MPU6515 accel/gyro,
Sway's active 720×1280 DSI output and Wi-Fi connectivity are observed. These
short reads do not qualify suspend, analogue voltage, calibration, all OPPs,
long reliability, camera operation, NFC integration or GPU rendering quality.

Startup initially waits for NTP. The established temporary DNS fallback runs
and removes its addition, but its saved-profile byte-identity assertion fails
while NetworkManager activates Wi-Fi. Exact profile preservation is therefore
not claimed for this attempt. Later native checks find the original active
router DNS and no fallback address in active or saved DNS settings; NTP and
systemd reach healthy states. A read-only verifier also initially uses the wrong
DSI PHY sysfs name; discovery confirms `fd922a00.phy`, with `power/control=auto`.

The [native RAM evidence](../../evidence/2026-11-11-native-kernel-6.18.63-ram.json)
records the trial and return separately. Normal kernel installation/update
hooks and integration of the later CPU/CPR and NFC work remain open. Audio is
excluded.
