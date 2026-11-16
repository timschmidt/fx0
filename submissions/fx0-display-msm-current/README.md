# Fx0 display source qualification

Five unsigned local patches cover MSM8226 lane CFG4 values, MDP5 video
flush ordering, cached plane ownership, right-pipe allocation ownership
and deterministic register-header generation. The existing ARM32 IOMMU
DMA-mapping detach is already present and is not patched again.

The maintainer base is the observed official `msm-fixes` branch at
`1e59855738454b14021b64115f0090eafc7526ae` (7.3-rc2). The separate
7.4-rc1 runtime integration preserves every path outside these five files,
including all board/binding, camera, sensor, panel, QFPROM, power, touch
and wireless work. Exact heads and trees are in `qualification.json`.
Neither source is represented as the accepted maintained-LTS phone kernel.

| Actual-source model | Cases | Candidate checks | Baseline failures |
| --- | ---: | ---: | ---: |
| 28nm PHY lane/register sequence | 192 | 1,056 | 144 |
| CRTC/CTL/video encoder ordering | 241 | 3,121 | 288 |
| Cached plane and split-pipe ownership | 1,258 | 20,150 | 1,442 |

All candidates pass with address, undefined-behavior and leak sanitizers.
Two PHY, two encoder and five ownership regression controls fail as
expected. The ownership check counts depend on allocation success paths;
baseline and mutant totals can therefore differ. All eight-pipe occupancy
masks are tested in old-only, new-only, mixed and released-in-new states.
The earlier 234-case targeted plane model also independently reproduced
and corrected the saved-state transition before the allocator extension.

Five Python hash seeds produce three baseline register headers and one
fixed header. Every one of the 18 usage arrays and all other declarations
are preserved. The replay regenerates all three display headers from
the included source XML and compares their bytes.

Native Qualcomm ARM and ARM64 profiles compile the complete MSM component
on both source trees with `COMPILE_TEST=n`, LLVM 21 and `W=1`: 75 ARM
and 140 ARM64 objects per tree, 430 total, including each composite
`msm.o`. There are no compiler diagnostics. A 7.4 ARM64 seed used
`DRM_PANEL=m`, which 7.3 accepts only as a boolean. Setting it to `y`
before configuration removes that warning and produces exactly the
already-compiled configuration. The warning and its resolution are
preserved in `native-components.json`; it was not suppressed.

Run the source-only replay from any location, with Clang 21, Python 3 and
the standard `patch` utility installed. It needs no Git checkout, network,
phone or private files. Use a new output directory outside this packet:

```sh
python3 -B /absolute/path/to/fx0-display-msm-current/replay.py /tmp/display-replay-new
```

The replay verifies the complete file manifest, applies all five patches
with zero fuzz, checks their resulting source bytes, builds and executes
17 sanitizer models, and verifies generator semantics. Do not disable
LeakSanitizer if a restricted environment prevents its execution; use a
normal host execution environment. Native builds are recorded evidence
and are not repeated by this small replay.

To reproduce a native profile, use its full pinned source tree, copy the
matching `configs/*.config` to an absolute output directory as `.config`,
then run `make O=/absolute/output ARCH=arm LLVM=-21 W=1 olddefconfig`,
`modules_prepare` and `drivers/gpu/drm/msm/msm.o` as successive targets.
Use `ARCH=arm64` for that profile. The recorded build also sets
`KCFLAGS=-Werror=incompatible-function-pointer-types` and `-j4`.
`native-source-manifests.json` binds the complete tracked MSM source set;
`native-components.json` binds configurations and object outputs.

Five copied upstream XML/schema files contain inherited trailing whitespace
or final blank lines. Their bytes are preserved and bound to the official
source by `source-copy-provenance.json`. The review whitespace check
excludes only those five exact snapshots after verifying their hashes;
all authored files and the five kernel patches pass their normal checks.

The older cached-plane Fixes tag named a PM callback move whose preceding
callbacks already used atomic suspend/resume. The current tag identifies
the earlier disable-time pipe release that creates the stale-cache
transition. Primary upstream commit metadata and diffs are included for
review. The newly found right-pipe bug is a separate patch and model
reproduction. These are classified as ordinary driver bugs for human
review; no security classification or upstream acceptance is asserted.

This bundle does not execute physical display/touch, scanout, PLL timing,
concurrent DRM transactions or suspend/resume. It does not identify or
resolve the original r2 display/IOMMU failure, qualify a full linked
kernel/package, establish package reproducibility, or authorize a phone
update. Physical combined-image tests remain required. Every patch lacks
human DCO certification pending human review. Maintainers were identified
locally; nothing was sent or published.
