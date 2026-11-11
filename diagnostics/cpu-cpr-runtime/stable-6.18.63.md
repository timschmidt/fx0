# CPU/CPR integration on stable Linux 6.18.63

The separate `6.18.63-r3` package combines CPU/CPR support with the stable r50
baseline, vibrator fixes and final NFC source. Its host qualification does not
establish physical startup, higher CPU rates or native installation. The phone
remains on r50/Sxmo r7. See the
[manifest](../../manifests/kernel-cpr-nfc-6.18.63-alpine.json) and
[evidence](../../evidence/2026-11-11-cpr-nfc-stable-6.18.63.json).

The source branch is
[`integration/fx0-6.18.63-cpr`](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-6.18.63-cpr),
commit `790c9c5407e17ad1d2395c2ec4bdfcfc8dc82826`. Twenty-nine cherry-picks
preserve the original authors and original-commit references. Two later
commits correct the qualification-target comment and style. Before those
changes, 30 carried files match the earlier CPR source exactly; the style
cleanup changes alignment, consistent branch braces and MAINTAINERS order.
The vibrator and NFC source remain byte-identical to the preceding stable
integration.

The normal source-build recipe is
[`integration/fx0-cpr-nfc-6.18.63-package`](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-cpr-nfc-6.18.63-package),
commit `43634e120d23298ce7e08db18ff9f86c6e54167f`. It uses the distinct
release `6.18.63-fx0-cpr-nfc-alpine`, enables the nvmem CPUFreq and MSM8926 CPR
drivers, and retains the NFC modules, nonpermissive CFI, schedutil and full
zlib-compressed DWARF5. A fresh build home creates a new runtime module
certificate. Keep this kernel, DTBs and complete signed module set together.

The ordinary DTB retains four CPU OPPs and no CPR consumer. It now describes
the always-on fixed-range APC provider, L2 master and full eight-byte raw CPU
calibration row. The separate `qcom-msm8926-lg-madai-cpr.dtb` supplies the
calibrated CPU/domain relationships. Fourteen described OPPs are filtered by
calibration; their presence does not qualify their physical operation. Both
DTBs retain the NFC wiring.

Forty-five current host tests execute the actual voltage, clock, calibration,
domain, error-recovery and controlled-start callbacks in instrumented models.
An initial extra historical fixture cannot compile against the later aux/pll
layout. Its current replacement executes the same original case body plus
the later handoff cases and passes. The historical fixture and failed attempt
are retained; the final source is checked again after the style changes.

Seven binding documents validate. Forty-two schema/compiled-board tests cover
the CPU/domain OPP relationships, parent clocks, fixed-range regulator, L2
ownership, raw calibration and NFC wiring. Two fixture classes initially fail
to launch the Alpine-native `dtc` from Fedora because its musl interpreter is
absent from the host's default path. An explicit loader wrapper runs that same
binary; only the 17 affected tests resume. The other 25 passing tests are not
repeated.

The final combined diff has zero checkpatch errors, five warnings and ten
checks, all recorded individually. The remaining findings concern the combined
binding/driver diff, new-file ownership review, mutable per-instance regulator
operations, existing voltage-unit names and the non-sleeping CPU0 IPI settling
delay. This is not a clean final submission series. Historical commit-message
and intermediate-layout findings remain recorded. Current maintainer-tree
validation and submission preparation remain open.

The new [registration script](register-stable.sh) pins this release and the
`stable-6.18.63-r3-registration` marker. It preserves the earlier guarded
control flow: require signature enforcement and userspace, verify the 300 MHz
unapplied bootstrap, load userspace before cpufreq-dt, then recheck the state.
It makes no explicit frequency or voltage request. Nine shell-model tests pass,
including 39 cases for the new script, the retained Alpine checks and the
existing RAM script checks. The old r55 and stable r1/r2 families reject before
any load.

The prepared registration image uses the exact packaged kernel, CPR DTB and
two signed modules. Five initramfs entries change; init, BusyBox, HTTP helper,
command line and the independent 180-second return timer retain their bytes.
ARM BusyBox syntax, image digest/addresses/readback and the kernel/BSS footprint
below the forced ramdisk address are checked. The image remains unstaged and
unbooted; its physical entry controller is not prepared in this phase. A fresh
native identity and physical UI confirmation are required before any entry.

The earlier physical 300/384/600 MHz CPR observations belong to their original
kernel family. They do not qualify this package. Startup/registration, all
eligible OPPs, sustained load, thermal behavior, physical rails, suspend,
installed updates and recovery remain separate work. The prepared r1 native
update still awaits display/touch confirmation for its exact r50 return.
Audio testing remains excluded.
