# Diagnostic kernel configurations

These generated configurations derive from the Nura shared MSM8226 kernel
configuration and the Linux 6.18.59 Kconfig tree. They retain the upstream
Linux configuration licensing (GPL-2.0-only); the coordination repository's
MIT license does not relicense upstream kernel material.

The first configuration records the completed initial kernel/module build.
The `simplefb` configuration additionally enables built-in simpledrm for
an inherited framebuffer console. Hardware support still depends on the
exact device tree, kernel source revision, firmware and physical validation.

`linux-6.18.59-fx0-r50.armv7` records the running restored-r50 configuration
read on 2026-11-08. Its exact hash is pinned in the kernel integration manifest.
It includes Clang CFI, four conservative CPU rates and no CPR provider.
`msm8926-cpr-qualification.fragment` enables built-in CPR/CPUfreq and a separate
module release for source/build qualification. Its presence is not hardware
acceptance or authorization to skip RAM-only controller/recovery qualification.
See [the reconstruction procedure](../docs/building.md#reconstruct-r50-and-the-cpucpr-source-candidate).

The later `linux-6.18.59-fx0-cpr-observe.armv7` differs only in LOCALVERSION
from the runtime candidate and belongs to the 43-patch read-only observation
profile. Its own kernel/certificate/module family passes enforced-userspace
registration and bounded 300–384 MHz fixed-corner RAM trials. The compiled
default remains schedutil, so follow the controlled RAM recipe rather than
loading cpufreq-dt without a checked userspace override and governor module.
Later-corner feedback and installed/distribution qualification remain open.

`linux-6.18.59-fx0-cpr-observe-alpine.armv7` is the separate r55 Alpine package
input. It differs from the host observation input only in LOCALVERSION,
using `-fx0-cpr-observe-alpine` to isolate the independently compiled module
family. The recipe normalizes compiler capabilities with `olddefconfig`;
the actual Alpine configuration retains CFI and signed modules and passes the
official community check. Host RAM results do not qualify this Alpine build,
its default schedutil path or installed update/recovery.

`linux-6.18.59-fx0-nfc-alpine.armv7` is the independent r56 PN547 package
input. It differs from the verified full host NFC configuration only in
LOCALVERSION, using `-fx0-nfc-alpine`; all NFC options, conservative CPU
choices, nonpermissive CFI, signing and losslessly compressed DWARF remain.
The [NFC package manifest](../manifests/kernel-nfc-package.json) selects the
exact ten-patch r50 composition followed by four NFC patches, excluding the
experimental CPU/CPR series. Alpine compiler-capability normalization is
recorded separately from this input. This family has no RAM/hardware pass.

Packaging revision r57 reuses the exact r55 Alpine CPU/CPR input and compiled
signing family. It corrects compressed-module dependency generation with kmod;
it does not change this configuration or recompile the kernel. The
[r57 manifest](../manifests/kernel-cpr-package-r57.json) records package version,
retained kernel build/release and exact artifact fingerprints separately.
Hardware, runtime autoload and installed update/recovery remain unqualified.
