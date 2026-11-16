# Legacy SCM calibration prerequisite and complete CPU scope

The new API supplies the legacy two-word fuse-row request and checks the
three-word reply before publishing the result. It refuses unavailable or
nonlegacy firmware, unaligned addresses and null output; errors preserve
the caller's value. This is an attributed feature port, not a claim that
an unrelated upstream commit introduced a bug. No `Fixes` tag is invented.

The verified Qualcomm `drivers-for-7.4` head is
`e284de4dfc0132764ef0e051a7024932b130c5e7`, whose kernel version is
7.3-rc1. This maintainer base and the combined runtime's 7.4-rc1 base are
distinct. Exact source and integration heads are in `qualification.json`.
The port preserves Timothy Schmidt's original feature authorship/date
from `789d5197844d5268197a17a94605316eedae9fdb`; original source-patch and
manufacturer commit hashes are in `evidence/SCM-provenance.json`.
The API was absent from this maintainer baseline and the original patch
applies cleanly. It adds three source paths without changing the legacy
transport itself. No CPU consumer, voltage write or higher OPP is enabled.

The manufacturer request/response structures and service/command constants
are provided as short pinned source excerpts. They are public code, with
no unit fuse contents. The new API additionally checks firmware status
instead of accepting data after a failed read. Firmware convention
detection, memory ordering and concurrent initialization are not qualified
by this packet.

The sanitizer wire model executes the actual API, availability check,
dispatcher, request/response accessors, SMC interruption loop, legacy
transport and error remapper. Actual header structures and argument
macros are used. Synthetic allocation, DMA, mutex and SMC services inspect
the request bytes independently and supply only synthetic response data.
Five aligned addresses, eight word pairs, four completion delays and four
interruption counts cover the successful path. Invalid alignment/output,
unavailable/nonlegacy service, allocation/mapping errors, transport errors
and firmware status failures exercise cleanup and unchanged output.

| Qualification | Cases | Checks | Result |
| --- | ---: | ---: | --- |
| Real legacy wire path with synthetic services | 667 | 34,017 | pass |
| Captured API boundary/error contracts | 13 | — | pass |

Six deliberately broken wire variants fail as expected: wrong command
(1,613 failures), swapped words (480), ignored status (10), early output
publication (5), missing legacy gate (646) and missing alignment gate (21).
All candidate and regression runs have no address, undefined-behavior or
leak sanitizer diagnostics. The captured API model additionally covers
positive transport returns and truncation of excess high bits in a result
word. Its transport is modeled; the wire model exercises the real transport.
No actual secure call, DMA transaction or fuse read occurs in either model.
These tests do not prove secure firmware behavior, real completion timing,
cache coherence, concurrency or calibration accuracy on the final image.

Four native Qualcomm ARM/ARM64 profiles compile 16 selected SCM,
legacy/SMCCC transport and TZMEM objects with LLVM 21, `W=1` and
`COMPILE_TEST=n`, without diagnostics. Both combined-runtime model
programs match the maintainer-source programs byte for byte. The initial
ARM64 configuration seed carried a newer modular DRM_PANEL value; setting
the older base's boolean option to built-in removed that configuration
warning. Exact successful configs and object hashes are included. These
are component builds, not full kernel links, modpost or package builds.

The source passes strict checkpatch with no errors, warnings or checks,
using `--no-signoff` because these are unsigned local drafts. A read-only
maintainer lookup is included. Port, messages and qualification used
OpenAI Codex assistance; the source includes the older base's required
`Assisted-by: LLM` tag. Human review and DCO attestation remain pending.
Nothing has been published or sent to maintainers.

Run the portable replay with Python 3, Clang 21 and standard `patch`:

```sh
python3 -B /absolute/path/to/fx0-scm-cpu-scope-current/replay.py /tmp/scm-replay-new
```

Choose a fresh output directory outside the packet. It verifies every
file, applies the patch with zero fuzz, checks final source bytes and
reproduces all eight model variants and exact program hashes. No Git,
network, credentials, firmware image or device are required. Keep normal
LeakSanitizer behavior enabled; use a normal host environment when an
execution sandbox blocks it. Native builds are recorded, not repeated by
the small replay. To reproduce them, use the pinned complete source for
the selected profile, copy its config to a new absolute output directory
and run `olddefconfig`, `modules_prepare`, then the object targets in
`evidence/native-components.json`, using `O=/absolute/output`, `ARCH=arm`
or `ARCH=arm64`, `LLVM=-21`, `W=1`,
`KCFLAGS=-Werror=incompatible-function-pointer-types`,
`--jobserver-style=pipe` and `-j4`.

## CPU scope correction

The earlier 89-path LTS snapshot contains only the initial rail helper
and secure-read prerequisite. It is not the complete later CPU candidate.
Comparing the tracked trees of LTS r7 `250e7412a5a15068b2a2fe32b57b66c300c91b5f`
and the later CPU source `790c9c5407e17ad1d2395c2ec4bdfcfc8dc82826`
finds 54 follow-up paths. The explicit audit is
`evidence/later-CPU-candidate-inventory.json`.

Thirty-three CPU/shared paths need reconciliation, spanning calibration,
corner and voltage planning, complete-row acquisition, the CPR domain,
OPP filtering and CPU attachment, clock error/startup guards, SAW/L2/RPM
recovery, bindings and a separate qualification DTB. Ten later-feature
files are absent from the assembled runtime, including four MSM8926 CPR
helpers, the basic voltage helper, SAW/L2 helpers, two headers and the
qualification board source. Whole-file inequality alone is not treated
as missing behavior.

Other differences in that old candidate touch NFC or previously refreshed
power, USB, camera, display and IIO work. Preserve the current qualified
implementations; replaying old deletions or whole-file copies would lose
later work. The CPU audit tracks every row and leaves those comparisons
explicit. The three SCM changes in this packet preserve every other
runtime path and the ordinary board's conservative configuration.

The complete CPU/CPR port remains open. Source reconciliation is followed
by full maintained-kernel/build/package/update/recovery work and final
physical CPU, thermal, suspend and peripheral qualification. Historical
CPU trials do not qualify this source. All seven bringup requirements,
all nonaudio hardware interactions and the unresolved original r2 display
fault remain in scope.
