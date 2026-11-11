# Linux 6.18.63 maintenance preparation

This candidate updates the r50 feature baseline to stable Linux 6.18.63.
It has a complete host ARM build and selected regression coverage. It has
neither a distribution source-package build nor a physical boot result.
The installed phone remains Linux 6.18.59-r50 with Sxmo r6.

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
reboot occurs in this phase. A base-system upgrade still needs its own complete
rollback preparation and approval. The pending eight-package Sxmo r7 proposal
does not authorize these broader upgrades.

The [evidence](../../evidence/2026-11-11-kernel-maintenance-6.18.63.json)
preserves prior input hashes and fresh build/audit receipts. A normal Alpine
source-package build, guarded RAM qualification and wider hardware acceptance
remain ahead. Audio testing remains excluded.
