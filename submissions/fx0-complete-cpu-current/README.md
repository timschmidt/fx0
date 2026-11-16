# Fx0 complete CPU source port and full ARM build checkpoint

This packet restores the complete later MSM8926 CPU/CPR source scope to the
current combined Fx0 development tree. The earlier 89-path LTS inventory did
not include this entire scope. The later candidate adds 54 follow-up paths,
including 33 CPU/shared paths and ten feature files missing from that earlier
inventory. This packet covers those 33 paths and a separately reproduced CAMSS
link dependency.

The eleven CPU commits end at
`57b4bd9ec2db78022e93be3c5bef3e9e25833f12`, tree
`d702ba07047957db565de4facd1c616f7be73f8c`, on combined-runtime parent
`d62a924a72d73e2b19c1bd0d5d8fa754c8caf24e`. They are composite ports of
Timothy Schmidt's later CPU candidate
`790c9c5407e17ad1d2395c2ec4bdfcfc8dc82826`, with component author dates retained.
The evidence preserves metadata for 78 original scoped commits. Codex performed
the API reconciliation, source review, fixture updates, commit preparation and
qualification. These commits do not reproduce the original private commit
messages or certify human DCO.

The complete runtime, including the separate CAMSS dependency fix, ends at
`9a45b7096c83954703f6852a948d838704fa8f63`, tree
`cd04ac562013a8696dd8f82d0f2c4a275588d2ef`. Source, runtime and this review remain
local. Earlier approvals for different exact heads do not publish these heads.

## Resulting source behavior

The port includes the full-row SCM/NVMEM calibration loader, independent fuse
selectors and numerical calibration, voltage and corner planning, fixed-range
PM8226 APC/SAW transactions, CPU0 L2 ownership, correlated SMD RPM replies,
APC/MX reconciliation, PLL/mux readback and rate guards, startup handoff, CPU
domain attachment and CPUfreq supplier filtering. Bindings, drivers and the
qualification board are in separate commits.

The current flexible-tail CPR fuse allocation and current OF machine-query
APIs are preserved. The ordinary Madai board retains its four-rate CPU policy;
the separate CPR qualification board describes 14 canonical domain/CPU OPP
links. Current charging, USB and NFC definitions are preserved. The old CPU
candidate's unrelated charging/USB deletions were excluded.

The separate one-line CAMSS fix selects `GENERIC_PHY_MIPI_DPHY` for its direct
caller. The first complete native ARM build failed at the undefined
`phy_mipi_dphy_get_default_config_for_hsclk` symbol with the optional Qualcomm
CSI2 PHY disabled. The same issue exists on freshly verified official
media-next `7969a6f407cf55b5254c824c87875452655ef11e`. Its standalone fix is
`1ed419f49`, authored by Codex, with a verified
`Fixes: 0ee6c8a921b1` tag. The optional hardware PHY remains optional.

## Qualification

* Four native QCOM profiles, ARM/ARM64 with the MSM8926 feature enabled and
  disabled: 80 CPU/core objects, LLVM 21, `W=1`, `COMPILE_TEST=n`, no diagnostics.
  Retained object and final source hashes were verified before the full build.
* Twenty DTBs build. All twenty pass unfiltered validation against the full
  processed schema with empty stdout/stderr. Binding examples and lint pass;
  the other eighteen DTBs retain their previous exact bytes.
* Forty-five actual-function model methods pass. Twenty-six standalone C
  compilations use normal address/undefined/leak sanitizers. Seven ctypes
  numerical shared-library oracles are explicitly unsanitized because they
  load into Python. An independent standalone decoder model adds 4,068
  synthetic cases and 178,907 checks under the sanitizers; all three deliberately
  broken decoder controls fail.
* Eighteen actual native Kconfig profiles cover built-in/module CAMSS and
  disabled/module/built-in optional PHY: six on media-next, twelve on the
  combined ARM/ARM64 tree. The baselines expose two/four missing dependencies;
  the repaired profiles have none. Two native ARM64 CAMSS/helper objects build
  without diagnostics on the fresh media-next fix.
* The complete ARM `zImage` and all 455 modules link after the CAMSS fix. The
  successful repeat reuses the first full build's output; it is not a second
  clean or reproducibility build. CFI and automatic module signing are enabled.
  Standard private `modules_install` succeeds. All 455 zstd modules pass
  explicit-certificate CMS signatures, ELF32 ARM and release checks; both
  corruption controls fail. Their dependency metadata matches all 355 direct
  and 517 transitive edges. Full runtime ABI/loading acceptance remains open.
* All eleven CPU patches pass strict checkpatch with four explicitly justified
  inherited/style exceptions in `evidence/series-checkpatch.json`. The separate
  CAMSS fix passes strict checkpatch without ignored types. No agent adds a
  Signed-off-by. Maintainer discovery is read-only; nothing was sent.

The first full build's warnings are retained in
`evidence/full-ARM-first-diagnostics.json`: 222 warning occurrences and one
link error. The warning locations are in eleven files byte-identical to the
CPU parent, outside the CPU delta. The full kernel is not described as
warning-free. The repaired incremental link has no additional diagnostics.

## Replay

From this directory, run:

```sh
python3 -B replay.py /tmp/fx0-complete-cpu-replay
```

The output must not exist. Python 3, GNU patch and Clang 21 are required. The
replay verifies every packet hash, applies the eleven CPU patches and the
runtime companion at zero fuzz, checks exact candidate bytes, also applies
the standalone media-next companion, and executes the 45 model methods plus
the independent decoder and its three controls. It needs no Git, network,
firmware, device, unit fuse data or private signing key. Normal leak detection
is retained. Models execute selected real functions with synthetic kernel
services; they do not emulate a running CPU, secure firmware or concurrent
hardware.

The packet includes full-source configuration snapshots and qualification
records for native/schema/full builds; the portable replay does not repeat
those builds. `companion/check-kconfig-matrix.py` can repeat its actual Kconfig
checks against a full kernel checkout, writing a fresh labeled output beside
that script; pass `--architectures arm64 --fixed` for the standalone fixed
media-next source and both architectures for the combined fixed source.

## Remaining acceptance

The CPU series is based on the combined current runtime, with a fresh PM-next
comparison recorded privately. It still needs subsystem-specific standalone
maintainer bases, review of genuine fix boundaries and valid Fixes provenance
where applicable. It is not a submission-ready series or an accepted maintained
LTS replacement. The CAMSS companion alone has the fresh standalone media base.

Deep CPU suspend remains unsupported until RPM sleep-vote handoff is
implemented and qualified. No current-source boot, CPU/thermal stress,
performance, battery/standby measurement or physical interaction was performed.
The original r2 display/IOMMU fault remains unresolved. The user's current
display/touch observation is accepted without inferring a fresh boot identity
or new trial availability.

Normal clean public-source package builds, reproducibility, installation,
kernel/userspace updates, boot and recovery remain required. All seven bringup
requirements and every physically present nonaudio hardware interaction remain
in scope; audio execution stays excluded and the missing SIM affects only final
cellular acceptance. Stock-restoration and layout acceptance are preserved.

## Licensing and private inputs

Kernel snapshots retain their original SPDX/copyright notices and licenses;
the included license texts accompany them. Existing project fixtures are under
the project's MIT license, copied into `LICENSES/MIT`. New replay/model tools
carry GPL-2.0-only identifiers. The standalone CAMSS fix is attributed to Codex;
human review and DCO remain pending. Public generic vendor tables and synthetic
vectors provide the numerical inputs. Private firmware, initramfs, boot images,
credentials, device records, unit calibration and signing keys are excluded.
