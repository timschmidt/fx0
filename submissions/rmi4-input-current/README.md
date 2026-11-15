# RMI4 I2C suspend and in-cell panel drafts

The suspend prerequisite prevents a function-suspend error from leaving the
controller powered off without a later resume callback. The feature series
carries optional reset support and sequences an in-cell I2C touchscreen with
its DRM panel. These are local, attributed drafts with host qualification.

| Route | Official Input base | Draft head |
| --- | --- | --- |
| Suspend fix, `for-linus` | `ce8010f11f3ea62f8675e9bc921ee485aef82019` | `0671b67481a1eaf61c8db1b19b1834ae130c7a47` |
| Prerequisites, binding and panel feature, `next` | `ab13b5fc808e043a13f861a7c1c2ba8173c22b84` | `75f0dd5b051c1b1cda53eb84726b3cb13e6a8552` |

The four-patch feature series includes the suspend prerequisite. Apply either
route to its recorded base. The suspend patches implement the same change;
they are not intended to be applied twice.

Roman Vivchar authored the original reset patch. Its existing human sign-off
and source link are preserved. Timothy Schmidt authored the original suspend,
reset-cleanup, binding and panel changes. Original Claude assistance and this
Codex:GPT-6 adaptation are disclosed in the adapted changelogs. The two bases
use different AI attribution formats. No new human sign-off was added.

The current adaptation keeps runtime callbacks on the same power-reference
helpers and defers them to a followed panel. It preserves existing handling of
runtime resume errors. The current RMI driver does not enable runtime PM;
the mixed callback sequences are synthetic controls for consistent tracking.

Native ARM32 and ARM64 component builds pass with LLVM 21, `W=1` and
`COMPILE_TEST=n`. The feature also builds with DRM built in, modular and
disabled. Five component builds produce 49 objects in total, including core,
transport and selected function objects. This is not a full-kernel link.
Only commit messages changed after the feature builds; every intermediate
and final tree remains identical to its compiled counterpart.

The exact [configurations](configs) accompany the object hashes. For a native
component rebuild, check out the corresponding recorded kernel head, copy
the selected configuration to a new output directory as `.config`, then run
`make O=OUTPUT ARCH=arm LLVM=-21 olddefconfig`,
`make O=OUTPUT ARCH=arm LLVM=-21 modules_prepare`, and
`make O=OUTPUT ARCH=arm LLVM=-21 W=1 drivers/input/rmi4/` sequentially. Use
`ARCH=arm64` for either ARM64 configuration. The original checks also set
`KCFLAGS=-Werror=incompatible-function-pointer-types`.

Ordinary Kbuild RMI binding examples pass. The retained complete, unchanged
Fx0 DTB passes the selected RMI schema. Optional-panel I2C and panel-free SPI
controls pass; malformed, empty and multiple panel references, an unsupported
SPI panel and an unknown property are rejected. Other full-board schema gaps
remain open. No board or audio descriptions were removed.

## Host replay

Run from an ordinary host environment that supports ASan/UBSan:

```sh
python3 -B replay-fixtures.py
```

This compiles four self-contained C fixtures, checks their recorded hashes
and verifies expected results:

| Fixture | Cases | Expected failures |
| --- | --- | --- |
| Original suspend callbacks | 22 | 4 stranded-controller cases |
| Corrected suspend callbacks | 22 | 0 |
| Original panel implementation port | 34 | 16 reference/sequencing cases |
| Adapted panel implementation | 34 | 0 |

Baseline failures are expected and required for replay success. Low-level
function I/O, IRQs and regulators are mocked. The suspend fixture extracts
two PM-core eligibility decisions; it does not execute the kernel PM core.
The panel fixture calls actual extracted RMI and transport callbacks; it
does not execute DRM or devres. Regulator disable is modeled as successful.
Real disable-failure recovery, concurrency and physical operation remain
unqualified. No current-base hardware test is claimed.

The [extraction tools](tools) can regenerate callback fixtures from a full
recorded source checkout. `check-suspend.py SOURCE LABEL` uses the production
transport, core and PM source. `check-panel.py TRANSPORT_C LABEL CORE_C` takes
the two production files explicitly. They create a new result directory
beside the tool, print observed counts and retain source hashes. The replay
above additionally enforces the expected counts. It requires no Git history,
kernel checkout, phone, credentials or network connection.

Exact source IDs, native object/configuration hashes, original commits,
lifecycle source checks and limits are in [qualification.json](qualification.json).
Maintainer discovery is recorded without contacting anyone. Human review and
DCO remain pending for adapted kernel patches. No phone changes or publication
occurred. The older r2 display-IOMMU fault remains unresolved.
